import json
import os
import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider
from pathlib import Path
from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger
from os.path import join


class CalleeFinder(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self):
        self.callees = []

    def visit_Call(self, node: cst.Call) -> bool | None:
        pos = self.get_metadata(PositionProvider, node)
        
        if isinstance(node.func, cst.Attribute):
            self.callees.append((node.func.attr.value, pos.start.line-1, pos.start.column))
        elif isinstance(node.func, cst.Name):
            self.callees.append((node.func.value, pos.start.line-1, pos.start.column))
        else:
            print(f"Warning: Unknown callee type {type(node.func)} -- ignoring this call")


def get_callees_in_code(tree): # TODO: give code?
    call_collector = CalleeFinder() # CalleeFinder, or RepoCallCollector
    # Use MetadataWrapper so metadata (PositionProvider, ParentNodeProvider) is populated
    wrapper = MetadataWrapper(tree)
    wrapper.visit(call_collector)
    return call_collector.callees

class ExtractCalleesInTestCode:
    def __init__(self, repo_path):
        self.repo_path = str(Path(repo_path).resolve()) # the test code shoule in the repo_path
        config = MultilspyConfig.from_dict({"code_language": "python"})
        logger = MultilspyLogger()
        self.lsp = SyncLanguageServer.create(config, logger, self.repo_path)

    def _normalize_paths(self, file_path: str):
        """Return (full_path: Path, rel_path: str (posix style relative to repo root))."""
        p = Path(file_path)
        if not p.is_absolute():
            full = Path(self.repo_path) / p
        else:
            full = p
        full = full.resolve()
        rel = os.path.relpath(full, self.repo_path)
        return full, Path(rel).as_posix()
    
    def get_callee_definitions(self, file_path, tree):
        """
        Use CST to find calls inside the function (def_line 0-based), then resolve each
        call with the LSP. Returns list of dicts with callee+definition info.
        """
        full_path, rel_path = self._normalize_paths(file_path)
        callees = get_callees_in_code(tree)

        callees_with_defs = []
        for callee_name, call_start_line, call_start_col in callees:
            defs = []
            try:
                # Jedi Language Server may fails to handle inheritance
                defs = self.lsp.request_definition(rel_path, call_start_line, call_start_col) or []
            except:
                pass

            for d in defs: # defs should only have one def if exist
                absolute = d.get("absolutePath")
                if absolute == str(full_path):
                    # the callee from the test code, we do not care whether a function from test code is private or not
                    continue

                if self.repo_path in absolute: # to filter out the built-in functions
                    rng = d.get("range", {})
                    start = rng.get("start", {})
                    def_line = start.get("line")
                    # def_col = start.get("character") or start.get("column") or start.get("col")
                    info = {
                        "callee_name": callee_name,
                        # "call_location": {"file": str(full_path), "line": call_start_line, "col": call_start_col},
                        "absolute": absolute,
                        "relative": d.get("relativePath"),
                        "line": def_line,
                        # "col": def_col,
                        # "raw": d,
                    }
                    callees_with_defs.append(info)

        return callees_with_defs

if __name__ == "__main__":
    test_path = "a0.py"
    repo_path = "data/repos/marshmallow/"
    repo = ExtractCalleesInTestCode(repo_path)

    with open(join(repo_path, test_path), "r", encoding="utf-8") as f:
        code = f.read()
    try:
        tree = cst.parse_module(code)
    except:
        pass

    with repo.lsp.start_server():
        callees = repo.get_callee_definitions(test_path, tree)
        with open("logs_a0_2277_condition.json", "w") as f:
            json.dump(callees, f, indent=2)

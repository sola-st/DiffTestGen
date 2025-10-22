import json
import os
import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider
from pathlib import Path
from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger


class CalleeFinder(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, target_def_line: int):
        self.target_def_line = target_def_line  # 0-based
        self._in_target = False
        self._target_node = None
        self.callees = []

    def visit_FunctionDef(self, node: cst.FunctionDef):
        pos = self.get_metadata(PositionProvider, node)
        if self._target_node is None and (pos.start.line - 1) == self.target_def_line:
            self._in_target = True
            self._target_node = node  # mark which function we're in

    def leave_FunctionDef(self, node: cst.FunctionDef):
        if node is self._target_node:
            self._in_target = False

    def visit_Call(self, node: cst.Call):
        if not self._in_target:
            return
        pos = self.get_metadata(PositionProvider, node)
        if isinstance(node.func, cst.Attribute):
            name = node.func.attr.value
        elif isinstance(node.func, cst.Name):
            name = node.func.value
        else:
            return
        self.callees.append((name, pos.start.line - 1, pos.start.column))  # LSP 0-based

def get_callees_in_function(file_path, def_line):
    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return []
    wrapper = MetadataWrapper(tree)
    finder = CalleeFinder(def_line)
    wrapper.visit(finder)  # visit the whole tree; finder records only inside target def
    return finder.callees


class ExtractCallerCallee:
    def __init__(self, repo_path):
        self.repo_path = str(Path(repo_path).resolve())
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

    def get_hover_text(self, file_path, line, column):
        # from PythonLanguageServer.py
        raw_result = self.lsp.request_hover(file_path, line, column)
        if type(raw_result) == dict and "contents" in raw_result:
            return raw_result["contents"]["value"]
        else:
            return ""
        
    def get_function_callers(self, file_path, def_line: int, def_col: int):
        """
        Return list of references (callers) for symbol at (file_path, def_line, def_col).
        file_path may be absolute or repo-relative; def_line/def_col are 0-based.
        """
        full_path, rel_path = self._normalize_paths(file_path)
        refs = []
        
        try:
            refs = self.lsp.request_references(rel_path, def_line, def_col) or []
        except:
            pass # no references

        callers = []
        for r in refs:
            # TODO check here whether necessary
            # Filter out the definition itself
            if r["relativePath"] == rel_path and r["range"]["start"]["line"] == def_line:
                continue
            callers.append(r)
        return callers

    def get_function_callees(self, file_path, def_line: int):
        """
        Use CST to find calls inside the function (def_line 0-based), then resolve each
        call with the LSP. Returns list of dicts with callee+definition info.
        """
        full_path, rel_path = self._normalize_paths(file_path)
        callees = get_callees_in_function(str(full_path), def_line)

        callees_with_defs = []
        for callee_name, call_start_line, call_start_col in callees:
            defs = []
            try:
                defs = self.lsp.request_definition(rel_path, call_start_line, call_start_col) or []
            except:
                pass
            for d in defs:
                # if self.repo_path in d["absolutePath"]: # to filter out the built-in functions
                #     callees_with_defs.append(d)

                absolute = d.get("absolutePath")
                relative = d.get("relativePath")
                rng = d.get("range", {})
                start = rng.get("start", {})
                def_line = start.get("line")
                def_col = start.get("character") or start.get("column") or start.get("col")
                info = {
                    "callee_name": callee_name,
                    "call_location": {"file": str(full_path), "line": call_start_line, "col": call_start_col},
                    "definition": {
                        "absolute": absolute,
                        "relative": relative,
                        "line": def_line,
                        "col": def_col,
                        "raw": d,
                    },
                }
                if self.repo_path in str(absolute):
                    callees_with_defs.append(info)

        return callees_with_defs


if __name__ == "__main__":
    # test_path = "hhh_server_test.py" # 9, 4
    # test_path = "src/marshmallow/error_store.py" # 16, 9
    test_path = "src/marshmallow/utils.py"
    repo_path = "data/repos/marshmallow/"
    repo = ExtractCallerCallee(repo_path)
    repo.lsp.start_server()

    callers = repo.get_function_callers(test_path, 135, 0) 
    with open("callers_utils_2699.json", "w") as f:
        json.dump(callers, f, indent=2)

    callees = repo.get_function_callees(test_path, 135)
    with open("callees_utils_2699.json", "w") as f:
        json.dump(callees, f, indent=2)


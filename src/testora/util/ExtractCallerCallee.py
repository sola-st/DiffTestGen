import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider
import json
from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger
from pathlib import Path
from os.path import join


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


class PythonLanguageServer:
    def __init__(self, repo_path):
        self.repo_path = repo_path
        config = MultilspyConfig.from_dict({"code_language": "python"})
        logger = MultilspyLogger()
        absolute_repo_path = str(Path(repo_path).resolve())
        self.lsp = SyncLanguageServer.create(config, logger, absolute_repo_path)

    def get_function_callers(self, file_path, def_line, def_col):
        """
        Get all call sites for the function defined at (file_path, def_line).
        func_name is for clarity, but disambiguation is by line number.
        """
        with self.lsp.start_server():
            refs = self.lsp.request_references(file_path, def_line, def_col)
            callers = []
            for r in refs:
                # TODO check here whether necessary
                # Filter out the definition itself
                if r["uri"] == file_path and r["range"]["start"]["line"] == def_line:
                    continue
                callers.append(r)
            return callers
    
    def get_function_callees(self, file_path, def_line):
        # Step 1: Use CST to get callees in the function
        callees = get_callees_in_function(join(self.repo_path, file_path), def_line)
        callees_with_defs = []
        for callee_name, call_start_line, call_start_col in callees:
            # Step 2: Use LSP to resolve the definition of each callee
            with self.lsp.start_server():
                # LSP expects 0-based line numbers
                defs = self.lsp.request_definition(file_path, call_start_line, call_start_col)
                for d in defs:
                    # callee_info = {
                    #     "callee_name": callee_name,
                    #     "call_lineno": call_start_line,
                    #     "definition_file": d.get("relativePath", d.get("uri")),
                    #     "definition_line": d["range"]["start"]["line"] + 1  # convert to 1-based
                    # }
                    callees_with_defs.append(d)
        return callees_with_defs


if __name__ == "__main__":
    # test_path = "hhh_server_test.py" # 9, 4
    test_path = "src/marshmallow/error_store.py"
    repo_path = "data/repos/marshmallow/"
    repo = PythonLanguageServer(repo_path)

    callers = repo.get_function_callers(test_path, 16, 9)
    with open("callers_error_store2.json", "w") as f:
        json.dump(callers, f, indent=2)

    callees = repo.get_function_callees(test_path, 16)
    with open("callees_error_store231.json", "w") as f:
        json.dump(callees, f, indent=2)


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
    def __init__(self, repo_path, python_lsp_backend: str = None):
        """
        repo_path: path to repository root
        python_lsp_backend: optional string to select python LSP backend. If not
            provided the constructor will check the MULTILSP_PYTHON_LSP env var and
            otherwise fall back to the default configured in MultilspyConfig ('jedi').
        """
        self.repo_path = str(Path(repo_path).resolve())
        cfg = {"code_language": "python"}
        if python_lsp_backend:
            cfg["python_lsp_backend"] = python_lsp_backend
        else:
            env_backend = os.getenv("MULTILSP_PYTHON_LSP")
            if env_backend:
                cfg["python_lsp_backend"] = env_backend

        # enable LSP trace when MULTILSP_TRACE_LSP is set (helps debugging)
        if os.getenv("MULTILSP_TRACE_LSP"):
            cfg["trace_lsp_communication"] = True

        config = MultilspyConfig.from_dict(cfg)
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
        
    def get_function_callers(self, file_path, def_line: int, def_col: int,
                             use_ast_fallback: bool = True,
                             verify_with_lsp: bool = True,
                             max_verifications: int = 500):
        """
        Return list of references (callers) for symbol at (file_path, def_line, def_col).
        file_path may be absolute or repo-relative; def_line/def_col are 0-based.
        """
        full_path, rel_path = self._normalize_paths(file_path)
        refs = []

        try:
            refs = self.lsp.request_references(rel_path, def_line, def_col) or []
        except:
            refs = []

        callers = []
        for r in refs:
            # Filter out the definition itself
            if r["relativePath"] == rel_path and r["range"]["start"]["line"] == def_line:
                continue
            callers.append(r)

        # Fallback: if LSP returned no callers, do an AST-based search for calls to the function
        # (helps when pyright doesn't return references but editor (Pylance) finds them).
        if len(callers) == 0:
            try:
                # find target function name from the definition file
                with open(str(full_path), "r", encoding="utf-8") as f:
                    src = f.read()
                try:
                    tree = cst.parse_module(src)
                except cst.ParserSyntaxError:
                    return callers

                func_name = None
                
                # Use MetadataWrapper visitor to find function by line
                wrapper = MetadataWrapper(tree)
                class _Finder(cst.CSTVisitor):
                    METADATA_DEPENDENCIES = (PositionProvider,)
                    def __init__(self, target_line):
                        self.target_line = target_line
                        self.name = None
                    def visit_FunctionDef(self, node):
                        pos = self.get_metadata(PositionProvider, node)
                        if (pos.start.line - 1) == self.target_line:
                            self.name = node.name.value

                finder = _Finder(def_line)
                wrapper.visit(finder)
                func_name = finder.name

                if func_name:
                    import time
                    from datetime import datetime
                    
                    max_files = int(os.getenv("MULTILSP_CALLERS_MAX_FILES", "2000"))
                    min_callers = int(os.getenv("MULTILSP_MIN_CALLERS", "10"))
                    start_time = time.time()
                    last_progress = start_time
                    checked = 0
                    total_size = 0
                    
                    # First collect Python files, but don't read them yet
                    python_files = []
                    for dirpath, dirnames, filenames in os.walk(self.repo_path):
                        for fn in filenames:
                            if not fn.endswith('.py'):
                                continue
                            abs_p = os.path.join(dirpath, fn)
                            python_files.append(abs_p)
                            if len(python_files) >= max_files:
                                break
                        if len(python_files) >= max_files:
                            break
                    
                    # Now process files one by one with progress tracking
                    for abs_p in python_files:
                        current_time = time.time()
                        if current_time - last_progress >= 5:  # Show progress every 5 seconds
                            elapsed = current_time - start_time
                            print(f"Progress: {checked}/{len(python_files)} files checked in {elapsed:.1f}s, {len(callers)} callers found")
                            last_progress = current_time
                            
                        try:
                            # Quick size check before reading
                            size = os.path.getsize(abs_p)
                            if size > 1_000_000:  # Skip files > 1MB
                                continue
                            
                            with open(abs_p, 'r', encoding='utf-8') as f:
                                txt = f.read()
                            total_size += len(txt)
                            
                            try:
                                t = cst.parse_module(txt)
                            except cst.ParserSyntaxError:
                                continue
                                
                            # Visit calls with optimized visitor
                            class _CallVisitor(cst.CSTVisitor):
                                METADATA_DEPENDENCIES = (PositionProvider,)
                                def __init__(self, target_name):
                                    self.target_name = target_name
                                    self.calls = []
                                def visit_Call(self, node):
                                    name = None
                                    if isinstance(node.func, cst.Name):
                                        name = node.func.value
                                    elif isinstance(node.func, cst.Attribute):
                                        name = node.func.attr.value
                                    if name == self.target_name:
                                        pos = self.get_metadata(PositionProvider, node)
                                        self.calls.append((pos.start.line-1, pos.start.column))

                            w = MetadataWrapper(t)
                            v = _CallVisitor(func_name)
                            w.visit(v)
                            
                            if v.calls:  # Only process if we found calls
                                rel = os.path.relpath(abs_p, self.repo_path)
                                for ln, col in v.calls:
                                    item = {
                                        "uri": Path(abs_p).as_uri(),
                                        "absolutePath": abs_p,
                                        "relativePath": rel,
                                        "range": {"start": {"line": ln, "character": col}, "end": {"line": ln, "character": col}},
                                    }
                                    callers.append(item)
                                    
                                # Early exit if we found enough callers
                                if len(callers) >= min_callers:
                                    print(f"Found {len(callers)} callers, stopping early")
                                    break
                                    
                        except Exception:
                            pass
                            
                        checked += 1
                        if checked >= max_files:
                            break
                            
                    end_time = time.time()
                    elapsed = end_time - start_time
                    mb_processed = total_size / (1024 * 1024)
                    print(f"Search complete: {checked} files ({mb_processed:.1f}MB) processed in {elapsed:.1f}s, found {len(callers)} callers")
            except Exception:
                pass

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
                absolute = d.get("absolutePath")
                if self.repo_path in absolute: # to filter out the built-in functions
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
                    callees_with_defs.append(info)

        return callees_with_defs


if __name__ == "__main__":
    # test_path = "hhh_server_test.py" # 9, 4
    # test_path = "src/marshmallow/error_store.py" # 16, 9
    test_path = "pandas/core/arrays/string_.py"
    repo_path = "data/repos/pandas/"
    # test_path = "src/marshmallow/utils.py"
    # repo_path = "data/repos/marshmallow/"

    # Example: choose backend via argument or environment variable
    # repo = ExtractCallerCallee(repo_path, python_lsp_backend="jedi")
    # or set env var: export MULTILSP_PYTHON_LSP=pyright
    repo = ExtractCallerCallee(repo_path)
    print("LSP backend class:", repo.lsp.language_server.__class__.__name__)
    print("LSP process cmd:", repo.lsp.language_server.server.process_launch_info.cmd)

    # Start the language server and run queries inside the context manager
    with repo.lsp.start_server():
        callers = repo.get_function_callers(test_path, 833, 4)
        with open("callers_test30.json", "w") as f:
            json.dump(callers, f, indent=2)

        callees = repo.get_function_callees(test_path, 833)


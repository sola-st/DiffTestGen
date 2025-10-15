import json
import os
import ast
from os.path import join


def get_all_from_init(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=file_path)

    for node in ast.walk(tree):
        # Look for assignments to __all__
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    # Handle simple lists of strings
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        return [elt.s for elt in node.value.elts if isinstance(elt, ast.Str)]
    return []

def get_functions_in_file(filepath):
    """Return a list of function names in a given Python file."""
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=filepath)
            functions = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append(node.name)
            return functions

        except SyntaxError:
            return []  # Skip invalid Python files

def list_project_functions(root_dir):
    results = []
    func_w_underscore_num = 0
    func_wo_underscore_num = 0
    public_functions = []
    public_func_num = 0
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip test directories
        if "test" in dirpath.lower() or "tests" in dirpath.lower():
            continue

        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            if filename.startswith("test") or filename.endswith("test.py"):
                continue

            filepath = os.path.join(dirpath, filename)
            relpath = os.path.relpath(filepath, root_dir)

            if filename == "__init__.py":
                print(filepath)
                funcs = get_all_from_init(filepath)
                if funcs:
                    public_functions.append({"relpath": relpath, "public_func": funcs})
                    public_func_num = len(funcs)
                continue

            # modname = relpath[:-3].replace(os.sep, ".")
            funcs = get_functions_in_file(filepath)
            for func in funcs:
                if [relpath, func] not in results:
                    results.append([relpath, func])
                    if func.startswith("_"):
                        func_w_underscore_num += 1
                    else:
                        func_wo_underscore_num += 1
    return results, func_w_underscore_num, func_wo_underscore_num, public_functions, public_func_num


if __name__ == "__main__":
    repo_folder_local = "data/repos"
    projects = ["marshmallow", "pandas", "scipy", "keras"]
    for project in projects:
        project_root = join(repo_folder_local, project)

        module_and_funcs, func_w_underscore_num, func_wo_underscore_num, \
                public_functions, public_func_num = list_project_functions(project_root)
        with open(f"{project}_all_funcs.txt", "w") as f:
            f.writelines("\n".join(map(str, module_and_funcs)))

        with open(f"{project}_public_funcs.txt", "w") as f:
            json.dump(public_functions, f, indent=4)

        print(f"Project: {project}")
        print(f" --'_' func: {func_w_underscore_num}")
        print(f" --non '_' func: {func_wo_underscore_num}")
        print(f" --public func: {public_func_num}")
        print()


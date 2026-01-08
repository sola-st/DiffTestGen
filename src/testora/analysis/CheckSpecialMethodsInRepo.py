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
    special_methods = []
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

            # modname = relpath[:-3].replace(os.sep, ".")
            funcs = get_functions_in_file(filepath)
            for func in funcs:
                if [relpath, func] not in results:
                    results.append([relpath, func])
                    if func.startswith("__") and func.endswith("__"):
                        special_methods.append([relpath, func])
    return results, special_methods


if __name__ == "__main__":
    repo_folder_local = "data/repos"
    projects = ["marshmallow"] # ["pandas", "scipy", "keras"] # "marshmallow"
    for project in projects:
        project_root = join(repo_folder_local, project)

        module_and_funcs, special_methods = list_project_functions(project_root)
        unique_specials_methods = set([m[1] for m in special_methods])
        with open(f"{project}_all_funcs.txt", "w") as f:
            f.writelines("\n".join(map(str, module_and_funcs)))

        with open(f"{project}_special_methods.txt", "w") as f:
            f.writelines("\n".join(map(str, special_methods)))

        with open(f"{project}_special_methods_unique.txt", "w") as f:
            f.writelines("\n".join(map(str, unique_specials_methods)))

        print(f"Project: {project}")
        print(f" --all functions: {len(module_and_funcs)}")
        print(f" --special methods: {len(special_methods)}")
        print(f" --unique special methods: {len(unique_specials_methods)}")
        print()


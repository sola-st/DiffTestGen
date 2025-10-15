import importlib.util
import os
import ast

def find_public_import_path(file_path: str, func_name: str):
    """
    Given a function's source file and name, detect if it is public
    (exported via __init__.py) and return the corresponding import statement.
    """
    # Step 1. Find the containing package root
    file_path = os.path.abspath(file_path)
    parts = file_path.split(os.sep)
    for i in range(len(parts) - 1, 0, -1):
        init_path = os.sep.join(parts[:i] + ["__init__.py"])
        if os.path.exists(init_path):
            package_root = os.sep.join(parts[:i])
            break
    else:
        return None, "# not inside a package"

    # Step 2. Build the dotted module name
    pkg_root_name = os.path.basename(package_root)
    module_parts = []
    rel = os.path.relpath(file_path, start=os.path.dirname(package_root))
    for part in rel.split(os.sep)[:-1]:
        if part != "__init__.py":
            module_parts.append(part)
    module_name = pkg_root_name + "." + ".".join(
        p.replace(".py", "") for p in module_parts if p.endswith(".py") is False
    )
    if module_name.endswith("."):
        module_name = module_name[:-1]

    # Step 3. Walk upward to parent packages
    parts = module_name.split(".")
    for i in range(len(parts), 0, -1):
        pkg_name = ".".join(parts[:i])
        try:
            spec = importlib.util.find_spec(pkg_name)
            if not spec or not spec.origin or "__init__.py" not in spec.origin:
                continue
            with open(spec.origin, "r", encoding="utf-8") as f:
                src = f.read()
            tree = ast.parse(src, filename=spec.origin)

            # Get __all__ values (if any)
            all_names = set()
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
                    and isinstance(node.value, (ast.List, ast.Tuple))
                ):
                    all_names.update(
                        [elt.s for elt in node.value.elts if isinstance(elt, ast.Constant)]
                    )

            # Check if func_name is imported and/or listed
            imported_from = None
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.asname == func_name or alias.name == func_name:
                            imported_from = node.module
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.asname == func_name or alias.name == func_name:
                            imported_from = alias.name

            if func_name in all_names or imported_from:
                # Construct import line
                if pkg_name.endswith(func_name):
                    return True, f"import {pkg_name}"
                elif imported_from:
                    return True, f"from {pkg_name} import {func_name}"
                else:
                    return True, f"from {pkg_name} import {func_name}"
        except Exception:
            continue

    return False, "# not exported publicly"

import ast
from pathlib import Path

REPO_DIR = Path(".").resolve()
API_DIR_CANDIDATES = [
    REPO_DIR / "keras",
    REPO_DIR / "build" / "keras",
]


def find_generated_api_root():
    for candidate in API_DIR_CANDIDATES:
        if candidate.exists():
            init_file = candidate / "__init__.py"
            if init_file.exists():
                return candidate
    raise FileNotFoundError("Could not locate generated Keras API package.")


def parse_imports_from_init(init_file: Path, package_root: Path):
    source = init_file.read_text(encoding="utf-8")
    tree = ast.parse(source)
    discovered = set()
    relative_module = (init_file.relative_to(package_root).parts[:-1])
    current_module = ".".join([package_root.name, *relative_module])

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if not node.names:
                continue

            module = node.module
            level = node.level
            current_parts = current_module.split(".")

            if level == 0:
                source_module = module or current_module
            else:
                base_len = len(current_parts) - (level - 1)
                if base_len < 1:
                    base_parts = current_parts[:1]
                else:
                    base_parts = current_parts[:base_len]

                base = ".".join(base_parts)
                source_module = f"{base}.{module}" if module else base

            for alias in node.names:
                impl_name = alias.name
                export_name = alias.asname or alias.name
                if (not export_name or export_name.startswith("_") or export_name == "*"):
                    continue

                impl_full = f"{source_module}.{impl_name}"
                export_full = f"{current_module}.{export_name}"
                discovered.add((export_full, impl_full))

    return discovered


def extract_public_apis(api_root: Path):
    public_mappings = set()
    for init_file in api_root.rglob("__init__.py"):
        try:
            discovered = parse_imports_from_init(init_file, api_root)
            public_mappings.update(discovered)
        except SyntaxError as e:
            print(f"[Warning] Failed parsing {init_file}: {e}")
    return sorted(public_mappings)


def save_outputs(mappings):
    out = REPO_DIR / "keras_objects.txt"
    with out.open("w", encoding="utf-8") as f:
        for export, impl in mappings:
            f.write(f"{export} -> {impl}\n")
    print(f"[Output] Wrote mapping file: {out}")


def main():
    api_root = find_generated_api_root()
    print(f"[Extract] Using API root: {api_root}")
    mappings = extract_public_apis(api_root)
    print(f"[Done] Extracted {len(mappings)} mappings")
    save_outputs(mappings)


if __name__ == "__main__":
    main()

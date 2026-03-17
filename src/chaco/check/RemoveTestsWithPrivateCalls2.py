from os.path import join
from os import listdir, makedirs
import shutil
import libcst as cst
from testora.util.PythonCodeUtil import AttributeExtractor, CallExtractor

# Further to filter the ChaCo-generated tests: remove the tests that have private calls.
class ImportTracker(cst.CSTVisitor):
    def __init__(self):
        self.alias_map = {}

    def visit_Import(self, node: cst.Import):
        for name in node.names:
            if name.asname is None:
                continue

            original = name.name.value
            alias = name.asname.name.value

            self.alias_map[alias] = original

    def visit_ImportFrom(self, node: cst.ImportFrom):
        for name in node.names:
            if not isinstance(name, cst.ImportAlias):
                continue

            if name.asname is None:
                continue

            original = name.name.value
            alias = name.asname.name.value

            self.alias_map[alias] = original


def has_private_accesses_or_fails_to_parse(code):
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return True

    # Track imports
    import_tracker = ImportTracker()
    tree.visit(import_tracker)

    alias_map = import_tracker.alias_map

    # Check calls
    call_extractor = CallExtractor()
    tree.visit(call_extractor)

    for callee in call_extractor.callees:
        if isinstance(callee, cst.Name):
            callee = callee.value
        original = alias_map.get(callee, callee)
        if original.startswith("_"):
            return True

    # Check attributes
    attribute_extractor = AttributeExtractor()
    tree.visit(attribute_extractor)

    for attribute in attribute_extractor.attributes:
        try:
            original = alias_map.get(attribute, attribute)
            if original.startswith("_"):
                return True
        except:
            if attribute.startswith("_"):
                return True

    return False

projects = ["pandas", "scipy"]
for project in projects:
    prs = set()
    target_test_folder = join("data", "chaco_tests_hhh", project)
    metadata_folder = join("data", "chaco_tests_3critiria", project)
    pr_folders = listdir(metadata_folder)

    for pr_folder in pr_folders:
        test_files = listdir(join(metadata_folder, pr_folder))
        for file in test_files:
            with open(join(metadata_folder, pr_folder, file), "r") as f:
                test_code = f.read()
            call_private = has_private_accesses_or_fails_to_parse(test_code)
            if call_private == False:
                print(f"Kept test: {file} in {pr_folder} in {project} without private calls.")
                target = join(target_test_folder, pr_folder)
                makedirs(target, exist_ok=True)
                shutil.copyfile(join(metadata_folder, pr_folder, file), join(target, file))
                prs.add(pr_folder)
            else:
                print(f"Discarding test: {file} in {pr_folder} in {project} due to private calls or parsing issues.")
          
        print(f"Finished processing PR folder: {pr_folder} in project: {project}")
    
    with open(f"data/meta/chaco_prs/{project}_further_noprivate222_{len(prs)}.txt", "w") as f:
        f.writelines("\n".join(map(str, prs)))
                    

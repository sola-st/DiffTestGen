from os.path import join
from os import listdir, makedirs
import shutil
import libcst as cst
from testora.util.PythonCodeUtil import AttributeExtractor, CallExtractor

# Further to filter the ChaCo-generated tests: remove the tests that have private calls.

def has_private_accesses_or_fails_to_parse(code):
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError as e:
        return True

    call_extractor = CallExtractor()
    tree.visit(call_extractor)
    for callee in call_extractor.callees:
        if callee.startswith("_"): # and not callee.startswith("__") and callee.endswith("__"):
            return True

    attribute_extractor = AttributeExtractor()
    tree.visit(attribute_extractor)
    for attribute in attribute_extractor.attributes:
        if attribute.startswith("_"): # and not attribute.startswith("__") and attribute.endswith("__"):
            return True

    return False

projects = ["pandas", "scipy"]
for project in projects:
    prs = set()
    target_test_folder = join("data", "chaco_tests_no_private1", project)
    metadata_folder = join("data", "chaco_tests", project)
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
    
    with open(f"data/meta/chaco_prs/{project}_further_noprivate1_{len(prs)}.txt", "w") as f:
        f.writelines("\n".join(map(str, prs)))
                    

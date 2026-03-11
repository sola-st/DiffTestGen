from os.path import join
from os import listdir, makedirs
import shutil
import json

# 3 criteria to filter the ChaCo-generated tests:
# 1. The test should be integrated.
# 2. The test should have a non-zero coverage increment.
# 3. The test should not have execution errors or failures, and should be runnable. 

projects = ["pandas", "scipy"]
for project in projects:
    target_test_folder = join("chaco_tests", project)
    makedirs(target_test_folder, exist_ok=True)
    metadata_folder = f"{project}_eval/{project}/test_cases/target_gen_base_dynamic_test_context_fb_integrated"
    pr_folders = listdir(metadata_folder)
    for pr_folder in pr_folders:
        test_related_files = listdir(join(metadata_folder, pr_folder))
        for file in test_related_files:
            # check only the integrated test file
            if file.endswith("_integrated.py"):
                keep_the_test = True
                test_name = file.rsplit("_", 1)[0]

                # check the coverage increment
                cov_increment_file = join(metadata_folder, pr_folder, f"{test_name}_integrated_coverage_increment.json")
                try:
                    with open(cov_increment_file, "r") as f:
                        cov_info = json.load(f)
                    incremented_info = cov_info["perc_coverage_increment"]
                    if incremented_info == 0.0:
                        keep_the_test = False
                        print(f"Discarding test: {test_name} in {pr_folder} in {project} due to zero coverage increment.")
                        continue
                except:
                    print(f"Coverage increment file not found for test: {test_name} in {pr_folder} in {project}.")
                    print(f"Discarding test: {test_name} in {pr_folder} in {project} due to zero coverage increment.")
                    continue

                # check the test execution errors, failures, and runability, pytest output log
                runtime_log_file = join(metadata_folder, pr_folder, f"{test_name}_integrated_runtime.log")
                with open(runtime_log_file, "r") as f:
                    runtime_log = f.read()
                log_lines = runtime_log.splitlines()
                reversed_log_lines = log_lines[::-1]

                error_failure_block_start = None
                try:
                    error_failure_block_start = log_lines.index("Coverage XML written to file coverage.xml") # scipy
                except:
                    error_failure_block_start_tmp = [i for i, line in enumerate(reversed_log_lines) if " generated xml file: " in line][0] # pandas
                    error_failure_block_start = len(log_lines) - 1 - error_failure_block_start_tmp

                error_failure_block = log_lines[error_failure_block_start:]
                print(error_failure_block)
                if any(line.startswith("ERROR ") or line.startswith("FAILED ") or "no tests ran in" in line for line in error_failure_block):
                    keep_the_test = False

                if keep_the_test:
                    target = join(target_test_folder, pr_folder)
                    makedirs(target, exist_ok=True)
                    shutil.copyfile(join(metadata_folder, pr_folder, f"{test_name}.py"), join(target, f"{test_name}.py"))
                    print(f"Kept test: {test_name} in {pr_folder} in {project} with coverage increment: {incremented_info}%")
                else:
                    print(f"Discarding test: {test_name} in {pr_folder} in {project} due to test execution issues.")

        print(f"Finished processing PR folder: {pr_folder} in project: {project}")
                    

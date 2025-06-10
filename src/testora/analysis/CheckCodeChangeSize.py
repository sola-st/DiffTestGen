import json
from os import makedirs
from os.path import join, exists
from testora.RegressionFinder import get_repo
from testora.util.PullRequest import PullRequest


def get_number_of_lines(pr, file, version="both"):
    if version == "both":
        old_modified_num = len(pr.old_file_path_to_all_modified_lines[file])
        new_modified_num = len(pr.new_file_path_to_all_modified_lines[file])
        return old_modified_num + new_modified_num
    elif version == "old":
        return len(pr.old_file_path_to_all_modified_lines[file])
    else:
        return len(pr.new_file_path_to_all_modified_lines[file])

def filter_files(module_name, pr, operation):
    # get the added or deleted non-test files
    init_file_list = []
    if operation == "add":
        init_file_list = pr.patch.added_files
    elif operation == "remove":
        init_file_list = pr.patch.removed_files

    desired_code_files = [
        f for f in init_file_list if
        f.path.endswith(".py") or
        f.path.endswith(".pyx") or
        f.path.endswith(".c") or
        f.path.endswith(".cpp") or
        f.path.endswith(".h")
    ]
    filtered_files = [f.path for f in desired_code_files 
            if "test" not in f.path and (f.path.startswith(module_name) or f.path.startswith(f"src/{module_name}"))]
    
    return filtered_files

def check_diff_for_single_pr(project, pr_nums):
    # Check the LoC of diff for non-test Python files, including non-executable lines.
    github_repo, cloned_repo_manager = get_repo(project)
    module_name = cloned_repo_manager.module_name

    diff_locs_from_modified = [] # from modified non-test files
    diff_locs_from_touched = [] # from all touched non-test files, including added, deleted, and modified

    for pr_nb in pr_nums:
        github_pr = github_repo.get_pull(int(pr_nb))
        pr = PullRequest(github_pr, github_repo, cloned_repo_manager)

        # # 1. all touched files, includes added, deleted, and modified files, also includes non-python and test files.
        # details = f"Fiile path to all touched lines: Old: {pr.old_file_path_to_all_modified_lines}, New: {pr.new_file_path_to_all_modified_lines}"
        # append_event(CoverageEvent(pr_nb=pr.number, message=f"All touched files", details=f"{details}"))
        
        # 2. only modified non-test 'python' files, actually, .py, .pyx, .c, .cpp, and .h files.
        total_modified_num = 0 # each single pr reports only one LoC
        for file in pr.non_test_modified_code_files: 
            total_modified_num += get_number_of_lines(pr, file)
        diff_locs_from_modified.append(total_modified_num)

        # 3. non-test 'python' files, but consider added, deleted, and modified files
        # 3.1 added files in new version
        non_test_added_files = filter_files(module_name, pr, "add")
        if non_test_added_files:
            for file in non_test_added_files:
                total_modified_num += get_number_of_lines(pr, file, "new")
        # 3.2 deleted files in old version
        non_test_deleted_files = filter_files(module_name, pr, "remove")
        if non_test_deleted_files:
            for file in non_test_deleted_files:
                total_modified_num += get_number_of_lines(pr, file, "old")
        
        diff_locs_from_touched.append(total_modified_num)

    return diff_locs_from_modified, diff_locs_from_touched

def main():
    diff_modified_locs = []
    diff_touched_locs = []
    with open(".target_project", "r") as f:
        project = f.read().strip()

    meta_folder = join("data", "meta", "diff_loc")
    makedirs(meta_folder, exist_ok=True)
    meta_file = join(meta_folder, f"{project}_loc_in_diff_meta.txt")
    if exists(meta_file):
        with open(meta_file, "r") as f:
            meta_info = json.load(f) 
        diff_modified_locs = json.loads(meta_info["diff_modified_locs"])    
        diff_touched_locs = json.loads(meta_info["diff_touched_locs"]) 
    else:
        project_pr_file = join("data", "meta", "pr_nums", f"{project}_PRs_all.txt")
        with open(project_pr_file, "r") as f:
            pr_nums = f.readlines()
        diff_modified_locs, diff_touched_locs = check_diff_for_single_pr(project, pr_nums)

        # write the numbers to a local file, for further helping to decide group size
        to_write = {
            "diff_modified_locs": f"{diff_modified_locs}",
            "diff_touched_locs": f"{diff_touched_locs}"
        }
    
        with open(meta_file, "w") as f:
            json.dump(to_write, f, indent=2)


if __name__=="__main__":\
    main()
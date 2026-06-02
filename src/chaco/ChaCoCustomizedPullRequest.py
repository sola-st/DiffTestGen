import requests
from unidiff import PatchSet
from testora.execution.CoverageAnalyzer import set_to_ranges
from testora.util.PythonCodeUtil import equal_modulo_docstrings
from testora import Config
from testora.util.PythonCodeUtil2 import get_function_names

class ChaCoCustomizedPullRequest:
    def __init__(self, github_pr, github_repo, cloned_repo_manager):
        self.github_pr = github_pr
        self.cloned_repo_manager = cloned_repo_manager
        self.number = github_pr.number
        self.title = github_pr.title
        self.post_commit = github_pr.merge_commit_sha
        self.parents = github_repo.get_commit(self.post_commit).parents
        self.pre_commit = self.parents[0].sha

        self._pr_url_to_patch()
        self._compute_non_test_modified_files()
        self.has_non_comment_change()

        self.full_diff = self.get_full_diff() 
        self._compute_modified_lines() # extract from full_diff, all modified lines, includes the non-excutable ones
        self._get_refined_changed_hunks()
        
    def _pr_url_to_patch(self): 
        ''' 
        The target is to get the modified files from the patch.
        (all the touch files in a PR , **exclude** deleted and newly added files). 
        '''
        # # option 1
        # diff_url = self.github_pr.html_url + ".diff"
        # diff = urllib.request.urlopen(diff_url)
        # encoding = diff.headers.get_charsets()[0]
        # self.patch = PatchSet(diff, encoding=encoding)

        # # option 2
        # if the above code hits the request limit, use the following instead.
        diff_url = self.github_pr.url
        token = open(".github_token", "r").read().strip()
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3.diff"
        }

        response = requests.get(diff_url, headers=headers)
        response.raise_for_status()

        # Load diff with unidiff PatchSet
        self.patch = PatchSet(response.text)

        # # option 3
        # self.github_pr.get_files() # then check the 'status' of every listed file.
        # reference: https://docs.github.com/en/rest/pulls/pulls?apiVersion=2022-11-28#list-pull-requests-files 

    def _compute_non_test_modified_files(self):
        self.module_name = self.cloned_repo_manager.module_name

        # Python files only
        self.modified_python_files = [f for f in self.patch.modified_files if f.path.endswith(".py")] # [cython issue Sept.11] or f.path.endswith(".pyx")]
        self.non_test_modified_python_files = [f.path for f in self.modified_python_files 
                if "test" not in f.path and (f.path.startswith(self.module_name) or f.path.startswith(f"src/{self.module_name}"))]

        # Python and other PLs
        modified_code_files = [
            f for f in self.patch.modified_files if
            f.path.endswith(".py") or
            f.path.endswith(".pyx") or
            f.path.endswith(".c") or
            f.path.endswith(".cpp") or
            f.path.endswith(".h")
        ]
        self.non_test_modified_code_files = [f.path for f in modified_code_files 
                if "test" not in f.path and (f.path.startswith(self.module_name) or f.path.startswith(f"src/{self.module_name}"))]

    def get_modified_files(self):
        if Config.code_change_pl == "python":
            return self.non_test_modified_python_files
        elif Config.code_change_pl == "all":
            return self.non_test_modified_code_files

    def has_non_comment_change(self):
        if Config.code_change_pl == "all":
            return len(self.non_test_modified_code_files) > 0

        pre_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.pre_commit)
        post_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.post_commit)

        self.files_with_non_comment_changes = []
        for modified_file in self.non_test_modified_python_files:
            with open(f"{pre_commit_cloned_repo.repo.working_dir}/{modified_file}", "r") as f:
                old_file_content = f.read()
            with open(f"{post_commit_cloned_repo.repo.working_dir}/{modified_file}", "r") as f:
                new_file_content = f.read()
            if not equal_modulo_docstrings(old_file_content, new_file_content):
                self.files_with_non_comment_changes.append(modified_file)

        self.files_with_non_comment_changes = list(dict.fromkeys(
            self.files_with_non_comment_changes))  # turn into set while preserving order
        return len(self.files_with_non_comment_changes) > 0

    def _get_relevant_changed_files(self) -> list[str]:
        if Config.code_change_pl == "python":
            return self.files_with_non_comment_changes
        elif Config.code_change_pl == "all":
            return self.non_test_modified_code_files
        else:
            raise Exception(f"Unexpected configuration value: {Config.code_change_pl}")

    def get_filtered_diff(self):
        post_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.post_commit)
        diff_parts = []
        for file_path in self._get_relevant_changed_files():
            raw_diff = post_commit_cloned_repo.repo.git.diff(self.pre_commit, self.post_commit, file_path)
            diff_parts.append(raw_diff)

        self.filtered_diff = "\n\n".join(diff_parts)

    def get_full_diff(self):
        post_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.post_commit)

        return post_commit_cloned_repo.repo.git.diff(self.pre_commit, self.post_commit)

    def get_changed_function_names(self): # from both old and new version
        self.changed_function_qualified_names_old = [] 
        pre_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.pre_commit)
        # update self.changed_function_qualified_names_old
        self.get_helper(pre_commit_cloned_repo, "old") # target on getting old context
            
        post_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.post_commit)
        # update self.changed_function_qualified_names_new
        self.changed_function_qualified_names_new = []
        self.get_helper(post_commit_cloned_repo, "new")

        self.union_changed_function_qualified_names = list(set(set(self.changed_function_qualified_names_old).union(set(self.changed_function_qualified_names_new))))
        return self.union_changed_function_qualified_names

    def get_helper(self, cloned_repo, version):
        for modified_file in self.patch.modified_files:
            if modified_file.path in self._get_relevant_changed_files():
                with open(f"{cloned_repo.repo.working_dir}/{modified_file.path}", "r") as f:
                    file_content = f.read()
                module_name = modified_file.path.replace("src/", "", 1).replace(".py", "").replace("/", ".").rstrip(".__init__")
                
                patch_ranges = []
                for hunk in modified_file:
                    patch_range = None
                    if version == "new":
                        start_line = hunk.target_start
                        end_line = hunk.target_start + hunk.target_length
                        patch_range = (start_line, end_line) # numbers start at 1 and end_line included
                    else:
                        start_line = hunk.source_start
                        end_line = hunk.source_start + hunk.source_length
                        patch_range = (start_line, end_line) # numbers start at 1 and end_line included
                    patch_ranges.append(patch_range)

                func_names, __, __ = get_function_names(file_content, patch_ranges)
                if func_names:
                    if version == "old":
                        for func_name in func_names:
                            self.changed_function_qualified_names_old.append(f"{module_name}.{func_name}")
                    else:
                        for func_name in func_names:
                            self.changed_function_qualified_names_new.append(f"{module_name}.{func_name}")


    def _compute_modified_lines(self):
        self.old_file_path_to_all_modified_lines = {}
        self.new_file_path_to_all_modified_lines = {}
        patch = PatchSet(self.full_diff) # always compute for all touched files (add, delete, modify)

        for patched_file in patch:
            self.old_file_path_to_all_modified_lines[patched_file.path] = set()
            self.new_file_path_to_all_modified_lines[patched_file.path] = set()
            for hunk in patched_file:
                for line in hunk:
                    if line.is_removed:
                        self.old_file_path_to_all_modified_lines[patched_file.path].add(line.source_line_no)
                    elif line.is_added:
                        self.new_file_path_to_all_modified_lines[patched_file.path].add(line.target_line_no)

    def _get_refined_changed_hunks(self):
        # to use the exact changed hunks, without unchanged lines, to locate the functions.
        self.old_file_path_to_change_hunks = _get_refined_changed_hunks_helper(self.old_file_path_to_all_modified_lines)
        self.new_file_path_to_change_hunks = _get_refined_changed_hunks_helper(self.new_file_path_to_all_modified_lines)


def _get_refined_changed_hunks_helper(file_path_to_all_modified_lines):
    file_path_to_change_hunks = {}
    for file_path, changed_lines in file_path_to_all_modified_lines.items():
        changed_hunks = set_to_ranges(changed_lines)
        file_path_to_change_hunks.update({file_path: changed_hunks})
    return file_path_to_change_hunks

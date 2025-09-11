import json
import requests
from unidiff import PatchSet
# import urllib.request
from testora.util.PythonCodeUtil import equal_modulo_docstrings, extract_target_function_by_range, get_name_of_defined_function
from testora import Config
from testora.util.PythonCodeUtil2 import (
        get_function_names,
        get_function_names_code, 
        get_function_names_code_with_line_num,
        get_function_names_code_to_with_mark,
        get_test_function_names_code_imports
)
from testora.util.ExtractCallerCallee import ExtractCallerCallee


class PullRequest:
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

        self.full_diff = self.get_full_diff() 
        self._compute_modified_lines() # extract from full_diff, all modified lines, includes the non-excutable ones

        # only compute diffs once, full_diff at above location, and filtered diff at the initial round test generation
        # all the following feedback rounds will get the diff strs by these two attributes.
        self.filtered_diff = ""

        # a extra context provider. 
        # could contains different types of contexts, e.g., the entire file contents, only the modified functions, etc.
        self.old_context = "" # str for models to easy-follow
        self.new_context = ""

        # needed when the code require both the function codes with and without line numbers
        self.old_context_with_line_num = {}
        self.new_context_with_line_num = {}

        self.old_test_function_code = {}
        self.new_test_function_code = {}
        # to help extract existing tests
        if Config.use_existing_tests != None:
            # to extract self.modified_test_python_files
            self._compute_modified_test_python_files()

        self.function_callers = {} # each dict element is a changed function maps to its callers
        self.function_callees = {}

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
        module_name = self.cloned_repo_manager.module_name

        # Python files only
        self.modified_python_files = [f for f in self.patch.modified_files if f.path.endswith(".py")] # [cython issue Sept.11] or f.path.endswith(".pyx")]
        self.non_test_modified_python_files = [f.path for f in self.modified_python_files 
                if "test" not in f.path and (f.path.startswith(module_name) or f.path.startswith(f"src/{module_name}"))]

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
                if "test" not in f.path and (f.path.startswith(module_name) or f.path.startswith(f"src/{module_name}"))]

    def get_modified_files(self):
        if Config.code_change_pl == "python":
            return self.non_test_modified_python_files
        elif Config.code_change_pl == "all":
            return self.non_test_modified_code_files
        
    def _compute_modified_test_python_files(self):
        self.modified_test_python_files = [f.path for f in self.modified_python_files 
                if ("test_" in f.path or "_test" in f.path)]

    def has_non_comment_change(self):
        if Config.code_change_pl == "all":
            return len(self.non_test_modified_code_files) > 0

        pre_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.pre_commit)
        post_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.post_commit)

        self.files_with_non_comment_changes = []
        for modified_file in self.non_test_modified_python_files:
            with open(f"{pre_commit_cloned_repo.repo.working_dir}/{modified_file.path}", "r") as f:
                old_file_content = f.read()
            with open(f"{post_commit_cloned_repo.repo.working_dir}/{modified_file.path}", "r") as f:
                new_file_content = f.read()
            if not equal_modulo_docstrings(old_file_content, new_file_content):
                self.files_with_non_comment_changes.append(modified_file.path)

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

    def get_changed_function_names(self):
        result = []
        
        # H: only the function name in new version
        post_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.post_commit)

        for modified_file in self.patch.modified_files:
            if modified_file.path in self._get_relevant_changed_files():
                with open(f"{post_commit_cloned_repo.repo.working_dir}/{modified_file.path}", "r") as f:
                    new_file_content = f.read()

                module_name = modified_file.path.replace("/", ".").replace(".pyx", "").replace(".py", "")
                # H: what about if a file has multiple classes
                for hunk in modified_file:
                    start_line = hunk.target_start
                    end_line = hunk.target_start + hunk.target_length
                    patch_range = (start_line, end_line)
                    fct_code = extract_target_function_by_range(
                        new_file_content, patch_range)
                    if fct_code is not None:
                        fct_name = get_name_of_defined_function(fct_code)
                        if fct_name:
                            result.append(f"{module_name}.{fct_name}")

        result = list(dict.fromkeys(result))
        return result
    
    def get_changed_function_names_and_context(self, prompt_base):
        # get_changed_function_names_and_context
        pre_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.pre_commit)
        changed_function_qualified_names_old = self.get_helper(pre_commit_cloned_repo, "old", prompt_base) # target on getting old context
        post_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.post_commit)
        changed_function_qualified_names_new = self.get_helper(post_commit_cloned_repo, "new", prompt_base)

        # get test function code
        if Config.use_existing_tests == "pr-modified":
            self.get_test_function_code(pre_commit_cloned_repo, "old") # update self.xxx_test_function_code
            self.get_test_function_code(post_commit_cloned_repo, "new") # TODO check whether repeated the repo build

        all_changed_func = list(set(changed_function_qualified_names_new).union(set(changed_function_qualified_names_old)))
        return all_changed_func
    
    def get_helper(self, cloned_repo, version, prompt_base):
        changed_functions = None
        if Config.call_gragh == True:
            # the server stays alive for the entire workspace
            server = ExtractCallerCallee(cloned_repo.repo.working_dir)
            with server.lsp.start_server(): # start only once, automatic stop
                changed_functions = self.helper_inner(cloned_repo, version, prompt_base, server)
        else:
            changed_functions = self.helper_inner(cloned_repo, version, prompt_base)

        return changed_functions  

    def helper_inner(self, cloned_repo, version, prompt_base, server=None):
        changed_functions = []
        code_context = ""
        code_context_with_line_num_str = ""
        code_context_with_line_num = {}

        for modified_file in self.patch.modified_files:
            if modified_file.path in self._get_relevant_changed_files():
                with open(f"{cloned_repo.repo.working_dir}/{modified_file.path}", "r") as f:
                    file_content = f.read()
                module_name = modified_file.path.replace("/", ".").replace(".pyx", "").replace(".py", "")
                patch_ranges = []
                for hunk in modified_file:
                    patch_range = None
                    if version == "new":
                        start_line = hunk.target_start
                        end_line = hunk.target_start + hunk.target_length
                        patch_range = (start_line, end_line) # numbers start at 1 andend_line included
                    else:
                        start_line = hunk.source_start
                        end_line = hunk.source_start + hunk.source_length
                        patch_range = (start_line, end_line) # numbers start at 1 andend_line included
                    patch_ranges.append(patch_range) 

                function_names = None
                functions_code = None
                functions_code_with_line_num = None
                if Config.context_version in [1]: # return only function names
                    function_names, __, __ = get_function_names(file_content, patch_ranges)
                elif Config.context_version in [2, 3]: # return function names and code
                    function_names, functions_code, __ = get_function_names_code(file_content, patch_ranges)
                elif Config.context_version in [7]: # return function names and code with line numbers
                    # 7 without diff, but with the @@ line mappings
                    # here the functions_code is with line numbers
                    function_names, functions_code, __ = get_function_names_code_with_line_num(file_content, patch_ranges)
                elif Config.context_version in [4, 5, 6, 8]: 
                    function_names, functions_code, functions_code_with_line_num = get_function_names_code_to_with_mark(file_content, patch_ranges)
                    code_context_with_line_num.update({modified_file.path: functions_code_with_line_num})

                    if Config.context_version in [4, 6] or prompt_base == 4:
                        code_context_with_line_num_str += f"The following are the affected functions from file <{modified_file.path}>:\n"
                        code_context_with_line_num_str += "\n\n".join(functions_code_with_line_num)
                        code_context_with_line_num_str += "\n"

                if function_names:
                    if type(function_names[0]) == tuple: 
                        if Config.call_gragh == True:
                            for func_info in function_names:
                                func_name, start_line_0_based, start_col_0_based = func_info
                        
                                # TODO maybe repetition here, check to visit less as possible as it can
                                try:
                                    callers = server.get_function_callers(modified_file.path, start_line_0_based, start_col_0_based)
                                    self.function_callers.update({func_name: callers})
                                    # print(f"*** Callers of {func_name}@{start_line}: {callers}")
                                    # with open(f"er_{self.number}_{func_name}_{start_col_0_based}.json", "w") as f:
                                    #     json.dump(callers, f, indent=2)
                                except:
                                    self.function_callers.update({func_name: "failed"})
                                    print(f"* [{version}-ER] Get caller failed: {(modified_file.path, func_name, start_line_0_based, start_col_0_based)}")

                                try:
                                    callees = server.get_function_callees(modified_file.path, start_line_0_based)
                                    self.function_callees.update({func_name: callees})
                                    # print(f"--- Callees of {func_name}@{start_line}: {callees}")
                                    # with open(f"ee_{self.number}_{func_name}_{start_col_0_based}.json", "w") as f:
                                    #     json.dump(callees, f, indent=2)
                                except:
                                    self.function_callees.update({func_name: "failed"})
                                    print(f"* [{version}-EE] Get callee failed: {(modified_file.path, func_name, start_line_0_based, start_col_0_based)}")
                        else:
                            for func_name in function_names:
                                function_name, start_line_0_based, start_col_0_based = func_name
                                changed_functions.append(f"{module_name}.{function_name}")
                    else:
                        for func_name in function_names:
                            changed_functions.append(f"{module_name}.{func_name}") # func_name also includes class_name if the setting goes like that

                if functions_code:
                    code_context += f"The following are the affected functions from file <{modified_file.path}>:\n"
                    code_context += "\n\n".join(functions_code)
                    code_context += "\n"

        if version == "old":
            self.old_context = code_context
        else:
            self.new_context = code_context 

        if Config.context_version == 5 or prompt_base == 5:
            if version == "old":
                self.old_context_with_line_num = code_context_with_line_num 
            else:
                self.new_context_with_line_num = code_context_with_line_num 
        elif Config.context_version in [4, 6] or prompt_base == 4:
            if version == "old":
                self.old_context_with_line_num = code_context_with_line_num_str 
            else:
                self.new_context_with_line_num = code_context_with_line_num_str 
                
        return changed_functions

    def get_test_function_code(self, cloned_repo, version):
        code_context = ""
        for modified_file in self.patch.modified_files: # does not consider the removed test files.
            if modified_file.path in self.modified_test_python_files:
                with open(f"{cloned_repo.repo.working_dir}/{modified_file.path}", "r") as f:
                    file_content = f.read()
                patch_ranges = []
                for hunk in modified_file:
                    patch_range = None
                    if version == "new":
                        start_line = hunk.target_start
                        end_line = hunk.target_start + hunk.target_length
                        patch_range = (start_line, end_line) # numbers start at 1 andend_line included
                    else:
                        start_line = hunk.source_start
                        end_line = hunk.source_start + hunk.source_length
                        patch_range = (start_line, end_line) # numbers start at 1 andend_line included
                    patch_ranges.append(patch_range)

                test_functions_code, test_file_imports = get_test_function_names_code_imports(file_content, patch_ranges)
                
                if test_functions_code:
                    code_context += f"The following are and the modified test functions from file <{modified_file.path}>:\n"
                    code_context += "Here starts with the import statements of this test file, refer to them if needed.\n"
                    code_context += "\n".join(test_file_imports)
                    code_context += "\n\n".join(test_functions_code)
                    code_context += "\n"

        if version == "old":
            self.old_test_function_code = code_context
        else:
            self.new_test_function_code = code_context 

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
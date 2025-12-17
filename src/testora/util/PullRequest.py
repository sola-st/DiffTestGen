import copy
import json
import requests
from unidiff import PatchSet
# import urllib.request
from testora.execution.CoverageAnalyzer import set_to_ranges
from testora.util.BuildDocumentation import BuildDocumentation
from testora.util.ListPublicAPIsLocal import get_apis
from testora.util.Logs import CallGraphEvent, Event, append_event
from testora.util.PythonCodeUtil import equal_modulo_docstrings, extract_target_function_by_range, get_name_of_defined_function
from testora import Config
from testora.util.PythonCodeUtil2 import (
        get_caller_function_names,
        get_function_names,
        get_function_names_code, 
        get_function_names_code_with_line_num,
        get_function_names_code_to_with_mark,
        get_test_function_names_code_imports,
        is_public
)
from testora.util.ExtractCallerCallee import ExtractCallerCallee
from collections import deque
from os.path import exists


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
        self._get_refined_changed_hunks()

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
        
        if Config.call_graph == True:
            self._prepae_to_use_call_graph()

    def _prepae_to_use_call_graph(self):
        self.public_apis_union = [] # for identifying the private functions in the generated tests
        self.public_apis_old = [] 
        self.public_apis_new = []
        '''
        A variable could have two versions (irrelevant to 'old' and 'new'):
            For the one with '_all"       it stores all the infomation
            For the one without '_all"      it stores the shortest call graph path related information
        '''
        # For both public and non-public ones, to return
        self.class_hover_texts = set() # shortest path related classes

        # for public changed functions
        # to 'return'
        self.public_func_imports = {}
        # for middle status
        self.public_func_imports_old = set()
        self.public_func_imports_new = set()
        self.public_class_hover_text_old = {}
        self.public_class_hover_text_new = {}

        # for private changed functions
        # to 'return' # shortests
        self.call_graph_paths = {}
        self.signatures_docstrings = {}
        self.imports = {}

        # for middle status
        self.call_graph_paths_old = []
        self.signatures_docstrings_old = []
        self.imports_old = []
        self.non_public_class_hover_text_old = {}

        self.call_graph_paths_new = []
        self.signatures_docstrings_new = []
        self.imports_new = []
        self.non_public_class_hover_text_new = {}

        # for focuing on specified folder, not the entire project
        self.target_folder = None
        project_name = self.cloned_repo_manager.repo_name
        if project_name == "marshmallow":
            self.target_folder = "src"
        elif project_name in ["scipy", "pandas"]:
            self.target_folder = project_name

        # for private functions, update the following three:
        self.all_call_graph_paths = {}
        self.all_signatures_docstrings = {}
        self.all_imports = {}

        # for the selected top k entries for each single changed private functions
        self.call_graph_paths_k = {}
        self.signatures_docstrings_k = {}
        self.imports_k = {}

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

    def get_changed_function_names(self): # only been used in original Testora
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
        self.changed_function_qualified_names_old = [] # all: public + private + unsure
        if Config.context_version != 1: # original Testora does not goes for old version of changed functions
            pre_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.pre_commit)
            # update self.changed_function_qualified_names_old
            self.changed_function_qualified_names_old_non_public = []
            self.get_helper(pre_commit_cloned_repo, "old", prompt_base) # target on getting old context

        post_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.post_commit)
        # update self.changed_function_qualified_names_new
        self.changed_function_qualified_names_new = []
        self.changed_function_qualified_names_new_no_public = []
        self.get_helper(post_commit_cloned_repo, "new", prompt_base)

        # get test function code
        if Config.use_existing_tests == "pr-modified":
            self.get_test_function_code(pre_commit_cloned_repo, "old") # update self.xxx_test_function_code
            self.get_test_function_code(post_commit_cloned_repo, "new") # TODO check whether repeated the repo build

        self.union_changed_function_qualified_names = list(set(set(self.changed_function_qualified_names_old).union(set(self.changed_function_qualified_names_new))))
        return self.union_changed_function_qualified_names
    
    def get_helper(self, cloned_repo, version, prompt_base):
        # update changed_functions for old or new version
        if Config.call_graph == True:
            # the server stays alive for the entire workspace
            server = ExtractCallerCallee(cloned_repo.repo.working_dir)
            with server.lsp.start_server(self.target_folder): # start only once, automatic stop, focus on only the given folder
                self.helper_inner(cloned_repo, version, prompt_base, server)
        else:
            self.helper_inner(cloned_repo, version, prompt_base)

    def helper_inner(self, cloned_repo, version, prompt_base, server=None):
        code_context = ""
        code_context_with_line_num_str = ""
        code_context_with_line_num = {}

        for modified_file in self.patch.modified_files:
            if modified_file.path in self._get_relevant_changed_files():
                with open(f"{cloned_repo.repo.working_dir}/{modified_file.path}", "r") as f:
                    file_content = f.read()
                # module_name = modified_file.path.replace("/", ".").replace(".pyx", "").replace(".py", "")
                # fully dotted path, not always the same as actual module
                module_name = modified_file.path.replace("src/", "", 1).replace(".py", "").replace("/", ".")
                
                patch_ranges = []
                if Config.context_version == 1: # original Testora
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
                else:
                    if version == "old":
                        patch_ranges = self.old_file_path_to_change_hunks[modified_file.path]
                    else:
                        patch_ranges = self.new_file_path_to_change_hunks[modified_file.path]

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
                    if type(function_names[0]) == tuple: # our approach
                        if Config.call_graph == True:
                            # to build documentation
                            container_name = cloned_repo.container_name
                            # if (version == "old" and not self.public_apis_old) or (version == "new" and not self.public_apis_new):
                            api_file = f"apis/api_{container_name}_{self.number}/objects.inv"
                            if not exists(api_file): # write it to local for quick repetition
                                # to build only once per version
                                # project_name = self.cloned_repo_manager.repo_name
                                # generate and copy it from container: a file f"api_{container_name}.inv" which includes all public apis
                                append_event(Event(pr_nb=self.number, message=f"Starting to bulid sphinx documentation ({version})."))
                                BuildDocumentation(container_name, self.cloned_repo_manager.repo_name, self.number).build()
                                append_event(Event(pr_nb=self.number, message=f"Done with sphinx bulid ({version})."))
                            
                            checked_parent_class = [] 
                            if version == "old":
                                # get public apis: self.public_apis_old, self.full_names_old, self.abbr_names_old
                                self.public_apis_old = get_apis(api_file)

                                function_names_to_get_cg_old = []
                                for func_name in function_names:
                                    function_name, start_line_0_based, start_col_0_based, parent_class = func_name

                                    check_parent_class = True
                                    if parent_class:
                                        if parent_class in checked_parent_class: # check the class hover text only once
                                            check_parent_class = False
                                        else:
                                            checked_parent_class.append(parent_class)
                                    else: # the cases with no parent class
                                        check_parent_class = False

                                    import_line, adjusted_module, class_hover_text = is_public(server, modified_file.path, module_name, 
                                            parent_class, function_name, self.public_apis_old, check_parent_class) # , is_changed_func=True)
                                    if class_hover_text:
                                        # here adjusted_module ends with class name
                                        self.public_class_hover_text_old.update({adjusted_module: class_hover_text})

                                    fully_qulified_name = f"{adjusted_module}.{function_name}"
                                    self.changed_function_qualified_names_old.append(fully_qulified_name)
                                    if import_line: # public and special methods
                                        if function_name.startswith("__"):
                                            self.public_func_imports_old.add(f"* To trigger changed method '{fully_qulified_name}', which is a special method of the class '{adjusted_module}', access the class with: {import_line}")
                                        else:
                                            self.public_func_imports_old.add(f"* To access changed function '{fully_qulified_name}': {import_line}")
                                    else:
                                        self.changed_function_qualified_names_old_non_public.append(fully_qulified_name)
                                        function_names_to_get_cg_old.append(func_name)
                                    
                                # update "self.all_call_graph_paths", "self.all_signatures_docstrings", and self.all_imports
                                if function_names_to_get_cg_old:
                                    self.get_call_graph_info(server, modified_file, function_names_to_get_cg_old, version)
                            else: # new code version
                                # self.public_apis_new, self.full_names_new, self.abbr_names_new
                                self.public_apis_new = get_apis(api_file)
                                if Config.private_call_indentification == 2: # this only used for private checking in the generated code
                                    self.public_apis_union = self.public_apis_old[0] + self.public_apis_new[0] 

                                function_names_to_get_cg_new = []
                                for func_name in function_names:
                                    function_name, start_line_0_based, start_col_0_based, parent_class = func_name
                                        
                                    check_parent_class = True
                                    if parent_class:
                                        if parent_class in checked_parent_class:
                                            check_parent_class = False
                                        else:
                                            checked_parent_class.append(parent_class)
                                    else: # the cases with no parent class
                                        check_parent_class = False

                                    import_line, adjusted_module, class_hover_text = is_public(server, modified_file.path, module_name, 
                                            parent_class, function_name, self.public_apis_new, check_parent_class) # , is_changed_func=True)
                                    if class_hover_text:
                                        self.public_class_hover_text_new.update({adjusted_module: class_hover_text})
                                    
                                    fully_qulified_name = f"{adjusted_module}.{function_name}"
                                    self.changed_function_qualified_names_new.append(fully_qulified_name)
                                    if import_line: # public
                                        if function_name.startswith("__"):
                                            self.public_func_imports_new.add(f"* To trigger changed method '{fully_qulified_name}', which is a special method of the class '{adjusted_module}', access the class with: {import_line}")
                                        else:
                                            self.public_func_imports_new.add(f"* To access changed function '{fully_qulified_name}': {import_line}")
                                    else:
                                        self.changed_function_qualified_names_new_no_public.append(fully_qulified_name)
                                        function_names_to_get_cg_new.append(func_name)
                                
                                if function_names_to_get_cg_new:
                                    self.get_call_graph_info(server, modified_file, function_names_to_get_cg_new, version)
                    else: # original Testora
                        for func_name in function_names:
                            self.changed_function_qualified_names_new.append(f"{module_name}.{func_name}")

                if functions_code:
                    code_context += f"The following are the affected functions from file <{modified_file.path}>:\n"
                    code_context += "\n\n".join(functions_code)
                    code_context += "\n"

        if version == "new" and (self.call_graph_paths_old or self.call_graph_paths_new or self.public_func_imports_old or self.public_func_imports_new):
            self.get_union_call_graph()
            self.get_shortest_path_each_entry()
            self.record_all_and_shortest_call_paths()
            self.get_top_k_shortest_across_different_entries()
            self.update_class_hover_text()

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
    
    def get_union_call_graph(self):
        # for public functions
        common_in_both = self.public_func_imports_old.intersection(self.public_func_imports_new)
        unique_in_old = self.public_func_imports_old.difference(self.public_func_imports_new)
        unique_in_new = self.public_func_imports_new.difference(self.public_func_imports_old)

        self.public_func_imports = {
            "common": list(common_in_both),
            "old": list(unique_in_old),
            "new": list(unique_in_new)
        }
        
        non_checked_new_indices = list(range(len(self.changed_function_qualified_names_new_no_public)))
        for qualified_func, old_cg_func_level_list, old_sig_doc_func_level_list, old_imports_func_level_list in \
                zip(self.changed_function_qualified_names_old_non_public, self.call_graph_paths_old, self.signatures_docstrings_old, self.imports_old):
            self.all_call_graph_paths.update(
                {qualified_func: {
                    "common": [],
                    "old": [],
                    "new": []
                }})
            self.all_signatures_docstrings.update(
                {qualified_func: {
                    "common": [],
                    "old": [],
                    "new": []
                }})
            self.all_imports.update(
                {qualified_func: {
                    "common": [],
                    "old": [],
                    "new": []
                }})
            if qualified_func in self.changed_function_qualified_names_new_no_public:
                # the same qualified function in both the versions
                idx = self.changed_function_qualified_names_new_no_public.index(qualified_func)
                try:
                    new_cg_func_level_list = self.call_graph_paths_new[idx]
                    new_sig_doc_func_level_list = self.signatures_docstrings_new[idx]
                    new_imports_func_level_list = self.imports_old[idx] 
                    non_checked_new_indices.remove(idx)
                except:
                    continue

                # the same in both, so far, get details from old
                cg_common_in_both = [x for x in old_cg_func_level_list if x in new_cg_func_level_list]
                sig_doc_common = []
                import_common = []
                for common in cg_common_in_both:
                    map_idx = old_cg_func_level_list.index(common)
                    sig_doc_common.append(old_sig_doc_func_level_list[map_idx])
                    import_common.append(old_imports_func_level_list[map_idx])
                
                # unique in old
                cg_unique_in_old = [x for x in old_cg_func_level_list if x not in new_cg_func_level_list]
                sig_doc_unique_in_old = []
                import_unique_in_old = []
                for unique in cg_unique_in_old:
                    map_idx = old_cg_func_level_list.index(unique)
                    sig_doc_unique_in_old.append(old_sig_doc_func_level_list[map_idx])
                    import_unique_in_old.append(old_imports_func_level_list[map_idx])

                # unique in new
                cg_unique_in_new = [x for x in new_cg_func_level_list if x not in old_cg_func_level_list]
                sig_doc_unique_in_new = []
                import_unique_in_new = []
                for unique in cg_unique_in_new:
                    map_idx = new_cg_func_level_list.index(unique)
                    sig_doc_unique_in_new.append(new_sig_doc_func_level_list[map_idx])
                    import_unique_in_new.append(new_imports_func_level_list[map_idx])

                # union info
                self.all_call_graph_paths[qualified_func]["common"].extend(cg_common_in_both)
                self.all_signatures_docstrings[qualified_func]["common"].extend(sig_doc_common)
                self.all_imports[qualified_func]["common"].extend(import_common)

                self.all_call_graph_paths[qualified_func]["old"].extend(cg_unique_in_old)
                self.all_signatures_docstrings[qualified_func]["old"].extend(sig_doc_unique_in_old)
                self.all_imports[qualified_func]["old"].extend(import_unique_in_old)

                self.all_call_graph_paths[qualified_func]["new"].extend(cg_unique_in_new)
                self.all_signatures_docstrings[qualified_func]["new"].extend(sig_doc_unique_in_new)
                self.all_imports[qualified_func]["new"].extend(import_unique_in_new)

            else: # unique in old
                self.all_call_graph_paths[qualified_func]["old"] = old_cg_func_level_list
                self.all_signatures_docstrings[qualified_func]["old"] = old_sig_doc_func_level_list
                self.all_imports[qualified_func]["old"] = old_imports_func_level_list

        if non_checked_new_indices: # unique in new
            for idx in non_checked_new_indices:
                func = self.changed_function_qualified_names_new_no_public[idx]
                
                self.all_call_graph_paths.update({func: {
                    "new": self.call_graph_paths_new[idx]
                }})
                self.all_signatures_docstrings.update({func: {
                    "new": self.signatures_docstrings_new[idx]
                }})
                self.all_imports.update({func: {
                    "new": self.imports_new[idx]
                }})

    def get_shortest_path_each_entry(self):
        for func_name, cg_path_func_level in self.all_call_graph_paths.items():
            if cg_path_func_level:
                self.call_graph_paths.update(
                    {func_name: {
                        "common": [],
                        "old": [],
                        "new": []
                    }})
                self.signatures_docstrings.update(
                    {func_name: {
                        "common": [],
                        "old": [],
                        "new": []
                    }})
                self.imports.update(
                    {func_name: {
                        "common": [],
                        "old": [],
                        "new": []
                    }})

                for label, cg_paths in cg_path_func_level.items(): # label could be common, old, and new
                    if cg_paths:
                        entry_func_to_paths = {}
                        for i, cg in enumerate(cg_paths):
                            cg.append(i) # to mark the idx, and map to signatures and imports
                            entry_func = cg[0]
                            if entry_func not in entry_func_to_paths.keys():
                                entry_func_to_paths.update({entry_func: [cg]})
                            else:
                                entry_func_to_paths[entry_func].append(cg)

                        for entry_func, paths in entry_func_to_paths.items():
                            shortest_path_tmp = min(paths, key=len)
                            shortest_path = shortest_path_tmp[:-1]
                            idx = shortest_path_tmp[-1]
                            sig_doc = self.all_signatures_docstrings[func_name][label][idx]
                            imports = self.all_imports[func_name][label][idx]

                            self.call_graph_paths[func_name][label].append(shortest_path)
                            self.signatures_docstrings[func_name][label].append(sig_doc)
                            self.imports[func_name][label].append(imports)

    def record_all_and_shortest_call_paths(self):
        # from the perspective of recording the call path length
        cg_path_len = {
            'shortest': [],
            'shortest_avg': 0,
            'all': [],
            'all_avg': 0
        }

        # **** for shortest entries
        for func_name, cg_path_func_level in self.call_graph_paths.items():
            if cg_path_func_level:
                for label, cg_paths in cg_path_func_level.items():
                    if cg_paths:
                        for cg in cg_paths:
                            cg_path_len['shortest'].append(len(cg))
        
        value = sum(cg_path_len['shortest']) / len(cg_path_len['shortest']) if cg_path_len['shortest'] else 0
        cg_path_len['shortest_avg'] = round(value, 3) if value != 0 else 0

        # **** for all entries
        for func_name, cg_paths_with_label in self.all_call_graph_paths.items():
            for lable, cg_paths in cg_paths_with_label.items():
                if cg_paths:
                    for cg in cg_paths:
                        cg_path_len['all'].append(len(cg)-1) # -1 to remove the index mark
            
        value = sum(cg_path_len['all']) / len(cg_path_len['all']) if cg_path_len['all'] else 0
        cg_path_len['all_avg'] = round(value, 3) if value != 0 else 0
        append_event(CallGraphEvent(pr_nb=self.number, message=f"Call graph length information", content=json.dumps(cg_path_len)))

    def get_top_k_shortest_across_different_entries(self):
        # get top k entry for each changed private function

        # starts with the same as shortests
        self.call_graph_paths_k = copy.deepcopy(self.call_graph_paths)
        self.signatures_docstrings_k = copy.deepcopy(self.signatures_docstrings)
        self.imports_k = copy.deepcopy(self.imports)

        # check to keep only top k
        # !! refer to unchanged call_graph_paths, and update call_graph_paths_k
        for func_name, cg_path_func_level in self.call_graph_paths.items():
            if cg_path_func_level:
                all_three_types_cg_paths = [] 
                for label, cg_paths in cg_path_func_level.items():
                    if cg_paths:
                        for cg in cg_paths:
                            all_three_types_cg_paths.append(len(cg)) # all the entries for the current func_name

                if len(all_three_types_cg_paths) > Config.top_k_entries:
                    # get the shortest k accross different entry fynctions (inner layer of shortest)
                    sorted_path_len = sorted(enumerate(all_three_types_cg_paths), key=lambda x: (x[1], x[0]))
                    top_k = sorted_path_len[:Config.top_k_entries]
                    top_k_indices = [index for index, value in top_k]

                    # go throught the paths again to get the desired ones
                    for label, cg_paths in cg_path_func_level.items():
                        if cg_paths:
                            for i, cg in enumerate(cg_paths):
                                if i not in top_k_indices:
                                    sig_doc = self.signatures_docstrings[func_name][label][i]
                                    im = self.imports[func_name][label][i]
                                    # delete it from the call_graph_paths_k
                                    self.call_graph_paths_k[func_name][label].remove(cg)
                                    self.signatures_docstrings_k[func_name][label].remove(sig_doc)
                                    self.imports_k[func_name][label].remove(im)

                        # update top_k_indices: remove the idx from the current label to avoid idx out of range
                        idx_delta = len(cg_paths) 
                        top_k_indices = [(idx - idx_delta) for idx in top_k_indices if idx >= idx_delta]

    def update_class_hover_text(self):
        # for public and non-public, get the uinon of dicts
        # if two items get the same key, the later one will overwrite the former one. Here should has no duplicated keys.
        public_hover = self.public_class_hover_text_old | self.public_class_hover_text_new 
        nonpublic_hover = self.non_public_class_hover_text_old | self.non_public_class_hover_text_new

        all_path_relevant_classes = nonpublic_hover.keys()
        # update class hover text to only the related ones
        for func_name, ims in self.imports_k.items():
            common_recorded = False
            for label, import_lines in ims:
                if import_lines:
                    for imline in import_lines:
                        if common_recorded == False: # provides only the info related to both versions if possible, to avoid confusion
                            # align with the prompt info preparation part in file RegressionFinder.py. function 'generate_tests'
                            module_endswith_class = imline.split(" import ")[0].split("from ")[1]
                            if module_endswith_class in all_path_relevant_classes:
                                # self.class_hover_texts.update({module_endswith_class, self.class_hover_texts_all[module_endswith_class]})
                                self.class_hover_texts.add(nonpublic_hover[module_endswith_class])
                        
                    if label == "common":
                        common_recorded = True

        # deduplicate between all the public changed function needed classes and the path relevant classes
        self.class_hover_texts.update(public_hover.values())

    def get_call_graph_info(self, server, modified_file, function_names, version):
        append_event(Event(pr_nb=self.number, message=f"Starting to explore call graph paths, only private relevant ({version})."))

        all_explored_paths = ""
        public_apis_list = self.public_apis_old
        if version == "new":
            public_apis_list = self.public_apis_new
        
        for func_info in function_names:
            func_name, start_line_0_based, start_col_0_based, parent_class = func_info
            # try:
            func_level_call_graph_paths = []
            func_level_imports = []
            func_level_signatures = [] # element: each path with a signature

            unique_entry_funcs = set()
            queue = deque()
            # Each item: (current_func_name, file rel path, start_line, start_col, path_so_far, path_with_detials_so_far, import_line, signature_so_far)
            queue.append((func_name, modified_file.path, start_line_0_based, start_col_0_based, 
                        [func_name], [[func_name, modified_file.path, start_line_0_based, start_col_0_based]], "", ""))

            while queue:
                curr_func, curr_rel_file_path, curr_line, curr_col, path, path_detailed, ref_import, signature_docstring = queue.popleft()
                if path_detailed[0] == "loop type 2--multi-func in the loop": # normal element should be list, here whatever the string is, the type does not match
                    all_explored_paths += "Path: " + ", ".join(map(str, path_detailed)) + "\n"
                    continue

                if signature_docstring and ref_import: 
                    func_level_call_graph_paths.append(path)
                    unique_entry_funcs.add(path[0])
                    func_level_imports.append(ref_import)
                    func_level_signatures.append(signature_docstring)
                    all_explored_paths += "Path: " + ", ".join(map(str, path_detailed)) + "\n"
                    # break # this gets the only one shortest
                    continue # this ends the current path, and goes for other paths
                
                callers = server.get_function_callers(curr_rel_file_path, curr_line, curr_col)

                if not callers:
                    # No more callers, but no public function found in the path
                    path_detailed.insert(0, "no_caller_no_public")
                    all_explored_paths += "Path: " + ", ".join(map(str, path_detailed)) + "\n"
                    continue
                
                checked_parent_class = []
                parent_class = None
                # add curr info here to remove function attribute access and recursive function call
                collected_funcs = [[curr_func, curr_rel_file_path, curr_line, curr_col]] # for later deduplication
                for caller in callers:
                    with open(caller["absolutePath"], "r") as f:
                        caller_file_content = f.read()

                    check_parent_class = True
                    if parent_class in checked_parent_class:
                        check_parent_class = False
                    range_starts_at1 = range(caller["range"]["start"]["line"]+1, caller["range"]["end"]["line"]+2) # +1 to start at 1, +1 to be a right-open range
                    call_function, new_ref_import, new_signature_docstring, parent_class, module_endswith_class, class_hover_text = get_caller_function_names(
                        caller["relativePath"], caller_file_content, range_starts_at1, public_apis_list, server, check_parent_class)
                    
                    checked_parent_class.append(parent_class)
                    if class_hover_text: # class exists
                        if version == "old":
                            self.non_public_class_hover_text_old.update({module_endswith_class: class_hover_text})
                        else:
                            self.non_public_class_hover_text_new.update({module_endswith_class: class_hover_text})
                        
                        append_event(Event(pr_nb=self.number, message=f"The hover text length of class '{module_endswith_class}': {len(class_hover_text)}."))

                    if call_function: 
                        '''
                        # For looped calls, it mainly consists two types:
                         * 1. function attribute access or recursive function call, like func_a calls func_a
                         * 2. multiple functions in the loop, like func_a --> func_b --> func_c --> func_a --> ...
                        '''
                        if call_function not in collected_funcs:
                            # path level deduplication, deduplicate all the callers
                            # like Function A(range from line 100 to 140) calls func_b in line 110 and line 120, only check the callers of func A once.
                            collected_funcs.append(call_function)
                        
                            next_func, next_rel_path, next_line, next_col = call_function
                            new_path = [next_func] + path # here it starts from same function, and get a set of callers, it is ok to do deduplication.
                            new_path_detailed = []
                            new_ref_imports_to_queue = ""
                            signature_docstring_to_queue = ""
                            
                            # to handle loops, inter-path
                            if call_function in path_detailed:
                                new_path_detailed = ["loop type 2--multi-func in the loop"] + path_detailed # inifinite loop
                                # we do not check more info, like 'new_path' in the else branch, because this will be an early stop
                            else:
                                new_path_detailed = [call_function] + path_detailed
                                if new_signature_docstring: # found the public function
                                    append_event(Event(pr_nb=self.number, message=f"The hover text length of caller function '{next_func}': {len(new_signature_docstring)}."))
                                    # * From file {caller['relativePath']}:\n
                                    # new_ref_imports_to_queue = f"To access function '{next_func}': {new_ref_import}\n"
                                    # signature_docstring_to_queue = f"Signature and docstrings (if available) of function '{next_func}': {new_signature_docstring}\n"
                                    new_ref_imports_to_queue = f"To access it: {new_ref_import}\n"
                                    signature_docstring_to_queue = f"Its signature and docstrings (if available): {new_signature_docstring}\n"
                            queue.append((next_func, next_rel_path, next_line, next_col, new_path, new_path_detailed, new_ref_imports_to_queue, signature_docstring_to_queue))
                        else:
                            path_str = ", ".join(map(str,  [call_function] + path_detailed))
                            # two cases: 1. loop, 2. curr_func be called by the same caller function at different location
                            all_explored_paths += f"Path: loop type 1--function attribute access or recursive function call. Deduplicate the same caller fucntion. {path_str}" + "\n"
            
            if version == "old":
                self.call_graph_paths_old.append(func_level_call_graph_paths)
                self.signatures_docstrings_old.append(func_level_signatures)
                self.imports_old.append(func_level_imports)
            else:
                self.call_graph_paths_new.append(func_level_call_graph_paths)
                self.signatures_docstrings_new.append(func_level_signatures)
                self.imports_new.append(func_level_imports)

        append_event(CallGraphEvent(pr_nb=self.number, message=f"Done with call graph exploration, all explored paths ({version})", content=all_explored_paths))
    
    def get_test_function_code(self, cloned_repo, version):
        code_context = ""
        for modified_file in self.patch.modified_files: # does not consider the removed test files.
            if modified_file.path in self.modified_test_python_files:
                with open(f"{cloned_repo.repo.working_dir}/{modified_file.path}", "r") as f:
                    file_content = f.read()
                patch_ranges = []
                try:
                    # The PR-modified files are not always in the full diff between old and new commits, e.g.,scipy 21954
                    if version == "old":
                        patch_ranges = self.old_file_path_to_change_hunks[modified_file.path]
                    else:
                        patch_ranges = self.new_file_path_to_change_hunks[modified_file.path]
                except:
                    pass
                
                if patch_ranges:
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

# def set_to_ranges2(numbers:set):
#     # tranfer numbers to ranges, start and end line included 
#     # e.g., from {1, 2, 10, 11, 12, 13, 25} to [(1, 2), (10, 13), (25, 25)]
#     ranges = []
#     if numbers:
#         sorted_numbers = sorted(numbers)
#         start = sorted_numbers[0]

#         for i in range(1, len(sorted_numbers)):
#             if sorted_numbers[i] != sorted_numbers[i - 1] + 1: 
#                 ranges.append((start, sorted_numbers[i - 1]))
#                 start = sorted_numbers[i]

#         ranges.append((start, sorted_numbers[-1]))
#     return ranges
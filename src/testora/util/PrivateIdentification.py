import io
from os.path import join
import docker
import tarfile
import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider, ParentNodeProvider
from testora.util.ExtractCalleesInTestCode import ExtractCalleesInTestCode
from testora.util.PythonCodeUtil2 import CallerFunctionCollector, is_public


# option 1: without using lsp, but the parent class in the module is not clear/reliable so far
class RepoCallCollector(cst.CSTVisitor): 
    # to get the callees which relevant to target repo in generated test code
    METADATA_DEPENDENCIES = (PositionProvider, ParentNodeProvider)

    def __init__(self, repo_package):
        self.repo_package = repo_package
        self.imports = {}  # local alias → full import path
        self.accesses = []  # (module, name, type: 'call' or 'attr')

    def visit_Import(self, node: cst.Import):
        for alias in node.names:
            full = alias.name.value
            if full.startswith(self.repo_package):
                local = alias.asname.name.value if alias.asname else full.split(".")[-1]
                self.imports[local] = full

    def visit_ImportFrom(self, node: cst.ImportFrom):
        if node.module and node.module.value.startswith(self.repo_package):
            module = node.module.value
            for alias in node.names:
                local = alias.asname.name.value if alias.asname else alias.name.value
                self.imports[local] = f"{module}.{alias.name.value}"

    def _resolve_chain(self, node):
        """Return full dotted name for attribute chain (e.g., u.sub.helper)."""
        parts = []
        cur = node
        while isinstance(cur, cst.Attribute):
            parts.append(cur.attr.value)
            cur = cur.value
        if isinstance(cur, cst.Name):
            parts.append(cur.value)
        return list(reversed(parts))  # ['u', 'sub', 'helper']

    def visit_Call(self, node: cst.Call):
        chain = self._resolve_chain(node.func)
        if chain and chain[0] in self.imports:
            base_mod = self.imports[chain[0]]
            module = base_mod
            if len(chain) > 1:
                module = f"{base_mod}." + ".".join(chain[1:-1])
            self.accesses.append((module, chain[-1], "calls the function"))

    def visit_Attribute(self, node: cst.Attribute):
        parent = self.get_metadata(ParentNodeProvider, node)
        # if this attribute is the function being called, skip (we already handle it in visit_Call)
        if isinstance(parent, cst.Call) and parent.func is node:
            return
        
        chain = self._resolve_chain(node)
        if chain and chain[0] in self.imports:
            base_mod = self.imports[chain[0]]
            module = base_mod
            if len(chain) > 1:
                module = f"{base_mod}." + ".".join(chain[1:-1])
            self.accesses.append((module, chain[-1], "accesses the attribute"))

# option 2 : with lsp
def write_test_code_into_repo(container, test_code, file_in_container):
    container.exec_run(f"rm -rf {file_in_container}")

    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode='w') as tar:
        data = test_code.encode("utf-8")
        tarinfo = tarfile.TarInfo(name=file_in_container)
        tarinfo.size = len(data)
        tar.addfile(tarinfo, io.BytesIO(data))
    tar_stream.seek(0)
    container.put_archive("/", tar_stream.read())

def clear_test_code_in_repo(container, file_in_container):
    container.exec_run(f"rm -rf {file_in_container}")

def get_callee_function_parent_class(callee_file, check_range):
    with open(callee_file, "r", encoding="utf-8") as f:
        code = f.read()
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return None

    wrapper = MetadataWrapper(tree)

    # Collect all functions
    collector = CallerFunctionCollector() # this is used here to track callee functions, they work similar
    wrapper.visit(collector)

    parent_class = None

    # Match the function by patch range
    for func in collector.functions:
        func_node, start_line, end_line, name_start_line_0base, name_start_col_0base, parent_class = func
        if check_range.stop -1 < start_line: # if range is range(1, 6), stop is 6
            break # no matched function
            
        if set(list(range(start_line, end_line+1))).intersection(set(list(check_range))):
            return parent_class
            
    return parent_class           

def has_private_accesses_or_fails_to_parse_api_lsp(codes: list, pr):
    '''
    Make V2 totally independent from 'has_private_accesses_or_fails_to_parse' (consider as V1) in PythonCodeUtil.py, also the cst parsers
    V1 to reproduce Testora
    V2 for our approach -> identify private functions with both name convention and public API reference.
    '''

    result = []
    test_msg_pairs = []

    # 1. Get server for each version of repo to use lsp
    # old code repo
    pre_commit_cloned_repo = pr.cloned_repo_manager.get_cloned_repo(pr.pre_commit)
    pre_server = ExtractCalleesInTestCode(pre_commit_cloned_repo.repo.working_dir)

    # new code repo
    post_commit_cloned_repo = pr.cloned_repo_manager.get_cloned_repo(pr.post_commit)
    post_server = ExtractCalleesInTestCode(post_commit_cloned_repo.repo.working_dir)

    # 2. sending all test codes to repo_path in both code versions
    with open(".target_project", "r") as f:
        target_project = f.read().strip()
    
    test_file_rel_path = "DTG_test_code.py"
    test_file_path = f"home/{target_project}/{test_file_rel_path}"

    pre_container_name = pre_commit_cloned_repo.container_name
    post_container_name = post_commit_cloned_repo.container_name

    client = docker.from_env()
    pre_container = client.containers.get(pre_container_name)
    pre_container.start()
    post_container = client.containers.get(post_container_name)
    post_container.start()

    # send them before start the servers, make sure the lsp will index these test files
    for i, test in enumerate(codes):
        indexed_file_path = test_file_path.replace(".py", f"_{i}.py")
        write_test_code_into_repo(pre_container, test, indexed_file_path)
        write_test_code_into_repo(post_container, test, indexed_file_path)

    # 3. start to check the test codes
    with pre_server.lsp.start_server():
        with post_server.lsp.start_server():
            # the lsp will incrementally check the newly added test code file
            for i, test in enumerate(codes):
                indexed_file_path = test_file_rel_path.replace(".py", f"_{i}.py")
                has, static_error_msg = private_identification_helper(test, pre_server, post_server, indexed_file_path, pr.public_apis_union)
                if has == False:
                    result.append(test)
                else:
                    if static_error_msg:
                        test_msg_pairs.append([i, test, static_error_msg])
                
                # to remove the corresponding test code in repos
                indexed_file_path = test_file_path.replace(".py", f"_{i}.py")
                clear_test_code_in_repo(pre_container, indexed_file_path)
                clear_test_code_in_repo(post_container, indexed_file_path)

    return result, test_msg_pairs

def private_identification_helper(code, pre_server, post_server, test_file_rel_path, public_apis_union):
    has_error = False
    static_error_msg = None
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError as e:
        static_error_msg = f"The code snippet could not be parsed. Error message: {e}"
        return True, static_error_msg

    pre_callees = pre_server.get_callee_definitions(test_file_rel_path, tree)
    post_callees = post_server.get_callee_definitions(test_file_rel_path, tree)
    # callees = pre_callees + post_callees 
    # if a call in a single version or both verson is private, consider with error message
    private_callees_old = check_callees(pre_callees, pre_server.repo_path, public_apis_union)
    private_callees_new = check_callees(post_callees, post_server.repo_path, public_apis_union)
    private_callees = list(set(private_callees_old + private_callees_new))
    
    if private_callees:
        has_error = True 
        private_callees_str = ", ".join(private_callees)
        static_error_msg = f"The code snippet accesses the following function(s)/attribute(s), which is not part of the public API: {private_callees_str}."

    return has_error, static_error_msg

def check_callees(callees, container_repo_path, public_apis_union):
    private_callees = [] # to mention all called private functions

    for callee in callees: # includes callee functions and attributes
        if not callee["callee_name"].startswith("_"): # may be public
            range_starts_at1 = range(callee["line"]+1, callee["line"]+2) # +1 to start at 1, +1 to be a right-open range
            module = callee["relative"].replace("src/", "", 1).replace(".py", "").replace("/", ".")
            parent_class = get_callee_function_parent_class(join(container_repo_path, callee["relative"]), range_starts_at1)
            if is_public(None, None, module, parent_class, callee["callee_name"], public_apis_union, None, return_bool=True) == False: 
                # private function and protected attribution = not in api list + startswith "_"
                private_callees.append(callee)
                    
                    # return True, static_error_msg # if there is one private function, does not goes for checking other callees.
    return private_callees # to mention all called private functions
            # else: # not in the public api list, but also not startswith "_" --> consider as public
        # else: # consider as private
import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider
from libcst._maybe_sentinel import MaybeSentinel


class FunctionCollector(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self):
        self.functions = []
        # self.class_stack = []

    # for pyan to mapping the nodes
    # def visit_ClassDef(self, node: cst.ClassDef):
    #     self.class_stack.append(node.name.value)

    # def leave_ClassDef(self, node: cst.ClassDef):
    #     # TODO remove class name when decided
    #     self.class_stack.pop()

    def visit_FunctionDef(self, node: cst.FunctionDef):
        # position of the entire 'def ...' statement (starts at 'def')
        full_pos = self.get_metadata(PositionProvider, node)

        # position of the function *name* (starts at 'foo')
        name_pos = self.get_metadata(PositionProvider, node.name)
        # parent_class = self.class_stack[-1] if self.class_stack else None
        self.functions.append((
            node,
            full_pos.start.line,
            full_pos.end.line,
            name_pos.start.line-1,      # <-- use this for LSP refs/defs
            name_pos.start.column,    # <-- use this for LSP refs/defs
            # parent_class
        ))

class TestFunctionCollector(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self):
        self.functions = []
        self.imports = []

    def visit_FunctionDef(self, node: cst.FunctionDef):
        pos = self.get_metadata(PositionProvider, node)
        self.functions.append((node, pos.start.line, pos.end.line))

    def visit_Import(self, node: cst.Import):
        self.imports.append(cst.Module([]).code_for_node(node))

    def visit_ImportFrom(self, node: cst.ImportFrom):
        self.imports.append(cst.Module([]).code_for_node(node))


'''
The following functions are some different versions of file analyis to return various information
All functions return 3 values.
'''

def get_function_names(code: str, patch_ranges: list):
    '''Return modified function names.'''
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return None, None, None

    wrapper = MetadataWrapper(tree)

    # Collect all functions
    collector = FunctionCollector()
    wrapper.visit(collector)

    # Match the function by patch range
    matched_functions = set() 
    for patch_range in patch_ranges:
        target_line = (patch_range[0] + patch_range[1]) / 2

        for func in collector.functions:
            func_node, start_line, end_line, name_start_line_0base, name_start_col_0base = func
            # the start and end lines are both included, and start at 1.
            if start_line <= target_line <= end_line:
                matched_functions.add(func_node.name.value) # Consider multiple functions involved in a single range

    return list(matched_functions), None, None

def get_function_names_code(code: str, patch_ranges: list):
    ''' Retrun modified function names, and the code of the functions.'''
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return None, None, None

    wrapper = MetadataWrapper(tree)
    collector = FunctionCollector()
    wrapper.visit(collector)

    matched_functions = set() # function names
    matched_functions_code = set()
    for patch_range in patch_ranges:
        target_line = (patch_range[0] + patch_range[1]) / 2

        for func in collector.functions:
            func_node, start_line, end_line, name_start_line_0base, name_start_col_0base = func
            # the start and end lines are both included, and start at 1.
            if start_line <= target_line <= end_line:
                matched_functions.add(func_node.name.value) 
                module_with_node = cst.Module(body=[func_node])
                function_code = module_with_node.code
                matched_functions_code.add(function_code)

    return list(matched_functions), list(matched_functions_code), None

def get_caller_function_names(code: str, check_range):
    '''
    Return caller function names and its location.
    Optionally, also return the definition or the function body of the caller function
    '''
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return None, None, None

    wrapper = MetadataWrapper(tree)

    # Collect all functions
    collector = FunctionCollector()
    wrapper.visit(collector)

    # Match the function by patch range
    call_function = []
    caller_func_info = None
    target_line = (check_range[0] + check_range[1]) / 2 + 1 # +1 to let it start at 1

    for func in collector.functions:
        func_node, start_line, end_line, name_start_line_0base, name_start_col_0base = func
        # the start and end lines are both included, and start at 1.
        if start_line <= target_line <= end_line:
            call_function_name = func_node.name.value
            call_function = [call_function_name, name_start_line_0base, name_start_col_0base] # languge server is 0-based

            # # option 1: return entire function code
            # module_with_node = cst.Module(body=[func_node])
            # caller_func_info = module_with_node.code

            # # option 2: return the signature
            signature = get_function_signature(func_node)

            # Get docstring if it exists
            docstring = None
            if func_node.body.body:
                first_stmt = func_node.body.body[0]
                if (
                    isinstance(first_stmt, cst.SimpleStatementLine) and
                    first_stmt.body and
                    isinstance(first_stmt.body[0], cst.SimpleString)
                ):
                    docstring = first_stmt.body[0].value  # This includes the quotes
            
            caller_func_info = f"{signature}\n"
            if docstring:
                caller_func_info += f"{docstring}\n"

    return call_function, caller_func_info

def get_function_signature(node: cst.FunctionDef) -> str:
    """Safely extract a readable function signature from a FunctionDef node."""
    params = node.params
    parts = []

    def format_param(param: cst.Param) -> str:
        name = param.name.value if param.name else ""
        annotation = (
            f": {param.annotation.annotation.value}" if param.annotation else ""
        )
        default = f"={param.default.value}" if param.default else ""
        return f"{name}{annotation}{default}"

    # positional-only + normal params
    for p in params.posonly_params + params.params:
        parts.append(format_param(p))

    # *args / bare *
    if isinstance(params.star_arg, cst.Param):
        if params.star_arg.name is not None:
            parts.append(f"*{format_param(params.star_arg)}")
        else:
            parts.append("*")

    # keyword-only params
    for p in params.kwonly_params:
        parts.append(format_param(p))

    # **kwargs
    if isinstance(params.star_kwarg, cst.Param):
        parts.append(f"**{format_param(params.star_kwarg)}")

    signature = ", ".join(parts)
    returns = node.returns.annotation.value if node.returns else ""
    if returns:
        return f"{node.name.value}({signature}) -> {returns}"
    else:
        return f"{node.name.value}({signature})"

def get_test_function_names_code_imports(code: str, patch_ranges: list):
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return None, None, None

    wrapper = MetadataWrapper(tree)
    collector = TestFunctionCollector()
    wrapper.visit(collector)

    matched_functions_code = set()
    for patch_range in patch_ranges:
        target_line = (patch_range[0] + patch_range[1]) / 2

        for func in collector.functions:
            func_node, start_line, end_line = func
            # the start and end lines are both included, and start at 1.
            if start_line <= target_line <= end_line:
                module_with_node = cst.Module(body=[func_node])
                function_code = module_with_node.code
                matched_functions_code.add(function_code)

    return list(matched_functions_code), collector.imports # test functions

def get_function_names_code_with_line_num(code: str, patch_ranges: list):
    ''' Retrun modified function names, and the code of the functions (with marked line numbers).'''
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return None, None, None

    wrapper = MetadataWrapper(tree)
    collector = FunctionCollector()
    wrapper.visit(collector)

    matched_functions = set() # function names
    matched_functions_code = set()
    for patch_range in patch_ranges:
        target_line = (patch_range[0] + patch_range[1]) / 2

        for func in collector.functions:
            func_node, start_line, end_line, name_start_line_0base, name_start_col_0base = func
            # the start and end lines are both included, and start at 1.
            if start_line <= target_line <= end_line:
                matched_functions.add(func_node.name.value)
                module_with_node = cst.Module(body=[func_node])
                function_code = module_with_node.code
                numbered_lines = [f"<{start_line + i}> {line}" for i, line in enumerate(function_code.splitlines())]
                function_code_with_line_numbers = "\n".join(numbered_lines)
                matched_functions_code.add(function_code_with_line_numbers)

    return list(matched_functions), list(matched_functions_code), None

def get_function_names_code_to_with_mark(code: str, patch_ranges: list):
    ''' 
    Retrun modified function names, the code of the functions, 
    and a line marked version of code (will be used to add the to_cover mark)
    '''
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return None, None, None

    wrapper = MetadataWrapper(tree)
    collector = FunctionCollector()
    wrapper.visit(collector)

    matched_functions = set() # function names

    # the to_cover information represents future knowledge that isn't available during the initial test generation.
    # So, we can't provide the marked code at this stage. 
    # Instead, we add the marks during the feedback loop as part of creating prompt.
    matched_functions_code = set() # used in initial test generation
    matched_function_code_with_line_num = set() # used to mark to_cover lines in the feedback loop
    for patch_range in patch_ranges:
        target_line = (patch_range[0] + patch_range[1]) / 2

        for func in collector.functions:
            func_node, start_line, end_line, name_start_line_0base, name_start_col_0base = func
            # the start and end lines are both included, and start at 1.
            if start_line <= target_line <= end_line:
                # # option 1: origianl testora
                # matched_functions.add(func_node.name.value)

                # # option 2: matching with call gragh tools
                # matched_functions.add(f"{class_name}.{func_node.name.value}")

                # option 3: language server
                matched_functions.add((func_node.name.value, name_start_line_0base, name_start_col_0base)) # languge server is 0-based

                module_with_node = cst.Module(body=[func_node])
                function_code = module_with_node.code
                matched_functions_code.add(function_code)
                numbered_lines = [f"<{start_line + i}> {line}" for i, line in enumerate(function_code.splitlines())]
                function_code_with_line_numbers = "\n".join(numbered_lines)
                matched_function_code_with_line_num.add(function_code_with_line_numbers)

    return list(matched_functions), list(matched_functions_code), list(matched_function_code_with_line_num)

def mark_to_cover_code_stmt(uncovered_info:list, file_path_to_code:dict): # list of dicts
    # mark all uncovered statements in the code, i.e., multiple uncovered info integrate into one code
    code_with_to_cover_mark = ""

    overall_uncovered = {}
    # unify all uncovered num for each file, now it is uncovered info from multiple pre_tests
    for uncovered_from_pre_single_test in uncovered_info:
        for file_path, uncovered_stmt_nums in uncovered_from_pre_single_test.items():
            try:
                overall_uncovered[file_path] = overall_uncovered[file_path].union(uncovered_stmt_nums)
            except:
                overall_uncovered.update({file_path: uncovered_stmt_nums})

    # mark the code lines
    # for uncovered_from_pre_all_test in overall_uncovered:
    for file_path, uncovered_stmt_nums in overall_uncovered.items():
        code_list = file_path_to_code[file_path]
        code_block = []
        for code in code_list:
            for code_line in code.splitlines(): # every code line starts with its line number
                num_mark, ori_line = code_line.split("> ", 1)
                if int(num_mark.replace("<", "")) in uncovered_stmt_nums:
                    # add a comment before the line/statement, keeps the structure clean, especially if lines are long or broken.
                    # Avoids accidental confusion with syntax in case trailing comments might affect parsing or execution.
                    code_block.append(f"# TO_COVER\n{ori_line}")
                else:
                    code_block.append(ori_line)

            code_with_to_cover_mark += f"The following are the affected functions from file <{file_path}>:\n"
            code_with_to_cover_mark += "\n".join(code_block)
            code_with_to_cover_mark += "\n"
                
    return code_with_to_cover_mark, overall_uncovered

def mark_code_stmt(covered_info:dict, union_uncovered_info:dict, file_path_to_code:dict): 
    code_with_mark = ""

    for file_path, uncovered_stmt_nums in union_uncovered_info.items():
        covered_stmt_set = covered_info[file_path] 
        still_uncovered_stmt_nums = uncovered_stmt_nums - covered_stmt_set
        code_list = file_path_to_code[file_path]
        code_block = []
        for code in code_list:
            for code_line in code.splitlines(): # every code line starts with its line number
                num_mark, ori_line = code_line.split("> ", 1)
                if int(num_mark.replace("<", "")) in still_uncovered_stmt_nums:
                    # add a comment before the line/statement, keeps the structure clean, especially if lines are long or broken.
                    # Avoids accidental confusion with syntax in case trailing comments might affect parsing or execution.
                    code_block.append(f"{ori_line} # TO_COVER")
                elif int(num_mark.replace("<", "")) in covered_stmt_set:
                    code_block.append(f"{ori_line} # COVERED")
                else:
                    code_block.append(ori_line)

            code_with_mark += f"The following are the affected functions from file <{file_path}>:\n"
            code_with_mark += "\n".join(code_block)
            code_with_mark += "\n"
                
    return code_with_mark


# --- Example, for test ---
if __name__ == "__main__":
    sample_code = '''\
def foo():
    """This is a
    multi-line
    docstring"""

    # to get the sum of two values
    x = 3 
    y = get_y(x) # this is a comment
    
    return x + y

def bar():
    # this is an empty function 
    pass'''

    patch_ranges = [(3, 3), (7, 8), (13, 13)]
    function_names = None
    functions_code = None
    functions_code_with_line_num = None

    # 1, original Testora (only diff, no contexts)
    context_version = 2 # change as needed
    if context_version == 1:
        function_names, functions_code, __ = get_function_names(sample_code, patch_ranges)
    elif context_version in [2, 3]:
        function_names, functions_code, __ = get_function_names_code(sample_code, patch_ranges)
    elif context_version == 4:
        function_names, functions_code, __ = get_function_names_code_with_line_num(sample_code, patch_ranges)
    elif context_version == 5:
        function_names, functions_code, functions_code_with_line_num = \
            get_function_names_code_to_with_mark(sample_code, patch_ranges)

    print(function_names)
    print(functions_code)
    print(functions_code_with_line_num)

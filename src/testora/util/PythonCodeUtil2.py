import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider


class FunctionCollector(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self):
        self.functions = []
        self.class_stack = []

    def visit_ClassDef(self, node: cst.ClassDef):
        class_name_pos = self.get_metadata(PositionProvider, node.name)
        self.class_stack.append((node.name.value, class_name_pos.start.line-1, class_name_pos.start.column))

    def leave_ClassDef(self, node: cst.ClassDef):
        self.class_stack.pop()

    def visit_FunctionDef(self, node: cst.FunctionDef):
        # position of the entire 'def ...' statement (starts at 'def')
        full_pos = self.get_metadata(PositionProvider, node)

        deco_start_line = None
        # If decorators exist, adjust start line/column to include them
        if node.decorators:
            first_decorator = node.decorators[0]
            deco_pos = self.get_metadata(PositionProvider, first_decorator)
            # Replace start of function with start of first decorator
            deco_start_line = deco_pos.start.line

        # position of the function *name* (starts at 'foo')
        name_pos = self.get_metadata(PositionProvider, node.name)
        parent_class = self.class_stack[-1] if self.class_stack else None
        self.functions.append((
            node,
            deco_start_line,
            full_pos.start.line,
            full_pos.end.line,
            name_pos.start.line-1,      # <-- use this for LSP refs/defs
            name_pos.start.column,    # <-- use this for LSP refs/defs
            parent_class
        ))


class CallerFunctionCollector(cst.CSTVisitor):
    # get function nodes and import lines
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self):
        self.functions = []
        self.class_stack = []
    
    def visit_ClassDef(self, node: cst.ClassDef):
        class_name_pos = self.get_metadata(PositionProvider, node.name)
        self.class_stack.append((node.name.value, class_name_pos.start.line-1, class_name_pos.start.column))

    def leave_ClassDef(self, node: cst.ClassDef):
        self.class_stack.pop()

    def visit_FunctionDef(self, node: cst.FunctionDef):
        # the same with FunctionCollector
        full_pos = self.get_metadata(PositionProvider, node)

        name_pos = self.get_metadata(PositionProvider, node.name)
        parent_class = self.class_stack[-1] if self.class_stack else None
        self.functions.append((
            node,
            full_pos.start.line,
            full_pos.end.line,
            name_pos.start.line-1,      # <-- use this for LSP refs/defs
            name_pos.start.column,    # <-- use this for LSP refs/defs
            parent_class
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
            func_node, deco_start_line, start_line, end_line, name_start_line_0base, name_start_col_0base, parent_class = func
            if target_line < start_line:
                break # no matched function
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
        for func in collector.functions:
            func_node, deco_start_line, start_line, end_line, name_start_line_0base, name_start_col_0base, parent_class = func
            start_to_compare = deco_start_line if deco_start_line else start_line
            if patch_range.stop -1 < start_to_compare: # if range is range(1, 6), stop is 6
                break # no matched function
            
            if set(list(range(start_to_compare, end_line+1))).intersection(set(list(patch_range))):
                # current function has overlaps with the modified lines
                # the start and end lines are both included, and start at 1.
                matched_functions.add(func_node.name.value) 
                module_with_node = cst.Module(body=[func_node])
                function_code = module_with_node.code
                matched_functions_code.add(function_code)

    return list(matched_functions), list(matched_functions_code), None

def get_caller_function_names(relativePath: str, code: str, check_range, public_apis_list, server, check_parent_class):
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
    collector = CallerFunctionCollector()
    wrapper.visit(collector)

    # Match the function by patch range
    call_function = []
    import_line = None
    signature_docstring = None
    parent_class = None
    class_hover_text = None

    for func in collector.functions:
        func_node, start_line, end_line, name_start_line_0base, name_start_col_0base, parent_class = func
        if check_range.stop -1 < start_line: # if range is range(1, 6), stop is 6
            break # no matched function
            
        if set(list(range(start_line, end_line+1))).intersection(set(list(check_range))):
            # current function has overlaps with the modified lines
            # the start and end lines are both included, and start at 1.
            call_function_name = func_node.name.value
            call_function = [call_function_name, name_start_line_0base, name_start_col_0base] # languge server is 0-based

            # # option 1: return entire function code
            # module_with_node = cst.Module(body=[func_node])
            # caller_func_info = "\n".join(collector.imports) + "\n" + module_with_node.code

            # # option 2: return the signature
            current_module = relativePath.lstrip("src/").replace(".py", "").replace("/", ".")
            import_line, __, class_hover_text = is_public(server, relativePath, current_module, parent_class, call_function_name, public_apis_list, check_parent_class)
            if import_line:
                # option 1: using cst to get signature and docstrings
                # signature = get_function_signature(func_node)
                # signature_docstring = f"{signature}"

                # option 2: get hover text with lsp
                signature_docstring_tmp = server.get_hover_text(relativePath, name_start_line_0base, name_start_col_0base)
                '''
                format of signature_docstring_tmp:
                    python code block wrapped signature:
                        ```python
                        <signature>
                        ```
                    hovered docsting (not exactly the same as the docstring in functions)
                '''
                # TODO take care of the length
                signature_docstring = signature_docstring_tmp.replace("```python\n", "", 1).replace("```\n", "", 1)

            break
    return call_function, import_line, signature_docstring, parent_class, class_hover_text

def is_public(server, file_path, module, parent_class, func_name, public_apis_list, check_parent_class, return_bool=False) -> str:
    # if the function is public, return its import line, if not, return "".
    import_line = ""
    class_hover_text_to_return = ""

    module_candi = f"{module}.{func_name}"

    parent_class_name = None
    class_name_start_line_0base = None
    class_name_start_col_0base = None
    if parent_class:
        parent_class_name, class_name_start_line_0base, class_name_start_col_0base = parent_class
        module = f"{module}.{parent_class_name}" # accurate module
        if func_name.startswith("__"): # special methods
            module_candi = module
        else:
            module_candi = f"{module}.{func_name}"

    if return_bool == True:
        if module_candi in public_apis_list: 
            return True
        else:
            return False
        
    if module_candi in public_apis_list: 
        if parent_class_name:
            if func_name.startswith("__"):
                if func_name == "__init__": # here the parent class should absolutely exist
                    import_line = f"from {module} import {parent_class_name}" # import the class
                    import_line += f"\nRefer to the above given '__init__' function of class '{parent_class_name}' to initialize it.\n"
                    # class_hover_text_to_return = parent_class
                else: # other special methods
                    import_line = f"from {module} import {parent_class_name}" # import the class
                    import_line += (f"\nMethod '{func_name}' is a special method of class '{module}'. Its behavior follows Python’s data model.\n"
                            f"To use this special method, write code that triggers it naturally, "
                            f"e.g., for the '__add__' method, writing 'a + b' will automatically call '__add__'.\n")

            else: # normal function from a class
                import_line = f"from {module} import {func_name}"
                if check_parent_class == True:
                    class_hover_text_tmp = server.get_hover_text(file_path, class_name_start_line_0base, class_name_start_col_0base)
                    class_hover_text = class_hover_text_tmp.replace("```python\n", "", 1).replace("```\n", "", 1)
                    class_hover_text_to_return = f"For class '{module}'\n{class_hover_text}:\n"
        else:
            import_line = f"from {module} import {func_name}" # import the function
        
    return import_line, module, class_hover_text_to_return

def get_function_signature(node: cst.FunctionDef) -> str:
    """
    Extract a reliable, fully formatted function signature from a FunctionDef node.
    Works for nodes parsed via libcst.parse_module().
    """
    params = node.params
    parts = []

    module = cst.Module(body=[node])

    def format_param(param: cst.Param) -> str:
        # The CST node retains full syntax, including annotations/defaults
        return module.code_for_node(param).strip()

    # Positional-only + regular params
    for p in params.posonly_params + params.params:
        parts.append(format_param(p))

    # *args or bare *
    if params.star_arg:
        if isinstance(params.star_arg, cst.Param):
            parts.append(f"*{format_param(params.star_arg)}")
        else:
            parts.append("*,")

    # Keyword-only params
    for p in params.kwonly_params:
        parts.append(format_param(p))

    # **kwargs
    if isinstance(params.star_kwarg, cst.Param):
        parts.append(f"**{format_param(params.star_kwarg)}")

    signature = " ".join(parts)

    # Return annotation
    returns = ""
    if node.returns:
        returns = f" -> {module.code_for_node(node.returns.annotation).strip()}"

    return f"{node.name.value}({signature}){returns}"

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
        for func in collector.functions:
            func_node, start_line, end_line = func
            if patch_range.stop -1 < start_line: # if range is range(1, 6), stop is 6
                break # no matched function
            
            if set(list(range(start_line, end_line+1))).intersection(set(list(patch_range))):
                # the start and end lines are both included, and start at 1.
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
        for func in collector.functions:
            func_node, deco_start_line, start_line, end_line, name_start_line_0base, name_start_col_0base, parent_class = func
            start_to_compare = deco_start_line if deco_start_line else start_line
            if patch_range.stop -1 < start_to_compare: # if range is range(1, 6), stop is 6
                break # no matched function
            
            if set(list(range(start_to_compare, end_line+1))).intersection(set(list(patch_range))):
                matched_functions.add(func_node.name.value)
                module_with_node = cst.Module(body=[func_node])
                function_code = module_with_node.code
                numbered_lines = [f"<{start_to_compare + i}> {line}" for i, line in enumerate(function_code.splitlines())]
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
        for func in collector.functions:
            func_node, deco_start_line, start_line, end_line, name_start_line_0base, name_start_col_0base, parent_class = func
            start_to_compare = deco_start_line if deco_start_line else start_line
            if patch_range.stop -1 < start_to_compare: # if range is range(1, 6), stop is 6
                break # no matched function
            
            if set(list(range(start_to_compare, end_line+1))).intersection(set(list(patch_range))):
                # # option 1: origianl testora
                # matched_functions.add(func_node.name.value)

                # # option 2: matching with call graph tools
                # matched_functions.add(f"{class_name}.{func_node.name.value}")

                # option 3: language server
                matched_functions.add((func_node.name.value, name_start_line_0base, name_start_col_0base, parent_class)) # languge server is 0-based

                module_with_node = cst.Module(body=[func_node])
                function_code = module_with_node.code
                matched_functions_code.add(function_code)
                numbered_lines = [f"<{start_to_compare + i}> {line}" for i, line in enumerate(function_code.splitlines())]
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

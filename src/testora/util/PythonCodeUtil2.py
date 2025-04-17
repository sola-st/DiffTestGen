import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider


class FunctionCollector(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self):
        self.functions = []

    def visit_FunctionDef(self, node: cst.FunctionDef):
        pos = self.get_metadata(PositionProvider, node)
        self.functions.append((node, pos.start.line, pos.end.line))



'''
The following functions are some different versions of file analyis to return various information
All functions return 2 values.
'''
# TODO get a union of these functions
def get_function_names(code: str, patch_ranges: list):
    '''Return modified function names.'''
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return None

    wrapper = MetadataWrapper(tree)

    # Collect all functions
    collector = FunctionCollector()
    wrapper.visit(collector)

    # Match the function by patch range
    matched_functions = set() 
    for patch_range in patch_ranges:
        target_line = (patch_range[0] + patch_range[1]) / 2

        for func in collector.functions:
            func_node, start_line, end_line = func
            # the start and end lines are both included, and start at 1.
            if start_line <= target_line <= end_line:
                matched_functions.add(func_node.name.value) # Consider multiple functions involved in a single range

    return list(matched_functions), None

def get_function_names_code(code: str, patch_ranges: list):
    ''' Retrun modified function names, and the code of the functions.'''
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return None

    wrapper = MetadataWrapper(tree)
    collector = FunctionCollector()
    wrapper.visit(collector)

    matched_functions = set() # function names
    matched_functions_code = set()
    for patch_range in patch_ranges:
        target_line = (patch_range[0] + patch_range[1]) / 2

        for func in collector.functions:
            func_node, start_line, end_line = func
            # the start and end lines are both included, and start at 1.
            if start_line <= target_line <= end_line:
                matched_functions.add(func_node.name.value) 
                module_with_node = cst.Module(body=[func_node])
                function_code = module_with_node.code
                matched_functions_code.add(function_code)

    return list(matched_functions), list(matched_functions_code)

def get_function_names_code_with_line_num(code: str, patch_ranges: list):
    ''' Retrun modified function names, and the code of the functions (with marked line numbers).'''
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return None

    wrapper = MetadataWrapper(tree)
    collector = FunctionCollector()
    wrapper.visit(collector)

    matched_functions = set() # function names
    matched_functions_code = set()
    for patch_range in patch_ranges:
        target_line = (patch_range[0] + patch_range[1]) / 2

        for func in collector.functions:
            func_node, start_line, end_line = func
            # the start and end lines are both included, and start at 1.
            if start_line <= target_line <= end_line:
                matched_functions.add(func_node.name.value)
                module_with_node = cst.Module(body=[func_node])
                function_code = module_with_node.code
                numbered_lines = [f"<<{start_line}>> {line}" for i, line in enumerate(function_code.splitlines())]
                function_code_with_line_numbers = "\n".join(numbered_lines)
                matched_functions_code.add(function_code_with_line_numbers)

    return list(matched_functions), list(matched_functions_code)

def get_function_names_code_with_mark(code: str, patch_ranges: list):
    pass


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
    functions = None
    functions_code = None

    # 1, original Testora (only diff, no contexts)
    context_version = 1 # change as needed
    if context_version == 1:
        functions, functions_code = get_function_names(sample_code, patch_ranges)
    elif context_version in [2, 3]:
        functions, functions_code = get_function_names_code(sample_code, patch_ranges)
    elif context_version == 4:
        functions, functions_code = get_function_names_code_with_line_num(sample_code, patch_ranges)
    elif context_version == 5:
        functions, functions_code = get_function_names_code_with_mark(sample_code, patch_ranges)

    print(functions)
    print(functions_code)

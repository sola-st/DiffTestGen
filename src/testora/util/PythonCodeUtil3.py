import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider


class FunctionCollector(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self):
        self.functions = []

    def visit_FunctionDef(self, node: cst.FunctionDef):
        pos = self.get_metadata(PositionProvider, node)
        self.functions.append((node, pos.start.line, pos.end.line))


def analyze_file_and_function(code: str, patch_ranges: list):
    # Retrun modified function names, and the code of these functions.
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return None

    wrapper = MetadataWrapper(tree)

    # Collect all functions
    collector = FunctionCollector()
    wrapper.visit(collector)

    # Match the function by patch range
    matched_functions = set() # function names
    matched_functions_code = set()
    for patch_range in patch_ranges:
        target_line = (patch_range[0] + patch_range[1]) / 2

        for func in collector.functions:
            func_node, start_line, end_line = func
            # the start and end lines are both included, and start at 1.
            if start_line <= target_line <= end_line:
                matched_functions.add(func_node.name.value) # Consider multiple functions involved in a single range
                module_with_node = cst.Module(body=[func_node])
                function_code = module_with_node.code
                matched_functions_code.add(function_code)

    # Return 
    return list(matched_functions), list(matched_functions_code)


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
    functions, func_code = analyze_file_and_function(sample_code, patch_ranges)
    print(functions)
    print(func_code)

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider


class FunctionCollector(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self):
        self.functions = []

    def visit_FunctionDef(self, node: cst.FunctionDef):
        pos = self.get_metadata(PositionProvider, node)
        self.functions.append((node.name.value, pos.start.line, pos.end.line))


class FileNonExecutableLineFinder(cst.CSTVisitor):
    # File-wide non-executable line finder
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self):
        self.non_exec_lines = set()

    def visit_EmptyLine(self, node: cst.EmptyLine):
        pos = self.get_metadata(PositionProvider, node)
        self.non_exec_lines.add(pos.start.line)

    def visit_SimpleStatementLine(self, node: cst.SimpleStatementLine):
        # Check for docstrings
        if isinstance(node.body[0], cst.Expr) and isinstance(node.body[0].value, cst.SimpleString):
            pos = self.get_metadata(PositionProvider, node)
            for line in range(pos.start.line, pos.end.line + 1):
                self.non_exec_lines.add(line)


def analyze_file_and_function(code: str, patch_ranges: list):
    # Retrun non_exec_lines and modified function names.
    try:
        tree = cst.parse_module(code)
    except cst.ParserSyntaxError:
        return None

    wrapper = MetadataWrapper(tree)

    # 1. Collect all functions
    collector = FunctionCollector()
    wrapper.visit(collector)

    # 2. Collect non-executable lines for entire file
    file_line_finder = FileNonExecutableLineFinder()
    wrapper.visit(file_line_finder)

    # 3. Match the function by patch range
    matched_functions = set() 
    for patch_range in patch_ranges:
        target_line = (patch_range[0] + patch_range[1]) / 2

        for func in collector.functions:
            func_name, start_line, end_line = func
            # the start and end lines are both included, and start at 1.
            if start_line <= target_line <= end_line:
                matched_functions.add(func) # Consider multiple functions involved in a single range

    # 4. Return 
    return set(sorted(file_line_finder.non_exec_lines)), list(matched_functions)


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
    non_exec_lines, functions = analyze_file_and_function(sample_code, patch_ranges)
    print(non_exec_lines)
    print(functions)

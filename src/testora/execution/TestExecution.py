from dataclasses import dataclass
from typing import Optional


@dataclass
class TestExecution:
    code: str
    output: Optional[str] = None
    coverage_report: Optional[str] = None
    coverage_percentage: Optional[str] = None
    # line number ranges
    all_executable_modified_stmt_ranges: Optional[list] = None # list of ranges
    all_covered_exec_modified_stmt_ranges: Optional[list] = None
    all_uncovered_exec_modified_stmt_ranges: Optional[dict] = None # file_path: uncovered ranges
    # line number sets
    all_executable_modified_stmts_num: Optional[set] = None # list of ranges
    all_covered_exec_modified_stms_num: Optional[set] = None
    all_uncovered_exec_modified_stmts_num: Optional[dict] = None # file_path: uncovered statement numbers


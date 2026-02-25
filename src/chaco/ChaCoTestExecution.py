from dataclasses import dataclass
from typing import Optional


@dataclass
class ChaCoTestExecution:
    code: str
    output: Optional[str] = None # to summarize the number of failed and passed tests, and records which tests are failed
    raw_output: Optional[str] = None
    # coverage_report: Optional[str] = None
    coverage_percentage: Optional[str] = None
    # 'all_' in the following means cross all the targeted files in the execution.
    # line number ranges
    all_executable_modified_stmt_ranges: Optional[dict] = None # list of ranges
    all_covered_exec_modified_stmt_ranges: Optional[dict] = None
    all_uncovered_exec_modified_stmt_ranges: Optional[dict] = None # file_path: uncovered ranges
    # line number sets
    all_executable_modified_stmts_num: Optional[dict] = None 
    all_covered_exec_modified_stms_num: Optional[dict] = None
    all_uncovered_exec_modified_stmts_num: Optional[dict] = None # file_path: a set of uncovered statement numbers


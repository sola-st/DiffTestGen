from dataclasses import dataclass
from typing import Optional


@dataclass
class TestExecution:
    code: str
    output: Optional[str] = None
    coverage_report: Optional[str] = None
    coverage_percentage: Optional[str] = None
    all_executable_modified_stmt_ranges: Optional[list] = None # list of ranges
    all_covered_exec_modified_stmt_ranges: Optional[list] = None
    all_uncovered_exec_modified_stmt_ranges: Optional[list] = None


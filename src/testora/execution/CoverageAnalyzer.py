from dataclasses import dataclass

import coverage


@dataclass
class DiffCoverage:
    percentage_covered: float
    total_exec_modified_lines: int
    total_covered_exec_modified_lines: int

    def __str__(self):
        return f"Coverage: {self.percentage_covered:.2%} ({self.total_covered_exec_modified_lines}/{self.total_exec_modified_lines})"

def summarize_coverage(pr, test_execution, is_old_version):
    # get coverage data
    tmp_coverage_file = "coverage_report"
    with open(tmp_coverage_file, "wb") as f:
        f.write(test_execution.coverage_report)
    cov = coverage.Coverage(tmp_coverage_file)
    cov.load()

    # adapt file paths from the container's file system
    project_name = pr.cloned_repo_manager.repo_name
    file_prefix = f"/home/{project_name}/"

    # check coverage for modified files
    # focus on the numbers of lines
    total_exec_modified_lines = 0
    total_covered_exec_modified_lines = 0
    # focus on the details lines, specifically which lines are uncovered
    all_exec_modified_lines = set()
    all_covered_exec_modified_lines = set()
    
    target_files = pr.non_test_modified_python_files
    for target_file in target_files:
        analysis = cov.analysis2(f"{file_prefix}{target_file}")
        # excluded_lines means the lines that were specified to be excluded. 
        # uncovered_lines: [30, 31], uncovered_lines_str: 30-31
        filename, executable_lines, excluded_lines, uncovered_lines, uncovered_lines_str = analysis

        # get executable modified lines
        if is_old_version:
            exec_modified_lines = pr.old_file_path_to_all_modified_lines[target_file].intersection(set(executable_lines))
        else:
            exec_modified_lines = pr.new_file_path_to_all_modified_lines[target_file].intersection(set(executable_lines))

        # get covered lines, if a line was covered, which exactly means it is coverable
        covered_lines = set(executable_lines) - set(uncovered_lines)
        if covered_lines is None:
            # happens, e.g., when generated test doesn't invoke the tested project
            covered_lines = set()

        total_exec_modified_lines += len(exec_modified_lines)
        covered_exec_modified_lines = set(exec_modified_lines) & set(covered_lines)
        total_covered_exec_modified_lines += len(covered_exec_modified_lines)

        all_exec_modified_lines = all_exec_modified_lines.union(exec_modified_lines)
        all_covered_exec_modified_lines = all_covered_exec_modified_lines.union(covered_exec_modified_lines)

    # here 0/0 counts as 100% coverage.
    percentage_covered = total_covered_exec_modified_lines / total_exec_modified_lines if total_exec_modified_lines > 0 else 1
    all_uncovered_exec_modified_lines = all_exec_modified_lines.difference(all_covered_exec_modified_lines)

    # transfer the individual line numbers to ranges
    all_covered_exec_modified_lines_in_ranges = to_ranges(all_covered_exec_modified_lines)
    all_uncovered_exec_modified_lines_ranges = to_ranges(all_uncovered_exec_modified_lines)
    return DiffCoverage(percentage_covered, total_exec_modified_lines, total_covered_exec_modified_lines), \
            all_covered_exec_modified_lines_in_ranges, all_uncovered_exec_modified_lines_ranges, all_uncovered_exec_modified_lines

def to_ranges(numbers:set):
    # tranfer numbers to ranges, 
    # e.g., from {1, 2, 10, 11, 12, 13, 25} to [range(1, 3), range(10, 14), range(25, 26)]
    ranges = []
    if numbers:
        sorted_numbers = sorted(numbers)
        start = sorted_numbers[0]

        for i in range(1, len(sorted_numbers)):
            if sorted_numbers[i] != sorted_numbers[i - 1] + 1:
                ranges.append(range(start, sorted_numbers[i - 1] + 1))
                start = sorted_numbers[i]

        ranges.append(range(start, sorted_numbers[-1] + 1))
    return ranges

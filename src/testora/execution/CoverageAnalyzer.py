import argparse
from dataclasses import dataclass
import json
import coverage


@dataclass
class DiffCoverage:
    percentage_covered: float
    total_exec_modified_lines: int
    total_covered_exec_modified_lines: int

    def __str__(self):
        return f"Coverage: {self.percentage_covered:.2%} ({self.total_covered_exec_modified_lines}/{self.total_exec_modified_lines})"

def analyze_coverage(coverage_report_file, coverage_files, version, \
            old_file_path_to_exec_modified_lines, new_file_path_to_exec_modified_lines):
    cov = coverage.Coverage(coverage_report_file) # default to be "/tmp/coverage_report"
    cov.load()
    
    # check coverage for modified files
    # 1. focus on the numbers of lines
    total_exec_modified_lines = 0
    total_covered_exec_modified_lines = 0
    # 2. focus on the details lines, specifically which lines are uncovered
    all_exec_modified_lines = set()
    all_covered_exec_modified_lines = set()
    
    for file in coverage_files:
        analysis = cov.analysis2(file)
        # excluded_lines means the lines that were specified to be excluded. 
        # uncovered_lines: [30, 31], uncovered_lines_str: 30-31
        # the executable_lines should be the same for the same file. TODO Deduplicate?
        filename, executable_lines, excluded_lines, uncovered_lines, uncovered_lines_str = analysis

        # get executable modified lines
        exec_modified_lines = None
        if version == "old":
            exec_modified_lines = old_file_path_to_exec_modified_lines[file.split("/", 3)[-1]].intersection(set(executable_lines))
        elif version == "new":
            exec_modified_lines = new_file_path_to_exec_modified_lines[file.split("/", 3)[-1]].intersection(set(executable_lines))

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
    total_exec_modified_lines_ranges, covered_modified_lines_ranges, uncovered_modified_lines_ranges = \
            set_to_ranges_in_batch([all_exec_modified_lines, all_covered_exec_modified_lines, all_uncovered_exec_modified_lines])
    
    coverage_percentage = DiffCoverage(percentage_covered, total_exec_modified_lines, total_covered_exec_modified_lines)

    json_str_to_send_out = {
        "total_exec_modified_lines_ranges": f"{total_exec_modified_lines_ranges}",
        "covered_modified_lines_ranges": f"{covered_modified_lines_ranges}",
        "uncovered_modified_lines_ranges": f"{uncovered_modified_lines_ranges}",
        "coverage_percentage": f"{coverage_percentage}"
    }

    print(json.dumps(json_str_to_send_out)) # send this out from the container

def set_to_ranges(numbers:set):
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

def range_to_set(ranges:list):
    number_list = []
    for ran in ranges:
        number_list.extend(list(ran))

    number_set = set(number_list)
    sorted_number_set = sorted(number_set)

    return sorted_number_set

def set_to_ranges_in_batch(list_of_set):
    list_of_ranges = []
    for number_set in list_of_set:
        ranges = set_to_ranges(number_set)
        list_of_ranges.append(ranges)
    return list_of_ranges

def ranges_to_set_in_batch(list_of_ranges):
    list_of_set = []
    for ranges in list_of_ranges:
        nb_set = range_to_set(ranges)
        list_of_set.append(nb_set)
    return list_of_set


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--coverage_report', required=True)
    parser.add_argument('--coverage_files', nargs='+', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--exec_modified_lines_old', type=str, required=True)
    parser.add_argument('--exec_modified_lines_new', type=str, required=True)
    args = parser.parse_args()

    old_tmp = json.loads(args.exec_modified_lines_old)
    new_tmp = json.loads(args.exec_modified_lines_new)
    old_file_path_to_exec_modified_lines = {k: set(v) if isinstance(v, list) else v for k, v in old_tmp.items()}
    new_file_path_to_exec_modified_lines = {k: set(v) if isinstance(v, list) else v for k, v in new_tmp.items()}

    analyze_coverage(args.coverage_report, args.coverage_files, args.version, \
            old_file_path_to_exec_modified_lines, new_file_path_to_exec_modified_lines)
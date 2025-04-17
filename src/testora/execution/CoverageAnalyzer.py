import argparse
from dataclasses import dataclass
import json
import coverage


@dataclass
class DiffCoverage:
    percentage_covered: float
    total_exec_modified_stmts: int
    total_covered_exec_modified_stmts: int

    def __str__(self):
        return f"Coverage: {self.percentage_covered:.2%} ({self.total_covered_exec_modified_stmts}/{self.total_exec_modified_stmts})"

def analyze_coverage(coverage_report_file, coverage_files, version, \
            old_file_path_to_exec_modified_lines, new_file_path_to_exec_modified_lines):
    cov = coverage.Coverage(coverage_report_file) # default to be "/tmp/coverage_report"
    cov.load()
    
    # check coverage for modified files
    # 1. focus on the numbers of statements
    total_exec_modified_stmts = 0
    total_covered_exec_modified_stmts = 0
    # 2. focus on the details statements, specifically which statements are uncovered
    all_exec_modified_stmts = set()
    all_covered_exec_modified_stmts = set() 
    all_uncovered_exec_modified_stmts = {} # file level uncovered statement line numbers, format -> file_path: line set
    
    for file in coverage_files:
        relative_file_path = file.split("/", 3)[-1]
        analysis = cov.analysis2(file)
        # excluded_stmts means the statements that were specified to be excluded. 
        # uncovered_stmts: [30, 31], uncovered_stmts_str: 30-31
        filename, executable_stmts, excluded_stmts, uncovered_stmts, uncovered_stmts_str = analysis # all are statements

        # get executable modified statements
        exec_modified_stmts = set()
        if version == "old":
            exec_modified_stmts = old_file_path_to_exec_modified_lines[relative_file_path].intersection(set(executable_stmts))
        elif version == "new":
            exec_modified_stmts = new_file_path_to_exec_modified_lines[relative_file_path].intersection(set(executable_stmts))

        # get covered statements, if a statement was covered, which exactly means it is coverable
        covered_stmts = set(executable_stmts) - set(uncovered_stmts)
        if covered_stmts is None:
            # happens, e.g., when generated test doesn't invoke the tested project
            covered_stmts = set()

        total_exec_modified_stmts += len(exec_modified_stmts)
        covered_exec_modified_stmts = set(exec_modified_stmts) & set(covered_stmts)
        total_covered_exec_modified_stmts += len(covered_exec_modified_stmts)

        all_exec_modified_stmts = all_exec_modified_stmts.union(exec_modified_stmts)
        all_covered_exec_modified_stmts = all_covered_exec_modified_stmts.union(covered_exec_modified_stmts)
        all_uncovered_exec_modified_stmts.update({relative_file_path: exec_modified_stmts.difference(covered_exec_modified_stmts)})

    # here 0/0 counts as 100% coverage.
    percentage_covered = total_covered_exec_modified_stmts / total_exec_modified_stmts if total_exec_modified_stmts > 0 else 1

    # transfer the individual statement numbers to ranges
    total_exec_modified_stmts_ranges, covered_modified_stmts_ranges = set_to_ranges_in_batch([all_exec_modified_stmts, all_covered_exec_modified_stmts])
    uncovered_exec_modified_stmts_ranges = {}
    for file_path, uncovered in all_uncovered_exec_modified_stmts.items():
        uncovered_ranges = set_to_ranges(uncovered)
        # update the all_uncovered_exec_modified_stmts dict to record ranges.
        uncovered_exec_modified_stmts_ranges.update({file_path: uncovered_ranges})
    
    coverage_percentage = DiffCoverage(percentage_covered, total_exec_modified_stmts, total_covered_exec_modified_stmts)

    json_str_to_send_out = {
        "total_exec_modified_stmts_ranges": f"{total_exec_modified_stmts_ranges}",
        "covered_modified_stmts_ranges": f"{covered_modified_stmts_ranges}",
        "uncovered_modified_stmts_ranges": f"{all_uncovered_exec_modified_stmts}",
        "all_executable_modified_stmts_num": f"{all_exec_modified_stmts}",
        "all_covered_exec_modified_stms_num": f"{all_covered_exec_modified_stmts}",
        "all_uncovered_exec_modified_stmts_num": f"{all_uncovered_exec_modified_stmts}",
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
    if ranges:
        number_list = []
        for ran in ranges:
            number_list.extend(list(ran))

        number_set = set(number_list)
        sorted_number_set = sorted(number_set)
        return sorted_number_set
    else:
        return []

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
    return list_of_set # it is a list of list


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
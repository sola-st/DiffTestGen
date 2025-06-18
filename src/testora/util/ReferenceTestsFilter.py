import random


def get_str_from_dict(uncover_dict:dict):
    # a util function for 'generate_replacement_tests'
    uncovered_str = ""
    for file_path, uncovered_nums in uncover_dict.items():
        if uncovered_nums:
            uncovered_str += f"{file_path}: lines {uncovered_nums}\n"

    if not uncovered_str:
        uncovered_str = "No specified lines.\n"
    return uncovered_str

def compute_line_distance(test_executions: list, files_to_union_uncovers: dict):
    # Mean Absolute Distance (MAD)
    # Lower MAD = closer current coverage to the uncovered stmts
    mad_distances = [] # each test a distance list

    files_with_uncovered = files_to_union_uncovers.keys()
    for exec in test_executions:
        covered_stmts_dict = exec.all_covered_exec_modified_stms_num
        mad_execution_level = [] # each element indicates the dist of a line
        for file, covered_nums in covered_stmts_dict.items():
            if covered_nums:
                if file in files_with_uncovered:
                    uncovered_nums = files_to_union_uncovers[file]
                    missing_in_cur_test = uncovered_nums - covered_nums
                    for b in missing_in_cur_test:
                        nearest_distance = min(abs(b - a) for a in covered_nums)
                        mad_execution_level.append(nearest_distance)
                # else: # all lines in this file are covered by this test

        mad_distances.append(mad_execution_level)

    return mad_distances # a list with each element is the mad list of the test / execution

def get_union_uncovered_stmts(test_executions: list, record_None: bool):
    union_uncovered = {}

    for i, exec in enumerate(test_executions):
        for file_path, uncovered_nums in exec.all_uncovered_exec_modified_stmts_num.items():
            if file_path in union_uncovered.keys():
                union_uncovered[file_path] = union_uncovered[file_path].union(uncovered_nums)
            else:
                if uncovered_nums and record_None == False: # if with no uncovered_nums, not record the file
                    union_uncovered.update({file_path: uncovered_nums})
                else:
                    union_uncovered.update({file_path: uncovered_nums})

    return union_uncovered

def filter_tests_by_line_distance(old_and_new_executions: dict, prompt_base: int):
    test_code_with_addi_info = ""
    union_uncovered = {}
    event_detail = ""
    old_covered_info = None # of the selected test
    new_covered_info = None

    old_executions, new_executions = old_and_new_executions.values()
    # get union uncovered stmts for the target old and new executions
    record_None = False
    if prompt_base == 5: 
        record_None = True
    old_files_to_union_uncovers_dict = get_union_uncovered_stmts(old_executions, record_None)
    new_files_to_union_uncovers_dict = get_union_uncovered_stmts(new_executions, record_None)
    
    test_num_before_filtering = len(old_executions)
    if test_num_before_filtering < 2:
        # no need to do further filterings
        for old_execution, new_execution in zip(old_executions, new_executions):
            test_code_with_addi_info = represent_info(old_execution, new_execution, \
                old_files_to_union_uncovers_dict, new_files_to_union_uncovers_dict, prompt_base)
            if prompt_base == 5:
                union_uncovered = {"old": old_files_to_union_uncovers_dict, "new": new_files_to_union_uncovers_dict}
                old_covered_info = old_execution.all_covered_exec_modified_stms_num
                new_covered_info = new_execution.all_covered_exec_modified_stms_num

        event_detail = f"No filtering. Keep all {test_num_before_filtering} tests as the reference test."
    else:
        # calculate line distance
        old_dist_lists = compute_line_distance(old_executions, old_files_to_union_uncovers_dict)
        new_dist_lists = compute_line_distance(new_executions, new_files_to_union_uncovers_dict)

        overall_dist_lists = [] # len == the number of tests/(old/new) executions
        for execution_level_dist_list, new in zip(old_dist_lists, new_dist_lists):
            execution_level_dist_list.extend(new) # extent to a long mad list
            # rank the long dist list, get the closest to any of the lines.
            if execution_level_dist_list:
                # to exclude the tests covers nothing, which has no distance.
                # related to 'if covered_nums:' in function 'compute_line_distance'.
                overall_dist_lists.append(sorted(execution_level_dist_list)) # the inner list could have different lengths
        
        # the length of the shortest exectuion level dist list represent the available max tries to get the unique closest
        max_num = min([len(dists) for dists in overall_dist_lists])
        idx = 0
        is_unique = False
        while (idx + 1 <= max_num) and (is_unique == False):
            execution_level_mins = [dists[idx] for dists in overall_dist_lists]
            overall_level_min = min(execution_level_mins)
            unique_check = [test_idx for test_idx, m in enumerate(execution_level_mins) if m == overall_level_min]
            if len(unique_check) == 1:
                is_unique = True
            idx += 1

        if is_unique == False:
            # pick the test with shortest dist list    
            # the shortor the dist list, the less lines the test missed
            pre_remains = [overall_dist_lists[test_idx] for test_idx in unique_check]
            shortest = min([len(dists) for dists in pre_remains])
            unique_check = [test_idx for test_idx, dists in enumerate(overall_dist_lists) if len(dists) == shortest]
            # here the unique_check may still have mutiple elements, but with same order and the same length, 
            # randomly pick one 
            if len(unique_check) > 1:
                random.shuffle(unique_check)

        # keep the most closest test and format a prompt string
        idx = unique_check[0]
        old_execution = old_executions[idx]
        new_execution = new_executions[idx]

        test_code_with_addi_info = represent_info(old_execution, new_execution, \
                old_files_to_union_uncovers_dict, new_files_to_union_uncovers_dict, prompt_base)
        if prompt_base == 5:
            union_uncovered = {"old": old_files_to_union_uncovers_dict, "new": new_files_to_union_uncovers_dict}
            old_covered_info = old_execution.all_covered_exec_modified_stms_num
            new_covered_info = new_execution.all_covered_exec_modified_stms_num
        
        # to record the basic info of test examples, will be used to form a ReferenceTestEvent
        event_detail = f"From {test_num_before_filtering} tests, keep the {idx}(th) (starts at 0) test as the reference test."

    return test_code_with_addi_info, event_detail, union_uncovered, old_covered_info, new_covered_info

def represent_info(old_execution, new_execution, old_files_to_union_uncovers_dict, new_files_to_union_uncovers_dict, prompt_base):
    # part 1: test code
    test_code_left, test_code_with_no_name_tmp = old_execution.code.split("# Round ", 1) # test_code_left could be reference fixed lines
    test_code_right = test_code_with_no_name_tmp.split("_diff):", 1)[1]
    test_code_with_no_example_name = test_code_left + "# " + test_code_right # from # Round 0 Example 4 (filtered_diff): ... to # ...

    if prompt_base == 4:
        # part 2: covered stmts info
        old_covered_str = get_str_from_dict(old_execution.all_covered_exec_modified_stms_num)
        new_covered_str = get_str_from_dict(new_execution.all_covered_exec_modified_stms_num)
        # part 3: union uncovered stmts info
        old_uncovered_str = get_str_from_dict(old_files_to_union_uncovers_dict)
        new_uncovered_str = get_str_from_dict(new_files_to_union_uncovers_dict)
        # the string that includes test code, covered stmts info by the selected test, and union (from all test) uncovered stmts info.
        test_code_cov_union_uncov_info = (
            f"Example:\n{test_code_with_no_example_name}\n"
            f"This example coveres the following lines:\nOld:\n{old_covered_str}New:\n{new_covered_str}\n"
            f"Lines that are expected to be covered by the newly created usage example(s):\nOld:\n{old_uncovered_str}New:\n{new_uncovered_str}"
        )
        return test_code_cov_union_uncov_info
    elif prompt_base == 5:
        test_code = f"Example:\n{test_code_with_no_example_name}\n"
        return test_code
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
    '''
    Options:
     * Top-2 closer tests (First try)
     * At most two tests for each modified main file. Up to 6 tests (at most 3 file * at most 2 test each).
     * Dynamically decide how many tests to keep
    '''
    # Mean Absolute Distance (MAD)
    # Lower MAD = closer current coverage to the uncovered stmts
    mad_distances = [] # each test a distance number

    files_with_uncovered = files_to_union_uncovers.keys()
    for exec in test_executions:
        covered_stmts_dict = exec.all_covered_exec_modified_stms_num
        mad_exec_level = 0
        for file, covered_nums in covered_stmts_dict.items():
            # TODO handle the test covers nothing
            if file in files_with_uncovered:
                uncovered_nums = files_to_union_uncovers[file]
                missing_in_cur_test = uncovered_nums - covered_nums
                dist_file_level = 0
                for b in missing_in_cur_test:
                    nearest_distance = min(abs(b - a) for a in covered_nums)
                    dist_file_level += nearest_distance
                mad_file_level = dist_file_level / len(missing_in_cur_test)
            # else: # all lines in this file are covered by this test
            mad_exec_level += mad_file_level

        mad_distances.append(mad_exec_level)

    return mad_distances # a list with each element is the mad of the test / execution

def get_union_uncovered_stmts(test_executions: list):
    union_uncovered = {}

    for i, exec in enumerate(test_executions):
        if i == 0:
            union_uncovered = exec.all_uncovered_exec_modified_stmts_num
        else:
            for file_path, uncovered_nums in exec.all_uncovered_exec_modified_stmts_num.items():
                if file_path in union_uncovered.keys():
                    union_uncovered[file_path] = union_uncovered[file_path].union(uncovered_nums)
                else:
                    union_uncovered.update({file_path: uncovered_nums})

    return union_uncovered

def filter_tests_by_line_distance(old_and_new_executions: dict, keep_at_most=2):
    test_code_and_covered_info = ""
    event_detail = ""

    old_executions, new_executions = old_and_new_executions.values()
    if len(old_executions) < 2:
        # no need to do further filterings
        for i, (old_execution, new_execution) in enumerate(zip(old_executions, new_executions)):
            info_str = represent_info(old_execution, new_execution, i)
            test_code_and_covered_info += info_str
        event_detail = f"No filtering. Keep all {len(old_executions)} tests as reference tests."
    else:
        # get union uncovered stmts for the target old and new executions
        old_files_to_union_uncovers_dict = get_union_uncovered_stmts(old_executions)
        new_files_to_union_uncovers_dict = get_union_uncovered_stmts(new_executions)

        # calculate line disntance
        old_line_distance = compute_line_distance(old_executions, old_files_to_union_uncovers_dict)
        new_line_distance = compute_line_distance(new_executions, new_files_to_union_uncovers_dict)
        overall_dist = [(old + new) for old, new in zip(old_line_distance, new_line_distance)]
        min_dist = min(overall_dist)
        all_min_indices = [i for i, dist in enumerate(overall_dist) if dist == min_dist] # could be one or more
        if len(all_min_indices) < 2:
            # get the 2nd min mad value
            updated_overall_dist = [dist for dist in enumerate(overall_dist) if dist != min_dist]
            min_dist_top2 = min(updated_overall_dist)
            all_min_indices_top2 = [i for i, dist in enumerate(overall_dist) if dist == min_dist_top2]
            all_min_indices.extend(all_min_indices_top2)

        # keep the top-2 closer tests and format a prompt string
        for i, idx in enumerate(all_min_indices):
            if i < keep_at_most: # pick the former ones in the index order
                # TODO keep the ones at least runs without error in one of the versions
                old_execution = old_executions[idx]
                new_execution = new_executions[idx]
                info_str = represent_info(old_execution, new_execution, i)
                test_code_and_covered_info += info_str

        # to record the basic info of test examples, will be used to form a ReferenceTestEvent
        event_detail = \
            f"From {len(overall_dist)} tests, get lower MAD with {len(all_min_indices)} Top-{keep_at_most} cases. Keep {max(len(all_min_indices), keep_at_most)} reference tests."

    return test_code_and_covered_info, event_detail

def represent_info(old_execution, new_execution, i):
    test_code_left, test_code_with_no_name_tmp = old_execution.code.split("# Round ", 1) # test_code_left could be reference fixed lines
    test_code_right = test_code_with_no_name_tmp.split("_diff): ", 1)[1]
    test_code_with_no_example_name = test_code_left + "# " + test_code_right # from # Round 0 Example 4 (filtered_diff): ... to # ...
    old_covered_str = get_str_from_dict(old_execution.all_covered_exec_modified_stms_num)
    new_covered_str = get_str_from_dict(new_execution.all_covered_exec_modified_stms_num)
    test_code_and_covered_info = \
        f"Example {i+1}:\n{test_code_with_no_example_name}\nThis example coveres the following lines:\nOld:\n{old_covered_str}New:\n{new_covered_str}\n"
    return test_code_and_covered_info


import argparse
import ast
import copy
import glob
import json
import re
from typing import List
from github import Github, Auth
from testora.execution.DockerExecutor import DockerExecutor
from testora.execution.ProgramMerger import merge_programs, separate_outputs
from testora.execution.TestExecution import TestExecution
from testora.llms.LLMCache import LLMCache
from testora.prompts.ParseErrorPrivateCallFixingPromptV2 import ParseErrorPrivateCallFixingPrompt
from testora.prompts.RegressionTestGeneratorPromptV1 import RegressionTestGeneratorPromptV1
from testora.prompts.RegressionTestGeneratorPromptV2 import RegressionTestGeneratorPromptV2
from testora.prompts.RegressionTestGeneratorPromptV345 import RegressionTestGeneratorPromptV345
from testora.prompts.RegressionTestGeneratorPromptV6 import RegressionTestGeneratorPromptV6
from testora.prompts.RegressionTestGeneratorPromptV7 import RegressionTestGeneratorPromptV7
from testora.prompts.FeedbackLoopPromptV1 import FeedbackTestGeneratorPromptV1
from testora.prompts.FeedbackLoopPromptV2 import FeedbackTestGeneratorPromptV2
from testora.prompts.FeedbackLoopPromptV3 import FeedbackTestGeneratorPromptV3
from testora.prompts.FeedbackLoopPromptV4 import FeedbackTestGeneratorPromptV4
from testora.prompts.FeedbackLoopPromptV5 import FeedbackTestGeneratorPromptV5
from testora.prompts.FeedbackLoopPromptV6 import FeedbackTestGeneratorPromptV6
from testora.prompts.FeedbackLoopPromptV7 import FeedbackTestGeneratorPromptV7
from testora.prompts.FeedbackLoopPromptV8 import FeedbackTestGeneratorPromptV8
from testora.prompts.RuntimeErrorsFixingPrompt import RuntimeErrorsFixingPrompt, check_whether_error_exist, extract_error_type
from testora.prompts.TestPythonBlockSeparatorPrompt import TestPythonBlockSeparatorPrompt
from testora.prompts.UndefinedRefsFixingPrompt import UndefinedRefsFixingPrompt
from testora.prompts.PRRegressionBugRanking import PRRegressionBugRanking
from testora.prompts.RegressionClassificationPromptV1 import RegressionClassificationPromptV1
from testora.prompts.RegressionClassificationPromptV2 import RegressionClassificationPromptV2
from testora.prompts.RegressionClassificationPromptV3 import RegressionClassificationPromptV3
from testora.prompts.RegressionClassificationPromptV4 import RegressionClassificationPromptV4
from testora.prompts.RegressionClassificationPromptV5 import RegressionClassificationPromptV5
from testora.prompts.RegressionClassificationPromptV6 import RegressionClassificationPromptV6
from testora.prompts.SelectExpectedBehaviorPrompt import SelectExpectedBehaviorPrompt
from testora.util.ClonedRepoManager import ClonedRepoManager
from testora.util.DocstringRetrieval import retrieve_relevant_docstrings
from testora.util.Exceptions import TestoraException
from testora.util.ExtractExistingTests import ExtractExistingTests
from testora.util.PullRequest import PullRequest
from testora.llms.OpenAIGPT import OpenAIGPT
from testora.util.Logs import (CoverageEvent, PreClassificationEvent, ReferenceTestEvent, start_logging, 
        ClassificationEvent, ErrorEvent, PREvent, SelectBehaviorEvent, TestExecutionEvent, append_event, 
        Event, ComparisonEvent, LLMEvent, get_logs_as_json, store_logs, reset_logs)
from testora.util.PythonCodeUtil import has_private_accesses_or_fails_to_parse
from testora.util.PythonCodeUtil2 import mark_code_stmt, mark_to_cover_code_stmt
from testora.util.ReferenceTestsFilter import filter_tests_by_line_distance, get_str_from_dict
from testora.util.UndefinedRefsFinder import get_undefined_references
from testora.evaluation import EvalTaskManager
from testora import Config

llm = LLMCache(OpenAIGPT())

if Config.classification_prompt_version == 1:
    RegressionClassificationPrompt = RegressionClassificationPromptV1
elif Config.classification_prompt_version == 2:
    RegressionClassificationPrompt = RegressionClassificationPromptV2
elif Config.classification_prompt_version == 3:
    RegressionClassificationPrompt = RegressionClassificationPromptV3
elif Config.classification_prompt_version == 4:
    RegressionClassificationPrompt = RegressionClassificationPromptV4
elif Config.classification_prompt_version == 5:
    RegressionClassificationPrompt = RegressionClassificationPromptV5
elif Config.classification_prompt_version == 6:
    RegressionClassificationPrompt = RegressionClassificationPromptV6

def clean_output(output):
    # remove warnings caused by coverage measurements
    cleaned_lines = []
    for line in output.split("\n"):
        if "CoverageWarning" in line:
            continue
        cleaned_lines.append(line)
    cleaned_output = "\n".join(cleaned_lines)

    # pandas-specific cleaning (to remove build output)
    result = []
    for line in cleaned_output.split("\n"):
        if line == "+ /usr/local/bin/ninja":
            continue
        # check if line starts with "[1/1]", "[2/4]", etc.
        if len(line) >= 6 and line.startswith("[") and \
                line[1].isdigit() and \
                line[2] == "/" and \
                line[3].isdigit() and \
                line[4] == "]" and \
                line[5] == " ":
            continue
        result.append(line)
    return "\n".join(result)


def merge_tests_and_execute(test_executions, docker_executor, version) -> List[str]:
    """
    Try to merge all tests into a single program (for efficiency, to avoid repeated imports and Python engine startup).
    If this fails (e.g., due to segfault of Python), execute smaller subsets of tests at once.
    In the extreme case, will try to execute each test separately.
    """

    if len(test_executions) > 20:
        # split into chunks of at most 20 test executions
        chunks = [test_executions[i:i + 20] for i in range(0, len(test_executions), 20)]
        all_outputs = []
        for chunk in chunks:
            all_outputs.extend(merge_tests_and_execute(chunk, docker_executor, version))
        return all_outputs

    merged_code = merge_programs([test.code for test in test_executions])
    append_event(ErrorEvent(pr_nb=-1, message="Merged code", details=merged_code))
    # TODO: in case we ever revive this code, use the coverage report provided here
    # TODO: H: check when this works and if the new changes makes sense.
    merged_outputs, coverage_report = docker_executor.execute_python_code(merged_code, version=version)
    append_event(ErrorEvent(pr_nb=-1, message="Merged output", details=merged_outputs))
    merged_outputs = clean_output(merged_outputs)
    outputs = separate_outputs(merged_outputs)
    if len(outputs) == len(test_executions):
        return outputs
    elif len(test_executions) == 1:
        # we can't split it any further but don't see the expected output format
        # (e.g., reaching this when code parses but raises a SyntaxError)
        return [merged_outputs]
    else:
        mid = len(test_executions) // 2
        test_executions_part1, test_executions_part2 = test_executions[:mid], test_executions[mid:]
        outputs_part1 = merge_tests_and_execute(test_executions_part1, docker_executor, version)
        outputs_part2 = merge_tests_and_execute(test_executions_part2, docker_executor, version)
        return outputs_part1 + outputs_part2


def execute_test(test_execution, docker_executor, version):
    # True -> to analyze the coverage info inside the container
    analysis = True
    if version == "main":
        analysis = False # Do not check coverage info when run tests at main. 1. in case the file does not exist in main 2. save time
    output, coverage_report = docker_executor.execute_python_code(test_execution.code, \
            analysis, version=version, test_execution=test_execution)
    output = clean_output(output)
    test_execution.output = output
    test_execution.coverage_report = coverage_report


def execute_tests_on_commit(cloned_repo_manager, pr, test_executions, commit, version):
    cloned_repo = cloned_repo_manager.get_cloned_repo(commit)
    container_name = cloned_repo.container_name
    docker_executor = DockerExecutor(pr, container_name,
            project_name=cloned_repo_manager.repo_name,
            coverage_files=pr.non_test_modified_python_files)

    append_event(
        Event(pr_nb=-1, message=f"Compiling {cloned_repo_manager.repo_name} at commit {commit} in container {container_name}"))

    # to trigger re-compilation (e.g., for pandas or scikit-learn)
    docker_executor.execute_python_code(f"import {cloned_repo_manager.module_name}")

    append_event(
        Event(pr_nb=pr.number, message=f"Done with compiling {cloned_repo_manager.repo_name} at commit {commit}"))

    try:
        if Config.use_program_merger:
            outputs = merge_tests_and_execute(test_executions, docker_executor, version)
            assert len(outputs) == len(test_executions)
            for output, test_execution in zip(outputs, test_executions):
                test_execution.output = output
                append_event(TestExecutionEvent(pr_nb=pr.number,
                                                message=f"Test execution ({version}, merge)",
                                                code=test_execution.code,
                                                output=output))
        else:
            for test_execution in test_executions:
                execute_test(test_execution, docker_executor, version)
                append_event(TestExecutionEvent(pr_nb=pr.number,
                                                message=f"Test execution ({version})",
                                                code=test_execution.code,
                                                output=test_execution.output))
    except RecursionError as e:
        raise TestoraException(f"Exception during merge_tests_and_execute: {str(e)}")


def is_crash(output):
    # TODO Reduce mis-matching.
    return "Traceback (most recent call last)" in output or \
        "error" in output.lower() or \
        "fail" in output.lower()

def de_dup_tests_with_name(tests):
    pure_test_code_list = []
    tests_dedup = []
    for test_code in tests:
        pure_test_code = test_code.split("\n", 1)[1]
        if pure_test_code not in pure_test_code_list:
            pure_test_code_list.append(pure_test_code)
            tests_dedup.append(test_code)
    return tests_dedup

def generate_tests_with_prompt(pr, prompt, model, diff_version, nb_samples=1, round=0, do_name_reformatting=True):
    raw_answer = model.query(prompt, nb_samples)
    append_event(LLMEvent(pr_nb=pr.number, message="Raw answer", content="\n---(next sample)---".join(raw_answer)))

    generated_tests = prompt.parse_answer(raw_answer)
    # Separate the examples if the model answers in a big python code block.
    if len(generated_tests) == 1:
        matches = re.findall(r'Example \d+', str(generated_tests))
        if len(matches) > 1: # multiple usage examples in one python block
            speparator_prompt = TestPythonBlockSeparatorPrompt(generated_tests[0])
            separate_raw_answer = llm.query(speparator_prompt)
            append_event(LLMEvent(pr_nb=pr.number, message="Separate raw answer", content="\n---(next sample)---".join(separate_raw_answer)))
            generated_tests = prompt.parse_answer(raw_answer)

    nb_tests_before_dedup_and_cleaning = len(generated_tests)
    if do_name_reformatting == False: # for the static error fixed tests
        # # de-dup tests, 
        # # not using static_err_fixed_tests_dedup here to avoid mismatching, 
        # # e.g., need 5 fixed but 3 after dedup, will have 2 tests left in the overall generated tests
        # # de-dup later when insert this tests back to the overall generated tests.
        static_err_fixed_tests_dedup = de_dup_tests_with_name(generated_tests)

        # clean tests, test_msg_pairs can be used to start another attmept if needed
        static_err_fixed_tests, test_msg_pairs = remove_tests_with_private_call(generated_tests)

        fixed = len(static_err_fixed_tests) - len(test_msg_pairs)
        append_event(Event(pr_nb=pr.number,
                message=f"Static error fixed {fixed}/{len(static_err_fixed_tests_dedup)} tests, ({nb_tests_before_dedup_and_cleaning} before deduplication and cleaning)"))

        return static_err_fixed_tests, test_msg_pairs # static_err_fixed_tests may duplicate
        
    # here works for generated_tests with pure generated code (e.g., generate_tests, generate_refinment_tests), 
    # also solve the example name non-consective issue.
    # deduplication and static error check first (above), then go to the test name formatting (below).
    # de-dup tests
    generated_tests = list(dict.fromkeys(generated_tests))

    # clean tests
    generated_tests, test_msg_pairs = remove_tests_with_private_call(generated_tests)

    append_event(Event(pr_nb=pr.number,
            message=f"Generated {len(generated_tests)} tests ({nb_tests_before_dedup_and_cleaning} before deduplication and cleaning)"))
    
    name_formatted_generated_tests = []
    for idx, test in enumerate(generated_tests):
        # for test:
        #  * normal: # Example 1: <code>
        #  * outliers: for projects that need further adjustments for import lines.
        #       e.g., import pandas as pd\nimport numpy as np\nimport pyarrow as pa\n\n# Example 1: <code>
        #       e.g., import pandas as pd\nimport numpy as np  # Fix: Importing numpy\n\n# Example 2: <code>
        
        # 1. modification to put all the example code (in the above formats) in the same format.
        test_lines = test.splitlines()
        for line in test_lines:
            if "# Example" in line:
                # get the newly formatted line
                test = line + "\n" + test.replace(f"{line}\n", "")
                break
        
        # 2. process to get the newly named tests
        test_name, test_code = test.split(":", 1)
        marked_name = test_name.replace("# Example", f"# Round {round} Example", 1) + f" ({diff_version}):"
        formatted_test = f"{marked_name}{test_code}"
        append_event(LLMEvent(pr_nb=pr.number, message=f"Generated test {idx+1}, round {round} ({diff_version})", content=formatted_test))
        name_formatted_generated_tests.append(formatted_test)
    return name_formatted_generated_tests, test_msg_pairs


def remove_tests_with_private_call(tests):
    result = []
    test_msg_pairs = [] # the msg could be parse error, could be private call issue
    for i, test in enumerate(tests):
        has, static_error_msg = has_private_accesses_or_fails_to_parse(test)
        if has == False:
            result.append(test)
        else:
            if static_error_msg:
                test_msg_pairs.append([i, test, static_error_msg])

    return result, test_msg_pairs


def generate_tests(pr, github_repo, changed_functions):
    # prepare context used by one or more prompts
    # full_diff is already computed (pr.full_diff) when the pull request is instantiated
    pr.get_filtered_diff() # this adds filtered_diff info to pr.filtered_diff 

    all_tests = []
    test_msg_pairs_full_diff = []
    test_msg_pairs_filtered_diff = []

    full_diff_len_fit = False
    filtered_diff_len_nonequal_fit = False

    if len(pr.full_diff.split("\n")) <= 200:
        full_diff_len_fit = True
        prompt_full_diff = None
        # full diff with GPT4
        if Config.initial_test_generation_prompt_version == 5: # TODO specific version of prompts
            prompt_full_diff = RegressionTestGeneratorPrompt(github_repo.name, changed_functions, pr.full_diff, \
                pr.old_context, pr.new_context, pr.old_test_function_code, pr.new_test_function_code)
        else: # e.g., other prompts, and testora
            prompt_full_diff = RegressionTestGeneratorPrompt(github_repo.name, changed_functions, pr.full_diff, pr.old_context, pr.new_context)
        
        generated_tests, test_msg_pairs_full_diff = generate_tests_with_prompt(pr, prompt_full_diff, llm, "full_diff")
        all_tests.extend(generated_tests)

    if len(pr.filtered_diff.split("\n")) <= 200 and pr.filtered_diff != pr.full_diff:
        filtered_diff_len_nonequal_fit = True
        prompt_filtered_diff = None
        # filtered diff with GPT4
        if Config.initial_test_generation_prompt_version == 5:
            prompt_filtered_diff = RegressionTestGeneratorPrompt(github_repo.name, changed_functions, pr.filtered_diff, \
                    pr.old_context, pr.new_context, pr.old_test_function_code, pr.new_test_function_code)
        else:
            prompt_filtered_diff = RegressionTestGeneratorPrompt(github_repo.name, changed_functions, pr.filtered_diff, pr.old_context, pr.new_context)
        
        generated_tests, test_msg_pairs_filtered_diff = generate_tests_with_prompt(pr, prompt_filtered_diff, llm, "filtered_diff")
        all_tests.extend(generated_tests)
    
    # also return the bool values to not check multiple times in the feedback rounds
    return all_tests, test_msg_pairs_full_diff, test_msg_pairs_filtered_diff, full_diff_len_fit, filtered_diff_len_nonequal_fit 


def generate_replacement_tests(pr, github_repo, changed_functions, full_diff_len_fit, filtered_diff_len_nonequal_fit,
            all_uncovered_modified_stmts_info_dict, round, all_for_further_needs:dict=None):
    '''
    Generate replacment tests for the ones that failed to reach the changed lines, 
    and keep different with the exisiting reached tests.
     * Has a similar body to function generate_test, but with different inputs and prompt class.
    ''' 

    old_context = ""
    new_context = ""
    all_uncovered_modified_stmts_info = ""

    if Config.context_version == 5:
        # process the code contexts to let code have 'to_cover' marks
        # in this case, all_uncovered_modified_stmts_info is an empty set
        old_context, overall_uncovered_old = mark_to_cover_code_stmt(all_uncovered_modified_stmts_info_dict["old"], pr.old_context_with_line_num)
        new_context, overall_uncovered_new = mark_to_cover_code_stmt(all_uncovered_modified_stmts_info_dict["new"], pr.new_context_with_line_num)
        all_uncovered_modified_stmts_info = len(all_for_further_needs["old"]) # to indicate how many tetst to generate

        details = f"All uncovered for to_cover marks: Old: {overall_uncovered_old}, New: {overall_uncovered_new}"
        append_event(CoverageEvent(pr_nb=pr.number, message=f"All uncovered, round {round}", details=f"{details}"))
    elif Config.context_version == 8:
        # Notes: 
        # 1. all_for_further_needs stores the old and new executions
        # 2. all_uncovered_modified_stmts_info:
        #       4-based: test_code_and_covered_info + union_uncovered_stmts
        #       5-based: test code
        all_uncovered_modified_stmts_info, event_detail, union_uncovered_stmts, old_covered_info, new_covered_info = \
                filter_tests_by_line_distance(all_for_further_needs, Config.initial_test_generation_prompt_version)
        append_event(ReferenceTestEvent(pr_nb=pr.number, message=f"Reference test filtering, round {round}", details=event_detail))
        
        if union_uncovered_stmts: # prompt-5 based prompt 8
            old_context = mark_code_stmt(old_covered_info, union_uncovered_stmts["old"], pr.old_context_with_line_num)
            new_context = mark_code_stmt(new_covered_info, union_uncovered_stmts["new"], pr.new_context_with_line_num)
        else:
            old_context = pr.old_context_with_line_num # code lines with line numbers marked
            new_context = pr.new_context_with_line_num
    else:
        if Config.context_version in [4, 6]:
            old_context = pr.old_context_with_line_num # code lines with line numbers marked
            new_context = pr.new_context_with_line_num
        else:
            old_context = pr.old_context # generally without line numbers, exclude for context_version == 7. 
            new_context = pr.new_context

        # get a model easy-to-follow string of uncovered info
        all_uncovered_modified_stmts_info = ""
        old_uncovered_list, new_uncovered_list = all_uncovered_modified_stmts_info_dict.values()
        for i, (single_old, single_new) in enumerate(zip(old_uncovered_list, new_uncovered_list)):
            old_uncovered_str = get_str_from_dict(single_old)
            new_uncovered_str = get_str_from_dict(single_new)
            all_uncovered_modified_stmts_info += f"Information {i+1}:\nOld:\n{old_uncovered_str}New:\n{new_uncovered_str}"

    all_tests = []
    test_msg_pairs_full_diff = []
    test_msg_pairs_filtered_diff = []

    if full_diff_len_fit == True:
        # full diff with GPT4
        prompt_full_diff = None
        # if Config.initial_test_generation_prompt_version == 5: # TODO specific version of prompts
        #     prompt_full_diff = FeedbackTestGeneratorPrompt(github_repo.name, changed_functions, pr.full_diff, 
        #         all_uncovered_modified_stmts_info, old_context, new_context, pr.old_test_function_code, pr.new_test_function_code)
        # else: # e.g., other prompts, and testora
        prompt_full_diff = FeedbackTestGeneratorPrompt(github_repo.name, changed_functions, pr.full_diff,
                all_uncovered_modified_stmts_info, old_context, new_context)
        
        generated_test, test_msg_pairs_full_diff = generate_tests_with_prompt(pr, prompt_full_diff, llm, "full_diff", round=round)
        all_tests.extend(generated_test)

    if filtered_diff_len_nonequal_fit == True:
        # filtered diff with GPT4
        prompt_filtered_diff = None
        # if Config.initial_test_generation_prompt_version == 5:
        #     prompt_filtered_diff = FeedbackTestGeneratorPrompt(github_repo.name, changed_functions, pr.filtered_diff,
        #             all_uncovered_modified_stmts_info, old_context, new_context, pr.old_test_function_code, pr.new_test_function_code)
        # else:
        prompt_filtered_diff = FeedbackTestGeneratorPrompt(github_repo.name, changed_functions, pr.filtered_diff,
                all_uncovered_modified_stmts_info, old_context, new_context)
        
        generated_test, test_msg_pairs_filtered_diff = generate_tests_with_prompt(pr, prompt_filtered_diff, llm, "filtered_diff", round=round)
        all_tests.extend(generated_test)

    return all_tests, test_msg_pairs_full_diff, test_msg_pairs_filtered_diff

def refine_tests_with_no_private_call(pr, github_repo, changed_functions, code_and_err_msgs_full_diff, code_and_err_msgs_filtered_diff):
    # TODO also to add test function bodies?
    static_err_fixed_tests = []

    if code_and_err_msgs_full_diff:
        # it will not change with the same PR. the initial round already checked the len. -> len(pr.full_diff.split("\n")) <= 200:
        prompt_full_diff = ParseErrorPrivateCallFixingPrompt(github_repo.name, changed_functions, pr.full_diff, 
                pr.old_context, pr.new_context, code_and_err_msgs_full_diff)
        generated_test, test_msg_pairs_full_diff = generate_tests_with_prompt(pr, prompt_full_diff, llm, "full_diff", do_name_reformatting=False)
        static_err_fixed_tests.extend(generated_test)

        for detail in test_msg_pairs_full_diff:
            test_idx, test_code, static_info = detail
            append_event(LLMEvent(pr_nb=pr.number, 
                    message=f"Failed to fix test #{test_idx} (full_diff). Static error: {static_info}", content=test_code))

    if code_and_err_msgs_filtered_diff:
        prompt_filtered_diff = ParseErrorPrivateCallFixingPrompt(github_repo.name, changed_functions, pr.filtered_diff, 
                pr.old_context, pr.new_context, code_and_err_msgs_filtered_diff)
        generated_test, test_msg_pairs_filtered_diff = generate_tests_with_prompt(pr, prompt_filtered_diff, llm, "filtered_diff", do_name_reformatting=False)
        static_err_fixed_tests.extend(generated_test)

        for detail in test_msg_pairs_filtered_diff:
            test_idx, test_code, static_info = detail
            append_event(LLMEvent(pr_nb=pr.number, 
                    message=f"Failed to fix test #{test_idx} (filtered_diff). Static error: {static_info}", content=test_code))
    
    return static_err_fixed_tests

def validate_output_difference(cloned_repo_manager, pr, old_execution, new_execution):
    assert (old_execution.output is not None)
    assert (new_execution.output is not None)

    # re-execute test on old and new version and ignore flaky differences
    # for _ in range(len(new_execution)): # H: default to 1?
    old_execution_repeated = TestExecution(old_execution.code)
    execute_tests_on_commit(cloned_repo_manager, pr, [old_execution_repeated], pr.pre_commit, "old_flaky")
    new_execution_repeated = TestExecution(new_execution.code)
    execute_tests_on_commit(cloned_repo_manager, pr, [new_execution_repeated], pr.post_commit, "new_flaky")
    if old_execution.output != old_execution_repeated.output:
        return False
    if new_execution.output != new_execution_repeated.output:
        return False
    return True


def reduce_test(cloned_repo_manager, pr, old_execution, new_execution):
    assert (old_execution.code == new_execution.code)
    assert (old_execution.output != new_execution.output)

    # create increasingly smaller variants of the test (by removing lines at the end)
    increasingly_smaller_tests = []
    lines = old_execution.code.split("\n")
    for line_nb in reversed(range(1, len(lines)+1)):  # last line to second line
        if lines[line_nb-1] == "" or lines[line_nb-1].startswith("#"):
            continue
        reduced_code = "\n".join(lines[:line_nb])
        increasingly_smaller_tests.append(reduced_code)

    # execute all variants
    old_executions = [TestExecution(t) for t in increasingly_smaller_tests]
    new_executions = [TestExecution(t) for t in increasingly_smaller_tests]
    execute_tests_on_commit(cloned_repo_manager, pr, old_executions, pr.pre_commit, "old_reduce")
    execute_tests_on_commit(cloned_repo_manager, pr, new_executions, pr.post_commit, "new_reduce")

    # find the last test that still shows a difference
    reduced_old_execution = old_execution
    reduced_new_execution = new_execution
    assert reduced_old_execution.output != reduced_new_execution.output
    for (reduced_old_execution_candidate, reduced_new_execution_candidate) in zip(old_executions, new_executions):
        if reduced_old_execution_candidate.output == reduced_new_execution_candidate.output:
            break
        reduced_old_execution = reduced_old_execution_candidate
        reduced_new_execution = reduced_new_execution_candidate
        assert reduced_old_execution.output != reduced_new_execution.output
        append_event(ComparisonEvent(pr_nb=pr.number,
                                     message="Different outputs (also after test reduction)",
                                     test_code=reduced_old_execution.code,
                                     old_output=reduced_old_execution.output,
                                     new_output=reduced_new_execution.output))

    return reduced_old_execution, reduced_new_execution


def check_if_present_in_main(cloned_repo_manager, pr, new_execution):
    main_execution = TestExecution(new_execution.code)
    execute_tests_on_commit(cloned_repo_manager, pr, [main_execution], "main", "main")
    # TODO NOT just matching the output strings
    return main_execution.output == new_execution.output


def classify_regression(project_name, pr, changed_functions, docstrings, old_execution, new_execution, no_cache=False, nb_samples=1):
    append_event(PreClassificationEvent(pr_nb=pr.number,
                                        message="Pre-classification",
                                        test_code=old_execution.code,
                                        old_output=old_execution.output,
                                        new_output=new_execution.output))

    prompt = RegressionClassificationPrompt(
        project_name, pr, changed_functions, docstrings, old_execution.code, old_execution.output, new_execution.output)
    raw_answer = llm.query(prompt,
                           temperature=Config.classification_temp,
                           no_cache=no_cache,
                           nb_samples=nb_samples)
    append_event(LLMEvent(pr_nb=pr.number, message="Raw answer", content="\n---(next sample)---".join(raw_answer)))
    assert (nb_samples == len(raw_answer))

    all_results = []
    for raw_answer_sample in raw_answer:
        is_relevant_change, is_deterministic, is_public, is_legal, is_surprising, correct_output = prompt.parse_answer(
            [raw_answer_sample])
        append_event(ClassificationEvent(pr_nb=pr.number,
                                         message="Classification",
                                         is_relevant_change=is_relevant_change,
                                         is_deterministic=is_deterministic,
                                         is_public=is_public,
                                         is_legal=is_legal,
                                         is_surprising=is_surprising,
                                         correct_output=correct_output,
                                         old_is_crash=is_crash(old_execution.output),
                                         new_is_crash=is_crash(new_execution.output)))
        result = is_relevant_change and is_deterministic and is_public and is_legal and is_surprising
        all_results.append(result)
    return all_results


def select_expected_behavior(project_name, pr, old_execution, new_execution, docstrings):
    """Ask LLM which of two possible outputs is the expected behavior."""
    prompt = SelectExpectedBehaviorPrompt(
        project_name, old_execution.code, old_execution.output, new_execution.output, docstrings)
    raw_answer = llm.query(prompt, temperature=Config.classification_temp)
    append_event(LLMEvent(pr_nb=pr.number, message="Raw answer", content="\n---(next sample)---".join(raw_answer)))
    expected_behavior = prompt.parse_answer(raw_answer)
    append_event(SelectBehaviorEvent(pr_nb=pr.number,
                                     message="Selected expected behavior",
                                     expected_output=expected_behavior))
    return expected_behavior


def check_pr(github_repo, cloned_repo_manager, pr):
    # ignore if too few or too many files changed
    # nb_modified_code_files = len(pr.non_test_modified_python_files)
    nb_modified_code_files = len(pr.non_test_modified_code_files)
    if nb_modified_code_files == 0:
        append_event(Event(pr_nb=pr.github_pr.number, message="Ignoring because no non-test code files were modified"))
        return
    if nb_modified_code_files > 3:
        append_event(Event(pr_nb=pr.number, message="Ignoring because too many non-test code files were modified"))
        return

    # ignore if PR has more than one parent
    if Config.single_parent_PRs_only and len(pr.parents) != 1:
        append_event(Event(pr_nb=pr.number, message=f"Ignoring because PR has != 1 parent"))
        return

    # ignore if only comment changes
    if not pr.has_non_comment_change():
        append_event(Event(pr_nb=pr.number, message="Ignoring because only comments changed"))
        return

    # ignore if labeled as documentation-only change
    if pr.title.startswith("DOC"):
        append_event(Event(pr_nb=pr.number, message="Ignoring because labeled as 'DOC'"))
        return

    '''
    Extract diff and names of changed functions. changed_function : qualified names
     * this function call wil also add the desired context to the pr.
     * old_changed_functions available if needed.
     * if Config.use_existing_tests == "pr-modified":
        this function call wil also add the test function body to the pr 
        -> 'old_test_function_code' and 'new_test_function_code'
     * if Config.call_gragh == True:
        this function will also return the callers and callees of the changed functions 
    '''
    changed_functions = pr.get_changed_function_names_and_context(Config.initial_test_generation_prompt_version) 
    # return
    # note: the initial round do not have converage info.

    # # extract call gragh and dependency gragh
    # output_dir = join("data", "results", github_repo.name)
    # call_gragh, dependency_gragh = extract_graphs_from_specified_files(
    #         github_repo, raw_info_changed_functions, output_dir)

    # existing developer-written tests
    # "none": do not make any extra effort about developer-written tests,
    # "pr-modified": use the PR-modified tests, 
    # "all": use PR-modified tests + local tests
    if Config.use_existing_tests == "all":
        cloned_repo = cloned_repo_manager.get_cloned_repo(pr.post_commit)
        container_name = cloned_repo.container_name
        project_name = cloned_repo_manager.repo_name
        
        ExtractExistingTests(pr.modified_test_python_files, changed_functions, container_name, project_name).main()
        # TODO
        return

    # generate tests via LLM
    generated_tests, test_msg_pairs_full_diff, test_msg_pairs_filtered_diff, \
            full_diff_len_fit, filtered_diff_len_nonequal_fit = generate_tests(pr, github_repo, changed_functions)
    old_executions, new_executions, all_covered_modified_stmts_old, all_covered_modified_stmts_new = \
            run_tests_and_feedback(github_repo, cloned_repo_manager, pr, changed_functions, \
                    generated_tests, test_msg_pairs_full_diff, test_msg_pairs_filtered_diff, full_diff_len_fit, filtered_diff_len_nonequal_fit)
    if all_covered_modified_stmts_old == None:
        return

    # analyze behavior of executions
    # TODO add covered lines to show which lines introduce the behavioral differences.

    # to separate the test genration and classification phase, here we store the breakpoint data.
    old_executions_differ_relevant = []
    new_executions_differ_relevant = []

    for (old_execution, new_execution, old_covered, new_covered) in zip(
            old_executions, new_executions, all_covered_modified_stmts_old, all_covered_modified_stmts_new):
        assert old_execution.output is not None
        assert new_execution.output is not None

        # check for behavioral differences
        difference_found = old_execution.output != new_execution.output
        # if is_crash(old_execution.output) and is_crash(new_execution.output):
        if check_whether_error_exist(old_execution.code, old_execution.output) and check_whether_error_exist(new_execution.code, new_execution.output):
            # ignore differences if both tests crash
            append_event(ComparisonEvent(pr_nb=pr.number,
                    message=f"Both tests failed, considering them the same\nCovered lines in old: {old_covered}, Covered lines in new: {new_covered}",
                    test_code=old_execution.code, old_output=old_execution.output,
                    new_output=new_execution.output))
            continue
        if difference_found:
            # double-check differences by re-executing the tests
            difference_found_again = validate_output_difference(cloned_repo_manager, pr, old_execution, new_execution)
            if not difference_found_again:
                difference_found = False

        if not difference_found:
            append_event(ComparisonEvent(pr_nb=pr.number, message=f"Same output\nCovered lines in old: {old_covered}, Covered lines in new: {new_covered}",
                    test_code=old_execution.code, old_output=old_execution.output, new_output=new_execution.output))
            continue

        append_event(ComparisonEvent(pr_nb=pr.number,
                message=f"Different outputs\nCovered lines in old: {old_covered}, Covered lines in new: {new_covered}",
                test_code=old_execution.code, old_output=old_execution.output, new_output=new_execution.output))

        if Config.phase_selection == "all": # run the entire workflow, including test genration and classification. 
            # if difference found, reduce the test while still observing a difference
            old_execution, new_execution = reduce_test(cloned_repo_manager, pr, old_execution, new_execution)
            assert old_execution.output != new_execution.output

            # check if new output is still present in head of current main branch
            if not check_if_present_in_main(cloned_repo_manager, pr, new_execution):
                append_event(Event(pr_nb=pr.number, message="Difference not present in main anymore"))

            # find docstrings
            cloned_repo_of_new_commit = cloned_repo_manager.get_cloned_repo(pr.post_commit)
            docstrings = retrieve_relevant_docstrings(cloned_repo_of_new_commit, new_execution.code)

            # if difference found, classify regression
            assert old_execution.code == new_execution.code
            is_regression_bug = classify_regression(
                github_repo.name, pr, changed_functions, docstrings, old_execution, new_execution)[0]

            # if classified as regression bug, ask LLM which behavior is expected (to handle coincidental bug fixes)
            if is_regression_bug:
                select_expected_behavior(github_repo.name, pr, old_execution, new_execution, docstrings)

        elif Config.phase_selection == "test_generation":
            '''
            store the breakpoint infomation for later continuing work:
            * changed_functions
            * old_excution (from the tests still show the output difference at this point)
            * new_excution (the same as above)
            '''
            
            simplified_old_execution = simplify_test_execution(old_execution)
            simplified_new_execution = simplify_test_execution(new_execution)
            old_executions_differ_relevant.append(simplified_old_execution)
            new_executions_differ_relevant.append(simplified_new_execution)

    # When need to further classify the different outputs, read the test info from stored files.
    # organize and write the breakpoint data to a local/db file
    if old_executions_differ_relevant:
        breakpoint_data_str = {
            "changed_functions": changed_functions,
            "old_executions_differ_relevant": f"{old_executions_differ_relevant}",
            "new_executions_differ_relevant": f"{new_executions_differ_relevant}"
        }

        with open(f"{github_repo.name}_{pr.number}_breakpoint_data.json", "w") as f:
            json.dump(breakpoint_data_str, f, indent=2)

def simplify_test_execution(execution):
    # simplify the execution by removing the redundant information.
    # keep only '.code' and '.output' is enough for further reduction and classification.
    simplified_execution = TestExecution(execution.code)
    simplified_execution.output = execution.output
    return simplified_execution

def check_union_coverage_full_cover_exist(missed_stmts:dict, covered_stmts:dict):
    updated_missed_stmts = {}
    uncover_exist = False
    for file_path, missed in missed_stmts.items():
        still_missed = missed - covered_stmts[file_path]
        if still_missed:
            uncover_exist = True
        updated_missed_stmts.update({file_path: still_missed})

    return updated_missed_stmts, uncover_exist

def run_tests_and_feedback(github_repo, cloned_repo_manager, pr, changed_functions, generated_tests, 
            test_msg_pairs_full_diff, test_msg_pairs_filtered_diff, full_diff_len_fit, filtered_diff_len_nonequal_fit,
            old_executions:list=[], new_executions:list=[], all_covered_modified_stmts_old:list=[], all_covered_modified_stmts_new:list=[], 
            round=0, old_missed:dict={}, new_missed:dict={}):
    ''' 
    A recursive function to run the generated tests and use the feedback for the next round test generation.
    Loop ends when:
     ** one or more of the generated tests union-covers all the changed lines, or 
     ** the union coverage is not increased.

    Initial generation is marked as round 0, and feedback loops marks start at round 1.
    '''

    if not generated_tests:
        if Config.fix_static_error == False:
            append_event(Event(pr_nb=pr.number, message="Ignoring because no tests were generated"))
            # return old_executions, new_executions, all_covered_modified_stmts_old, all_covered_modified_stmts_new
            return None, None, None, None

    # inner feedback about parse error and 'private' calls
    if Config.fix_static_error == True and round == 0: # TODO let it work for only R0
        code_and_err_msgs_full_diff = ""
        code_and_err_msgs_filtered_diff = ""
        test_idx_full_diff = []
        test_idx_filtered_diff = []

        for pair in test_msg_pairs_full_diff:
            test_idx, test_code, static_error_msg = pair
            code_and_err_msgs_full_diff += f"{test_code}\n\nStatic analyis results: {static_error_msg}\n\n"
            test_idx_full_diff.append(test_idx)

        for pair in test_msg_pairs_filtered_diff:
            code_and_err_msgs_filtered_diff += f"{test_code}\n\nStatic analyis results: {static_error_msg}\n\n"
            test_idx_filtered_diff.append(test_idx)

        # ** Single -- PromptV2**
        if test_idx_full_diff or test_idx_filtered_diff:
            static_err_fixed_tests_may_dup = refine_tests_with_no_private_call(pr, github_repo, changed_functions, code_and_err_msgs_full_diff, code_and_err_msgs_filtered_diff)
            # go through to update the tests
            append_event(Event(pr_nb=pr.number, message=f"Static error feedback ends."))
            for idx, test in zip((test_idx_full_diff + test_idx_filtered_diff), static_err_fixed_tests_may_dup):
                generated_tests.insert(test_idx, test)

            # overall dedup, to remove the duplicates in remianing generated tests and static_err_fixed_tests_may_dup
            generated_tests = de_dup_tests_with_name(generated_tests)

    if cloned_repo_manager.repo_name == "pandas":
        # make sure the tests import pandas
        updated_tests = []
        for test in generated_tests:
            if "import pandas" not in test:
                updated_tests.append("import pandas as pd\n" + test)
            else:
                updated_tests.append(test)
        generated_tests = updated_tests

    # ask LLM to fix undefined references in tests
    if Config.fix_undefined_refs:
        fixed_tests = []
        for test in generated_tests:
            undefined_refs = get_undefined_references(test)
            if undefined_refs:
                prompt = UndefinedRefsFixingPrompt(test, undefined_refs)
                raw_answer = llm.query(prompt)[0]
                append_event(LLMEvent(pr_nb=pr.number, message="Raw answer", content=raw_answer))
                fixed_test = prompt.parse_answer(raw_answer)
                append_event(LLMEvent(pr_nb=pr.number, message="Fixed undefined references", content=fixed_test))
                fixed_tests.append(fixed_test)
            else:
                fixed_tests.append(test)
        generated_tests = fixed_tests

    # execute tests
    old_executions_cur_round = [TestExecution(t) for t in generated_tests]
    new_executions_cur_round = [TestExecution(t) for t in generated_tests]

    execute_tests_on_commit(cloned_repo_manager, pr, old_executions_cur_round, pr.pre_commit, "old")
    execute_tests_on_commit(cloned_repo_manager, pr, new_executions_cur_round, pr.post_commit, "new")

    if Config.use_error_feedabck == True:
        '''
        Two options for giving the feedback:
        1. max attempts
        2. the error type does not changes
        '''
        # runtime error feedabck
        error_fixed_tests_indices = []
        fixed_executions_old = []
        fixed_executions_new = []
        error_fixed_tests = [] # ideally fixed
        # pre_error_types = [] # option 2
        for test_i, (old_execution, new_execution) in enumerate(zip(old_executions_cur_round, new_executions_cur_round)):
            error_type_in_old = extract_error_type(old_execution.output)
            error_type_in_new = extract_error_type(new_execution.output)

            inner_round = 0 # decide when to stop the inner feddback loop for a single test
            fixed_test = None # from last inner round
            end_event_recorded = False
            while error_type_in_old and error_type_in_new: # both failed to run
                # option 1
                if inner_round >= Config.error_feedback_max:
                    # max attempt to fix the test, but still fails on both versions of the code
                    append_event(Event(pr_nb=pr.number, message=f"Error feedback loop ends after inner round {inner_round}. Max attempt ({Config.error_feedback_max}) reaches."))
                    break
                
                # option 2
                # if [error_type_in_old, error_type_in_new] in pre_error_types:
                #     # TODO same type error, or same type but different location
                #     append_event(Event(pr_nb=pr.number, message=f"Error feedback loop ends after inner round {inner_round}. Error type does not change."))
                #     end_event_recorded = True
                #     break

                # refine the test by fixing the error
                prompt = RuntimeErrorsFixingPrompt(old_execution.code, old_execution.output) #, new_execution.output)
                raw_answer = llm.query(prompt, no_cache=True)[0] # no_cache set to true, allow the model to get different answers with the same error message.
                append_event(LLMEvent(pr_nb=pr.number, message="Raw answer", content=raw_answer))
                fixed_test = prompt.parse_answer(raw_answer)
                # if "# Round" not in fixed_test:
                #     print(test_i)
                message = f"Fix runtime errors. Error types: old: {error_type_in_old}, new: {error_type_in_new}"
                append_event(LLMEvent(pr_nb=pr.number, message=message, content=fixed_test)) # a mark to show which test
                inner_round += 1

                # rerun the current ideally fixed test
                fixed_executions_old_single = [TestExecution(fixed_test)]
                fixed_executions_new_single = [TestExecution(fixed_test)]
                execute_tests_on_commit(cloned_repo_manager, pr, fixed_executions_old_single, pr.pre_commit, f"old_error_fix_inner_r{inner_round})")
                execute_tests_on_commit(cloned_repo_manager, pr, fixed_executions_new_single, pr.post_commit, f"new_error_fix_inner_r{inner_round})")

                # check whether the test need more rounds of error message feedback
                old_execution = fixed_executions_old_single[0]
                new_execution = fixed_executions_new_single[0]
                # pre_error_types.append([error_type_in_old, error_type_in_new]) # option 2
                error_type_in_old = extract_error_type(old_execution.output)
                error_type_in_new = extract_error_type(new_execution.output)

            if fixed_test: # only consider the tests that fails at leat at one side
                # recodrs the fixed tests from the last inner rounds
                error_fixed_tests_indices.append(test_i)
                error_fixed_tests.append(fixed_test)
                fixed_executions_old.append(old_execution)
                fixed_executions_new.append(new_execution)
                if end_event_recorded == False:
                    append_event(Event(pr_nb=pr.number, message=f"Error feedback loop ends after inner round {inner_round}. Test passes at least one of the code versions."))

        # replace the old failed tests with the last fix
        append_event(Event(pr_nb=pr.number, message=f"Round #{round}. Discard {len(error_fixed_tests)} error tests."))
        for idx, old_execution, new_execution in zip(error_fixed_tests_indices, fixed_executions_old, fixed_executions_new):
            old_executions_cur_round[idx] = old_execution
            new_executions_cur_round[idx] = new_execution
            
    old_executions.extend(old_executions_cur_round) # get the executions for all the rounds
    new_executions.extend(new_executions_cur_round)
    assert None not in [e.output for e in old_executions_cur_round]

    # analyze coverage during test execution
    fail_to_cover_all_indices = []
    all_uncovered_modified_stmts_info = {"old": [], "new": []}
    # all_for_further_needs could be all uncovered info, or all covered info
    all_for_further_needs =  {"old": [], "new": []} # Config.context_version = 8
    full_coverage_exists = False # union full coverage, or single test full coverage

    # here exactly use the missed info provided by the function call
    # the for loop below will update the 'old_missed' and 'new_missed'
    pre_round_old_missed = copy.deepcopy(old_missed) # after the update of 'old_missed', it will be the missed info for current round
    pre_round_new_missed = copy.deepcopy(new_missed) # deepcopy to avoid changes in pre_round

    for test_i, (old_execution, new_execution) in enumerate(zip(old_executions_cur_round, new_executions_cur_round)):
        # Check whether to enter to the feebackloop
        uncovered_modified_stmts_old_exist = False
        uncovered_modified_stmts_new_exist = False
        
        if not old_missed: # Record the event only once
            details = f"All executable/coverable modified lines: Old: {old_execution.all_executable_modified_stmt_ranges}, New: {new_execution.all_executable_modified_stmt_ranges}"
            append_event(CoverageEvent(pr_nb=pr.number, message=f"Diff coverage, all rounds", details=details))
            # for checking union coverage
            old_missed = old_execution.all_executable_modified_stmts_num
            new_missed = new_execution.all_executable_modified_stmts_num

        # Uncovered modified lines are recorded for further checking,
        # Covered modified lines are recorded for later union coverage calculating
        details = (f"Old: {old_execution.coverage_percentage}, New: {new_execution.coverage_percentage}\n"
                f"Uncovered modified lines: Old: {old_execution.all_uncovered_exec_modified_stmt_ranges}, New: {new_execution.all_uncovered_exec_modified_stmt_ranges}\n"
                f"Covered modified lines: Old: {old_execution.all_covered_exec_modified_stmt_ranges}, New: {new_execution.all_covered_exec_modified_stmt_ranges}")
        append_event(CoverageEvent(pr_nb=pr.number, message=f"Diff coverage, {old_execution.code.split(':', 1)[0]}", details=details))

        old_missed, uncovered_modified_stmts_old_exist = check_union_coverage_full_cover_exist(old_missed, old_execution.all_covered_exec_modified_stms_num)
        new_missed, uncovered_modified_stmts_new_exist = check_union_coverage_full_cover_exist(new_missed, new_execution.all_covered_exec_modified_stms_num)

        if uncovered_modified_stmts_old_exist or uncovered_modified_stmts_new_exist:
            fail_to_cover_all_indices.append(test_i+1) # keep the index as absolute number (consistency with the test prefix)
            # deduplicate from all rounds 
            if (old_execution.all_covered_exec_modified_stmt_ranges not in all_covered_modified_stmts_old or \
                    new_execution.all_covered_exec_modified_stmt_ranges not in all_covered_modified_stmts_new): 
                # uncovered_info will be used in feedback prompt.
                all_uncovered_modified_stmts_info["old"].append(old_execution.all_uncovered_exec_modified_stmts_num)
                all_uncovered_modified_stmts_info["new"].append(new_execution.all_uncovered_exec_modified_stmts_num)
                if Config.context_version == 8: 
                    all_for_further_needs["old"].append(old_execution)
                    all_for_further_needs["new"].append(new_execution)
        
        # to check if all the rounds and executions cover the same statements
        all_covered_modified_stmts_old.append(old_execution.all_covered_exec_modified_stmt_ranges) # a dict, and each value is a list of ranges
        all_covered_modified_stmts_new.append(new_execution.all_covered_exec_modified_stmt_ranges)

        if Config.feedback_test_generation_prompt_version != 0:
            if not old_missed and not new_missed:
                # union coverage reaches 100%
                full_coverage_exists = True
                # still keep checking the coverage information

    if Config.feedback_test_generation_prompt_version != 0: # 0 means to run original Testora, which does not have a feedback loop
        if full_coverage_exists == False: # no full coverage exists in all the tests
            is_coverage_changed = True
            if round > 0: # initail round is 0, and feedback loop starts from 1
                # start from the first round of feedback, if the union coverage (round level) does not change, even have not reaches 100%, stop the feedback loop.
                if pre_round_old_missed == old_missed and pre_round_new_missed == new_missed:
                    is_coverage_changed = False
                    append_event(Event(pr_nb=pr.number, message=f"Refinement ends after round {round}, union coverage info does not change anymore."))
            
            # feedback loop to get new tests that are expected to cover more modified lines.
            if is_coverage_changed == True: # and round < Config.max_round:
                deduplicated_len = len(all_uncovered_modified_stmts_info["old"])
                if deduplicated_len > 0:
                    round+=1
                    details = f"Tests need to be refined: {fail_to_cover_all_indices}. After deduplicate the uncovered lines, the number of the tests: {deduplicated_len}"
                    append_event(CoverageEvent(pr_nb=pr.number, 
                            message=f"Refinement, round {round}, expected to get {len(fail_to_cover_all_indices)} more tests", details=details))
                    
                    refined_tests, test_msg_pairs = generate_replacement_tests(pr, github_repo, changed_functions, 
                            full_diff_len_fit, filtered_diff_len_nonequal_fit, all_uncovered_modified_stmts_info, round, all_for_further_needs)
                    run_tests_and_feedback(github_repo, cloned_repo_manager, pr, changed_functions, refined_tests, test_msg_pairs_full_diff,
                            test_msg_pairs_filtered_diff, full_diff_len_fit, filtered_diff_len_nonequal_fit,
                            old_executions, new_executions, all_covered_modified_stmts_old, all_covered_modified_stmts_new, round, old_missed, new_missed)
                else:
                    append_event(Event(pr_nb=pr.number, message=f"Refinement ends after round {round}, union coverage reaches 100%."))
        else:
            append_event(Event(pr_nb=pr.number, message=f"Refinement ends after round {round}, full coverage exists."))

    return old_executions, new_executions, all_covered_modified_stmts_old, all_covered_modified_stmts_new


def get_merged_prs(github_repo, max_prs):
    """First element is newest PR."""
    all_prs = github_repo.get_pulls(state="closed")
    merged_prs = []
    for github_pr in all_prs:
        if github_pr.is_merged():
            merged_prs.append(github_pr)
        print(f"Added {len(merged_prs)} merged PRs")
        if len(merged_prs) >= max_prs:
            break
    return merged_prs


def find_prs_checked_in_past():
    done_prs = set()

    logs = glob.glob('logs_*.json') + glob.glob('done_prs*.json')
    for log in logs:
        with open(log, "r") as f:
            entries = json.load(f)
        for entry in entries:
            if entry["message"] == "Done with PR":
                done_prs.add(entry["pr_nb"])

    return done_prs


def filter_and_sort_prs_by_risk(github_prs, cloned_repo_manager):
    # split into chunks of 20
    chunks = [github_prs[i:i + 20] for i in range(0, len(github_prs), 20)]

    # ask LLM to rank PRs by risk of introducing a regression bug
    all_high_risk_prs = []
    all_medium_risk_prs = []
    for chunk in chunks:
        prompt = PRRegressionBugRanking(chunk, cloned_repo_manager.repo_name)
        raw_answer = llm.query(prompt)
        append_event(LLMEvent(pr_nb=0, message="Raw answer", content="\n---(next sample)---".join(raw_answer)))
        ranking_result = prompt.parse_answer(raw_answer)
        if ranking_result is None:
            append_event(Event(pr_nb=0, message="Failed to parse ranking result; keeping them all"))
            all_medium_risk_prs.extend(chunk)
        else:
            high_risk_prs, medium_risk, _ = ranking_result
            all_high_risk_prs.extend(high_risk_prs)
            all_medium_risk_prs.extend(medium_risk)

    result = all_high_risk_prs + all_medium_risk_prs
    append_event(Event(pr_nb=0, message=f"Keeping {len(result)} high/medium-risk PRs out of {len(github_prs)} total PRs"))
    return result


def get_repo(project_name):
    if project_name == "pandas":
        cloned_repo_manager = ClonedRepoManager(
            "../clones", "pandas", "pandas-dev/pandas", "pandas-dev", "pandas")
    elif project_name == "scikit-learn":
        cloned_repo_manager = ClonedRepoManager(
            "../clones", "scikit-learn", "scikit-learn/scikit-learn", "scikit-learn-dev", "sklearn")
    elif project_name == "scipy":
        cloned_repo_manager = ClonedRepoManager(
            "../clones", "scipy", "scipy/scipy", "scipy-dev", "scipy")
    elif project_name == "numpy":
        cloned_repo_manager = ClonedRepoManager(
            "../clones", "numpy", "numpy/numpy", "numpy-dev", "numpy")
    elif project_name == "transformers":
        cloned_repo_manager = ClonedRepoManager(
            "../clones", "transformers", "huggingface/transformers", "transformers-dev", "transformers")
    elif project_name == "keras":
        cloned_repo_manager = ClonedRepoManager(
            "../clones", "keras", "keras-team/keras", "keras-dev", "keras")
    elif project_name == "marshmallow":
        cloned_repo_manager = ClonedRepoManager(
            "../clones", "marshmallow", "marshmallow-code/marshmallow", "marshmallow-dev", "marshmallow")
    elif project_name == "pytorch_geometric":
        cloned_repo_manager = ClonedRepoManager(
            "../clones", "pytorch_geometric", "pyg-team/pytorch_geometric", "pytorch_geometric-dev", "torch_geometric")
    elif project_name == "scapy":
        cloned_repo_manager = ClonedRepoManager(
            "../clones", "scapy", "secdev/scapy", "scapy-dev", "scapy")

    cloned_repo = cloned_repo_manager.get_cloned_repo("main")
    cloned_repo.repo.git.pull()
    token = open(".github_token", "r").read().strip()
    github = Github(auth=Auth.Token(token))
    github_repo = github.get_repo(cloned_repo_manager.repo_id)

    return github_repo, cloned_repo_manager


def check_single_pr(project, pr_nb):
    global RegressionTestGeneratorPrompt
    global FeedbackTestGeneratorPrompt

    if Config.initial_test_generation_prompt_version == 1:
        RegressionTestGeneratorPrompt = RegressionTestGeneratorPromptV1
    elif Config.initial_test_generation_prompt_version == 2:
        RegressionTestGeneratorPrompt = RegressionTestGeneratorPromptV2
    elif Config.initial_test_generation_prompt_version in [3, 4, 5]:
        RegressionTestGeneratorPrompt = RegressionTestGeneratorPromptV345
    elif Config.initial_test_generation_prompt_version == 6:
        RegressionTestGeneratorPrompt = RegressionTestGeneratorPromptV6
    elif Config.initial_test_generation_prompt_version == 7:
        RegressionTestGeneratorPrompt = RegressionTestGeneratorPromptV7

    if Config.feedback_test_generation_prompt_version == 1:
        FeedbackTestGeneratorPrompt = FeedbackTestGeneratorPromptV1
    elif Config.feedback_test_generation_prompt_version == 2:
        FeedbackTestGeneratorPrompt = FeedbackTestGeneratorPromptV2
    elif Config.feedback_test_generation_prompt_version == 3:
        FeedbackTestGeneratorPrompt = FeedbackTestGeneratorPromptV3
    elif Config.feedback_test_generation_prompt_version == 4:
        FeedbackTestGeneratorPrompt = FeedbackTestGeneratorPromptV4
    elif Config.feedback_test_generation_prompt_version == 5:
        FeedbackTestGeneratorPrompt = FeedbackTestGeneratorPromptV5
    elif Config.feedback_test_generation_prompt_version == 6:
        FeedbackTestGeneratorPrompt = FeedbackTestGeneratorPromptV6
    elif Config.feedback_test_generation_prompt_version == 7:
        FeedbackTestGeneratorPrompt = FeedbackTestGeneratorPromptV7
    elif Config.feedback_test_generation_prompt_version == 8:
        FeedbackTestGeneratorPrompt = FeedbackTestGeneratorPromptV8

    github_repo, cloned_repo_manager = get_repo(project)
    github_pr = github_repo.get_pull(pr_nb)
    pr = PullRequest(github_pr, github_repo, cloned_repo_manager)

    # check the PR
    append_event(PREvent(pr_nb=pr_nb,
                         message="Starting to check PR",
                         title=pr.github_pr.title, url=pr.github_pr.html_url))

    check_pr(github_repo, cloned_repo_manager, pr)

    append_event(PREvent(pr_nb=pr_nb,
                         message="Done with PR",
                         title=pr.github_pr.title, url=pr.github_pr.html_url))


def fetch_and_check_prs(prs):
    # project, pr_nb, timestamp = EvalTaskManager.fetch_task()
    # Isolate the containers to fetch only the expected pr tasks
    project, pr_nb, timestamp = EvalTaskManager.fetch_task_with_pr_filter(prs)
    while project and pr_nb:
        try:
            # write configuration for every fetched task
            config_dict = {
                k: v for k, v in vars(Config).items()
                if not k.startswith("__") and not callable(v)
            }
            append_event(Event(pr_nb=0, message=f"Configuration: {config_dict}"))

            check_single_pr(project, pr_nb)
        except TestoraException as e:
            append_event(ErrorEvent(
                pr_nb=pr_nb, message="Caught TestoraError; will continue with next PR", details=str(e)))
            continue

        # store log on disk and into DB
        store_logs()
        log = get_logs_as_json()
        EvalTaskManager.write_results(project, pr_nb, log, timestamp)
        reset_logs()

        # project, pr_nb, timestamp = EvalTaskManager.fetch_task()
        project, pr_nb, timestamp = EvalTaskManager.fetch_task_with_pr_filter(prs)

    print("No more tasks to work on")


def main():
    parser = argparse.ArgumentParser(description="Testora's main entry point")
    parser.add_argument("--db", action="store_true", help="Run on PRs fetched from the database")
    parser.add_argument("--paras", type=ast.literal_eval, help="To help run exepeimenta non-stop")
    parser.add_argument("--prs", type=ast.literal_eval, help="To help isolate the running among different containers")
    parser.add_argument("--project", type=str,
                        help="Project to analyze",
                        choices=["keras", "marshmallow", "pandas", "scipy"])
    parser.add_argument("--pr", type=int, help="PR number to analyze")
    args = parser.parse_args()

    start_logging()
    if args.paras:
        # auto-updates the prompt versions, available for both db mode and single-pr mode
        Config.initial_test_generation_prompt_version, Config.feedback_test_generation_prompt_version, Config.context_version, \
                Config.use_error_feedabck, Config.fix_static_error, Config.use_existing_tests, Config.iteration, Config.model_version = args.paras
        
    if args.db:
        if args.project or args.pr:
            raise ValueError("When using --db, cannot use --project and --pr")
        EvalTaskManager.initialize()
        fetch_and_check_prs(args.prs)
    else:
        if not args.project or not args.pr:
            raise ValueError("Must specify --project and --pr")
        
        config_dict = {
            k: v for k, v in vars(Config).items()
            if not k.startswith("__") and not callable(v)
        }
        append_event(Event(pr_nb=0, message=f"Configuration: {config_dict}"))

        check_single_pr(args.project, args.pr)
        store_logs()


if __name__ == "__main__":
    main()

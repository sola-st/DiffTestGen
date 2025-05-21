import argparse
import ast
import glob
import json
from typing import List
from github import Github, Auth
from testora.execution.DockerExecutor import DockerExecutor
from testora.execution.ProgramMerger import merge_programs, separate_outputs
from testora.execution.TestExecution import TestExecution
from testora.llms.LLMCache import LLMCache
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
from testora.util.PullRequest import PullRequest
from testora.llms.OpenAIGPT import OpenAIGPT
from testora.util.Logs import CoverageEvent, PreClassificationEvent, start_logging, ClassificationEvent, ErrorEvent, PREvent, SelectBehaviorEvent, TestExecutionEvent, append_event, Event, ComparisonEvent, LLMEvent, get_logs_as_json, store_logs, reset_logs
from testora.util.PythonCodeUtil import has_private_accesses_or_fails_to_parse
from testora.util.PythonCodeUtil2 import mark_to_cover_code_stmt
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
                                                message=f"Test execution ({version})",
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


def generate_tests_with_prompt(pr, prompt, model, diff_version, nb_samples=1, round=0):
    raw_answer = model.query(prompt, nb_samples)
    append_event(LLMEvent(pr_nb=pr.number, message="Raw answer", content="\n---(next sample)---".join(raw_answer)))

    generated_tests = prompt.parse_answer(raw_answer)
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
    return name_formatted_generated_tests


def remove_tests_with_private_call(tests):
    result = []
    for test in tests:
        if not has_private_accesses_or_fails_to_parse(test):
            result.append(test)
    return result


def generate_tests(pr, github_repo, changed_functions):
    # prepare context used by one or more prompts
    # full_diff is already computed (pr.full_diff) when the pull request is instantiated
    pr.get_filtered_diff() # this adds filtered_diff info to pr.filtered_diff 

    all_tests = []
    full_diff_len_fit = False
    filtered_diff_len_nonequal_fit = False

    if len(pr.full_diff.split("\n")) <= 200:
        full_diff_len_fit = True
        # full diff with GPT4
        prompt_full_diff = RegressionTestGeneratorPrompt(github_repo.name, changed_functions, pr.full_diff, pr.old_context, pr.new_context)
        all_tests.extend(generate_tests_with_prompt(pr, prompt_full_diff, llm, "full_diff"))

        # full diff with GPT3.5
        # all_tests.extend(generate_tests_with_prompt(pr, prompt_full_diff, gpt35, "full_diff", nb_samples=10))

    if len(pr.filtered_diff.split("\n")) <= 200 and pr.filtered_diff != pr.full_diff:
        filtered_diff_len_nonequal_fit = True
        # filtered diff with GPT4
        prompt_filtered_diff = RegressionTestGeneratorPrompt(github_repo.name, changed_functions, pr.filtered_diff, pr.old_context, pr.new_context)
        all_tests.extend(generate_tests_with_prompt(pr, prompt_filtered_diff, llm, "filtered_diff"))

        # filtered diff with GPT3.5
        # all_tests.extend(generate_tests_with_prompt(pr, prompt_filtered_diff, gpt35, "filtered_diff", nb_samples=10))

    # de-dup tests
    nb_tests_before_dedup_and_cleaning = len(all_tests)
    all_tests = list(dict.fromkeys(all_tests))

    # clean tests
    all_tests = remove_tests_with_private_call(all_tests)

    append_event(Event(pr_nb=pr.number,
            message=f"Generated {len(all_tests)} tests ({nb_tests_before_dedup_and_cleaning} before deduplication and cleaning)"))
    
    # also return the bool values to not check multiple times in the feedback rounds
    return all_tests, full_diff_len_fit, filtered_diff_len_nonequal_fit 

def get_str_from_dict(uncover_dict:dict):
    # a util function for 'generate_replacement_tests'
    uncovered_str = ""
    for file_path, uncovered_nums in uncover_dict.items():
        if uncovered_nums:
            uncovered_str += f"{file_path}: lines {uncovered_nums}\n"

    if not uncovered_str:
        uncovered_str = "No specified lines.\n"
    return uncovered_str

def generate_replacement_tests(pr, github_repo, changed_functions, full_diff_len_fit, filtered_diff_len_nonequal_fit,
            all_uncovered_modified_stmts_info_dict, round, all_uncovered_for_further_needs:dict=None):
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
        old_context, overall_uncovered_old = mark_to_cover_code_stmt(all_uncovered_for_further_needs["old"], pr.old_context_with_line_num)
        new_context, overall_uncovered_new = mark_to_cover_code_stmt(all_uncovered_for_further_needs["new"], pr.new_context_with_line_num)
        all_uncovered_modified_stmts_info = len(all_uncovered_for_further_needs["old"]) # to indicate how many tetst to generate

        details = f"All uncovered for to_cover marks: Old: {overall_uncovered_old}, New: {overall_uncovered_new}"
        append_event(CoverageEvent(pr_nb=pr.number, message=f"All uncovered, round {round}", details=f"{details}"))
    elif Config.context_version == 8:
        test_code_list, old_uncovered_list, new_uncovered_list = all_uncovered_for_further_needs.values()
        for i, (test_code, old_uncover, new_uncover) in enumerate(zip(test_code_list, old_uncovered_list, new_uncovered_list)):
            test_code_left, test_code_with_no_name_tmp = test_code.split("# Round ", 1) # test_code_left could be reference fixed lines
            test_code_right = test_code_with_no_name_tmp.split("_diff): ", 1)[1]
            tect_code_with_no_example_name = test_code_left + "# " + test_code_right # from # Round 0 Example 4 (filtered_diff): ... to # ...
            old_uncovered_str = get_str_from_dict(old_uncover)
            new_uncovered_str = get_str_from_dict(new_uncover)
            all_uncovered_modified_stmts_info += \
                f"Existing usage example {i+1}:\n{tect_code_with_no_example_name}\nCorresponding uncovered lines:\nOld:\n{old_uncovered_str}New:\n{new_uncovered_str}\n"
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

    if full_diff_len_fit == True:
        # full diff with GPT4
        prompt_full_diff = FeedbackTestGeneratorPrompt(github_repo.name, changed_functions, pr.full_diff, 
                all_uncovered_modified_stmts_info, old_context, new_context)
        all_tests.extend(generate_tests_with_prompt(pr, prompt_full_diff, llm, "full_diff", round=round))

        # full diff with GPT3.5
        # all_tests.extend(generate_tests_with_prompt(pr, prompt_full_diff, gpt35, "full_diff", nb_samples=10, round=round))

    if filtered_diff_len_nonequal_fit == True:
        # filtered diff with GPT4
        prompt_filtered_diff = FeedbackTestGeneratorPrompt(github_repo.name, changed_functions, pr.filtered_diff, 
                all_uncovered_modified_stmts_info, old_context, new_context)
        all_tests.extend(generate_tests_with_prompt(pr, prompt_filtered_diff, llm, "filtered_diff", round=round))

        # filtered diff with GPT3.5
        # all_tests.extend(generate_tests_with_prompt(pr, prompt_filtered_diff, gpt35, "filtered_diff", nb_samples=10, round=round))

    # de-dup tests
    nb_tests_before_dedup_and_cleaning = len(all_tests)
    all_tests = list(dict.fromkeys(all_tests))

    # clean tests
    all_tests = remove_tests_with_private_call(all_tests)

    append_event(Event(pr_nb=pr.number,
            message=f"Generated {len(all_tests)} more tests. ({nb_tests_before_dedup_and_cleaning} tests before deduplication and cleaning)"))
    return all_tests

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

    # extract diff and names of changed functions. changed_function : qualified names
    # this function call wil also add the desired context to the pr.
    # old_changed_functions available if needed.
    changed_functions = pr.get_changed_function_names_and_context() 
    # note: the initial round do not have converage info.

    # # extract call gragh and dependency gragh
    # output_dir = join("data", "results", github_repo.name)
    # call_gragh, dependency_gragh = extract_graphs_from_specified_files(
    #         github_repo, raw_info_changed_functions, output_dir)

    # TODO extract existing tests

    # generate tests via LLM
    generated_tests, full_diff_len_fit, filtered_diff_len_nonequal_fit = generate_tests(pr, github_repo, changed_functions)
    old_executions, new_executions, all_covered_modified_stmts_old, all_covered_modified_stmts_new = \
            run_tests_and_feedback(github_repo, cloned_repo_manager, pr, changed_functions, \
                    generated_tests, full_diff_len_fit, filtered_diff_len_nonequal_fit)
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
        if is_crash(old_execution.output) and is_crash(new_execution.output):
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

def run_tests_and_feedback(github_repo, cloned_repo_manager, pr, changed_functions, generated_tests, 
            full_diff_len_fit, filtered_diff_len_nonequal_fit,
            old_executions:list=[], new_executions:list=[], all_covered_modified_stmts_old:list=[], all_covered_modified_stmts_new:list=[], 
            round=0, total_exec_recorded=False):
    ''' 
    A recursive function to run the generated tests and use the feedback for the next round test generation.
    Loop ends when:
     ** reach the specified max round, or 
     ** one or more of the generated tests covers all the changed lines [may impractical], or 
     ** the coverage is not increased.

    Initial generation is marked as round 0, and feedback loops marks start at round 1.
    '''

    if not generated_tests:
        append_event(Event(pr_nb=pr.number, message="Ignoring because no tests were generated"))
        # return old_executions, new_executions, all_covered_modified_stmts_old, all_covered_modified_stmts_new
        return None, None, None, None

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
    old_executions.extend(old_executions_cur_round) # get the executions for all the rounds
    new_executions.extend(new_executions_cur_round)

    execute_tests_on_commit(cloned_repo_manager, pr, old_executions_cur_round, pr.pre_commit, "old")
    execute_tests_on_commit(cloned_repo_manager, pr, new_executions_cur_round, pr.post_commit, "new")

    assert None not in [e.output for e in old_executions_cur_round]

    # analyze coverage during test execution
    fail_to_cover_all_indices = []
    all_uncovered_modified_stmts_info = {"old": [], "new": []}
    all_uncovered_for_further_needs =  {"test_code": [], "old": [], "new": []} # Config.context_version = 5 or 8
    full_coverage_exists = False

    for test_i, (old_execution, new_execution) in enumerate(zip(old_executions_cur_round, new_executions_cur_round)):
        assert old_execution.coverage_percentage is not None
        assert new_execution.coverage_percentage is not None
        
        if total_exec_recorded == False: # Record the event only once
            details = f"All executable/coverable modified lines: Old: {old_execution.all_executable_modified_stmt_ranges}, New: {new_execution.all_executable_modified_stmt_ranges}"
            append_event(CoverageEvent(pr_nb=pr.number, message=f"Diff coverage, all rounds", details=details))
            total_exec_recorded = True

        # Uncovered modified lines are recorded for further checking,
        # Covered modified lines are recorded for later union coverage calculating
        details = (f"Old: {old_execution.coverage_percentage}, New: {new_execution.coverage_percentage}\n"
                f"Uncovered modified lines: Old: {old_execution.all_uncovered_exec_modified_stmt_ranges}, New: {new_execution.all_uncovered_exec_modified_stmt_ranges}\n"
                f"Covered modified lines: Old: {old_execution.all_covered_exec_modified_stmt_ranges}, New: {new_execution.all_covered_exec_modified_stmt_ranges}")
        append_event(CoverageEvent(pr_nb=pr.number, message=f"Diff coverage, {old_execution.code.split(':', 1)[0]}", details=details))

        # Check whether to enter to the feebackloop
        uncovered_modified_stmts_old_exist = False
        for uncover in old_execution.all_uncovered_exec_modified_stmts_num.values():
            if uncover:
                uncovered_modified_stmts_old_exist = True
                break # uncovered statements exist
        
        uncovered_modified_stmts_new_exist = False
        for uncover in new_execution.all_uncovered_exec_modified_stmts_num.values():
            if uncover:
                uncovered_modified_stmts_new_exist = True
                break 

        if uncovered_modified_stmts_old_exist or uncovered_modified_stmts_new_exist:
            fail_to_cover_all_indices.append(test_i+1) # keep the index as absolute number (consistency with the test prefix)
            # deduplicate from all rounds 
            if (old_execution.all_covered_exec_modified_stmt_ranges not in all_covered_modified_stmts_old or \
                    new_execution.all_covered_exec_modified_stmt_ranges not in all_covered_modified_stmts_new): 
                # uncovered_info will be used in feedback prompt.
                if Config.context_version == 5: 
                    all_uncovered_for_further_needs["old"].append(old_execution.all_uncovered_exec_modified_stmts_num)
                    all_uncovered_for_further_needs["new"].append(new_execution.all_uncovered_exec_modified_stmts_num)
                elif Config.context_version == 8:
                    all_uncovered_for_further_needs["test_code"].append(old_execution.code)
                    all_uncovered_for_further_needs["old"].append(old_execution.all_uncovered_exec_modified_stmts_num)
                    all_uncovered_for_further_needs["new"].append(new_execution.all_uncovered_exec_modified_stmts_num)
                else:
                    all_uncovered_modified_stmts_info["old"].append(old_execution.all_uncovered_exec_modified_stmts_num)
                    all_uncovered_modified_stmts_info["new"].append(new_execution.all_uncovered_exec_modified_stmts_num)
        
        # to check if all the rounds and executions cover the same statements
        all_covered_modified_stmts_old.append(old_execution.all_covered_exec_modified_stmt_ranges) # a dict, and each value is a list of ranges
        all_covered_modified_stmts_new.append(new_execution.all_covered_exec_modified_stmt_ranges)

        if Config.feedback_test_generation_prompt_version != 0:
            if uncovered_modified_stmts_old_exist == False and uncovered_modified_stmts_new_exist == False:
                # the test covers all the modified lines
                full_coverage_exists = True
                # still keep checking the coverage information

    if Config.feedback_test_generation_prompt_version != 0: # 0 means to run original Testora, which does not have a feedback loop
        if (fail_to_cover_all_indices and full_coverage_exists == False): # no full coverage exists in all the tests
            is_coverage_changed = True
            if round > 0: # initail round is 0, and feedback loop starts from 1
                # start from the first round of feedback, if the coverage info in not change anymore, stop the feedback loop.
                if (Config.context_version in [5, 8] and not all_uncovered_for_further_needs["old"]) or \
                    (Config.context_version not in [5, 8] and not all_uncovered_modified_stmts_info["old"]):
                    is_coverage_changed = False
                    append_event(Event(pr_nb=pr.number, message=f"Refinement ends after round {round}, coverage info does not change anymore."))
            
            # feedback loop to get new tests that are expected to cover more modified lines.
            if is_coverage_changed == True: # and round < Config.max_round:
                round+=1
                deduplicated_len = 0
                if Config.context_version in [5, 8]: 
                    deduplicated_len = len(all_uncovered_for_further_needs["old"])
                else:
                    deduplicated_len = len(all_uncovered_modified_stmts_info["old"])
                details = f"Tests need to be refined: {fail_to_cover_all_indices}. After deduplicate the uncovered lines, the number of the tests: {deduplicated_len}"
                append_event(CoverageEvent(pr_nb=pr.number, 
                        message=f"Refinement, round {round}, expected to get {len(fail_to_cover_all_indices)} more tests", details=details))
                
                refined_tests = generate_replacement_tests(pr, github_repo, changed_functions, 
                        full_diff_len_fit, filtered_diff_len_nonequal_fit, all_uncovered_modified_stmts_info, round, all_uncovered_for_further_needs)
                run_tests_and_feedback(github_repo, cloned_repo_manager, pr, changed_functions, refined_tests, 
                        full_diff_len_fit, filtered_diff_len_nonequal_fit,
                        old_executions, new_executions, all_covered_modified_stmts_old, all_covered_modified_stmts_new, round, total_exec_recorded)
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


def fetch_and_check_prs():
    project, pr_nb, timestamp = EvalTaskManager.fetch_task()
    while project and pr_nb:
        try:
            # write configuration for every fetched task
            config_dict = {
                k: v for k, v in vars(Config).items()
                if not k.startswith("__") and not callable(v)
            }
            append_event(Event(pr_nb=0, message=f"Configuration: {config_dict}"))

            # check_single_pr(project, pr_nb)
        except TestoraException as e:
            append_event(ErrorEvent(
                pr_nb=pr_nb, message="Caught TestoraError; will continue with next PR", details=str(e)))
            continue

        # store log on disk and into DB
        store_logs()
        log = get_logs_as_json()
        EvalTaskManager.write_results(project, pr_nb, log, timestamp)
        reset_logs()

        project, pr_nb, timestamp = EvalTaskManager.fetch_task()

    print("No more tasks to work on")


def main():
    parser = argparse.ArgumentParser(description="Testora's main entry point")
    parser.add_argument("--db", action="store_true", help="Run on PRs fetched from the database")
    parser.add_argument("--paras", type=ast.literal_eval, help="To help run exepeimenta non-stop")
    parser.add_argument("--project", type=str,
                        help="Project to analyze",
                        choices=["keras", "marshmallow", "pandas", "scipy"])
    parser.add_argument("--pr", type=int, help="PR number to analyze")
    args = parser.parse_args()

    start_logging()
    if args.db:
        # auto-updates the prompt versions
        Config.initial_test_generation_prompt_version, Config.feedback_test_generation_prompt_version, Config.context_version = args.paras
        
        if args.project or args.pr:
            raise ValueError("When using --db, cannot use --project and --pr")
        EvalTaskManager.initialize()
        fetch_and_check_prs()
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

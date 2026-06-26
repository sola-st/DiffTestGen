import argparse
import ast
import json
import random
from os.path import exists
from testora import Config
from testora.llms.LLMCache import LLMCache, LLMEvent
from testora.RegressionFinder import classify_regression, get_repo, is_crash
from testora.evaluation import EvalTaskManager
from testora.execution.TestExecution import TestExecution
from testora.llms.OpenAIGPT import OpenAIGPT
from testora.prompts.SelectExpectedBehaviorPrompt import SelectExpectedBehaviorPrompt
from testora.util.ClassificationResult import Classification
from testora.util.DocstringRetrieval import retrieve_relevant_docstrings
from testora.util.Exceptions import TestoraException
from testora.util.Logs import ClassificationEvent, ErrorEvent, Event, PREvent, PreClassificationEvent, SelectBehaviorEvent, append_event, get_logs_as_json, reset_logs, start_logging, store_logs
from testora.util.PullRequest import PullRequest
from testora.prompts.RegressionClassificationPromptV7 import RegressionClassificationPromptV7 as RegressionClassificationPrompt


def select_expected_behavior(project_name, pr, old_execution, new_execution, docstrings):
    """Ask LLM which of two possible outputs is the expected behavior."""

    attempts_left = 3
    while attempts_left > 0:
        try:
            prompt = SelectExpectedBehaviorPrompt(
            project_name, old_execution.code, old_execution.output, new_execution.output, docstrings)
            raw_answer = llm.query(prompt, temperature=Config.classification_temp)
            append_event(LLMEvent(pr_nb=pr.number,
                                message="Raw answer", content="\n---(next sample)---".join(raw_answer)))
            expected_behavior = prompt.parse_answer(raw_answer)
            append_event(SelectBehaviorEvent(pr_nb=pr.number,
                                                message="Selected expected behavior",
                                                expected_output=expected_behavior))
            return expected_behavior

        except TestoraException as e:
            attempts_left -= 1
            append_event(Event(pr_nb=pr.number,
                               message=f"Error selecting expected behavior: {e}"))
            if attempts_left == 0:
                raise e

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
    append_event(LLMEvent(pr_nb=pr.number,
                          message="Raw answer", content="\n---(next sample)---".join(raw_answer)))
    assert (nb_samples == len(raw_answer))

    all_results = []
    for raw_answer_sample in raw_answer:
        attempts_left = 3
        while attempts_left > 0:
            try:
                classification_result = prompt.parse_answer([raw_answer_sample])
                break
            except TestoraException as e:
                attempts_left -= 1
                append_event(Event(pr_nb=pr.number,
                                   message=f"Error parsing classification answer: {e}"))
                if attempts_left == 0:
                    raise e
        append_event(ClassificationEvent(pr_nb=pr.number,
                                         message="Classification",
                                         test_code=old_execution.code,
                                         old_output=old_execution.output,
                                         new_output=new_execution.output,
                                         classification=classification_result.classification, # type: ignore
                                         classification_explanation=classification_result.classification_explanation, # type: ignore
                                         old_is_crash=is_crash(old_execution.output),
                                         new_is_crash=is_crash(new_execution.output)))
        result = classification_result.classification == Classification.REGRESSION # type: ignore
        all_results.append(result)
    return all_results

def classify_tests(github_repo, cloned_repo_manager, pr, log_file, checked_indices_file):
    '''Read the recorded changed functions and test executions to continue the classification phase.'''

    changed_functions, old_executions_differ_relevant, new_executions_differ_relevant = get_stored_info(log_file)
    if old_executions_differ_relevant:
        valid_indices = set(range(0, len(old_executions_differ_relevant)))

        # exclude the previous checked indices
        checked_indices = set()
        if exists(checked_indices_file):
            with open(checked_indices_file, "r") as f:
                idxs = f.readlines()
            checked_indices = {int(pr) for pr in idxs}
            valid_indices = valid_indices - checked_indices
        
        # use a seed to random get a pair of execution
        reproduce = random.Random(42)  # Fixed seed
        idx = reproduce.choice(list(valid_indices))
        old_execution = old_executions_differ_relevant[idx]
        new_execution = new_executions_differ_relevant[idx]

        # write the newly selected one to file
        with open(checked_indices_file, "a") as f:
            f.writelines(f"{idx}\n")

        # find docstrings
        cloned_repo_of_new_commit = cloned_repo_manager.get_cloned_repo(pr.post_commit)
        docstrings = retrieve_relevant_docstrings(cloned_repo_of_new_commit, new_execution.code)

        # if difference found, classify regression
        assert old_execution.code == new_execution.code
        is_regression_bug = classify_regression(github_repo.name, pr, changed_functions, docstrings, old_execution, new_execution)[0]

        # if classified as regression bug, ask LLM which behavior is expected (to handle coincidental bug fixes)
        if is_regression_bug:
            select_expected_behavior(github_repo.name, pr, old_execution, new_execution, docstrings)
    else:
        append_event(Event(pr_nb=pr.number, message="No tests expose differences from the test generation phase."))


def check_single_pr(project, pr_nb, log_file, checked_indices_file):
    global llm
    llm = LLMCache(OpenAIGPT())

    # reproduce the cloned_repo_manager, git_repo, and pr
    github_repo, cloned_repo_manager = get_repo(project)
    github_pr = github_repo.get_pull(pr_nb)
    pr = PullRequest(github_pr, github_repo, cloned_repo_manager)

    append_event(PREvent(pr_nb=pr_nb,
                         message="Starting to Reduce and Classify Tests",
                         title=pr.github_pr.title, url=pr.github_pr.html_url))

    classify_tests(github_repo, cloned_repo_manager, pr, log_file, checked_indices_file)

    append_event(PREvent(pr_nb=pr_nb,
                         message="Done with Reduction and Classification",
                         title=pr.github_pr.title, url=pr.github_pr.html_url))


def fetch_and_check_prs():
    project, pr_nb = EvalTaskManager.fetch_task()
    while project and pr_nb:
        try:
            check_single_pr(project, pr_nb)
        except TestoraException as e:
            append_event(ErrorEvent(
                pr_nb=pr_nb, message="Caught TestoraError; will continue with next PR", details=str(e)))
            continue

        # store log on disk and into DB
        store_logs()
        log = get_logs_as_json()
        EvalTaskManager.write_results(project, pr_nb, log)
        reset_logs()

        project, pr_nb = EvalTaskManager.fetch_task()

    print("No more tasks to work on")

def get_stored_info(log_file):
    with open(log_file, "r") as f:
        data = json.load(f)
    loaded_data = data[-2] # breakpoint info
    if loaded_data["message"] == "Breakpoint data":
        changed_functions = ast.literal_eval(loaded_data["changed_functions"]) # a list of fully qualified function names
        # Make TestExecution available in eval scope
        old_executions_differ_relevant = eval(loaded_data["old_executions_differ_relevant"], {"TestExecution": TestExecution}) # a list of TestExecution objects.
        new_executions_differ_relevant = eval(loaded_data["new_executions_differ_relevant"], {"TestExecution": TestExecution})

        return changed_functions, old_executions_differ_relevant, new_executions_differ_relevant
    return None, None, None
    
def main():
    parser = argparse.ArgumentParser(description="Testora's reduction and classification entry point")
    parser.add_argument("--project", type=str,
                        help="Project to analyze",
                        choices=["keras", "marshmallow", "pandas", "scipy"])
    parser.add_argument("--pr", type=int, help="PR number to analyze")
    parser.add_argument("--log_file", type=str, help="The parent folder of breakpoint files")
    parser.add_argument("--checked_indices_file", type=str, help="The file which records the checked tests")
    args = parser.parse_args()  

    start_logging()
    '''
    let the first version of continuing classification phase work in this branch.
    Take care of the 'data_storage_folder' in function get_stored_info.
    '''
    if not args.project or not args.pr:
        raise ValueError("Must specify --project and --pr")
    check_single_pr(args.project, args.pr, args.log_file, args.checked_indices_file)
    store_logs()


if __name__ == "__main__":
    main()
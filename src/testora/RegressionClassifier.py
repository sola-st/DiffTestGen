import argparse
import json
import time
from testora.RegressionFinder import check_if_present_in_main, classify_regression, get_repo, reduce_test, select_expected_behavior
from testora.evaluation import EvalTaskManager
from testora.util.DocstringRetrieval import retrieve_relevant_docstrings
from testora.util.Exceptions import TestoraException
from testora.util.Logs import ErrorEvent, Event, PREvent, append_event, get_logs_as_json, reset_logs, start_logging, store_logs
from testora.util.PullRequest import PullRequest
from os.path import join, exists


def reduce_and_classify_tests(github_repo, cloned_repo_manager, pr):
    '''Record changed functions and test executions to restart/continue the classification phase.'''

    changed_functions, old_executions_differ_relevant, new_executions_differ_relevant = get_stored_info(github_repo.name, pr.number)
    if changed_functions:
        for (old_execution, new_execution) in zip(old_executions_differ_relevant, new_executions_differ_relevant):
            '''The following are exactly the remaining steps from RegressionFinder.'''

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
    else:
        append_event(Event(pr_nb=pr.number, message="No tests expose differences from the previous phase."))


def check_single_pr(project, pr_nb):
    # reproduce the cloned_repo_manager, git_repo, and pr
    start = time.time()
    github_repo, cloned_repo_manager = get_repo(project)
    github_pr = github_repo.get_pull(pr_nb)
    pr = PullRequest(github_pr, github_repo, cloned_repo_manager)
    print(f"Duration: {((time.time() - start) * 1000):.2f}")

    append_event(PREvent(pr_nb=pr_nb,
                         message="Starting to Reduce and Classify Tests",
                         title=pr.github_pr.title, url=pr.github_pr.html_url))

    reduce_and_classify_tests(github_repo, cloned_repo_manager, pr)

    append_event(PREvent(pr_nb=pr_nb,
                         message="Done with Reduction and Classification",
                         title=pr.github_pr.title, url=pr.github_pr.html_url))


def fetch_and_check_prs():
    # TODO handle the database overwritten issue
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

def get_stored_info(repo_name, pr_num):
    # 1. for single pr mode, make sure the same as it is in RegressionFinder
    # data_storage_folder = join("data", "results", "breakpoint_data", "iter1") 
    # 2. TODO manage the storage on the DB

    # data_file = join(data_storage_folder, f"{repo_name}_{pr_num}_breakpoint_data.json")
    if exists(f"{repo_name}_{pr_num}_breakpoint_data.json"):
        with open(f"{repo_name}_{pr_num}_breakpoint_data.json", "r") as f:
            loaded_data = json.load(f)
        changed_functions = loaded_data["changed_functions"] # a list of fully qualified function names
        old_executions_differ_relevant = eval(loaded_data["old_executions_differ_relevant"]) # a list of TestExecution objects.
        new_executions_differ_relevant = eval(loaded_data["new_executions_differ_relevant"])

        return changed_functions, old_executions_differ_relevant, new_executions_differ_relevant
    return None, None, None
    
def main():
    parser = argparse.ArgumentParser(description="Testora's reduction and classification entry point")
    parser.add_argument("--db", action="store_true", help="Run on PRs fetched from the database")
    parser.add_argument("--project", type=str,
                        help="Project to analyze",
                        choices=["keras", "marshmallow", "pandas", "scipy"])
    parser.add_argument("--pr", type=int, help="PR number to analyze")
    args = parser.parse_args()

    start_logging()
    if args.db:
        if args.project or args.pr:
            raise ValueError("When using --db, cannot use --project and --pr")
        EvalTaskManager.initialize()
        fetch_and_check_prs()
    else:
        '''
        let the first version of continuing classification phase work in this branch.
        Take care of the 'data_storage_folder' in function get_stored_info.
        '''
        if not args.project or not args.pr:
            raise ValueError("Must specify --project and --pr")
        check_single_pr(args.project, args.pr)
        store_logs()


if __name__ == "__main__":
    main()
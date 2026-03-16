import argparse
import json
from os.path import join, exists
from os import listdir
from chaco.ChaCoCustomizedPullRequest import ChaCoCustomizedPullRequest
from chaco.ChaCoDockerExecutor import ChaCoDockerExecutor
from chaco.ChaCoTestExecution import ChaCoTestExecution
from testora.RegressionFinder import get_repo, simplify_test_execution, validate_output_difference
from testora.util.Exceptions import TestoraException
from testora.util.Logs import BreakpointEvent, ChaCoTestExecutionEvent, ComparisonEvent, CoverageEvent, Event, PREvent, append_event, start_logging, store_logs


def execute_test(test_execution, docker_executor, version):
    # True -> to analyze the coverage info inside the container
    analysis = True
    if version == "main":
        analysis = False # Do not check coverage info when run tests at main. 1. in case the file does not exist in main 2. save time
    raw_output, output = docker_executor.execute_python_code(test_execution.code, analysis, version=version, test_execution=test_execution)
    test_execution.test_idx = test_execution.code.splitlines()[0] # extract test index from the first line of the code (e.g., "# Test test_123" -> "test_123")
    test_execution.output = output
    test_execution.raw_output = raw_output

def execute_tests_on_commit(cloned_repo_manager, pr, test_executions, commit, version):
    cloned_repo = cloned_repo_manager.get_cloned_repo(commit)
    container_name = cloned_repo.container_name
    docker_executor = ChaCoDockerExecutor(pr, container_name,
            project_name=cloned_repo_manager.repo_name,
            coverage_files=pr.non_test_modified_python_files)

    append_event(
        Event(pr_nb=-1, message=f"Compiling {cloned_repo_manager.repo_name} at commit {commit} in container {container_name}"))

    # to trigger re-compilation (e.g., for pandas or scikit-learn)
    docker_executor.execute_python_code(f"import {cloned_repo_manager.module_name}")

    append_event(
        Event(pr_nb=pr.number, message=f"Done with compiling {cloned_repo_manager.repo_name} at commit {commit}"))

    try:
        for test_execution in test_executions:
            execute_test(test_execution, docker_executor, version)
            append_event(ChaCoTestExecutionEvent(pr_nb=pr.number,
                                            message=f"Test execution {test_execution.test_idx} ({version})",
                                            code=test_execution.code,
                                            output=test_execution.output,
                                            raw_output=test_execution.raw_output))
    except RecursionError as e:
        raise TestoraException(f"Exception during merge_tests_and_execute: {str(e)}")

def validate_output_difference(cloned_repo_manager, pr, old_executions, new_executions):
    repeat_difference_found_list = []
    old_executions_repeated = [ChaCoTestExecution(old_exec.code) for old_exec in old_executions]
    new_executions_repeated = [ChaCoTestExecution(new_exec.code) for new_exec in new_executions]

    # re-execute test on old and new version and ignore flaky differences
    execute_tests_on_commit(cloned_repo_manager, pr, old_executions_repeated, pr.pre_commit, "old_flaky")
    execute_tests_on_commit(cloned_repo_manager, pr, new_executions_repeated, pr.post_commit, "new_flaky")

    for old_execution, new_execution, old_execution_repeated, new_execution_repeated in zip(old_executions, new_executions, old_executions_repeated, new_executions_repeated):
        if old_execution.output != old_execution_repeated.output:
            repeat_difference_found_list.append(False)
            continue
        if new_execution.output != new_execution_repeated.output:
            repeat_difference_found_list.append(False)
            continue
        repeat_difference_found_list.append(True)

    return repeat_difference_found_list

class RunChaCoTests():
    def __init__(self, github_repo, cloned_repo_manager, pr):
        self.github_repo = github_repo
        self.cloned_repo_manager = cloned_repo_manager
        self.pr = pr

    def run_tests(self, generated_tests):
        # get changed function names in both old and new version, an union
        changed_functions = self.pr.get_changed_function_names() 
        append_event(Event(pr_nb=self.pr.number, message=f"Run {len(generated_tests)} tests."))
        
        # execute tests
        old_executions = [ChaCoTestExecution(t) for t in generated_tests]
        new_executions = [ChaCoTestExecution(t) for t in generated_tests]

        execute_tests_on_commit(self.cloned_repo_manager, self.pr, old_executions, self.pr.pre_commit, "old")
        execute_tests_on_commit(self.cloned_repo_manager, self.pr, new_executions, self.pr.post_commit, "new")
        
        all_covered_modified_stmts_old = []
        all_covered_modified_stmts_new = []
        for test_i, (old_execution, new_execution) in enumerate(zip(old_executions, new_executions)):
            if test_i == 0: # Record the event only once
                details = f"All executable/coverable modified lines: Old: {old_execution.all_executable_modified_stmt_ranges}, New: {new_execution.all_executable_modified_stmt_ranges}"
                append_event(CoverageEvent(pr_nb=self.pr.number, message=f"Diff coverage, all rounds", details=details))

            # Uncovered modified lines are recorded for further checking,
            # Covered modified lines are recorded for later union coverage calculating
            details = (f"Old: {old_execution.coverage_percentage}, New: {new_execution.coverage_percentage}\n"
                    f"Uncovered modified lines: Old: {old_execution.all_uncovered_exec_modified_stmt_ranges}, New: {new_execution.all_uncovered_exec_modified_stmt_ranges}\n"
                    f"Covered modified lines: Old: {old_execution.all_covered_exec_modified_stmt_ranges}, New: {new_execution.all_covered_exec_modified_stmt_ranges}")
            append_event(CoverageEvent(pr_nb=self.pr.number, message=f"Diff coverage, {old_execution.code.split(':', 1)[0]}", details=details))   

            all_covered_modified_stmts_old.append(old_execution.all_covered_exec_modified_stmt_ranges) # a dict, and each value is a list of ranges
            all_covered_modified_stmts_new.append(new_execution.all_covered_exec_modified_stmt_ranges)                                           
    
        append_event(Event(pr_nb=self.pr.number, message=f"Check differences for {len(old_executions)} pairs of executions."))

        # to compile the dev only once for all flaky tests
        old_executions_to_flaky = []
        new_executions_to_flaky = []
        flaky_indices = []

        # to separate the test genration and classification phase, here we store the breakpoint data.
        old_executions_differ_relevant = []
        new_executions_differ_relevant = []

        # step 1: iter-through to get "both failed" and the xxx_to_flaky executions
        for i, (old_execution, new_execution, old_covered, new_covered) in enumerate(
                zip(old_executions, new_executions, all_covered_modified_stmts_old, all_covered_modified_stmts_new)):
            assert old_execution.output is not None
            assert new_execution.output is not None

            # check for behavioral differences
            difference_found = old_execution.output != new_execution.output

            if difference_found:
                old_executions_to_flaky.append(old_execution)
                new_executions_to_flaky.append(new_execution)
                flaky_indices.append(i)
            else:
                append_event(ComparisonEvent(pr_nb=self.pr.number, 
                        message=f"Same output\nCovered lines in old: {old_covered}, Covered lines in new: {new_covered}",
                        test_code=old_execution.code, old_output=old_execution.output, new_output=new_execution.output))
        
        # step 2: to handle the xxx_to_flaky executions
        # double-check differences by re-executing the tests
        if old_executions_to_flaky:
            flaky_change_found_list = validate_output_difference(self.cloned_repo_manager, self.pr, old_executions_to_flaky, new_executions_to_flaky)
            for flaky_change_found, idx in zip(flaky_change_found_list, flaky_indices):
                if flaky_change_found == False:  # flaky test gets the same output as before, consider as the same
                    append_event(ComparisonEvent(pr_nb=self.pr.number, 
                            message=f"Same output\nCovered lines in old: {all_covered_modified_stmts_old[idx]}, Covered lines in new: {all_covered_modified_stmts_new[idx]}",
                            test_code=old_executions[idx].code, old_output=old_executions[idx].output, new_output=new_executions[idx].output))
                    continue

                append_event(ComparisonEvent(pr_nb=self.pr.number,
                        message=f"Different outputs\nCovered lines in old: {all_covered_modified_stmts_old[idx]}, Covered lines in new: {all_covered_modified_stmts_new[idx]}",
                        test_code=old_executions[idx].code, old_output=old_executions[idx].output, new_output=new_executions[idx].output))
                
                simplified_old_execution = simplify_test_execution(old_executions[idx])
                simplified_new_execution = simplify_test_execution(new_executions[idx])
                old_executions_differ_relevant.append(simplified_old_execution)
                new_executions_differ_relevant.append(simplified_new_execution)

        # When need to further classify the different outputs, read the test info from stored files.
        # organize and write the breakpoint data to a local/db file
        if old_executions_differ_relevant:
            append_event(BreakpointEvent(pr_nb=self.pr.number, message=f"Breakpoint data", changed_functions=f"{changed_functions}", 
                    old_executions_differ_relevant=f"{old_executions_differ_relevant}", new_executions_differ_relevant=f"{new_executions_differ_relevant}"))
        # else: # no different outputs

def get_generated_tests(project, pr_nb):
    # read chaco genrated tests
    generated_tests = []

    test_folder = join("data", "chaco_tests", project, f"{pr_nb}")
    if exists(test_folder): # otherwise, no tests for the pr
        test_files = listdir(test_folder)
        for file in test_files:
            with open(join(test_folder, file), "r") as f:
                test_code = f.readlines()
                test_idx = file.split("_")[1].replace(".py", "") # extract test index from filename (e.g., "test_123.py" -> "test_123")
                generated_tests.append(f"# Test_{test_idx}\n" + "".join(test_code))
    
    return generated_tests
    
def main():
    parser = argparse.ArgumentParser(description="ChaCo's entry point")
    parser.add_argument("--project", type=str, help="Project to analyze", choices=["pandas", "scipy"])
    parser.add_argument("--pr_nb", type=int, help="PR number to analyze")
    args = parser.parse_args()

    if not args.project or not args.pr_nb:
        raise ValueError("Must specify --project and --pr_nb")
    
    start_logging()

    generated_tests = get_generated_tests(args.project, args.pr_nb)
    if not generated_tests:
        append_event(Event(pr_nb=args.pr_nb, message=f"Ignoring because no tests were recorded."))
        return 
    
    github_repo, cloned_repo_manager = get_repo(args.project)
    github_pr = github_repo.get_pull(args.pr_nb)
    pr = ChaCoCustomizedPullRequest(github_pr, github_repo, cloned_repo_manager)

    # check the PR
    append_event(PREvent(pr_nb=args.pr_nb,
                         message="Starting to check PR",
                         title=pr.github_pr.title, url=pr.github_pr.html_url))

    runner = RunChaCoTests(github_repo, cloned_repo_manager, pr, )
    runner.run_tests(generated_tests)

    append_event(PREvent(pr_nb=args.pr_nb,
                         message="Done with PR",
                         title=pr.github_pr.title, url=pr.github_pr.html_url))
    store_logs()


if __name__=="__main__":
    main()
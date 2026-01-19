from datetime import datetime
import json
from os.path import join, exists
from os import listdir
from chacho.ChaCoCustomizedPullRequest import ChaCoCustomizedPullRequest
from testora.RegressionFinder import execute_tests_on_commit, get_repo, simplify_test_execution, validate_output_difference
from testora.execution.TestExecution import TestExecution
from testora.prompts.RuntimeErrorsFixingPrompt import extract_error_type
from testora.util.Logs import ComparisonEvent, CoverageEvent, Event, PREvent, append_event, reset_logs, start_logging, events

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
        old_executions = [TestExecution(t) for t in generated_tests]
        new_executions = [TestExecution(t) for t in generated_tests]

        execute_tests_on_commit(self.cloned_repo_manager, self.pr, old_executions, self.pr.pre_commit, "old")
        execute_tests_on_commit(self.cloned_repo_manager, self.pr, new_executions, self.pr.post_commit, "new")

        # early stop for PRs with no executable modified lines
        if ("(0/0)" in old_executions[0].coverage_percentage) and ("(0/0)" in new_executions[0].coverage_percentage):
            append_event(Event(pr_nb=self.pr.number, message="Ignoring because no executable modified code lines/statements."))
            # return old_executions, new_executions, all_covered_modified_stmts_old, all_covered_modified_stmts_new
            return 
        
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
            old_error_type = extract_error_type(old_execution.output)
            new_error_type = extract_error_type(new_execution.output)

            if old_error_type == new_error_type:
                if old_error_type != None: # same error type exists in both version
                    append_event(ComparisonEvent(pr_nb=self.pr.number,
                        message=f"Both tests failed with error {old_error_type}, considering them the same\nCovered lines in old: {old_covered}, Covered lines in new: {new_covered}",
                        test_code=old_execution.code, old_output=old_execution.output,
                        new_output=new_execution.output))
                else: # no errors, go for flaky tests
                    if difference_found:
                        old_executions_to_flaky.append(old_execution)
                        new_executions_to_flaky.append(new_execution)
                        flaky_indices.append(i)
                    else:
                        append_event(ComparisonEvent(pr_nb=self.pr.number, 
                                message=f"Same output\nCovered lines in old: {old_covered}, Covered lines in new: {new_covered}",
                                test_code=old_execution.code, old_output=old_execution.output, new_output=new_execution.output))
            else:
                # 1. error exists in one version,
                # 2. two different error types
                append_event(ComparisonEvent(pr_nb=self.pr.number,
                        message=f"Different outputs\nCovered lines in old: {old_covered}, Covered lines in new: {new_covered}",
                        test_code=old_execution.code, old_output=old_execution.output, new_output=new_execution.output))
                
                simplified_old_execution = simplify_test_execution(old_execution)
                simplified_new_execution = simplify_test_execution(new_execution)
                old_executions_differ_relevant.append(simplified_old_execution)
                new_executions_differ_relevant.append(simplified_new_execution)
        
        # step 2: to handle the xxx_to_flaky executions
        # double-check differences by re-executing the tests
        flaky_change_found_list = validate_output_difference(self.cloned_repo_manager, self.pr, old_executions_to_flaky, new_executions_to_flaky)
        for flaky_change_found, idx in zip(flaky_change_found_list, flaky_indices):
            if flaky_change_found == False: # flaky test gets the same output as before
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
            breakpoint_data_str = {
                "changed_functions": changed_functions,
                "old_executions_differ_relevant": f"{old_executions_differ_relevant}",
                "new_executions_differ_relevant": f"{new_executions_differ_relevant}"
            }

            with open(f"{self.github_repo.name}_{self.pr.number}_breakpoint_data.json", "w") as f:
                json.dump(breakpoint_data_str, f, indent=2)

def get_generated_tests(project, pr_nb):
    # read chaco genrated tests
    generated_tests = []

    test_folder = join("data", "chaco_tests", project, f"{pr_nb}")
    if exists(test_folder): # otherwise, no tests for the pr
        test_files = listdir(test_folder)
        for file in test_files:
            with open(join(test_folder, file), "r") as f:
                test_code = f.readlines()
                generated_tests.append("".join(test_code))
    
    return generated_tests
    
def main(project, pr_nb):
    generated_tests = get_generated_tests(project, pr_nb)
    if not generated_tests:
        append_event(Event(pr_nb=pr_nb, message=f"Ignoring because no tests were recorded."))
        return 
    
    github_repo, cloned_repo_manager = get_repo(project)
    github_pr = github_repo.get_pull(pr_nb)
    pr = ChaCoCustomizedPullRequest(github_pr, github_repo, cloned_repo_manager)

    # check the PR
    append_event(PREvent(pr_nb=pr_nb,
                         message="Starting to check PR",
                         title=pr.github_pr.title, url=pr.github_pr.html_url))

    runner = RunChaCoTests(github_repo, cloned_repo_manager, pr, )
    runner.run_tests(generated_tests)

    append_event(PREvent(pr_nb=pr_nb,
                         message="Done with PR",
                         title=pr.github_pr.title, url=pr.github_pr.html_url))

def store_pr_log(pr):
    global last_file_stored_to
    timestamp = datetime.now().isoformat()
    event_dicts = [evt.dict() for evt in events]
    out_file = f"logs_{pr}_{timestamp}.json"
    json.dump(event_dicts, open(out_file, "w"), indent=2)
    last_file_stored_to = out_file


if __name__=="__main__":
    with open(".target_project", "r") as f:
        target_project = f.read().strip()

    pr_meta = {
        "pandas": 29,
        "scipy": 46
    }
    # pr_meta = {
    #     "pandas": 45,
    #     "scipy": 50
    # }
    pr_file = join("data", "meta", f"chaco_{target_project}_unique_{pr_meta[target_project]}.txt")

    with open(pr_file, "r") as f:
        prs = f.readlines()
    pr_list = [int(pr) for pr in prs]
    for pr in pr_list:
        reset_logs()
        start_logging()
        main(target_project, pr)
        store_pr_log(pr)
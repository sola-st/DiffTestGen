import argparse
import ast
import json
import random
from os.path import exists
from testora import Config
from testora.llms.LLMCache import LLMCache, LLMEvent
from testora.RegressionFinder import get_repo, is_crash
from testora.execution.TestExecution import TestExecution
from testora.llms.OpenAIGPT import OpenAIGPT
from testora.prompts.SelectExpectedBehaviorPrompt import SelectExpectedBehaviorPrompt
from testora.util.ClassificationResult import Classification
from testora.util.DocstringRetrieval import retrieve_relevant_docstrings
from testora.util.Exceptions import TestoraException
from testora.util.Logs import ClassificationEvent, Event, PREvent, PreClassificationEvent, SelectBehaviorEvent, append_event, start_logging, store_logs
from testora.util.PullRequest import PullRequest
from testora.prompts.RegressionClassificationPromptV7 import RegressionClassificationPromptV7 as RegressionClassificationPrompt


class RegressionClassifier:
    def __init__(self):
        self.llm = LLMCache(OpenAIGPT())

        self.pr = None
        self.cloned_repo_manager = None
        self.project_name = None
        self.changed_functions = None
        self.checked_indices_file = None
        self.checked_indices = set()
        self.top_k = 0
        self.old_executions_differ_relevant = None
        self.new_executions_differ_relevant = None


    def select_expected_behavior(self, old_execution, new_execution, docstrings):
        """Ask LLM which of two possible outputs is the expected behavior."""

        attempts_left = 3
        while attempts_left > 0:
            try:
                prompt = SelectExpectedBehaviorPrompt(
                self.project_name, old_execution.code, old_execution.output, new_execution.output, docstrings)
                raw_answer = self.llm.query(prompt, temperature=Config.classification_temp)
                append_event(LLMEvent(pr_nb=self.pr.number,
                                    message="Raw answer", content="\n---(next sample)---".join(raw_answer)))
                expected_behavior = prompt.parse_answer(raw_answer)
                append_event(SelectBehaviorEvent(pr_nb=self.pr.number,
                                                    message="Selected expected behavior",
                                                    expected_output=expected_behavior))
                return expected_behavior

            except TestoraException as e:
                attempts_left -= 1
                append_event(Event(pr_nb=self.pr.number,
                                message=f"Error selecting expected behavior: {e}"))
                if attempts_left == 0:
                    raise e

    def classify_regression(self, docstrings, old_execution, new_execution, no_cache=False, nb_samples=1):
        append_event(PreClassificationEvent(pr_nb=self.pr.number,
                                            message="Pre-classification",
                                            test_code=old_execution.code,
                                            old_output=old_execution.output,
                                            new_output=new_execution.output))

        prompt = RegressionClassificationPrompt(
            self.project_name, self.pr, self.changed_functions, docstrings, old_execution.code, old_execution.output, new_execution.output)
        raw_answer = self.llm.query(prompt,
                            temperature=Config.classification_temp,
                            no_cache=no_cache,
                            nb_samples=nb_samples)
        append_event(LLMEvent(pr_nb=self.pr.number,
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
                    append_event(Event(pr_nb=self.pr.number,
                                    message=f"Error parsing classification answer: {e}"))
                    if attempts_left == 0:
                        raise e
            append_event(ClassificationEvent(pr_nb=self.pr.number,
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

    def classify_tests(self):
        '''Read the recorded changed functions and test executions to continue the classification phase.'''

        if self.old_executions_differ_relevant:
            indices = []
            valid_indices = set(range(0, len(self.old_executions_differ_relevant)))
            if len(valid_indices) < self.top_k: 
                # to check all the tests
                indices = valid_indices
            else:
                # exclude the previous checked indices
                if self.checked_indices:
                    valid_indices = valid_indices - self.checked_indices
                
                # use a seed to random get a pair of execution
                reproduce = random.Random(42)  # Fixed seed
                # idx = reproduce.choice(list(valid_indices))
                indices = sorted(reproduce.sample(list(valid_indices), self.top_k))
                self.old_executions_differ_relevant = [self.old_executions_differ_relevant[i] for i in indices]
                self.new_executions_differ_relevant = [self.new_executions_differ_relevant[i] for i in indices]

            # write the newly selected one to file
            with open(self.checked_indices_file, "a") as f:
                f.writelines("\n".join(map(str, indices)))

            for old_execution, new_execution in zip(self.old_executions_differ_relevant, self.new_executions_differ_relevant):
                # find docstrings
                cloned_repo_of_new_commit = self.cloned_repo_manager.get_cloned_repo(self.pr.post_commit)
                docstrings = retrieve_relevant_docstrings(cloned_repo_of_new_commit, new_execution.code)

                # if difference found, classify regression
                assert old_execution.code == new_execution.code
                is_regression_bug = self.classify_regression(docstrings, old_execution, new_execution)[0]

                # if classified as regression bug, ask LLM which behavior is expected (to handle coincidental bug fixes)
                if is_regression_bug:
                    self.select_expected_behavior(old_execution, new_execution, docstrings)
        else:
            append_event(Event(pr_nb=self.pr.number, message="No tests expose differences from the test generation phase."))


    def check_single_pr(self):
        # reproduce the cloned_repo_manager, git_repo, and pr
        github_repo, self.cloned_repo_manager = get_repo(self.project)
        github_pr = github_repo.get_pull(self.pr_nb)
        self.pr = PullRequest(github_pr, github_repo, self.cloned_repo_manager)

        append_event(PREvent(pr_nb=self.pr_nb,
                            message="Starting to Classify Tests",
                            title=self.pr.github_pr.title, url=self.pr.github_pr.html_url))

        self.classify_tests()

        append_event(PREvent(pr_nb=self.pr_nb,
                            message="Done with Classification",
                            title=self.pr.github_pr.title, url=self.pr.github_pr.html_url))
        
    
    def main(self):
        parser = argparse.ArgumentParser(description="Testora's classification entry point")
        parser.add_argument("--project", type=str,
                            help="Project to analyze",
                            choices=["keras", "marshmallow", "pandas", "scipy"])
        parser.add_argument("--pr", type=int, help="PR number to analyze")
        parser.add_argument("--log_file", type=str, help="The parent folder of breakpoint files")
        parser.add_argument("--checked_indices_file", type=str, help="The file which records the checked tests")
        parser.add_argument("--top_k", type=int, help="How many test to check for each PR")
        args = parser.parse_args()  

        # pre check befor start logging
        if exists(args.checked_indices_file):
            with open(args.checked_indices_file, "r") as f:
                idxs = f.readlines()
            self.checked_indices = {int(pr) for pr in idxs}
        
        self.changed_functions, self.old_executions_differ_relevant, self.new_executions_differ_relevant = get_stored_info(args.log_file)
        
        if len(self.checked_indices) < len(self.old_executions_differ_relevant):
            if not args.project or not args.pr:
                raise ValueError("Must specify --project and --pr")
            
            self.project = args.project
            self.pr_nb = args.pr
            self.top_k = args.top_k
            self.checked_indices_file = args.checked_indices_file

            start_logging()
            self.check_single_pr()
            store_logs()
        # else: # all tests have been checked, not to write any logs.

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


if __name__ == "__main__":
    RegressionClassifier().main()
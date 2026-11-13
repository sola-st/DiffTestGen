import argparse

from testora import Config
from testora.llms.LLMCache import LLMCache, LLMEvent
from testora.llms.OpenAIGPT import OpenAIGPT
from testora.prompts.BehaviorChangeClassificationPrompt import BehaviorChangeClassificationPrompt
from testora.RegressionFinder import get_repo
from testora.util.Logs import BehaviorChangeClassificationEvent, PREvent, append_event, start_logging, store_logs
from testora.util.PullRequest import PullRequest


class BehaviorChangeClassifier:
    def __init__(self):
        self.llm = LLMCache(OpenAIGPT())
        self.project = None
        self.pr_number = None
        self.pr = None
        self.cloned_repo_manager = None

    def classify_pr(self):
        changed_functions, old_bodies, new_bodies = self.pr.get_changed_function_names_and_bodies()
        prompt = BehaviorChangeClassificationPrompt(self.project, self.pr, changed_functions, old_bodies, new_bodies)
        raw_answers = self.llm.query(prompt, temperature=Config.classification_temp, nb_samples=1)
        if len(raw_answers) != 1:
            raise RuntimeError(f"Expected one behavior-change answer, received {len(raw_answers)}.")

        append_event(LLMEvent(pr_nb=self.pr.number, message="Raw behavior change classification answer", content=raw_answers[0]))
        answer = prompt.parse_answer(raw_answers)
        append_event(BehaviorChangeClassificationEvent(
            pr_nb=self.pr.number,
            message="Behavior change classification result",
            behavior_change=answer["behavior_change"],
            summary=answer["summary"],
            evidence=answer["evidence"],
        ))
        return answer

    def check_single_pr(self):
        github_repo, self.cloned_repo_manager = get_repo(self.project)
        github_pr = github_repo.get_pull(self.pr_number)
        self.pr = PullRequest(github_pr, github_repo, self.cloned_repo_manager)

        append_event(PREvent(pr_nb=self.pr_number, message="Starting behavior change classification", title=self.pr.github_pr.title, url=self.pr.github_pr.html_url))
        answer = self.classify_pr()
        append_event(PREvent(pr_nb=self.pr_number, message="Done with behavior change classification", title=self.pr.github_pr.title, url=self.pr.github_pr.html_url))
        return answer

    def main(self):
        parser = argparse.ArgumentParser(description="Classify whether a pull request changes code behavior")
        parser.add_argument("--project", type=str, required=True, choices=["keras", "marshmallow", "pandas", "scipy"], help="Project containing the pull request")
        parser.add_argument("--pr", type=int, required=True, help="Pull request number to analyze")
        args = parser.parse_args()

        self.project = args.project
        self.pr_number = args.pr
        start_logging()
        self.check_single_pr()
        store_logs()


if __name__ == "__main__":
    BehaviorChangeClassifier().main()

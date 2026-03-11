import argparse
# import ast
from github import Github, Auth
from testora.util import SphinxOnlyPR
from testora.util.ClonedRepoManager import ClonedRepoManager
from testora.util.SphinxOnlyPR import SphinxOnlyPR
from testora.util.Logs import (start_logging, store_logs)


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
    pr = SphinxOnlyPR(github_pr, github_repo, cloned_repo_manager)

def main():
    parser = argparse.ArgumentParser(description="Testora's main entry point")
    # parser.add_argument("--prs", type=ast.literal_eval, help="To help isolate the running among different containers")
    parser.add_argument("--project", type=str,
                        help="Project to analyze",
                        choices=["keras", "marshmallow", "pandas", "scipy"])
    parser.add_argument("--pr", type=int, help="PR number to analyze")
    args = parser.parse_args()

    if not args.project or not args.pr:
        raise ValueError("Must specify --project and --pr")
    
    start_logging()
    check_single_pr(args.project, args.pr)
    store_logs()


if __name__ == "__main__":
    main()

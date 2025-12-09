from github import Github
import csv
from os.path import join


token = open(".github_token", "r").read().strip()
project_names = ["marshmallow", "pandas", "scipy"]
nums = ["53", "128", "129"]

for project_name, num in zip(project_names, nums):
    if project_name == "pandas":
        full_repo_name = "pandas-dev/pandas"
    elif project_name == "scipy":
        full_repo_name = "scipy/scipy"
    elif project_name == "keras":
        full_repo_name = "keras-team/keras"
    elif project_name == "marshmallow":
        full_repo_name = "marshmallow-code/marshmallow"


    pr_list = [] 
    with open(f"data/meta/pr_nums/{project_name}_PRs_subset{num}.txt", "r") as f:
        prs = f.readlines()
        pr_list = [int(pr) for pr in prs]

    output_csv_file = join("local", "a_keyword_check", f"prs_output_{project_name}.csv")

    g = Github(token)
    github_repo = g.get_repo(full_repo_name)

    rows = []

    for pr_nb in pr_list:
        try:
            github_pr = github_repo.get_pull(pr_nb)
            rows.append({
                "pr_number": pr_nb,
                "title": github_pr.title,
                "description": github_pr.body or "",
            })
            # print(f"Fetched PR #{pr_nb}")
        except Exception as e:
            print(f"Failed to fetch PR #{pr_nb}: {e}")

    with open(output_csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["pr_number", "title", "description"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} PRs to {output_csv_file}")

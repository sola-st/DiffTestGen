import random


def main(target_projects, target_num):
    random.seed(29)

    for target_project in target_projects:
        with open(f"data/{target_project}_PRs.txt", "r") as f:
            prs = f.readlines()

        subset = random.sample(prs, target_num)
        with open(f"data/{target_project}_PRs_subset{target_num}.txt", "w") as f:
            f.writelines("\n".join([pr.strip() for pr in subset]))

if __name__=="__main__":
    target_projects = ["scipy", "marshmallow", "pandas", "keras"]
    target_num = 15
    main(target_projects, target_num)
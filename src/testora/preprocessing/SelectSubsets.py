'''First time for get a random set of PRs.'''
import random


# def main(target_projects, target_num):
#     random.seed(29)
#     data_base_folder = "data/meta/pr_nums"

#     for target_project in target_projects:
#         with open(f"{data_base_folder}/{target_project}_PRs.txt", "r") as f:
#             prs = f.readlines()

#         subset = random.sample(prs, target_num)
#         with open(f"{data_base_folder}/{target_project}_PRs_subset{target_num}.txt", "w") as f:
#             f.writelines("\n".join([pr.strip() for pr in subset]))

# if __name__=="__main__":
#     target_projects = ["scipy", "marshmallow", "pandas", "keras"]
#     target_num = 15
#     main(target_projects, target_num)


'''More ramdom PRs, but deduplicated with the ones extracted before.'''
def main(target_projects, target_num):
    random.seed(29)
    data_base_folder = "data/meta/pr_nums"

    for target_project in target_projects:
        collected = []
        with open(f"{data_base_folder}/{target_project}_PRs.txt", "r") as f:
            prs = f.readlines()

        with open(f"{data_base_folder}/{target_project}_PRs_subset10.txt", "r") as f:
            exist_prs = f.readlines()

        random.shuffle(prs)
        for pr in prs:
            if pr not in exist_prs:
                collected.append(pr)
                if len(collected) == target_num:
                    break

        with open(f"{data_base_folder}/{target_project}_PRs_subset{target_num}.txt", "w") as f:
            f.writelines("\n".join([pr.strip() for pr in collected]))

if __name__=="__main__":
    target_projects = ["pandas"]
    target_num = 20
    main(target_projects, target_num)
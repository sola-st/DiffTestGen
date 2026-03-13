from os.path import join


target_projects = ["scipy", "pandas"]
maps = [["scipy", 129, 18], ["pandas", 128, 16]]
chaco_pr_folder = join("data", "meta", "chaco_prs")

for item in maps:
    target_project, pr_num_bigger, pr_num = item
    with open(join("data", "meta", "pr_nums_checks", f"{target_project}_PRs_subset{pr_num_bigger}.txt"), "r") as f:
        prs = f.readlines()
        pr_list_bigger = [int(pr) for pr in prs]

    with open(join(chaco_pr_folder, f"chaco_{target_project}_{pr_num}.txt"), "r") as f:
        prs2 = f.readlines()
        pr_list_chaco = [int(pr) for pr in prs2]

    unique = []
    common = []
    for pr in pr_list_chaco:
        if not pr in pr_list_bigger:
            unique.append(pr)
        else:
            common.append(pr)

    if common:
        with open(join(chaco_pr_folder, f"{target_project}_common_{len(common)}.txt"), "w") as f:
            f.writelines("\n".join(map(str, common)))
        
        with open(join(chaco_pr_folder, f"{target_project}_unique_{len(unique)}.txt"), "w") as f:
            f.writelines("\n".join(map(str, unique)))
    else:
        print(f"-- No common PRs for {target_project}.")
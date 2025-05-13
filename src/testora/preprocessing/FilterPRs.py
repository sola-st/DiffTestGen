import json
from os import listdir, makedirs
import os
from os.path import join
import shutil


def get_numerator_and_denominator_from_str(cov_str):
    tmp = cov_str.split("(")[1].replace(")", "")
    numerator_str, denominator_str = tmp.split("/")

    return int(numerator_str)


def main(target_projects):
    to_write = ""

    for target_project in target_projects:
        # take care of the path, make sure the folders are accessible
        # results_03_2025 is from the data release from Testora
        target_folder = join("results_03_2025", target_project)
        exclude_ignores = join("exclude_ignores", target_project)
        executable = join("executable", target_project)
        makedirs(exclude_ignores, exist_ok=True)
        makedirs(executable, exist_ok=True)

        selected1 = 0
        selected2 = 0
        may_non_executable = []
        remained_pr_nums = []

        files = listdir(target_folder)
        for file in files:
            if os.stat(join(target_folder, file)).st_size > 1000: 
                shutil.copyfile(join(target_folder, file), join(exclude_ignores, file))
                selected1 +=1

                all_old_covered = 0
                all_new_covered = 0
                with open(join(target_folder, file), "r") as f:
                    info = json.load(f)
            
                for info_block in info:
                    if "details" in info_block.keys():
                        old_str, new_str = info_block["details"].split(",")
                        old_covered = get_numerator_and_denominator_from_str(old_str)
                        all_old_covered += old_covered
                        new_covered = get_numerator_and_denominator_from_str(new_str)
                        all_new_covered += new_covered
                if all_old_covered == 0 and all_new_covered == 0:
                    may_non_executable.append(f"{target_project}/{file}")
                else:
                    selected2 += 1
                    shutil.copyfile(join(target_folder, file), join(executable, file))
                    remained_pr_nums.append(file.split("_")[0])
        
        with open(f"data/{target_project}_PRs.txt", "w") as f:
            f.writelines("\n".join(remained_pr_nums))

        print(f"Filtering for project {target_project} done.")
        print(f"Not ignored: {selected1}")
        print(f"Executable: {selected2}\n")
        to_write += f"Not ignored: {selected1}\nExecutable: {selected2}\nNon-executable: {may_non_executable}\n\n"
    
    with open("data/results/filtered_details.txt", "w") as f:
        f.writelines(to_write)


if __name__=="__main__":
    target_projects = ["scipy", "marshmallow", "pandas", "keras"]
    main(target_projects)
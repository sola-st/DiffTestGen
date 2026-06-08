from os.path import join
from os import listdir
import json


projects = ["pandas", "scipy"]
for project in projects:
    project_level_usage = {}
    project_level_usage.update({"overall": {}})
    project_level_usage.update({"avg": {}})
    total = 0
    input = 0
    output = 0

    num = 16
    if project == "scipy":
        num = 18

    pr_file =f"chaco_{project}_{num}.txt"
    with open(pr_file, "r") as f:
        prs = f.readlines()
        pr_list = [int(pr) for pr in prs]

    metadata_folder = f"{project}_eval/{project}/augmented_discussion"
    pr_files = listdir(metadata_folder)
    for file in pr_files:
        pr_num = int(file.replace(".json", ""))
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        if pr_num in pr_list:
            with open(join(metadata_folder, file), "r") as f:
                info = json.load(f)
            if "token_usage" in info.keys():
                token_usage_list = info["token_usage"]
                for usage in token_usage_list:
                    input_tokens += usage["prompt_tokens"]
                    output_tokens += usage["completion_tokens"]
                    total_tokens += usage["total_tokens"]
            else:
                input_tokens = None
                output_tokens = None
                total_tokens = None

            if input_tokens:
                input += input_tokens
                output += output_tokens
                total += total_tokens
        
            project_level_usage.update({pr_num:{
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens
            }})
    
    # update project level overall
    project_level_usage["overall"].update({"input_tokens": input})
    project_level_usage["overall"].update({"output_tokens": output})
    project_level_usage["overall"].update({"total_tokens": total})

    # update project level average
    num_checked_prs = len(project_level_usage.keys()) - 2
    project_level_usage["avg"].update({"input_tokens": input / num_checked_prs})
    project_level_usage["avg"].update({"output_tokens": output / num_checked_prs})
    project_level_usage["avg"].update({"total_tokens": total / num_checked_prs})

    result_file = f"{project}_token_usage_{num_checked_prs}.json"
    with open(result_file, "w") as f:
        json.dump(project_level_usage, f, indent=4)

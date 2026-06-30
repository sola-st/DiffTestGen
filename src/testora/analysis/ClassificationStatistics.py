import json
from os import listdir
from os.path import join

iteration = 0
model = "gpt-5-mini-2025-08-07"
classification_folder = join("data", "results", "classification", model, f"iter_{iteration}", "classification_difftestgen")
projects = ["keras", "marshmallow", "pandas", "scipy"] # ["marshmallow"]
for pro in projects:
    regressions = {}
    classified_tests = 0

    project_folder = join(classification_folder, pro)
    files = listdir(project_folder)

    for log_file in files:
        with open(join(project_folder, log_file), "r") as f:
            result_json = json.load(f)
            pr = log_file.split("_", 1)[0]
            for entry in result_json:
                if entry["message"] == "Classification":
                    classified_tests += 1
                    # print(entry["classification"]) # "intended_change" or "regression"
                    if entry["classification"] == "regression":
                        test = entry["test_code"].split("\n", 1)[0]
                        if pr in regressions.keys():
                            regressions[pr]["regression_num"] += 1
                            regressions[pr]["tests"].append(test)
                        else:
                            regressions.update({
                                pr: {
                                    "regression_num": 1,
                                    "tests": [test]
                                }
                            })
    print(f"{pro} with {classified_tests} classified tests.")
    if regressions:
        result_file = join(classification_folder, f"{pro}.json")
        with open(result_file, "w") as f:
            json.dump(regressions, f, indent=4)
    else:
        print(f"No regressions found for {pro}.")
        

                            
import json
from os import listdir, makedirs
from os.path import join, isdir

from matplotlib import pyplot as plt
from testora.visualization.CoverageComparison import CoverageComparison


def get_numerator_and_denominator_from_str(cov_str):
    tmp = cov_str.split("(")[1].replace(")", "")
    numerator_str, denominator_str = tmp.split("/")
    return int(numerator_str), int(denominator_str)

def get_overall_cov_rate(cov_pair_dict):
    old = cov_pair_dict["old"]
    new = cov_pair_dict["new"]
    numerator_old, denominator_old = get_numerator_and_denominator_from_str(old)
    numerator_new, denominator_new = get_numerator_and_denominator_from_str(new)

    # old + new
    numerator_all = numerator_old + numerator_new
    denominator_all = denominator_old + denominator_new
    overall_cov = numerator_all / denominator_all if denominator_all > 0 else 1
    overall_cov_str = f"{overall_cov:.2%}"

    return overall_cov_str

def get_overall_coverage_rates(all_data):
    overall_data = [] # element is approach level

    for approach_data in all_data: # single approach data
        pr_level_rates = []
        for pr_rec in approach_data:
            # for every PR, get an aggregated coverage rate.
            pr_num = list(pr_rec.keys())[-1]
            last_round_cov_pair_dict = {}

            if "Feedback" in pr_rec[pr_num].keys() and \
                    "--" not in json.dumps(pr_rec[pr_num]["Feedback"]["R-1"]):
                feedback_rec = pr_rec[pr_num]["Feedback"]
                key_idx = -1
                last_round_key = list(feedback_rec.keys())[key_idx]
                last_round_cov_pair_dict = feedback_rec[last_round_key]
                while "--" in json.dumps(last_round_cov_pair_dict):
                    key_idx -= 1
                    last_round_key = list(feedback_rec.keys())[key_idx]
                    last_round_cov_pair_dict = feedback_rec[last_round_key]
            else:
                last_round_cov_pair_dict = pr_rec[pr_num]["Initial"]["R-0"]
            
            # the highest coverage for a pr, a pr a rate.
            overall_cov_str = get_overall_cov_rate(last_round_cov_pair_dict)
            pr_level_rates.append(overall_cov_str)

        overall_data.append(pr_level_rates)
    
    return overall_data
            

def plot_coverages_violin(overall_data, all_version_id, title):
    # Convert percentage strings to floats
    cleaned_data = [
        [float(cov.strip('%')) for cov in pr_level_rates]
        for pr_level_rates in overall_data
    ]

    # Create the violin plot
    fig, ax = plt.subplots()
    ax.violinplot(cleaned_data, showmeans=True)

    # Label the x-axis
    ax.set_xticks(range(1, len(all_version_id) + 1))
    ax.set_xticklabels(all_version_id)

    # Add labels and title
    ax.set_ylabel("Coverage (%)")
    ax.set_title(title)
    
    plt.grid(True)
    plt.savefig("overall.pdf")


def main():
    iteration = 2

    all_data = []
    all_version_id = []

    results_folder = join("data", "results")
    log_folder_parent = join(results_folder, f"logs_iter{iteration}")
    table_output_folder = join(results_folder, "table_and_plots", f"meta_iter{iteration}")
    makedirs(table_output_folder, exist_ok=True)

    all_log_folder = [join(log_folder_parent, folder) for folder in listdir(log_folder_parent)\
            if isdir(join(log_folder_parent, folder)) and folder.startswith("log_")]
    all_log_folder = sorted(all_log_folder)
    for log_folder in all_log_folder:
        version_id = f"V{log_folder.rsplit('_', 1)[1]}"
        if "1_0_1" in log_folder:
            version_id = "Testora"
        init = CoverageComparison(log_folder, version_id)
        all_from_cur_version = init.get_multiple_pr_coverage_info()
        # # write a meta file for a version
        # meta_file = join(table_output_folder, f"coverage_comparison_meta_{version_id}.json")
        # with open(meta_file, "w") as f:
        #     json.dump(all_from_cur_version, f, indent=4, ensure_ascii=False)   
        # print(f"Collected coverage information is written to {meta_file}")

        all_data.append(all_from_cur_version)
        all_version_id.append(version_id)

    overall_data = get_overall_coverage_rates(all_data)

    # generate the table
    caption = "Coverage Comparison between Testora and Our Approach"
    plot_coverages_violin(overall_data, all_version_id, caption)


if __name__=="__main__":
    main()

import json
from os import makedirs
from os.path import join, exists
from matplotlib import pyplot as plt


def get_group_zise(loc_list, min_groups=5, max_groups=10, group_size_threashold=10):
    # dynamically decide a group size, default with at least 5 groups and at most 10 groups
    data_num = len(loc_list)
    max_loc = max(loc_list)
    min_loc = min(loc_list)
    
    possible_group_nums = list(range(min_groups, max_groups+1))
    reversed(possible_group_nums)
    for group_num in possible_group_nums:
        group_size = max_loc / max_groups # all reminaders stay in the last (the 10th) group
        if group_size < group_size_threashold: # if group size too small, get less groups
            pass

def plot_diff_locs(diff_modified_locs, diff_touched_locs, title, result_pdf):
    # Get groups
    # upper_bound
    # groups_modified = range(0, upper_bound, group_size)
    # groups_touched = range(0, upper_bound, group_size)
    
    # Create a figure with two subplots (1 row, 2 columns)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Plot histogram for diff_modified_locs
    n1, bins1, patches1 = axes[0].hist(diff_modified_locs, bins=bins1, color='skyblue', edgecolor='black', align='left', rwidth=0.3)
    axes[0].set_title(f"{title} (Modified)")
    axes[0].set_xlabel('LoC')
    axes[0].set_ylabel('Number of PRs')

    # Add count labels to bars
    for count, patch in zip(n1, patches1):
        if count > 0:
            height = patch.get_height()
            axes[0].text(patch.get_x() + patch.get_width() / 2, height, int(count),
                        ha='center', va='bottom', fontsize=9)


    # Plot histogram for diff_touched_locs
    n2, bins2, patches2 = axes[1].hist(diff_touched_locs, bins=bins, color='salmon', edgecolor='black', align='left', rwidth=0.3)
    axes[1].set_title(f"{title} (Touched)")
    axes[1].set_xlabel('LoC')
    axes[1].set_ylabel('Number of PRs')

    # Add count labels to bars
    for count, patch in zip(n2, patches2):
        if count > 0:
            height = patch.get_height()
            axes[1].text(patch.get_x() + patch.get_width() / 2, height, int(count),
                        ha='center', va='bottom', fontsize=9)


    # Adjust layout to prevent overlap
    plt.tight_layout()
    plt.savefig(result_pdf)


def main():
    diff_modified_locs = []
    diff_touched_locs = []

    result_folder = join("data", "results", "table_and_plots")
    makedirs(result_folder, exist_ok=True)
    meta_file = join(result_folder, "loc_in_diff_meta.txt")
    if exists(meta_file):
        with open(meta_file, "r") as f:
            meta_info = json.load(f) 
        diff_modified_locs =  json.loads(meta_info["diff_modified_locs"])    
        diff_touched_locs =  json.loads(meta_info["diff_touched_locs"]) 
    else:
        with open(".target_project", "r") as f:
            project = f.read().strip()
        project_pr_file = join("data", f"{project}_PRs_all.txt")
        with open(project_pr_file, "r") as f:
            pr_nums = f.readlines()
        diff_modified_locs, diff_touched_locs = check_diff_for_single_pr(project, pr_nums)

        # write the numbers to a local file, for further helping to decide group size
        to_write = {
            "diff_modified_locs": f"{diff_modified_locs}",
            "diff_touched_locs": f"{diff_touched_locs}"
        }
    
        with open(meta_file, "w") as f:
            json.dump(to_write, f, indent=2)

    # title = "LoC in diff of Non-test Main Files"
    # result_folder = join("data", "results", "table_and_plots")
    # makedirs(result_folder, exist_ok=True)
    # plot_diff_locs(diff_modified_locs, diff_touched_locs, title, join(result_folder, "loc_in_diff.pdf"))


if __name__=="__main__":\
    main()
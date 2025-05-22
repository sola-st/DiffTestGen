import json
from os.path import join
from os import makedirs
from matplotlib import pyplot as plt


def plot_diff_locs(diff_modified_locs, diff_touched_locs, title, result_pdf, group_zise=20):
    # Get groups
    max_modified= max(diff_modified_locs)
    groups = list(range(1, max_modified, group_zise)) # hard code group size group_zise
    group_labels = [f"[{groups[i]},\n {groups[i+1]-1}]" for i in range(len(groups) - 1)]

    group_labels.append(f"[{groups[-1]},\n {max_modified}]")
    to_add = ((max_modified // group_zise) +1 ) * group_zise
    groups.append(to_add)
    
    # Create a figure with two subplots (1 row, 2 columns)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Plot histogram for diff_modified_locs
    n1, bins1, patches1 = axes[0].hist(diff_modified_locs, bins=groups, color='skyblue', edgecolor='black', align='left', rwidth=0.4)
    axes[0].set_title(f"{title} (Modified)")
    axes[0].set_xlabel('LoC')
    axes[0].set_ylabel('Number of PRs')

    # Set custom x-tick labels
    axes[0].set_xticks([groups[i] for i in range(len(groups) - 1)])
    axes[0].set_xticklabels(group_labels)
    # axes[0].tick_params(axis='x', labelrotation=90)

    # Add count labels to bars
    for count, patch in zip(n1, patches1):
        if count > 0:
            height = patch.get_height()
            axes[0].text(patch.get_x() + patch.get_width() / 2, height, int(count),
                        ha='center', va='bottom', fontsize=9)


    # Plot histogram for diff_touched_locs
    groups_touched = list(range(1, max_modified, group_zise)) # a list of range start numbers
    group_labels = [f"[{groups_touched[i]},\n {groups_touched[i+1]-1}]" for i in range(len(groups_touched) - 1)]

    max_touched = max(diff_touched_locs)
    group_labels.append(f"[{groups_touched[-1]},\n {max_touched}]")
    to_add = ((max_touched // group_zise) +1 ) * group_zise
    groups_touched.append(to_add)

    n2, bins2, patches2 = axes[1].hist(diff_touched_locs, bins=groups_touched, color='salmon', edgecolor='black', align='left', rwidth=0.4)
    axes[1].set_title(f"{title} (Touched)")
    axes[1].set_xlabel('LoC')
    axes[1].set_ylabel('Number of PRs')

    axes[1].set_xticks([groups_touched[i] for i in range(len(groups_touched) - 1)])
    axes[1].set_xticklabels(group_labels)
    # axes[1].tick_params(axis='x', labelrotation=90)

    # Fix the width of the last bar
    # TODO butifiy the last bin (bar)
    if patches2:
        last_patch = patches2[-1]
        last_patch.set_width(group_zise / 2)
        last_patch.set_x(bins2[-2])  # start of the last bin

    for count, patch in zip(n2, patches2):
        if count > 0:
            height = patch.get_height()
            axes[1].text(patch.get_x() + patch.get_width() / 2, height, int(count),
                        ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    plt.savefig(result_pdf)


def main():
    # After running CheckCodeChangeSize.py for all projects, run the following code
    target_projects = ["scipy", "marshmallow", "pandas", "keras"]
    diff_modified_locs = []
    diff_touched_locs = []

    for project in target_projects:
        meta_file = join("data", "meta", "diff_loc", f"{project}_loc_in_diff_meta.txt")
        with open(meta_file, "r") as f:
            meta_info = json.load(f) 
        sub_diff_modified_locs = json.loads(meta_info["diff_modified_locs"])    
        diff_modified_locs.extend(sub_diff_modified_locs)
        sub_diff_touched_locs = json.loads(meta_info["diff_touched_locs"]) 
        diff_touched_locs.extend(sub_diff_touched_locs)

    title = "LoC in diff of Non-test Main Files"
    result_folder = join("data", "results", "table_and_plots")
    makedirs(result_folder, exist_ok=True)
    plot_diff_locs(diff_modified_locs, diff_touched_locs, title, join(result_folder, "loc_in_diff.pdf"))


if __name__=="__main__":
    main()
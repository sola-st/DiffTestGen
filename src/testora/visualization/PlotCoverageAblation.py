import json
from os import makedirs
from os.path import join, exists
import numpy as np

from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
from testora.visualization.CoverageComparison import CoverageComparison
from testora.visualization.CoverageUtils import get_overall_cov_rate


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
            union_old_new_cov_str = get_overall_cov_rate(last_round_cov_pair_dict)
            pr_level_rates.append(union_old_new_cov_str)

        overall_data.append(pr_level_rates)
    
    return overall_data
            

def plot_coverages_violin(overall_data, all_version_id, result_pdf):
    # Convert percentage strings to floats
    cleaned_data = [
        [float(cov.strip('%')) for cov in pr_level_rates]
        for pr_level_rates in overall_data
    ]

    # violin plot
    fig, ax = plt.subplots()
    # ax.violinplot(cleaned_data, showmeans=True) # default: arithmetic mean
    ax.violinplot(cleaned_data, showmeans=False)  # Turn off default mean

    # arithmetic means
    arith_means = [np.mean(group) for group in cleaned_data]
    ax.scatter(
        range(1, len(arith_means) + 1),
        arith_means,
        color='blue',
        marker='x',
        label='Arithmetic Mean',
        zorder=3
    )

    # # geometric means
    # geom_means = [gmean(group) for group in cleaned_data]
    # ax.scatter(
    #     range(1, len(geom_means) + 1),  # x positions
    #     geom_means,                     # y values (geometric means)
    #     color='orange',
    #     marker='o',
    #     label='Geometric Mean',
    #     zorder=3
    # )

    for i, arith in enumerate(arith_means, start=1):
        # Arithmetic Mean label
        plt.text(i + 0.1, arith + 0.5, f"{arith:.3f}%", color='blue', fontsize=8)

    # Label the x-axis
    ax.set_xticks(range(1, len(all_version_id) + 1))
    ax.set_xticklabels(all_version_id)
    ax.set_xlim(0.5, len(all_version_id) + 0.6)  # add space after last bar

    # Add labels and title
    ax.set_ylabel("Union Coverage (%)")
    # ax.set_title(title)

    # Add legend
    legend_elements = [
        Line2D([0], [0], marker='x', color='blue', label='Arithmetic Mean', linestyle='None'),
        # Line2D([0], [0], marker='o', color='orange', label='Geometric Mean', linestyle='None'),
    ]
    ax.legend(handles=legend_elements, loc='center right')
    
    plt.grid(True)
    plt.savefig(result_pdf)


def plot_coverages_violin_subplot(overall_data, all_version_id, result_pdf, title=None):
    """Create a single subplot for violin plot (used in multi-subplot figures)"""
    # Convert percentage strings to floats
    cleaned_data = [
        [float(cov.strip('%')) for cov in pr_level_rates]
        for pr_level_rates in overall_data
    ]
    
    return cleaned_data

def plot_all_coverages_combined(all_project_data, project_names, all_version_id, result_pdf):
    """Plot all projects + overall in a single figure with grouped violins for each approach"""
    # all_project_data: dict with project names as keys and cleaned_data as values
    # Each value is a list of lists: [approach1_data, approach2_data, ..., approach5_data]
    # For each approach, we have coverage data for each project
    
    # Define colors for each approach
    colors = ["#4F8A8B", "#01A9B4", "#EA907A", "#FFCB74", "#E36387"]
    
    fig, ax = plt.subplots(figsize=(9, 4))
    plt.rcParams.update({'font.size': 11})
    
    # Get the number of approaches (should be 5)
    num_approaches = len(list(all_project_data.values())[0])
    num_projects = len(all_project_data)
    
    # Positions for each project group on x-axis
    project_positions = np.arange(num_projects)
    
    # Width and offsets updated to bring the violin bars closer together
    violin_width = 0.15
    offset_positions = np.linspace(-0.3, 0.3, num_approaches)
    
    # Plot violins for each approach
    for approach_idx in range(num_approaches):
        approach_data = []
        positions = []
        
        for proj_idx, (project_name, cleaned_data) in enumerate(all_project_data.items()):
            # cleaned_data[approach_idx] contains coverage data for this approach in this project
            approach_data.append(cleaned_data[approach_idx])
            positions.append(proj_idx + offset_positions[approach_idx])
        
        # Create violin plot for this approach with custom positions
        parts = ax.violinplot(
            approach_data,
            positions=positions,
            widths=violin_width,
            showmeans=False,
            showmedians=False
        )
        
        # Color the violins
        for pc in parts['bodies']:
            pc.set_facecolor(colors[approach_idx])
            pc.set_alpha(1)

        # # Set the "middle bone" (extrema lines and caps) to gray
        # for partname in ('cbars', 'cmins', 'cmaxes'):
        #     if partname in parts:
        #         parts[partname].set_edgecolor('gray')
        
        # Plot arithmetic means as markers
        arith_means = [np.mean(data) for data in approach_data]
        ax.scatter(
            positions,
            arith_means,
            color='black',
            marker='x',
            zorder=3,
        )
        
        # Annotate the arithmetic mean values keeping 1 digit after decimal point
        for pos, mean_val in zip(positions, arith_means):
            ax.text(
                pos,
                mean_val + 1.2,  # Adjust this offset if needed depending on your y-scale
                f'{mean_val:.1f}',
                ha='center',
                va='bottom',
                fontsize=9,
                color='black',
                zorder=3
            )
    
    # Set x-axis
    ax.set_xticks(project_positions)
    ax.set_xticklabels([name for name in all_project_data.keys()])
    ax.set_xlim(-0.5, num_projects - 0.5)
    
    # Labels and title
    ax.set_ylabel("Union Coverage (%)")
    
    # Create custom legend
    legend_elements = [
        Line2D([0], [0], color=colors[i], lw=8, label=all_version_id[i]) # , alpha=0.7
        for i in range(num_approaches)
    ]
    # Add arithmetic mean marker to legend
    legend_elements.append(
        Line2D([0], [0], marker='x', color='w', markerfacecolor='black', 
               markeredgecolor='black', markersize=8, markeredgewidth=2,
               label='Arithmetic Mean', linestyle='None')
    )
    
    # Place legend inside the figure box, centered horizontally under group 2 (index 1)
    # Relative coordinate: (target_index - xmin) / total_range = (1 - (-0.5)) / num_projects
    legend_x = 1.5 / num_projects
    ax.legend(
        handles=legend_elements, 
        loc='lower center', 
        bbox_to_anchor=(legend_x, 0.05), 
        fontsize=9, 
        borderpad=1
    )
    
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(result_pdf, dpi=150, bbox_inches='tight')
    plt.close()


def main():
    iteration = 0
    subset_mode = False
   # model_version = "gpt-4o-mini-2024-07-18"
    model_version = "gpt-5-mini-2025-08-07"
    target_projects = ["keras", "marshmallow", "pandas", "scipy"]
    config_names = ["testora", "testora_100", "only_coverage_feedback", "only_cg", "difftestgen"]
    axis_names = ["Testora", "Testora++", "Only Coverage Feedback", "Only Access Information", "DiffTestGen"]
    results_folder = join("data", "results")
    output_base_folder = join(results_folder, "table_and_plots", "coverage_meta_info", f"iter_{iteration}")  
    across_projects = []
    
    # For combined plot
    all_project_cleaned_data = {}
    
    for i, project in enumerate(target_projects):
        all_data = []

        for name in config_names:
            output_folder = join(output_base_folder, f"log_{name}")
            makedirs(output_folder, exist_ok=True)

            log_folder = join(results_folder, model_version, f"iter_{iteration}", f"log_{name}", project)
            if name == "testora_100":
                log_folder = join(results_folder, model_version, f"iter_{iteration}_100", f"log_testora", project)
            if subset_mode == True:
                log_folder = join(results_folder, model_version, f"iter_{iteration}_subset", f"log_{name}", project)
            
            meta_file = join(output_folder, f"{project}_coverage_meta.json")
            all_from_cur_version = []
            if exists(meta_file):
                print(f"Meta file {meta_file} already exists. Skipping processing for {name} on {project}.")
                with open(meta_file, "r") as f:
                    all_from_cur_version = json.load(f)
            else:
                init = CoverageComparison(log_folder, name)
                all_from_cur_version = init.get_multiple_pr_coverage_info(project)
                # write a meta file for a version
                with open(meta_file, "w") as f:
                    json.dump(all_from_cur_version, f, indent=4, ensure_ascii=False)   
                print(f"Collected coverage information is written to {meta_file}, relevant pr num: {len(all_from_cur_version)}")

            all_data.append(all_from_cur_version)

        overall_data = get_overall_coverage_rates(all_data)
        result_pdf = join(output_base_folder, f"coverage_comparison_ablation_{project}.pdf") 
        plot_coverages_violin(overall_data, axis_names, result_pdf)
        
        # Store cleaned data for combined plot
        cleaned_data = [
            [float(cov.strip('%')) for cov in pr_level_rates]
            for pr_level_rates in overall_data
        ]
        all_project_cleaned_data[project] = cleaned_data

        if i == 0:
            across_projects.extend(all_data)
        else:
            for j, approach_data in enumerate(all_data):
                across_projects[j].extend(approach_data)

    # for the plot
    overall_data = get_overall_coverage_rates(across_projects)
    cleaned_overall = [
        [float(cov.strip('%')) for cov in pr_level_rates]
        for pr_level_rates in overall_data
    ]
    all_project_cleaned_data['Overall'] = cleaned_overall
    
    # Create combined plot with all subplots
    result_pdf_combined = join(output_base_folder, f"coverage_comparison_ablation_combined.pdf")
    plot_all_coverages_combined(all_project_cleaned_data, target_projects, axis_names, result_pdf_combined)
    print(f"Combined plot saved to {result_pdf_combined}")
    
    # Also keep individual overall plot for backward compatibility
    result_pdf = join(output_base_folder, f"coverage_comparison_ablation.pdf") 
    # title = "Coverage Comparison (Ablation study)"
    plot_coverages_violin(overall_data, axis_names, result_pdf)


if __name__=="__main__":
    main()

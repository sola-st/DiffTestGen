import json


def get_feedback_round_max_list(grouped_data):
    feedback_round_max_list = [] # a max num for a pr
    for pr_rec_cross_approaches in grouped_data:
        feedback_round_max = 0
        pr_num = None
        for pr_rec in pr_rec_cross_approaches:
            if not pr_num:
                pr_num = list(pr_rec.keys())[-1]
            
            if "Feedback" in pr_rec[pr_num].keys(): 
                # to know how many feedback rounds in current approach
                feedback_round_num = len(pr_rec[pr_num]["Feedback"].keys())
                feedback_round_max = max(feedback_round_max, feedback_round_num)

        feedback_round_max_list.append(feedback_round_max)

    return feedback_round_max_list

def get_feedback_round_max_num(single_approach_data):
    feedback_round_max = 0
    for pr_rec in single_approach_data:
        pr_num = list(pr_rec.keys())[-1]
        
        if "Feedback" in pr_rec[pr_num].keys(): 
            feedback_round_num = 0
            for i, (round_name, round_rec) in enumerate(pr_rec[pr_num]["Feedback"].items()):
                if json.dumps(round_rec).count("100") == 2:
                    feedback_round_num = i + 1
                    break
            feedback_round_max = max(feedback_round_max, feedback_round_num)

    return feedback_round_max

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
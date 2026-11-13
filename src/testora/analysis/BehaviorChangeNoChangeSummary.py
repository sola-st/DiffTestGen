import json
import os
from os.path import dirname, join
from testora import Config


def summarize_logs(log_base_folder, project):
    log_folder = join(log_base_folder, project)
    log_files = os.listdir(log_folder)

    project_results = {}
    for file in log_files:
        log_file = join(log_folder, file)
        with open(log_file, "r") as source_file:
            events = json.load(source_file)
        if not isinstance(events, list):
            print(log_file)

        for event in events:
            if not isinstance(event, dict) or event.get("message") != "Behavior change classification result":
                continue
            behavior_change = event.get("behavior_change")
            if behavior_change not in {"yes", "no", "unclear"}:
                raise ValueError(f"Invalid behavior_change value in log file: {log_file}")
            try:
                pr_number = int(event["pr_nb"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"Invalid PR number in log file: {log_file}") from error

            summary = event.get("summary")
            if not isinstance(summary, str):
                raise ValueError(f"Invalid summary in log file: {log_file}")
            timestamp = event.get("timestamp", "")
            previous = project_results.get(pr_number)
            if previous is None or timestamp >= previous[0]:
                project_results[pr_number] = (timestamp, behavior_change, summary)

    prs_by_decision = {
        decision: {
            str(pr_number): {"summary": summary}
            for pr_number, (_, behavior_change, summary) in sorted(project_results.items())
            if behavior_change == decision
        }
        for decision in ("no", "yes", "unclear")
    }
    return {
        project: {
            "no_behavioral_change_count": len(prs_by_decision["no"]),
            "no_behavioral_change_prs": prs_by_decision["no"],
            "yes_behavioral_change_count": len(prs_by_decision["yes"]),
            "yes_behavioral_change_prs": prs_by_decision["yes"],
            "unclear_behavioral_change_count": len(prs_by_decision["unclear"]),
            "unclear_behavioral_change_prs": prs_by_decision["unclear"],
        }
    }


def main():
    with open(".target_project", "r") as f:
        project = f.read().strip()
    log_base_folder = join("data", "results", "behavior_change", Config.model_version)
    output_file = join(log_base_folder, f"no_behavioral_change_summary_{project}.json")
    summary = summarize_logs(log_base_folder, project)
    os.makedirs(dirname(output_file), exist_ok=True)
    with open(output_file, "w") as destination:
        json.dump(summary, destination, indent=4)
    print(f"Wrote behavior-change summary to {output_file}")


if __name__ == "__main__":
    main()

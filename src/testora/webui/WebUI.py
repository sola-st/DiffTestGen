from collections import Counter
from typing import Dict, List
from flask import Flask, render_template
import argparse
import re
from datetime import timedelta
from testora.util.LogParser import PRResult, parse_log_files, parse_time_stamp, pr_results_as_dict

app = Flask("Testora Web UI")


parser = argparse.ArgumentParser(description="Web UI for Testora")
parser.add_argument("--files", help="Log file(s) to process",
                    type=str, required=False, nargs="+")

pr_results: List[PRResult] = []
pr_number_to_result: Dict[int, PRResult] = {}


def summarize_status():
    summary = Counter()
    total_time = timedelta(0)
    for pr_result in pr_results:
        summary["total"] += 1
        summary[pr_result.status()] += 1
        if pr_result.entries:
            start = parse_time_stamp(pr_result.entries[0]["timestamp"])
            end = parse_time_stamp(pr_result.entries[-1]["timestamp"])
            total_time += end - start

    # add percentages
    for key in summary:
        if key != "total":
            percentage = (int(summary[key]) / summary['total']) * 100
            summary[key] = f"{summary[key]} ({percentage:.1f}%)"

    # add average execution time
    if pr_results:
        average_time = total_time / len(pr_results)
        summary["avg. time"] = str(average_time)
    else:
        summary["avg. time"] = "0:00:00"

    return summary


def compute_perf_stats(entries):
    total_time = parse_time_stamp(entries[-1]["timestamp"]) - \
        parse_time_stamp(entries[0]["timestamp"])

    message_prefix_to_timedelta = {}
    message_prefix_to_nb = Counter()
    previous_timestamp = None
    previous_message_prefix = None

    for entry in entries:
        if previous_timestamp is None:
            previous_timestamp = entry["timestamp"]
            previous_message_prefix = entry["message"].split(" ")[0]
        else:
            current_timestamp = entry["timestamp"]
            current_message_prefix = entry["message"].split(" ")[0]
            message_prefix_to_timedelta[previous_message_prefix] = message_prefix_to_timedelta.get(
                previous_message_prefix, timedelta(0)) + (parse_time_stamp(current_timestamp) - parse_time_stamp(previous_timestamp))
            message_prefix_to_nb[previous_message_prefix] += 1
            previous_timestamp = current_timestamp
            previous_message_prefix = current_message_prefix

    # sort by time and keep only top-k
    message_prefix_to_timedelta = dict(
        sorted(message_prefix_to_timedelta.items(), key=lambda item: item[1], reverse=True)[:6])

    result = [["All", len(entries), total_time, total_time / len(entries)]]
    for message_prefix, time in message_prefix_to_timedelta.items():
        if message_prefix in ["Done", "Starting"]:
            continue
        result.append([message_prefix, message_prefix_to_nb[message_prefix], time,
                       time / message_prefix_to_nb[message_prefix]])

    return result


def categorize_entry(entry):
    message = entry.get("message", "")
    content = entry.get("content", "")

    if message.startswith("Call graph ("):
        return "Call graph"
    if message.startswith("Added info about call graph"):
        return "Added call graph"
    if message.startswith("Test execution"):
        return "Test execution"
    if message.startswith("Fix runtime errors"):
        return "Fix runtime errors"
    if message == "Pre-classification":
        return "Pre-classification"
    if message.startswith("Different outputs"):
        return "Different outputs"
    if message.startswith("Diff coverage, #"):
        return "Diff coverage"
    if message.startswith("Querying") or message.startswith("Cached result for querying"):
        return "Querying"
    if message.startswith("Compiling"):
        return "Compiling"
    if message == "Token usage":
        return "Token usage"
    if re.search(r"^(Generated \d+ tests|Generated \d+ more tests|Static error fixed \d+/)", message):
        return "Generated tests"
    return "Other"


status_colors = {
    "unknown": "#FFFFE0",
    "checked": "#D3D3D3",
    "intended_change": "#CCFFCC",
    "coincidental_fix": "#CBC3E3",
    "regression": "#FFCCCC",
}


def nl2br(value):
    if type(value) == str:
        return value.replace("\n", "<br>")
    else:
        return value


app.jinja_env.filters["nl2br"] = nl2br


def escape_tags(value):
    if type(value) == str:
        return value.replace("<", "&lt;").replace(">", "&gt;")
    else:
        return value


app.jinja_env.filters["escape_tags"] = escape_tags


@app.route('/')
def main_page():
    global pr_results, pr_number_to_result
    pr_results, _ = parse_log_files(args.files)
    summary = summarize_status()
    pr_number_to_result = pr_results_as_dict(pr_results)
    return render_template("index.html", summary=summary, data=pr_results, color_mapping=status_colors)


@app.route('/pr<int:number>')
def pr_page(number):
    pr_result = pr_number_to_result[int(number)]
    perf_stats = compute_perf_stats(pr_result.entries)

    entry_groups = [categorize_entry(entry) for entry in pr_result.entries]
    unique_groups = []
    for group in entry_groups:
        if group not in unique_groups:
            unique_groups.append(group)

    group_counts = Counter(entry_groups)
    entry_data = list(zip(pr_result.entries, entry_groups))

    return render_template(
        'pr.html',
        pr_result=pr_result,
        perf_stats=perf_stats,
        entry_data=entry_data,
        groups=unique_groups,
        group_counts=group_counts
    )


if __name__ == "__main__":
    args = parser.parse_args()
    app.run(debug=True, port=4000)

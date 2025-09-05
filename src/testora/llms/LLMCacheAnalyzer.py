import json
import matplotlib.pyplot as plt
from os.path import join
from os import makedirs


def analyze_llm_cache(file_path, result_parent_folder, repetition_idx):
    with open(file_path, "r") as f:
        cache = json.load(f)
    print(f"Total cache entries: {len(cache)}")
    query_sizes = []
    answer_sizes = []
    for query, answer in cache.items():
        query_sizes.append(len(query))
        answer_sizes.append(len(answer))
        if len(answer) == 0:
            print(f"Warning: empty answer found!")

    # plot histogram of query sizes
    plt.hist(query_sizes, bins=50)
    plt.title("Query sizes")
    plt.xlabel("Size")
    plt.ylabel("Frequency")
    # plt.show()
    plt.savefig(join(result_parent_folder, f"query_size_{repetition_idx}.pdf"))

    # plot histogram of answer sizes
    plt.hist(answer_sizes, bins=50)
    plt.title("Answer sizes")
    plt.xlabel("Size")
    plt.ylabel("Frequency")
    # plt.show()
    plt.savefig(join(result_parent_folder, f"answer_size_{repetition_idx}.pdf"))


if __name__ == "__main__":
    # model_version = "gpt-4o-mini-2024-07-18"
    model_version = "gpt-5-mini-2025-08-07"
    repetition_idx = None # could be None, 1, 2, 3 ...

    result_parent_folder = join("data", "results", "table_and_plots", model_version)
    makedirs(result_parent_folder, exist_ok=True)
    
    cache_file = f"data/llm_cache/{model_version}/cache.json"
    if repetition_idx != None:
        cache_file = cache_file.replace(".json", f"_{repetition_idx}.json")
    analyze_llm_cache(cache_file, result_parent_folder, repetition_idx)

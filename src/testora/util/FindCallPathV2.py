import json
import networkx as nx
from os.path import join, exists


# Adjust these to your function names as they appear in the .dot file
target_function = "marshmallow__fields__Enum____init__"    # e.g., "othermodule.function"

# Step 1: Load DOT file
graph = nx.drawing.nx_pydot.read_dot("local/call_gragh_marshmallow2730.dot")

print(f"[+] Graph loaded with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")

# Step 2: Find reachable nodes
reachable = set(nx.descendants(graph, target_function)) | {target_function}

# Step 3: Map nodes back to files
node_to_file = {"startsfrom": target_function}
for node in reachable:
    # Example heuristic: module parts are joined with "__"
    parts = node.split("__")
    file_guess = join(*parts[:-1]) + ".py"
    node_to_file[node] = file_guess

# Step 4: Deduplicate and keep only existing files
files_to_analyze = sorted({f for f in node_to_file.values()}) # if exists(f)})
node_to_file.update({"deduplicated_files": files_to_analyze})

with open("node_to_file.json", "w") as f:
    json.dump(node_to_file, f, indent=4)

# # Step 5: Run pyan3 again on the subset
# if files_to_analyze:
#     files_str = " ".join(files_to_analyze)
#     os.system(f"pyan3 {files_str} --dot > subset.dot")
#     print(f"[+] Generated subset.dot for {len(files_to_analyze)} files")
# else:
#     print("No related files found")


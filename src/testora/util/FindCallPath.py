import networkx as nx


# Adjust these to your function names as they appear in the .dot file
start_node = "tests__test_deserialization__TestFieldDeserialization__test_fields_accept_internal_types" # e.g., "module.function"
end_node = "marshmallow__fields__Enum___deserialize"    # e.g., "othermodule.function"

# Step 1: Load DOT file
graph = nx.drawing.nx_pydot.read_dot("local/call_gragh_marshmallow2730.dot")

print(f"[+] Graph loaded with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")

# Step 2: Ensure start and end exist
if start_node not in graph:
    raise ValueError(f"Start node '{start_node}' not found in call graph")
if end_node not in graph:
    raise ValueError(f"End node '{end_node}' not found in call graph")

# Step 3: Find all simple paths from start_node to end_node
paths = list(nx.all_simple_paths(graph, source=start_node, target=end_node))

print(f"[+] Found {len(paths)} path(s) from '{start_node}' to '{end_node}':")
for p in paths:
    print(" -> ".join(p))

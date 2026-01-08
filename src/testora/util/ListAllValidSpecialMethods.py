# Method 1:
# Get all special methods implemented by core built-in types in current Python version.

special_methods = set()
for t in (object, int, float, str, list, dict, tuple, set):
    special_methods.update(m for m in dir(t) if m.startswith("__") and m.endswith("__"))

sorted(special_methods)

with open("src/testora/util/special_methods_build_in.txt", "w") as f: 
    f.writelines("\n".join(map(str, special_methods)))

# Method 2:
# another reference: https://docs.python.org/3/reference/datamodel.html#special-methods 
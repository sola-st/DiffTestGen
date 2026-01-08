from os.path import join

# offical documented special methods
offical_special_methods_file = "src/testora/util/special_methods.txt" # the name only version file
with open(offical_special_methods_file, "r") as f:
    offical_special_methods_tmp = f.readlines()
    offical_special_methods = [methods.strip() for methods in offical_special_methods_tmp]

base_folder = join("local", "private_func_check", "private_in_repo")
projects = ["marshmallow","pandas", "scipy", "keras"]
for target_project in projects:
    special_methods_file = f"{base_folder}/{target_project}_special_methods_unique.txt"
    with open(special_methods_file, "r") as f:
        special_methods_tmp = f.readlines()
        special_methods = [methods.strip() for methods in special_methods_tmp]

    delta = []
    for methods in special_methods:
        if not methods in offical_special_methods:
            delta.append(methods)
    
    if delta:
        with open(f"{base_folder}/{target_project}_customized_special_methods_{len(set(delta))}.txt", "w") as f:
            f.writelines("\n".join(delta))
    else:
        print(f"Project {target_project} has no customized special methods.")

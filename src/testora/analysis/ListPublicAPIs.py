# dump_api_from_inventory.py
# this used to be run in the containers, will be delivered to the containers
import sphobjinv as soi
from pathlib import Path

# the project will be changed automatically when delivered to containers 
inv_path = Path("/home/target_project/docs/_build/html/objects.inv")
inv = soi.Inventory(str(inv_path))

wanted_roles = {"py:module", "py:class", "py:function", "py:method", "py:attribute", "py:data", "py:exception"}

with open("Hcheck.txt", "w") as f:
    for o in inv.objects:
        role = f"{o.domain}:{o.role}"
        if role in wanted_roles:
            line = f"{o.name}\t[{role}]\t{o.uri}\n"
            print(line.strip())
            f.write(line)

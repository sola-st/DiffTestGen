import sphobjinv as soi
from pathlib import Path

def get_apis(path):
    all_apis = []

    inv_path = Path(path)
    inv = soi.Inventory(str(inv_path))
    wanted_roles = {"py:module", "py:class", "py:function", "py:method", "py:attribute", "py:data", "py:exception"}

    for o in inv.objects:
        role = f"{o.domain}:{o.role}"
        if role in wanted_roles:
            all_apis.append(o.name)
    
    return all_apis

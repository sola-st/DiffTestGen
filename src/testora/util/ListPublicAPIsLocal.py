'''
The roles represent Python language constructs that can appear in objects.inv entries:
* Python Domain (py:)
    | Role                         | Meaning                                           |
    | ---------------------------- | ------------------------------------------------- |
    | `py:mod`                     | Python **module** or package                      |
    | `py:class`                   | **Class** or type                                 |
    | `py:func`                    | **Module-level function**                         |
    | `py:meth`                    | **Method** of a class                             |
    | `py:attr`                    | **Attribute** of a class or module                |
    | `py:property` (or `py:prop`) | **Property**, i.e., a `@property` descriptor      |
    | `py:data`                    | **Variable** or data object at module level       |
    | `py:const`                   | **Constant**                                      |
    | `py:exc`                     | **Exception class**                               |
    | `py:obj`                     | **Generic Python object** (auto-detects kind)     |
    | `py:classmethod`             | **Class method** (declared with `@classmethod`)   |
    | `py:staticmethod`            | **Static method** (declared with `@staticmethod`) |

* Standard Domain (std:)
    These are not Python-specific, but Sphinx uses them for cross-document and general references.
    | Role            | Meaning                                                      |
    | --------------- | ------------------------------------------------------------ |
    | `std:doc`       | A **document** (reStructuredText source page)                |
    | `std:label`     | A **section label** / explicit target (via `.. _labelname:`) |
    | `std:term`      | A **glossary term** (from a `.. glossary::` directive)       |
    | `std:envvar`    | An **environment variable**                                  |
    | `std:option`    | A **command-line option** (e.g., `--help`)                   |
    | `std:program`   | A **program name** (used with `std:option`)                  |
    | `std:cmdoption` | A **command-line option for a program**                      |
    | `std:command`   | A **generic command** (like a shell command)                 |
    | `std:token`     | A **token** in syntax-highlighting / grammar contexts        |
    | `std:pep`       | A **PEP (Python Enhancement Proposal)** reference            |
    | `std:rfc`       | An **RFC (Request for Comments)** reference                  |
'''


import sphobjinv as soi
from pathlib import Path

def get_apis(path):
    all_apis = []
    full_names = []
    abbr_names = []

    inv_path = Path(path)
    inv = soi.Inventory(str(inv_path))
    # get the accessible or callable roles
    wanted_roles = {"py:module", "py:class", "py:function", "py:method", 
            "py:attribute", "py:data", "py:exception", "py:property", "py:constant", "py:object"}

    for o in inv.objects:
        ''' 
        The fomrat of a single entry:
            |   fully qualified name        | domain:role   |   where to find it on the doc webUI # Abbr. qualified name |
            | ----------------------------- | ------------- | ---------------------------------------------------------- |
            |pandas.core.indexes.base.Index |   [py:class]  |   reference/api/pandas.Index.html#pandas.Index             |
        '''
        role = f"{o.domain}:{o.role}"
        if role in wanted_roles:
            # check whether a abbr. qualified name exists
            if "#$" in o.uri: 
                all_apis.append(o.name)
            else:
                name = o.uri.split("#")[1]
                if o.name not in full_names and name not in abbr_names:
                    full_names.append(o.name)
                    abbr_names.append(name)
                all_apis.append(name)

    # the order of the full and abbr name could differ, so here we do a second round check to update the names
    all_relevant_apis = []
    for full, abbr in zip(full_names, abbr_names):
        tmp = [(idx, full, abbr) for idx, api in enumerate(all_apis) if abbr in api]
        all_relevant_apis.extend(tmp)

    for triple in all_relevant_apis:
        idx, full, abbr = triple
        all_apis[idx] = all_apis[idx].replace(abbr, full)

    return all_apis, full_names, abbr_names

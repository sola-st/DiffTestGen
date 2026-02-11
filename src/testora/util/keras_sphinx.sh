#!/bin/bash
# Complete setup script for Sphinx documentation on Keras to extract public APIs
# this should be ran in folder home/project

set -e  # Exit on any error
rm -rf docs

echo "====================================="
echo "Keras Sphinx Setup Script"
echo "====================================="

# Step 1: Install Sphinx and dependencies
echo ""
echo "[Step 1] Installing Sphinx and dependencies..."
pip install sphinx sphinx-rtd-theme autodocsumm sphinx-version-warning

# Step 2: Create Sphinx project structure using sphinx-quickstart
echo ""
echo "[Step 2] Running sphinx-quickstart..."
mkdir -p docs
cd docs

# Run sphinx-quickstart non-interactively
sphinx-quickstart -q \
    --sep \
    -p "Keras" \
    -a "Keras Team" \
    -v "3.0" \
    -l "en" \
    --makefile \
    --no-batchfile

echo "Sphinx project created in $(pwd)/source"

# Step 3: Update conf.py
echo ""
echo "[Step 3] Updating conf.py with autodoc settings..."
CONF_FILE="source/conf.py"

# Backup original conf.py
cp "$CONF_FILE" "$CONF_FILE.bak"
echo "Backed up original conf.py to conf.py.bak"

# Add Keras path and extensions to conf.py
cat >> "$CONF_FILE" << 'CONFEOF'

# ===== KERAS SPHINX CONFIGURATION =====
import os
import sys

# Add Keras to Python path
sys.path.insert(0, os.path.abspath('../../'))

# Extensions for autodoc and autosummary
if 'sphinx.ext.autodoc' not in extensions:
    extensions.extend([
        'sphinx.ext.autodoc',
        'sphinx.ext.autosummary',
        'sphinx.ext.intersphinx',
        'sphinx.ext.viewcode',
    ])

# HTML theme
html_theme = 'sphinx_rtd_theme'

# Autodoc settings to extract all members
autodoc_default_options = {
    'members': True,
    'undoc-members': False,
    'inherited-members': True,
    'show-inheritance': True,
}
autosummary_generate = True
autodoc_member_order = 'bysource'
# ===== END KERAS SPHINX CONFIGURATION =====
CONFEOF

echo "Updated conf.py with autodoc settings"

# Step 4: Update index.rst
echo ""
echo "[Step 4] Updating index.rst..."
INDEX_FILE="source/index.rst"

# Read current index.rst and modify
cat > "$INDEX_FILE" << 'INDEXEOF'
Keras API Documentation
========================

.. toctree::
   :maxdepth: 2

   api
INDEXEOF

echo "Updated index.rst with API documentation toctree"

# steps 5 and 6 prepare two files that will be needed when automatically updates the public api list

# Step 5: Create api.rst with module-level API listing
echo ""
echo "[Step 5] Creating api.rst with Keras public API modules..."

# Create the Python script to generate api.rst
cat > "../gen_api_rst_auto.py" << 'GENSCRIPT'
import os

# Path to the source folder where Sphinx looks for rst files
SOURCE_DIR = "source"
API_DIR = "../keras/api"
API_RST = os.path.join(SOURCE_DIR, "api.rst")

HEADER = """Keras Public API
================

.. autosummary::
   :toctree: _autosummary
   :recursive:

"""

def main():
    submodules = []
    for fname in os.listdir(API_DIR):
        fpath = os.path.join(API_DIR, fname)
        if os.path.isdir(fpath) and os.path.exists(os.path.join(fpath, "__init__.py")):
            submodules.append(f"keras.api.{fname}")

    submodules.sort()

    with open(API_RST, "w") as f:
        f.write(HEADER)
        for sm in submodules:
            f.write(f"   {sm}\n")

    print(f"Generated {API_RST} with {len(submodules)} API modules.")

if __name__ == "__main__":
    main()
GENSCRIPT

# # Run the script to generate api.rst
# echo "Auto-generated api.rst from keras/api directory"
# python3 ../gen_api_rst_auto.py

# Step 6: Create api.rst with module-level API listing
echo ""
echo "[Step 6] Creating api.rst with Keras public API modules..."

# Create the Python script to list all public apis
cat > "../extract_all_apis.py" << 'GENSCRIPT'
#!/usr/bin/env python3
"""
Extract all public APIs from keras.api package using introspection.
Outputs: modules, classes, functions, methods, attributes, data, exceptions, properties, constants.
"""

import sys
import os
import inspect
from typing import Dict, Set, Tuple

# Add Keras to path if needed
# KERAS_ROOT = os.getenv('KERAS_ROOT', '/home/keras')
# if KERAS_ROOT not in sys.path:
#     sys.path.insert(0, KERAS_ROOT)

def get_object_type(obj) -> str:
    """Determine the Sphinx role type for an object."""
    if inspect.ismodule(obj):
        return 'py:module'
    elif inspect.isclass(obj):
        return 'py:class'
    elif inspect.isfunction(obj):
        return 'py:function'
    elif inspect.ismethod(obj):
        return 'py:method'
    elif inspect.isbuiltin(obj):
        return 'py:function'
    elif isinstance(obj, property):
        return 'py:property'
    elif inspect.isroutine(obj):
        return 'py:function'
    elif isinstance(obj, Exception):
        return 'py:exception'
    else:
        # Check if it's data/constant
        if isinstance(obj, (int, float, str, bool, list, dict, tuple)):
            return 'py:data'
        return 'py:object'

def extract_module_members(module_name: str, module_obj) -> Dict[str, str]:
    """Extract all public members from a module."""
    members = {}
    
    try:
        # Try to get __all__ first
        if hasattr(module_obj, '__all__'):
            all_names = getattr(module_obj, '__all__')
            for name in all_names:
                if not name.startswith('_'):
                    try:
                        obj = getattr(module_obj, name)
                        role = get_object_type(obj)
                        full_name = f"{module_name}.{name}"
                        members[full_name] = role
                    except Exception:
                        pass
        else:
            # Fall back to dir() but exclude private/special
            for name in dir(module_obj):
                if not name.startswith('_'):
                    try:
                        obj = getattr(module_obj, name)
                        # Skip imported standard library or external modules (to focus on Keras API)
                        if inspect.ismodule(obj):
                            # Only include if it's part of keras.api
                            if 'keras' in obj.__name__:
                                role = get_object_type(obj)
                                full_name = f"{module_name}.{name}"
                                members[full_name] = role
                        else:
                            role = get_object_type(obj)
                            full_name = f"{module_name}.{name}"
                            members[full_name] = role
                    except Exception:
                        pass
    except Exception as e:
        print(f"Warning: Could not extract members from {module_name}: {e}", file=sys.stderr)
    
    return members

def recursively_extract_apis(base_module_name: str, base_module_obj, visited: Set[str] = None) -> Dict[str, str]:
    """Recursively extract all public APIs from a base module and its submodules."""
    if visited is None:
        visited = set()
    
    all_apis = {}
    
    # Add the module itself
    all_apis[base_module_name] = 'py:module'
    visited.add(base_module_name)
    
    # Extract members
    members = extract_module_members(base_module_name, base_module_obj)
    all_apis.update(members)
    
    # Recursively process submodules
    for name in dir(base_module_obj):
        if not name.startswith('_'):
            try:
                obj = getattr(base_module_obj, name)
                if inspect.ismodule(obj) and 'keras' in obj.__name__:
                    submodule_name = f"{base_module_name}.{name}"
                    if submodule_name not in visited:
                        sub_apis = recursively_extract_apis(submodule_name, obj, visited)
                        all_apis.update(sub_apis)
            except Exception:
                pass
    
    return all_apis

def main():
    """Main entry point."""
    try:
        # Import keras.api
        print("Importing keras.api...", file=sys.stderr)
        import keras.api as keras_api
        
        print("Extracting all public APIs...", file=sys.stderr)
        all_apis = recursively_extract_apis('keras.api', keras_api)
        
        # Sort and output
        print(f"Found {len(all_apis)} total API items\n", file=sys.stderr)
        
        # Group by type
        by_type = {}
        for api_name, role in sorted(all_apis.items()):
            if role not in by_type:
                by_type[role] = []
            by_type[role].append(api_name)
        
        # Print grouped output
        for role in sorted(by_type.keys()):
            print(f"\n# {role} ({len(by_type[role])} items)")
            for api_name in by_type[role]:
                print(f"{api_name}\t[{role}]\t_autosummary/{api_name.replace('.', '/')}.html")
        
        output_file = 'keras_objects.txt'
        with open(output_file, 'w') as f:
            for api_name in sorted(all_apis.keys()):
                role = all_apis[api_name]
                f.write(f"{api_name}\t[{role}]\t_autosummary/{api_name.replace('.', '/')}.html#\n")
        
        print(f"\n\nOutput saved to {output_file}", file=sys.stderr)
        
    except ImportError as e:
        print(f"Error: Could not import keras.api: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
GENSCRIPT

# # Run the script to list all public apis
# echo "List all public apis (keras_objects.txt) to where the .py file locates"
# python3 ../extract_all_apis.py

echo ""
echo "Ready for running sphinx-build"

echo "[Step 7] Run to get the public api file"
cd ..
# Run the script to generate module keras.api
echo "Run api_gen.py to generate module keras.api"
python3 api_gen.py

# Run the script to generate api.rst
echo " "
echo "Auto-generated api.rst from keras/api directory"
python3 gen_api_rst_auto.py

echo " "
echo "Run sphinx-build"
sphinx-build -b html -d docs/build/doctrees docs/source docs/build/html

# Run the script to list all public apis
echo " "
echo "List all public apis (keras_objects.txt) to where the .py file locates"
python3 extract_all_apis.py

echo " "
echo "All public apis are listed in home/keras/keras_objects.txt"

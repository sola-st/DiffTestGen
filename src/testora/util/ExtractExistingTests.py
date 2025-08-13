import json
from os import chdir, getcwd
import tarfile
import tempfile
import docker
from os.path import join


class ExtractExistingTests():
    def __init__(self, modified_test_python_files, changed_functions, container_name, project_name):
        client = docker.from_env()
        # adapt file paths to the container's file system
        self.modified_test_python_files = [f"/home/{project_name}/{f}" for f in modified_test_python_files]
        self.changed_functions = changed_functions # fully qualified function names
        self.container = client.containers.get(container_name)
        self.container.start()
        self.project_name = project_name

        # to return
        self.function_test_pairs = {}

    def analysis_test_python_files(self):
        # pytest --collect-only -q >> ../../marshmallow_tests.txt
        command = "pytest --collect-only -q"

        # for scipy and numpy, make sure we run inside the their dev environment
        if self.container.name.startswith("scipy-dev"):
            command = (
                f"bash -c 'source /root/conda/etc/profile.d/conda.sh"
                f" && source /root/conda/etc/profile.d/mamba.sh && mamba activate scipy-dev"
                f" && {command}'"
            )
        elif self.container.name.startswith("numpy-dev"):
            command = (
                f"bash -c 'source /root/conda/etc/profile.d/conda.sh"
                f" && source /root/conda/etc/profile.d/mamba.sh"
                f"' && mamba activate numpy-dev && {command}'"
            )

        exec_result = self.container.exec_run(command)
        listed_test_details = exec_result.output.decode("utf-8")
        # These listed tests include the modified tests.
        self.analysis_pytest_output(listed_test_details)

    def analysis_pytest_output(self, listed_test_details):
        # TODO filter the relevant tests, and get the pyan .dot file formatted fully qualified function name.
        lines = listed_test_details.split("\n")
        for line in lines:
            '''
            Two foramts for line :
                * <test_file_path>::<test_class_name>::<test_function_name[<paras(if exists)>]> 
                * <test_file_path>::<test_function_name[<paras(if exists)>]> 
            e.g.,
            tests/test_context.py::TestContext::test_validates_schema_with_context
            tests/test_decorators.py::test_decorated_processors[True]
            ''' 
            clean_prefix = line
            if "[" in clean_prefix:
                clean_prefix = line.split("[")[0]

            sep_num = clean_prefix.count("::")
            test_file_path = None
            if sep_num == 1:
                test_file_path, test_function_name = clean_prefix.split("::")
            elif sep_num == 2:
                test_file_path, test_class_name, test_function_name = clean_prefix.split("::")

            self.identify_related_tests([test_file_path]) #TODO

        #TODO
        # result_file = join(results_folder, "table_and_plots", f"Error_feedback_statistics_{version_id}.json")
        result_file = "refined_test_files_meta_unmodified.json"
        with open(result_file, "w") as f:
            json.dump(self.function_test_pairs, f, indent=4)

    def copy_code_to_container(self, code, target_file_path):
        target_dir = target_file_path.rsplit("/", 1)[0]
        target_file_name = target_file_path.rsplit("/", 1)[1]

        with tempfile.TemporaryDirectory() as tmp_dir:
            code_file = join(tmp_dir, target_file_name)
            with open(code_file, "w") as f:
                f.write(code)
            tar_file = join(tmp_dir, "archive.tar")
            with tarfile.open(tar_file, mode="w") as tar:
                wd = getcwd()
                try:
                    chdir(tmp_dir)
                    tar.add(target_file_name)
                finally:
                    chdir(wd)

            data = open(tar_file, "rb").read()
            self.container.put_archive(target_dir, data)

    def get_call_graph(self):
        # TODO If this works, this should be installed when build the dev
        self.container.exec_run('/bin/sh -c "cd /home/marshmallow && pip install pyan3"')
        self.container.exec_run("rm -rf /tmp/Testora")
        self.container.exec_run("mkdir /tmp/Testora")
        code = """import os
import pyan

# Step 1: Collect all Python files recursively
project_root = "/home/marshmallow"
py_files = []
for root, dirs, files in os.walk(project_root):
    for f in files:
        if f.endswith(".py"):
            py_files.append(os.path.abspath(os.path.join(root, f)))

print(f"[+] Found {len(py_files)} Python files.")

# Step 2: Create the call graph
dot_output = pyan.create_callgraph(
    filenames=py_files,
    draw_defines=True,
    draw_uses=True,
)

# Step 3: Save as DOT file
with open("callgraph.dot", "w") as f:
    f.write(dot_output)

print(f"Call graph written to callgraph.dot with {len(py_files)} files")
""" 
        self.copy_code_to_container(code, "/tmp/Testora/generate_callgraph.py")
        self.container.exec_run('/bin/sh -c "cd /home/marshmallow && python3 /tmp/Testora/generate_callgraph.py"')
        

    def main(self):
        if self.modified_test_python_files:
            self.get_call_graph()

import io
import json
import os
import docker
import tarfile
import tempfile
from os.path import join
from os import chdir, getcwd


class DockerExecutor:
    def __init__(self, pr, container_name, project_name, coverage_files):
        client = docker.from_env()
        self.pr = pr
        self.container = client.containers.get(container_name)
        self.container.start()
        self.project_name = project_name

        # adapt paths of coverage files to the container's file system
        self.coverage_files = [f"/home/{project_name}/{f}" for f in coverage_files]

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

    def copy_file_from_container(self, file_path_in_container, target_dir):
        data, _ = self.container.get_archive(file_path_in_container)
        temp_tar_file = "temp.tar"
        with open(temp_tar_file, "wb") as f:
            for d in data:
                f.write(d)
        
        with tarfile.open(temp_tar_file, mode="r") as tar:
            tar.extractall(target_dir)

        os.remove(temp_tar_file)

    def execute_python_code(self, code, analysis=False, version=None, test_execution=None):
        # create a fresh directory to get rid of any old state
        self.container.exec_run("rm -rf /tmp/Testora")
        self.container.exec_run("mkdir /tmp/Testora")

        if len(code.splitlines()) == 1 and self.project_name == "keras":
            self.container.exec_run('/bin/sh -c "cd /home/keras && pip install -e ./"')

        self.copy_code_to_container(code, "/tmp/Testora/Testora_test_code.py")
        coverage_files = ",".join(f"\"{f}\"" for f in self.coverage_files)
        # -u to avoid non-deterministic buffering
        # coverage run: to get the coverage report.
        # --include is a list of file name patterns. If specified, only files matching those patterns will be measured. 
        command = (
            f"timeout 300s python -u -m coverage run "
            f"--include={coverage_files} "
            f"--data-file /tmp/coverage_report /tmp/Testora/Testora_test_code.py"
        )

        # for scipy and numpy, make sure we run inside the their dev environment
        if self.container.name.startswith("scipy-dev"):
            # command = (
            #     f"bash -c 'source /root/conda/etc/profile.d/conda.sh"
            #     f" && source /root/conda/etc/profile.d/mamba.sh && mamba activate scipy-dev"
            #     f" && {command}'"
            # )
            command = (
                "bash -c '"
                "source /root/conda/etc/profile.d/conda.sh"
                " && conda activate scipy-dev"
                f" && {command}'"
            )
        elif self.container.name.startswith("numpy-dev"):
            command = (
                f"bash -c 'source /root/conda/etc/profile.d/conda.sh"
                f" && source /root/conda/etc/profile.d/mamba.sh"
                f"' && mamba activate numpy-dev && {command}'"
            )

        exec_result = self.container.exec_run(command)
        output = exec_result.output.decode("utf-8")

        if analysis == True:
            # copy CoverageAnalyzer.py to the container root directory
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                tar.add("src/testora/execution/CoverageAnalyzer.py", arcname="CoverageAnalyzer.py")
            tar_stream.seek(0)
            self.container.put_archive("/", tar_stream.read())

            # Convert all sets to lists
            old_tmp = {k: list(v) if isinstance(v, set) else v for k, v in self.pr.old_file_path_to_all_modified_lines.items()}
            new_tmp = {k: list(v) if isinstance(v, set) else v for k, v in self.pr.new_file_path_to_all_modified_lines.items()}
            old_file_path_to_all_modified_lines = json.dumps(old_tmp)
            new_file_path_to_all_modified_lines = json.dumps(new_tmp)

            analysis_command = (f"python /CoverageAnalyzer.py "
                f"--coverage_report /tmp/coverage_report " 
                f"--coverage_files {' '.join(self.coverage_files)} "
                f"--version {version} "
                f"--exec_modified_lines_old \'{old_file_path_to_all_modified_lines}\' "
                f"--exec_modified_lines_new \'{new_file_path_to_all_modified_lines}\'")
            
            # intsall this in the containers
            # self.container.exec_run("python3 -m pip install coverage") 
            analysis_results = self.container.exec_run(analysis_command)
            analysis_output = analysis_results.output.decode()
            if analysis_output:
                result_json_str = json.loads(analysis_output)
                # the values of the following 6 keys are a dict.
                # ranges
                test_execution.all_executable_modified_stmt_ranges = eval(result_json_str["all_exec_modified_stmts_ranges"])
                test_execution.all_covered_exec_modified_stmt_ranges = eval(result_json_str["all_covered_modified_stmts_ranges"]) 
                test_execution.all_uncovered_exec_modified_stmt_ranges = eval(result_json_str["all_uncovered_modified_stmts_ranges"]) 
                # detailed numbers
                test_execution.all_executable_modified_stmts_num = eval(result_json_str["all_executable_modified_stmts_num"]) 
                test_execution.all_covered_exec_modified_stms_num = eval(result_json_str["all_covered_exec_modified_stms_num"]) 
                test_execution.all_uncovered_exec_modified_stmts_num = eval(result_json_str["all_uncovered_exec_modified_stmts_num"]) 
                # coverage rate
                test_execution.coverage_percentage = result_json_str["coverage_percentage"]

            self.container.exec_run("rm -rf CoverageAnalyzer.py")
            
        self.copy_file_from_container("/tmp/coverage_report", ".")
        with open("coverage_report", "rb") as f:
            coverage_report = f.read()
            return output, coverage_report


if __name__ == "__main__":
    code = """
x = 23

print(x)
x.foo()
print("never reach this")
"""

    executor = DockerExecutor("pandas-dev", "pandas", coverage_files=[])
    output = executor.execute_python_code(code)
    print(output)

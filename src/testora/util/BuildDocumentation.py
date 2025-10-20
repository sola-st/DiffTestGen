import os
import docker
import tarfile


class BuildDocumentation:
    def __init__(self, container_name, project_name):
        client = docker.from_env()
        self.container = client.containers.get(container_name)
        self.container.start()
        self.project_name = project_name

    def copy_file_from_container(self, file_path_in_container, target_dir):
        data, _ = self.container.get_archive(file_path_in_container)
        temp_tar_file = "temp.tar"
        with open(temp_tar_file, "wb") as f:
            for d in data:
                f.write(d)
        
        with tarfile.open(temp_tar_file, mode="r") as tar:
            tar.extractall(target_dir)

        os.remove(temp_tar_file)

    def build(self):
        build_folder = "docs"
        if self.project_name in ["scipy", "pandas"]:
            build_folder = "doc/source"
        
        # Execute sphinx-build in the project directory
        working_dir = f"/home/{self.project_name}"
        build_command = f"sphinx-build -b html {build_folder}/ {build_folder}/_build/html"
        self.container.exec_run(build_command, workdir=working_dir)
            
        self.copy_file_from_container(
                f"/home/{self.project_name}/{build_folder}/_build/html/objects.inv", f"api_{self.container.name}")
        print(f"{self.container.name}: API file written done.")


import os
import docker
import tarfile


class BuildDocumentation:
    def __init__(self, container_name, project_name, pr_num):
        client = docker.from_env()
        self.container = client.containers.get(container_name)
        self.container.start()
        self.project_name = project_name
        self.pr_num = pr_num

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
        '''
        To speed up the building:
         * -d {build_folder}/_build/doctrees:       store doctrees → incremental builds
         * -j auto:                                 parallel builds using all cores
         * -D 'extensions=[]':                      overrides all extensions → safest for speed and avoiding missing imports
        '''
        build_command = f"sphinx-build -b html -d {build_folder}/_build/doctrees -j auto -D \"extensions=[]\" {build_folder}/ {build_folder}/_build/html"
        # if self.project_name == "pandas":
        #     build_command = (
        #         'sh -c "sphinx-build -b html -d doc/source/_build/doctrees -j auto '
        #         '-D extensions=sphinx.ext.intersphinx,sphinx.ext.autodoc,sphinx.ext.autosummary,numpydoc '
        #         '-D nbsphinx_execute=never '
        #         'doc/source doc/source/_build/html"'
        #     ) 
        if self.project_name == "scipy":
            build_command = (
                f"bash -c 'source /root/conda/etc/profile.d/conda.sh"
                f" && source /root/conda/etc/profile.d/mamba.sh && mamba activate scipy-dev"
                f" && {build_command}'"
            )
        self.container.exec_run(build_command, workdir=working_dir)
        
        # it will automatically create the 'apis' folder
        self.copy_file_from_container(
                f"/home/{self.project_name}/{build_folder}/_build/html/objects.inv", f"apis/api_{self.container.name}_{self.pr_num}")
        # print(f"{self.container.name}: API file written done.")


import io
import docker
import tarfile
from testora.util.ClonedRepoManager import ClonedRepoManager


def get_repo(project_name):
    if project_name == "pandas":
        cloned_repo_manager = ClonedRepoManager(
            "../clones", "pandas", "pandas-dev/pandas", "pandas-dev", "pandas")
    elif project_name == "scipy":
        cloned_repo_manager = ClonedRepoManager(
            "../clones", "scipy", "scipy/scipy", "scipy-dev", "scipy")
    elif project_name == "keras":
        cloned_repo_manager = ClonedRepoManager(
            "../clones", "keras", "keras-team/keras", "keras-dev", "keras")
    elif project_name == "marshmallow":
        cloned_repo_manager = ClonedRepoManager(
            "../clones", "marshmallow", "marshmallow-code/marshmallow", "marshmallow-dev", "marshmallow")

    cloned_repo = cloned_repo_manager.get_cloned_repo("main")
    return cloned_repo    

# def deliver_code_to_container(container, target_file, file_in_container):
#     tar_stream = io.BytesIO()
#     with tarfile.open(fileobj=tar_stream, mode='w') as tar:
#         tar.add(target_file, arcname=file_in_container)
#     tar_stream.seek(0)
#     container.put_archive("/", tar_stream.read())

def deliver_code_to_container(container, target_file, file_in_container, replacements=None):
    container.exec_run(f"rm -rf {file_in_container}")

    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode='w') as tar:
        if replacements:
            # generally, to change the project name
            with open(target_file, "r", encoding="utf-8") as f:
                content = f.read()
            for old, new in replacements.items():
                content = content.replace(old, new)
            data = content.encode("utf-8")
            tarinfo = tarfile.TarInfo(name=file_in_container)
            tarinfo.size = len(data)
            tar.addfile(tarinfo, io.BytesIO(data))
        else:
            tar.add(target_file, arcname=file_in_container)
    tar_stream.seek(0)
    container.put_archive("/", tar_stream.read())


if __name__=="__main__":
    target_file = "src/testora/analysis/ListPublicAPIs.py"
    file_in_container = "ListPublicAPIs.py"

    with open(".target_project", "r") as f:
        target_project = f.read().strip()
    cloned_repo = get_repo(target_project)
    container_name = cloned_repo.container_name

    client = docker.from_env()
    container = client.containers.get(container_name)
    container.start()

    replacements = {"/home/target_project": f"/home/{target_project}"}
    deliver_code_to_container(container, target_file, file_in_container, replacements)

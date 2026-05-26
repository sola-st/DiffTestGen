from testora.util.BuildDocumentation import BuildDocumentation
from testora.util.Logs import Event, append_event
from os.path import exists


class SphinxOnlyPR:
    def __init__(self, github_pr, github_repo, cloned_repo_manager):
        self.cloned_repo_manager = cloned_repo_manager
        self.number = github_pr.number
        self.post_commit = github_pr.merge_commit_sha
        self.parents = github_repo.get_commit(self.post_commit).parents
        self.pre_commit = self.parents[0].sha

        pre_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.pre_commit)
        self.sphnix_build_only(pre_commit_cloned_repo, "old")
        post_commit_cloned_repo = self.cloned_repo_manager.get_cloned_repo(self.post_commit)
        self.sphnix_build_only(post_commit_cloned_repo, "new")


    def sphnix_build_only(self, cloned_repo, version):
        api_suffix_1 = "bulid sphinx documentation"
        api_suffix_2 = "sphinx documentation"
        container_name = cloned_repo.container_name
        api_file_name = "objects.inv"
        if self.cloned_repo_manager.repo_name == "keras":
            api_file_name = "keras_objects.txt"
            api_suffix_1 = "extract public APIs"
            api_suffix_2 = "extracted APIs"
        api_file = f"apis/api_{container_name}_{self.number}/{api_file_name}"
        if not exists(api_file): # write it to local for quick repetition
            # to build only once per version
            # project_name = self.cloned_repo_manager.repo_name
            # generate and copy it from container: a file f"api_{container_name}.inv" which includes all public apis
            append_event(Event(pr_nb=self.number, message=f"Starting to {api_suffix_1} ({version})."))
            BuildDocumentation(container_name, self.cloned_repo_manager.repo_name, self.number).build()
            append_event(Event(pr_nb=self.number, message=f"Done with {api_suffix_2} ({version})."))
        else:
            append_event(Event(pr_nb=self.number, message=f"Exist, {api_suffix_2} ({version})."))

"""Git platform integration for GitHub and GitLab."""

from typing import Any

import structlog
from github import Github
from gitlab import Gitlab

from config.settings import settings

logger = structlog.get_logger()


class GitClient:
    """Client for GitHub or GitLab operations."""

    def __init__(self):
        """Initialize Git client based on configuration."""
        self.platform = settings.git_platform
        self.repo_owner = settings.git_repo_owner
        self.repo_name = settings.git_repo_name
        self.logger = logger.bind(component="git_client", platform=self.platform)

        if self.platform == "github":
            if not settings.github_token:
                raise ValueError("GitHub token not configured")
            self.client = Github(settings.github_token)
            self.repo = self.client.get_repo(f"{self.repo_owner}/{self.repo_name}")
        else:  # gitlab
            if not settings.gitlab_token:
                raise ValueError("GitLab token not configured")
            self.client = Gitlab("https://gitlab.com", private_token=settings.gitlab_token)
            self.repo = self.client.projects.get(f"{self.repo_owner}/{self.repo_name}")

    async def create_branch(self, branch_name: str, from_branch: str = "main") -> None:
        """Create a new branch.

        Args:
            branch_name: Name of the new branch
            from_branch: Source branch to branch from
        """
        self.logger.info("git.creating_branch", branch=branch_name, from_branch=from_branch)

        if self.platform == "github":
            source = self.repo.get_branch(from_branch)
            self.repo.create_git_ref(f"refs/heads/{branch_name}", source.commit.sha)
        else:
            self.repo.branches.create({"branch": branch_name, "ref": from_branch})

    async def commit_files(
        self, branch: str, files: dict[str, str], message: str
    ) -> None:
        """Commit multiple files to a branch.

        Args:
            branch: Target branch
            files: Dict of file_path: content
            message: Commit message
        """
        self.logger.info("git.committing", branch=branch, file_count=len(files))

        if self.platform == "github":
            for file_path, content in files.items():
                try:
                    # Try to update existing file
                    contents = self.repo.get_contents(file_path, ref=branch)
                    self.repo.update_file(
                        file_path,
                        message,
                        content,
                        contents.sha,
                        branch=branch,
                    )
                except:
                    # Create new file
                    self.repo.create_file(file_path, message, content, branch=branch)
        else:
            # GitLab batch commit
            actions = [
                {
                    "action": "create",
                    "file_path": path,
                    "content": content,
                }
                for path, content in files.items()
            ]

            self.repo.commits.create(
                {
                    "branch": branch,
                    "commit_message": message,
                    "actions": actions,
                }
            )

    async def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main",
    ) -> str:
        """Create a pull/merge request.

        Args:
            title: PR title
            body: PR description
            head_branch: Source branch
            base_branch: Target branch

        Returns:
            URL of the created PR
        """
        self.logger.info("git.creating_pr", title=title, head=head_branch, base=base_branch)

        if self.platform == "github":
            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=base_branch,
            )
            return pr.html_url
        else:
            mr = self.repo.mergerequests.create(
                {
                    "source_branch": head_branch,
                    "target_branch": base_branch,
                    "title": title,
                    "description": body,
                }
            )
            return mr.web_url

    async def create_release(
        self,
        tag_name: str,
        name: str,
        body: str,
        target_branch: str = "main",
    ) -> str:
        """Create a release.

        Args:
            tag_name: Git tag name (e.g., v1.0.0)
            name: Release name
            body: Release notes
            target_branch: Target branch

        Returns:
            URL of the created release
        """
        self.logger.info("git.creating_release", tag=tag_name)

        if self.platform == "github":
            release = self.repo.create_git_release(
                tag=tag_name,
                name=name,
                message=body,
                target_commitish=target_branch,
            )
            return release.html_url
        else:
            release = self.repo.releases.create(
                {
                    "tag_name": tag_name,
                    "name": name,
                    "description": body,
                    "ref": target_branch,
                }
            )
            return release._attrs["_links"]["self"]

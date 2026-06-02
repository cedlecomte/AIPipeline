"""Git workspace manager for shared agent file access."""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger()

BASE_PATH = os.environ.get("WORKSPACES_PATH", "/workspaces")


class WorkspaceManager:
    """Manages Git workspaces for pipeline runs."""

    def __init__(self, correlation_id: str):
        self.correlation_id = correlation_id
        self.path = os.path.join(BASE_PATH, correlation_id)
        self.logger = logger.bind(workspace=correlation_id)

    async def create(
        self,
        repo_url: str | None = None,
        branch: str = "main",
        git_token: str | None = None,
    ) -> str:
        """Create workspace: clone existing repo or init empty one."""
        os.makedirs(self.path, exist_ok=True)

        if repo_url:
            auth_url = self._inject_token(repo_url, git_token)
            await self._run_git("clone", "--branch", branch, auth_url, self.path)
            # Create a working branch for this pipeline run
            work_branch = f"pipeline-{self.correlation_id[:8]}"
            await self._run_git("-C", self.path, "checkout", "-b", work_branch)
            self.logger.info("workspace.cloned", repo=repo_url, branch=branch)
        else:
            await self._run_git("init", self.path)
            await self._run_git("-C", self.path, "config", "user.email", "agent-pipeline@local")
            await self._run_git("-C", self.path, "config", "user.name", "Agent Pipeline")
            self.logger.info("workspace.initialized")

        return self.path

    def exists(self) -> bool:
        return os.path.isdir(self.path)

    async def list_files(self, subpath: str = ".") -> list[str]:
        """List files in the workspace, respecting .gitignore."""
        target = os.path.join(self.path, subpath)
        if not os.path.isdir(target):
            return []
        result = await self._run_git(
            "-C", self.path, "ls-files", "--cached", "--others", "--exclude-standard"
        )
        return [f for f in result.strip().split("\n") if f]

    async def read_file(self, filepath: str) -> str:
        """Read a file from the workspace."""
        full_path = os.path.join(self.path, filepath)
        self._check_path(full_path)
        if not os.path.isfile(full_path):
            raise FileNotFoundError(f"File not found: {filepath}")
        with open(full_path) as f:
            return f.read()

    async def write_file(self, filepath: str, content: str) -> None:
        """Write a file to the workspace."""
        full_path = os.path.join(self.path, filepath)
        self._check_path(full_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        self.logger.info("workspace.file_written", file=filepath, size=len(content))

    async def diff(self) -> str:
        """Show uncommitted changes."""
        staged = await self._run_git("-C", self.path, "diff", "--cached")
        unstaged = await self._run_git("-C", self.path, "diff")
        untracked = await self._run_git(
            "-C", self.path, "ls-files", "--others", "--exclude-standard"
        )
        parts = []
        if staged.strip():
            parts.append(f"=== STAGED ===\n{staged}")
        if unstaged.strip():
            parts.append(f"=== UNSTAGED ===\n{unstaged}")
        if untracked.strip():
            parts.append(f"=== UNTRACKED ===\n{untracked}")
        return "\n".join(parts) if parts else "No changes"

    async def commit(self, message: str) -> str:
        """Stage all changes and commit."""
        await self._run_git("-C", self.path, "add", "-A")
        result = await self._run_git("-C", self.path, "commit", "-m", message, "--allow-empty")
        self.logger.info("workspace.committed", message=message)
        return result

    async def push(self, remote_branch: str | None = None) -> str:
        """Push current branch to origin."""
        branch = remote_branch or await self._current_branch()
        result = await self._run_git("-C", self.path, "push", "-u", "origin", branch)
        self.logger.info("workspace.pushed", branch=branch)
        return result

    async def create_pr(self, title: str, body: str, base: str = "main") -> dict[str, Any]:
        """Create a PR/MR using the GitClient."""
        from config.settings import settings
        from shared.utils.git_client import GitClient

        client = GitClient()
        head = await self._current_branch()
        result = await client.create_pull_request(title, body, head, base)
        self.logger.info("workspace.pr_created", title=title, head=head, base=base)
        return result

    async def run_command(self, command: str, timeout: int = 120) -> str:
        """Run a shell command in the workspace directory."""
        self.logger.info("workspace.run_command", command=command[:100])
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=self.path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return f"Command timed out after {timeout}s"
        return stdout.decode("utf-8", errors="replace")

    async def cleanup(self) -> None:
        """Remove the workspace directory."""
        if os.path.isdir(self.path):
            shutil.rmtree(self.path)
            self.logger.info("workspace.cleaned_up")

    async def _current_branch(self) -> str:
        return (await self._run_git("-C", self.path, "rev-parse", "--abbrev-ref", "HEAD")).strip()

    async def _run_git(self, *args: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            self.logger.warning("workspace.git_error", args=args[:3], output=output[:200])
        return output

    def _inject_token(self, url: str, token: str | None) -> str:
        if not token:
            return url
        parsed = urlparse(url)
        return f"{parsed.scheme}://{token}@{parsed.netloc}{parsed.path}"

    def _check_path(self, full_path: str) -> None:
        """Prevent path traversal outside workspace."""
        resolved = os.path.realpath(full_path)
        workspace_resolved = os.path.realpath(self.path)
        if not resolved.startswith(workspace_resolved):
            raise ValueError(f"Path traversal detected: {full_path}")

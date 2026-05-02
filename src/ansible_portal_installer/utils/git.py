"""Git operations utilities."""

from pathlib import Path
from typing import Optional

from ..core.exceptions import GitError
from .shell import run_command, ensure_tool_exists


def clone_repo(url: str, dest: Path, branch: Optional[str] = None) -> None:
    """Clone a git repository.

    Args:
        url: Git repository URL
        dest: Destination directory
        branch: Optional branch to checkout

    Raises:
        GitError: If clone fails
    """
    ensure_tool_exists("git")

    cmd = ["git", "clone", url, str(dest)]
    if branch:
        cmd.extend(["--branch", branch])

    try:
        run_command(cmd)
    except Exception as e:
        raise GitError(f"Failed to clone repository: {e}") from e


def checkout_branch(repo_path: Path, branch: str, create: bool = False) -> None:
    """Checkout a git branch.

    Args:
        repo_path: Repository path
        branch: Branch name
        create: Create branch if it doesn't exist

    Raises:
        GitError: If checkout fails
    """
    ensure_tool_exists("git")

    cmd = ["git", "checkout"]
    if create:
        cmd.append("-b")
    cmd.append(branch)

    try:
        run_command(cmd, cwd=repo_path)
    except Exception as e:
        raise GitError(f"Failed to checkout branch '{branch}': {e}") from e


def get_current_branch(repo_path: Path) -> str:
    """Get the current git branch.

    Args:
        repo_path: Repository path

    Returns:
        Current branch name

    Raises:
        GitError: If getting branch fails
    """
    ensure_tool_exists("git")

    try:
        result = run_command(
            ["git", "branch", "--show-current"],
            cwd=repo_path,
            capture_output=True,
        )
        return result.stdout.strip()
    except Exception as e:
        raise GitError(f"Failed to get current branch: {e}") from e


def git_pull(repo_path: Path) -> None:
    """Pull latest changes from git.

    Args:
        repo_path: Repository path

    Raises:
        GitError: If pull fails
    """
    ensure_tool_exists("git")

    try:
        run_command(["git", "pull"], cwd=repo_path)
    except Exception as e:
        raise GitError(f"Failed to pull changes: {e}") from e

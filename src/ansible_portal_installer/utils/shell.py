"""Shell command execution utilities."""

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..core.exceptions import ToolNotFoundError
from ..ui import print_error, print_info


def run_command(
    cmd: list[str],
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
    capture_output: bool = False,
    check: bool = True,
    verbose: bool = False,
) -> subprocess.CompletedProcess:
    """Run a shell command.

    Args:
        cmd: Command and arguments as list
        cwd: Working directory
        env: Environment variables
        capture_output: Capture stdout/stderr
        check: Raise exception on non-zero exit
        verbose: Print command being executed

    Returns:
        CompletedProcess instance

    Raises:
        subprocess.CalledProcessError: If command fails and check=True
    """
    if verbose:
        print_info(f"Running: {' '.join(cmd)}")

    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=capture_output,
        text=True,
        check=check,
    )


def check_tool_exists(tool: str) -> bool:
    """Check if a tool exists in PATH.

    Args:
        tool: Tool name to check

    Returns:
        True if tool exists, False otherwise
    """
    return shutil.which(tool) is not None


def get_tool_version(tool: str, version_flag: str = "--version") -> Optional[str]:
    """Get version of a tool.

    Args:
        tool: Tool name
        version_flag: Flag to get version (default: --version)

    Returns:
        Version string or None if not found
    """
    try:
        result = run_command(
            [tool, version_flag],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0]
        return None
    except FileNotFoundError:
        return None


def ensure_tool_exists(tool: str) -> None:
    """Ensure a tool exists, raise exception if not.

    Args:
        tool: Tool name to check

    Raises:
        ToolNotFoundError: If tool is not found
    """
    if not check_tool_exists(tool):
        raise ToolNotFoundError(
            f"Required tool '{tool}' not found in PATH. Please install it first."
        )


def validate_required_tools(tools: list[str]) -> list[str]:
    """Validate that all required tools are installed.

    Args:
        tools: List of required tool names

    Returns:
        List of missing tools (empty if all present)
    """
    missing = []
    for tool in tools:
        if not check_tool_exists(tool):
            missing.append(tool)
    return missing

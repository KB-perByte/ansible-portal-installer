"""Container operations (Podman/Docker) utilities."""

from pathlib import Path
from typing import Optional

from ..core.exceptions import ContainerError
from .shell import run_command, ensure_tool_exists, check_tool_exists


def get_container_tool() -> str:
    """Get available container tool (podman or docker).

    Returns:
        Container tool name

    Raises:
        ContainerError: If no container tool is found
    """
    if check_tool_exists("podman"):
        return "podman"
    elif check_tool_exists("docker"):
        return "docker"
    else:
        raise ContainerError("Neither podman nor docker found in PATH")


def login_registry(
    registry: str,
    username: str,
    password: str,
    tool: Optional[str] = None,
) -> None:
    """Login to a container registry.

    Args:
        registry: Registry URL
        username: Username
        password: Password/token
        tool: Container tool to use (auto-detect if None)

    Raises:
        ContainerError: If login fails
    """
    if tool is None:
        tool = get_container_tool()

    ensure_tool_exists(tool)

    try:
        run_command(
            [tool, "login", "-u", username, "-p", password, registry],
            capture_output=True,
        )
    except Exception as e:
        raise ContainerError(f"Failed to login to registry: {e}") from e


def build_image(
    context_dir: Path,
    containerfile: str,
    tag: str,
    tool: Optional[str] = None,
) -> None:
    """Build a container image.

    Args:
        context_dir: Build context directory
        containerfile: Path to Containerfile/Dockerfile
        tag: Image tag
        tool: Container tool to use (auto-detect if None)

    Raises:
        ContainerError: If build fails
    """
    if tool is None:
        tool = get_container_tool()

    ensure_tool_exists(tool)

    try:
        run_command(
            [tool, "build", "-f", containerfile, "-t", tag, "."],
            cwd=context_dir,
        )
    except Exception as e:
        raise ContainerError(f"Failed to build image: {e}") from e


def push_image(tag: str, tool: Optional[str] = None) -> None:
    """Push a container image to registry.

    Args:
        tag: Image tag
        tool: Container tool to use (auto-detect if None)

    Raises:
        ContainerError: If push fails
    """
    if tool is None:
        tool = get_container_tool()

    ensure_tool_exists(tool)

    try:
        run_command([tool, "push", tag])
    except Exception as e:
        raise ContainerError(f"Failed to push image: {e}") from e


def tag_image(source: str, target: str, tool: Optional[str] = None) -> None:
    """Tag a container image.

    Args:
        source: Source image tag
        target: Target image tag
        tool: Container tool to use (auto-detect if None)

    Raises:
        ContainerError: If tagging fails
    """
    if tool is None:
        tool = get_container_tool()

    ensure_tool_exists(tool)

    try:
        run_command([tool, "tag", source, target])
    except Exception as e:
        raise ContainerError(f"Failed to tag image: {e}") from e


def skopeo_inspect(
    image_ref: str,
    credentials_file: Optional[Path] = None,
) -> dict:
    """Inspect an OCI image using skopeo.

    Args:
        image_ref: Full image reference (registry/org/name:tag)
        credentials_file: Path to auth.json file

    Returns:
        Dict with image manifest information

    Raises:
        ContainerError: If inspection fails
    """
    ensure_tool_exists("skopeo")

    cmd = ["skopeo", "inspect", f"docker://{image_ref}"]
    if credentials_file:
        cmd.extend(["--authfile", str(credentials_file)])

    try:
        result = run_command(cmd, capture_output=True)
        import json
        return json.loads(result.stdout)
    except Exception as e:
        raise ContainerError(f"Failed to inspect image: {e}") from e

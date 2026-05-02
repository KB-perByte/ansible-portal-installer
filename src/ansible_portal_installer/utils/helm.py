"""Helm operations utilities."""

from pathlib import Path
from typing import Optional, Dict

from ..core.exceptions import HelmError
from .shell import run_command, ensure_tool_exists


def helm_install(
    release_name: str,
    chart_path: Path,
    namespace: str,
    values: Optional[Dict[str, str]] = None,
    create_namespace: bool = False,
) -> None:
    """Install a Helm chart.

    Args:
        release_name: Helm release name
        chart_path: Path to Helm chart
        namespace: Target namespace
        values: Optional values to set
        create_namespace: Create namespace if it doesn't exist

    Raises:
        HelmError: If install fails
    """
    ensure_tool_exists("helm")

    cmd = ["helm", "install", release_name, str(chart_path), "-n", namespace]

    if create_namespace:
        cmd.append("--create-namespace")

    if values:
        for key, value in values.items():
            cmd.extend(["--set", f"{key}={value}"])

    try:
        run_command(cmd)
    except Exception as e:
        raise HelmError(f"Failed to install Helm chart: {e}") from e


def helm_upgrade(
    release_name: str,
    chart_path: Path,
    namespace: str,
    values: Optional[Dict[str, str]] = None,
    install: bool = True,
) -> None:
    """Upgrade a Helm release.

    Args:
        release_name: Helm release name
        chart_path: Path to Helm chart
        namespace: Target namespace
        values: Optional values to set
        install: Install if release doesn't exist

    Raises:
        HelmError: If upgrade fails
    """
    ensure_tool_exists("helm")

    cmd = ["helm", "upgrade", release_name, str(chart_path), "-n", namespace]

    if install:
        cmd.append("--install")

    if values:
        for key, value in values.items():
            cmd.extend(["--set", f"{key}={value}"])

    try:
        run_command(cmd)
    except Exception as e:
        raise HelmError(f"Failed to upgrade Helm release: {e}") from e


def helm_uninstall(release_name: str, namespace: str) -> None:
    """Uninstall a Helm release.

    Args:
        release_name: Helm release name
        namespace: Target namespace

    Raises:
        HelmError: If uninstall fails
    """
    ensure_tool_exists("helm")

    try:
        run_command(["helm", "uninstall", release_name, "-n", namespace])
    except Exception as e:
        raise HelmError(f"Failed to uninstall Helm release: {e}") from e


def helm_get_values(release_name: str, namespace: str) -> str:
    """Get values for a Helm release.

    Args:
        release_name: Helm release name
        namespace: Target namespace

    Returns:
        YAML values

    Raises:
        HelmError: If getting values fails
    """
    ensure_tool_exists("helm")

    try:
        result = run_command(
            ["helm", "get", "values", release_name, "-n", namespace],
            capture_output=True,
        )
        return result.stdout
    except Exception as e:
        raise HelmError(f"Failed to get Helm values: {e}") from e


def helm_list(namespace: Optional[str] = None) -> list[dict]:
    """List Helm releases.

    Args:
        namespace: Optional namespace filter

    Returns:
        List of release dictionaries

    Raises:
        HelmError: If listing fails
    """
    ensure_tool_exists("helm")

    cmd = ["helm", "list", "-o", "json"]
    if namespace:
        cmd.extend(["-n", namespace])

    try:
        result = run_command(cmd, capture_output=True)
        import json

        return json.loads(result.stdout) if result.stdout else []
    except Exception as e:
        raise HelmError(f"Failed to list Helm releases: {e}") from e


def helm_status(release_name: str, namespace: str) -> str:
    """Get status of a Helm release.

    Args:
        release_name: Helm release name
        namespace: Target namespace

    Returns:
        Status output

    Raises:
        HelmError: If getting status fails
    """
    ensure_tool_exists("helm")

    try:
        result = run_command(
            ["helm", "status", release_name, "-n", namespace],
            capture_output=True,
        )
        return result.stdout
    except Exception as e:
        raise HelmError(f"Failed to get Helm status: {e}") from e

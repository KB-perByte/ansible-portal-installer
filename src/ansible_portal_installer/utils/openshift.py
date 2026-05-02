"""OpenShift CLI operations utilities."""

from pathlib import Path
from typing import Optional, Dict

from ..core.exceptions import OpenShiftError
from .shell import run_command, ensure_tool_exists


def oc_login(
    server: str,
    token: str,
    insecure_skip_tls_verify: bool = False,
) -> None:
    """Login to OpenShift cluster.

    Args:
        server: OpenShift server URL
        token: Authentication token
        insecure_skip_tls_verify: Skip TLS verification

    Raises:
        OpenShiftError: If login fails
    """
    ensure_tool_exists("oc")

    cmd = ["oc", "login", "--server", server, "--token", token]
    if insecure_skip_tls_verify:
        cmd.append("--insecure-skip-tls-verify")

    try:
        run_command(cmd, capture_output=True)
    except Exception as e:
        raise OpenShiftError(f"Failed to login to OpenShift: {e}") from e


def oc_project_exists(namespace: str) -> bool:
    """Check if an OpenShift project/namespace exists.

    Args:
        namespace: Namespace name

    Returns:
        True if project exists, False otherwise
    """
    ensure_tool_exists("oc")

    try:
        result = run_command(
            ["oc", "get", "project", namespace],
            capture_output=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def oc_create_project(namespace: str) -> None:
    """Create an OpenShift project.

    Args:
        namespace: Namespace name

    Raises:
        OpenShiftError: If project creation fails
    """
    ensure_tool_exists("oc")

    try:
        run_command(["oc", "new-project", namespace])
    except Exception as e:
        raise OpenShiftError(f"Failed to create project: {e}") from e


def oc_use_project(namespace: str) -> None:
    """Switch to an OpenShift project.

    Args:
        namespace: Namespace name

    Raises:
        OpenShiftError: If switching project fails
    """
    ensure_tool_exists("oc")

    try:
        run_command(["oc", "project", namespace])
    except Exception as e:
        raise OpenShiftError(f"Failed to switch to project: {e}") from e


def oc_create_secret(
    name: str,
    data: Dict[str, str],
    namespace: Optional[str] = None,
    secret_type: str = "generic",
) -> None:
    """Create an OpenShift secret.

    Args:
        name: Secret name
        data: Dictionary of key-value pairs
        namespace: Target namespace
        secret_type: Secret type (generic, dockerconfigjson, etc.)

    Raises:
        OpenShiftError: If secret creation fails
    """
    ensure_tool_exists("oc")

    cmd = ["oc", "create", "secret", secret_type, name]

    if secret_type == "generic":
        for key, value in data.items():
            cmd.extend([f"--from-literal={key}={value}"])
    elif secret_type == "docker-registry":
        # Handle docker registry secrets differently
        cmd.extend(data.get("args", []))

    if namespace:
        cmd.extend(["-n", namespace])

    try:
        run_command(cmd)
    except Exception as e:
        raise OpenShiftError(f"Failed to create secret '{name}': {e}") from e


def oc_secret_exists(name: str, namespace: Optional[str] = None) -> bool:
    """Check if a secret exists.

    Args:
        name: Secret name
        namespace: Target namespace

    Returns:
        True if secret exists, False otherwise
    """
    ensure_tool_exists("oc")

    cmd = ["oc", "get", "secret", name]
    if namespace:
        cmd.extend(["-n", namespace])

    try:
        result = run_command(cmd, capture_output=True, check=False)
        return result.returncode == 0
    except Exception:
        return False


def oc_get_route(
    release_name: str,
    namespace: Optional[str] = None,
) -> Optional[str]:
    """Get the route URL for a release.

    Args:
        release_name: Helm release name
        namespace: Target namespace

    Returns:
        Route URL or None if not found
    """
    ensure_tool_exists("oc")

    cmd = ["oc", "get", "route", "-o", "jsonpath={.items[0].spec.host}"]
    if namespace:
        cmd.extend(["-n", namespace])

    try:
        result = run_command(cmd, capture_output=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            return f"https://{result.stdout.strip()}"
        return None
    except Exception:
        return None


def oc_get_pods(namespace: Optional[str] = None) -> list[dict]:
    """Get pods in a namespace.

    Args:
        namespace: Target namespace

    Returns:
        List of pod dictionaries with name and status
    """
    ensure_tool_exists("oc")

    cmd = [
        "oc",
        "get",
        "pods",
        "-o",
        "jsonpath={range .items[*]}{.metadata.name},{.status.phase}{'\\n'}{end}",
    ]
    if namespace:
        cmd.extend(["-n", namespace])

    try:
        result = run_command(cmd, capture_output=True, check=False)
        if result.returncode != 0:
            return []

        pods = []
        for line in result.stdout.strip().split("\n"):
            if line:
                name, status = line.split(",")
                pods.append({"name": name, "status": status})
        return pods
    except Exception:
        return []


def oc_wait_for_pods(
    namespace: str,
    timeout: int = 300,
) -> None:
    """Wait for all pods to be running.

    Args:
        namespace: Target namespace
        timeout: Timeout in seconds

    Raises:
        OpenShiftError: If pods don't become ready
    """
    ensure_tool_exists("oc")

    try:
        run_command(
            [
                "oc",
                "wait",
                "--for=condition=Ready",
                "pod",
                "--all",
                "-n",
                namespace,
                f"--timeout={timeout}s",
            ]
        )
    except Exception as e:
        raise OpenShiftError(f"Pods did not become ready: {e}") from e


def oc_get_pod_logs(
    pod_name: str,
    container: Optional[str] = None,
    namespace: Optional[str] = None,
    previous: bool = False,
) -> str:
    """Get logs from a pod container.

    Args:
        pod_name: Pod name
        container: Container name (omit for single-container pods)
        namespace: Target namespace
        previous: Get logs from previous container instance

    Returns:
        Log output as string

    Raises:
        OpenShiftError: If getting logs fails
    """
    ensure_tool_exists("oc")

    cmd = ["oc", "logs", pod_name]
    if container:
        cmd.extend(["-c", container])
    if namespace:
        cmd.extend(["-n", namespace])
    if previous:
        cmd.append("--previous")

    try:
        result = run_command(cmd, capture_output=True)
        return result.stdout
    except Exception as e:
        raise OpenShiftError(f"Failed to get logs from pod '{pod_name}': {e}") from e


def oc_describe_pod(
    pod_name: str,
    namespace: Optional[str] = None,
) -> str:
    """Describe a pod.

    Args:
        pod_name: Pod name
        namespace: Target namespace

    Returns:
        Describe output as string

    Raises:
        OpenShiftError: If describe fails
    """
    ensure_tool_exists("oc")

    cmd = ["oc", "describe", "pod", pod_name]
    if namespace:
        cmd.extend(["-n", namespace])

    try:
        result = run_command(cmd, capture_output=True)
        return result.stdout
    except Exception as e:
        raise OpenShiftError(f"Failed to describe pod '{pod_name}': {e}") from e


def oc_get_events(
    namespace: Optional[str] = None,
    sort_by: str = ".lastTimestamp",
) -> str:
    """Get events in a namespace.

    Args:
        namespace: Target namespace
        sort_by: Field to sort by (default: .lastTimestamp)

    Returns:
        Events output as string

    Raises:
        OpenShiftError: If getting events fails
    """
    ensure_tool_exists("oc")

    cmd = ["oc", "get", "events", f"--sort-by={sort_by}"]
    if namespace:
        cmd.extend(["-n", namespace])

    try:
        result = run_command(cmd, capture_output=True)
        return result.stdout
    except Exception as e:
        raise OpenShiftError(f"Failed to get events: {e}") from e


def oc_rollout_status(
    deployment_name: str,
    namespace: Optional[str] = None,
    timeout: int = 600,
) -> None:
    """Wait for deployment rollout to complete.

    Args:
        deployment_name: Deployment name
        namespace: Target namespace
        timeout: Timeout in seconds

    Raises:
        OpenShiftError: If rollout fails or times out
    """
    ensure_tool_exists("oc")

    cmd = ["oc", "rollout", "status", f"deployment/{deployment_name}"]
    if namespace:
        cmd.extend(["-n", namespace])
    cmd.append(f"--timeout={timeout}s")

    try:
        run_command(cmd)
    except Exception as e:
        raise OpenShiftError(f"Rollout status check failed: {e}") from e


def oc_get_pod_status(
    pod_name: str,
    namespace: Optional[str] = None,
) -> dict:
    """Get detailed pod status including container states.

    Args:
        pod_name: Pod name
        namespace: Target namespace

    Returns:
        Dict with pod status information

    Raises:
        OpenShiftError: If getting status fails
    """
    ensure_tool_exists("oc")

    cmd = [
        "oc",
        "get",
        "pod",
        pod_name,
        "-o",
        "json",
    ]
    if namespace:
        cmd.extend(["-n", namespace])

    try:
        result = run_command(cmd, capture_output=True)
        import json
        return json.loads(result.stdout)
    except Exception as e:
        raise OpenShiftError(f"Failed to get pod status: {e}") from e

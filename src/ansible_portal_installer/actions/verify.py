"""Verification and status check actions."""

from ..config import Settings
from ..constants import REQUIRED_TOOLS
from ..core import ValidationError
from ..ui import (
    print_header,
    print_success,
    print_error,
    print_warning,
    console,
    print_status_table,
)
from ..utils import check_tool_exists, oc_get_pods, oc_get_route


def check_prerequisites() -> dict[str, bool]:
    """Check that all required tools are installed.

    Returns:
        Dictionary of tool names and their availability status
    """
    print_header("Checking Prerequisites")

    results = {}
    for tool in REQUIRED_TOOLS:
        available = check_tool_exists(tool)
        results[tool] = available

        if available:
            print_success(f"{tool} is installed")
        else:
            print_error(f"{tool} is NOT installed")

    return results


def verify_deployment(settings: Settings) -> dict[str, bool]:
    """Verify deployment status.

    Args:
        settings: Application settings

    Returns:
        Dictionary of verification checks and their status
    """
    print_header(f"Verifying Deployment: {settings.helm_release_name}")

    namespace = settings.openshift_namespace
    results = {}

    # Check pods
    pods = oc_get_pods(namespace)
    if pods:
        all_running = all(pod["status"] == "Running" for pod in pods)
        results["Pods Running"] = all_running

        if all_running:
            print_success(f"All {len(pods)} pod(s) are running")
        else:
            print_warning(f"Not all pods are running ({len(pods)} total)")
            for pod in pods:
                status = "✓" if pod["status"] == "Running" else "✗"
                console.print(f"  [{status}] {pod['name']}: {pod['status']}")
    else:
        results["Pods Running"] = False
        print_error("No pods found")

    # Check route
    route = oc_get_route(settings.helm_release_name, namespace)
    if route:
        results["Route Exists"] = True
        print_success(f"Portal route: {route}")
    else:
        results["Route Exists"] = False
        print_error("Portal route not found")

    # Summary
    console.print()
    if all(results.values()):
        print_success("All verification checks passed!")
    else:
        print_warning("Some verification checks failed")

    print_status_table(results)

    return results

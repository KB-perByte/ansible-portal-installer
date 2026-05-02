"""Health check action for deployment verification."""

from typing import Dict, Optional

from ..config import Settings
from ..core import HealthCheckError
from ..ui import print_header, print_success, print_error, print_warning, console, print_status_table
from ..utils import (
    oc_get_pods,
    oc_get_pod_logs,
    oc_get_route,
    oc_get_pod_status,
    http_health_check,
    skopeo_inspect,
)


# Expected plugin names in init container logs
EXPECTED_PLUGINS = [
    "ansible-plugin-scaffolder-backend-module-backstage-rhaap",
    "ansible-backstage-plugin-catalog-backend-module-rhaap",
    "ansible-plugin-backstage-self-service",
    "ansible-backstage-plugin-auth-backend-module-rhaap-provider",
]


def check_pod_health(settings: Settings) -> Dict[str, bool]:
    """Check pod health status.

    Returns:
        Dict of check name -> pass/fail
    """
    results = {}
    namespace = settings.openshift_namespace

    try:
        pods = oc_get_pods(namespace=namespace)

        if not pods:
            results["Pods Exist"] = False
            return results

        results["Pods Exist"] = True

        # Check if any pods are running
        running_pods = [p for p in pods if p["status"] == "Running"]
        results["Pods Running"] = len(running_pods) > 0

        # Check for RHDH hub pod
        rhdh_pods = [p for p in pods if "rhaap-portal" in p["name"] or "backstage" in p["name"]]
        results["RHDH Pod Running"] = any(p["status"] == "Running" for p in rhdh_pods)

        # Check for PostgreSQL pod
        postgres_pods = [p for p in pods if "postgres" in p["name"].lower()]
        results["PostgreSQL Pod Running"] = any(p["status"] == "Running" for p in postgres_pods)

        # Check init containers completed
        if rhdh_pods:
            try:
                pod_status = oc_get_pod_status(rhdh_pods[0]["name"], namespace)
                init_statuses = pod_status.get("status", {}).get("initContainerStatuses", [])

                init_complete = all(
                    status.get("state", {}).get("terminated", {}).get("reason") == "Completed"
                    for status in init_statuses
                )
                results["Init Containers Completed"] = init_complete
            except Exception:
                results["Init Containers Completed"] = False

    except Exception as e:
        console.print(f"[yellow]Warning: Pod health check failed: {e}[/yellow]")
        results["Pods Running"] = False

    return results


def check_init_container_logs(settings: Settings) -> Dict[str, bool]:
    """Parse init container logs for plugin installation success.

    Returns:
        Dict of check name -> pass/fail
    """
    results = {}
    namespace = settings.openshift_namespace

    try:
        # Find RHDH pod
        pods = oc_get_pods(namespace=namespace)
        rhdh_pods = [p for p in pods if "rhaap-portal" in p["name"] or "backstage" in p["name"]]

        if not rhdh_pods:
            results["Plugin Logs Available"] = False
            return results

        # Get init container logs
        logs = oc_get_pod_logs(
            pod_name=rhdh_pods[0]["name"],
            container="install-dynamic-plugins",
            namespace=namespace,
        )

        results["Plugin Logs Available"] = True

        # Check for each expected plugin
        for plugin in EXPECTED_PLUGINS:
            plugin_installed = plugin in logs and "Successfully installed" in logs
            results[f"Plugin: {plugin.split('-')[-1]}"] = plugin_installed

        # Check for overall success
        results["All Plugins Loaded"] = all(
            plugin in logs for plugin in EXPECTED_PLUGINS
        )

    except Exception as e:
        console.print(f"[yellow]Warning: Init container log check failed: {e}[/yellow]")
        results["Plugin Logs Available"] = False

    return results


def check_route_reachability(settings: Settings) -> Dict[str, bool]:
    """Check portal route accessibility.

    Returns:
        Dict of check name -> pass/fail
    """
    results = {}

    try:
        route = oc_get_route(
            release_name=settings.helm_release_name,
            namespace=settings.openshift_namespace,
        )

        if not route:
            results["Route Exists"] = False
            return results

        results["Route Exists"] = True

        # HTTP health check
        reachable = http_health_check(route, timeout=30, expected_status=200)
        results["Route Reachable"] = reachable

    except Exception as e:
        console.print(f"[yellow]Warning: Route check failed: {e}[/yellow]")
        results["Route Exists"] = False

    return results


def check_aap_connectivity(settings: Settings) -> Dict[str, bool]:
    """Check AAP connectivity via catalog sync status.

    Returns:
        Dict of check name -> pass/fail
    """
    results = {}

    try:
        route = oc_get_route(
            release_name=settings.helm_release_name,
            namespace=settings.openshift_namespace,
        )

        if not route:
            results["AAP Sync Endpoint"] = False
            return results

        # Check AAP sync endpoint
        sync_url = f"{route}/api/ansible/sync/status"
        aap_reachable = http_health_check(sync_url, timeout=30)
        results["AAP Sync Endpoint"] = aap_reachable

    except Exception as e:
        console.print(f"[yellow]Warning: AAP connectivity check failed: {e}[/yellow]")
        results["AAP Sync Endpoint"] = False

    return results


def check_settings_api(settings: Settings) -> Dict[str, bool]:
    """Check settings management API health.

    Returns:
        Dict of check name -> pass/fail
    """
    results = {}

    try:
        route = oc_get_route(
            release_name=settings.helm_release_name,
            namespace=settings.openshift_namespace,
        )

        if not route:
            results["Settings API"] = False
            return results

        # Check settings API endpoint
        settings_url = f"{route}/api/portal-settings/health"
        settings_reachable = http_health_check(settings_url, timeout=30)
        results["Settings API"] = settings_reachable

    except Exception as e:
        console.print(f"[yellow]Warning: Settings API check failed: {e}[/yellow]")
        results["Settings API"] = False

    return results


def check_plugin_registry(settings: Settings) -> Dict[str, bool]:
    """Check plugin registry OCI image accessibility.

    Returns:
        Dict of check name -> pass/fail
    """
    results = {}

    try:
        # Build OCI image reference
        image_ref = settings.full_image_reference

        # Try to inspect image (will fail if not accessible)
        skopeo_inspect(image_ref)
        results["Plugin Registry Accessible"] = True

    except Exception as e:
        console.print(f"[yellow]Warning: Plugin registry check failed: {e}[/yellow]")
        results["Plugin Registry Accessible"] = False

    return results


def health_check_command(
    settings: Settings,
    namespace: Optional[str] = None,
    release_name: Optional[str] = None,
) -> Dict[str, bool]:
    """Execute comprehensive health check.

    Args:
        settings: Application settings
        namespace: Override namespace
        release_name: Override release name

    Returns:
        Dict of all checks and results

    Raises:
        HealthCheckError: If critical checks fail
    """
    # Override settings if provided
    if namespace:
        settings.openshift_namespace = namespace
    if release_name:
        settings.helm_release_name = release_name

    print_header(f"Health Check: {settings.helm_release_name}")
    console.print()

    all_results = {}

    # Run all checks
    console.print("[cyan]Checking pod health...[/cyan]")
    all_results.update(check_pod_health(settings))

    console.print("[cyan]Checking init container logs...[/cyan]")
    all_results.update(check_init_container_logs(settings))

    console.print("[cyan]Checking route reachability...[/cyan]")
    all_results.update(check_route_reachability(settings))

    console.print("[cyan]Checking AAP connectivity...[/cyan]")
    all_results.update(check_aap_connectivity(settings))

    console.print("[cyan]Checking settings API...[/cyan]")
    all_results.update(check_settings_api(settings))

    console.print("[cyan]Checking plugin registry...[/cyan]")
    all_results.update(check_plugin_registry(settings))

    # Print summary
    console.print()
    print_status_table(all_results)
    console.print()

    # Check critical failures
    critical_checks = ["Pods Running", "Route Exists", "Route Reachable"]
    critical_failures = [
        check for check in critical_checks
        if check in all_results and not all_results[check]
    ]

    if critical_failures:
        print_error(f"Critical checks failed: {', '.join(critical_failures)}")
    else:
        # Check for any warnings
        failed_checks = [k for k, v in all_results.items() if not v]
        if failed_checks:
            print_warning(f"Some checks failed: {', '.join(failed_checks)}")
        else:
            print_success("All health checks passed!")

    return all_results

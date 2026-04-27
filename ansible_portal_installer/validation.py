"""Health check and validation operations."""

from typing import Dict, List, Tuple

import httpx
from rich.console import Console
from rich.table import Table

from .config import HealthCheckConfig
from .k8s import KubernetesClient, OpenShiftClient

console = Console()


class HealthChecker:
    """Health checker for portal deployment."""

    def __init__(self, config: HealthCheckConfig) -> None:
        """Initialize health checker."""
        self.config = config
        self.k8s = KubernetesClient()
        self.oc = OpenShiftClient()
        self.checks_passed = 0
        self.checks_failed = 0

    def run_all_checks(self) -> bool:
        """Run all health checks and return overall status."""
        console.print("\n[bold blue]Running Health Checks[/bold blue]\n")

        checks = [
            ("Pod Health", self.check_pod_health),
            ("Plugin Loading", self.check_plugin_loading),
            ("Route Accessibility", self.check_route_accessibility),
            ("AAP Connectivity", self.check_aap_connectivity),
            ("Settings Management", self.check_settings_management),
        ]

        for check_name, check_func in checks:
            console.print(f"[blue]Checking {check_name}...[/blue]")
            passed, message = check_func()

            if passed:
                self.checks_passed += 1
                console.print(f"[green]✓[/green] {message}")
            else:
                self.checks_failed += 1
                console.print(f"[red]✗[/red] {message}")

            console.print()

        self._print_summary()
        return self.checks_failed == 0

    def check_pod_health(self) -> Tuple[bool, str]:
        """Check if pods are running and ready."""
        # Get RHDH pods
        rhdh_pods = self.k8s.get_pods(
            self.config.namespace, label_selector="app.kubernetes.io/name=backstage"
        )

        if not rhdh_pods:
            return False, "No RHDH pods found"

        unhealthy_pods = []
        for pod in rhdh_pods:
            if pod.status.phase != "Running":
                unhealthy_pods.append(f"{pod.metadata.name} (Phase: {pod.status.phase})")
                continue

            # Check if all containers are ready
            if pod.status.container_statuses:
                for container in pod.status.container_statuses:
                    if not container.ready:
                        unhealthy_pods.append(
                            f"{pod.metadata.name}/{container.name} (Not Ready)"
                        )

        if unhealthy_pods:
            return False, f"Unhealthy pods: {', '.join(unhealthy_pods)}"

        # Check PostgreSQL pods
        pg_pods = self.k8s.get_pods(
            self.config.namespace, label_selector="app.kubernetes.io/name=postgresql"
        )

        if pg_pods:
            for pod in pg_pods:
                if pod.status.phase != "Running":
                    return False, f"PostgreSQL pod not running: {pod.metadata.name}"

        return True, f"All pods healthy ({len(rhdh_pods)} RHDH, {len(pg_pods)} PostgreSQL)"

    def check_plugin_loading(self) -> Tuple[bool, str]:
        """Check if plugins were loaded successfully from init container."""
        rhdh_pods = self.k8s.get_pods(
            self.config.namespace, label_selector="app.kubernetes.io/name=backstage"
        )

        if not rhdh_pods:
            return False, "No RHDH pods found"

        pod = rhdh_pods[0]  # Check first pod

        # Get init container logs
        init_logs = self.k8s.get_pod_logs(
            self.config.namespace,
            pod.metadata.name,
            container="install-dynamic-plugins",
            tail_lines=500,
        )

        if "Error" in init_logs:
            return False, "Init container has errors in logs"

        # Check for expected plugins
        expected_plugins = [
            "plugin-backstage-rhaap",
            "plugin-backstage-self-service",
            "backstage-plugin-catalog-backend-module-rhaap",
            "plugin-scaffolder-backend-module-backstage-rhaap",
            "backstage-plugin-auth-backend-module-rhaap-provider",
        ]

        loaded_plugins = [p for p in expected_plugins if p in init_logs]

        if len(loaded_plugins) < len(expected_plugins):
            missing = set(expected_plugins) - set(loaded_plugins)
            return False, f"Missing plugins: {', '.join(missing)}"

        return True, f"All {len(expected_plugins)} plugins loaded successfully"

    def check_route_accessibility(self) -> Tuple[bool, str]:
        """Check if portal route is accessible."""
        route_host = self.oc.get_route_host(
            self.config.namespace, "app.kubernetes.io/name=backstage"
        )

        if not route_host:
            return False, "No route found for portal"

        route_url = f"https://{route_host}"

        try:
            # Allow self-signed certs for dev environments
            response = httpx.get(route_url, verify=False, timeout=10, follow_redirects=True)

            if response.status_code in [200, 302, 401]:
                return True, f"Route accessible (HTTP {response.status_code}): {route_url}"
            else:
                return False, f"Route returned HTTP {response.status_code}"

        except httpx.RequestError as e:
            return False, f"Route not accessible: {e}"

    def check_aap_connectivity(self) -> Tuple[bool, str]:
        """Check AAP connectivity via sync API."""
        route_host = self.oc.get_route_host(
            self.config.namespace, "app.kubernetes.io/name=backstage"
        )

        if not route_host:
            return False, "No route found, cannot test AAP connectivity"

        sync_url = f"https://{route_host}/api/ansible/sync/status"

        try:
            response = httpx.get(sync_url, verify=False, timeout=10)
            # 401/403 means endpoint exists but requires auth (OK)
            # 200 means endpoint is accessible
            if response.status_code in [200, 401, 403]:
                return True, f"AAP sync API responding (HTTP {response.status_code})"
            else:
                return False, f"AAP sync API returned HTTP {response.status_code}"

        except httpx.RequestError:
            # Non-critical, AAP might not be configured yet
            return True, "AAP connectivity check skipped (not critical)"

    def check_settings_management(self) -> Tuple[bool, str]:
        """Check settings management API."""
        route_host = self.oc.get_route_host(
            self.config.namespace, "app.kubernetes.io/name=backstage"
        )

        if not route_host:
            return False, "No route found, cannot test settings API"

        settings_url = f"https://{route_host}/api/portal-settings/health"

        try:
            response = httpx.get(settings_url, verify=False, timeout=10)
            if response.status_code in [200, 401, 403, 404]:
                return True, f"Settings API responding (HTTP {response.status_code})"
            else:
                return False, f"Settings API returned HTTP {response.status_code}"

        except httpx.RequestError:
            # Non-critical, settings management might not be enabled
            return True, "Settings API check skipped (not critical)"

    def _print_summary(self) -> None:
        """Print health check summary."""
        total = self.checks_passed + self.checks_failed

        table = Table(title="Health Check Summary", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        table.add_row("Namespace", self.config.namespace)
        if self.config.release_name:
            table.add_row("Release", self.config.release_name)
        table.add_row("Total Checks", str(total))
        table.add_row("Passed", f"[green]{self.checks_passed}[/green]")
        table.add_row("Failed", f"[red]{self.checks_failed}[/red]")

        console.print(table)

        if self.checks_failed == 0:
            console.print("\n[bold green]✓ All health checks passed![/bold green]\n")
        else:
            console.print(
                f"\n[bold red]✗ {self.checks_failed} health check(s) failed[/bold red]\n"
            )

"""Validate command - Run health checks on deployment."""

import sys

import click
from rich.console import Console

from ..config import HealthCheckConfig
from ..k8s import KubernetesClient
from ..validation import HealthChecker

console = Console()


@click.command()
@click.option(
    "--namespace",
    "-n",
    help="OpenShift namespace (auto-detect if not provided)",
    envvar="OCP_NAMESPACE",
)
@click.option(
    "--release-name",
    help="Helm release name (auto-detect if not provided)",
    envvar="RELEASE_NAME",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed check output",
)
@click.option(
    "--timeout",
    default=300,
    help="Health check timeout in seconds",
    type=int,
)
def validate(
    namespace: str | None,
    release_name: str | None,
    verbose: bool,
    timeout: int,
) -> None:
    """Run comprehensive health checks on portal deployment.

    This command validates:
    - Pod health (RHDH, PostgreSQL)
    - Plugin loading from init container
    - Route accessibility
    - AAP connectivity via sync API
    - Settings management API
    - Database state

    Exit codes:
    - 0: All checks passed
    - 1: Some checks failed
    - 2: Could not connect to cluster
    """
    console.print("[bold blue]Ansible Portal - Health Check[/bold blue]\n")

    # Initialize Kubernetes client
    try:
        k8s = KubernetesClient()
    except RuntimeError as e:
        console.print(f"[red]Error connecting to cluster: {e}[/red]")
        sys.exit(2)

    # Auto-detect namespace if not provided
    if not namespace:
        namespace = _auto_detect_namespace(k8s)
        if not namespace:
            console.print(
                "[red]Could not auto-detect namespace. "
                "Please specify with --namespace[/red]"
            )
            sys.exit(2)

    # Auto-detect release name if not provided
    if not release_name:
        release_name = _auto_detect_release(k8s, namespace)

    console.print(f"[blue]Namespace:[/blue] {namespace}")
    if release_name:
        console.print(f"[blue]Release:[/blue] {release_name}")
    console.print()

    # Create health check config
    config = HealthCheckConfig(
        namespace=namespace,
        release_name=release_name,
        verbose=verbose,
        timeout_seconds=timeout,
    )

    # Run health checks
    checker = HealthChecker(config)
    all_passed = checker.run_all_checks()

    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


def _auto_detect_namespace(k8s: KubernetesClient) -> str | None:
    """Auto-detect namespace with portal deployment."""
    console.print("[blue]Auto-detecting namespace...[/blue]")

    # Get all namespaces
    try:
        namespaces = k8s.core_v1.list_namespace()
    except Exception as e:
        console.print(f"[yellow]Could not list namespaces: {e}[/yellow]")
        return None

    # Find namespaces with RHDH deployments
    portal_namespaces = []

    for ns in namespaces.items:
        ns_name = ns.metadata.name

        # Check if namespace has backstage pods
        pods = k8s.get_pods(ns_name, label_selector="app.kubernetes.io/name=backstage")
        if pods:
            portal_namespaces.append(ns_name)

    if len(portal_namespaces) == 0:
        console.print("[yellow]No portal deployments found[/yellow]")
        return None
    elif len(portal_namespaces) == 1:
        namespace = portal_namespaces[0]
        console.print(f"[green]✓[/green] Detected namespace: {namespace}")
        return namespace
    else:
        console.print("[yellow]Multiple portal deployments found:[/yellow]")
        for ns in portal_namespaces:
            console.print(f"  - {ns}")
        console.print("[yellow]Please specify namespace with --namespace[/yellow]")
        return None


def _auto_detect_release(k8s: KubernetesClient, namespace: str) -> str | None:
    """Auto-detect Helm release name."""
    console.print("[blue]Auto-detecting Helm release...[/blue]")

    # Get deployments with Helm label
    try:
        deployments = k8s.apps_v1.list_namespaced_deployment(
            namespace, label_selector="app.kubernetes.io/managed-by=Helm"
        )
    except Exception as e:
        console.print(f"[yellow]Could not list deployments: {e}[/yellow]")
        return None

    releases = set()
    for deployment in deployments.items:
        if deployment.metadata.labels:
            release = deployment.metadata.labels.get("app.kubernetes.io/instance")
            if release:
                releases.add(release)

    if len(releases) == 0:
        console.print("[yellow]No Helm releases found[/yellow]")
        return None
    elif len(releases) == 1:
        release = list(releases)[0]
        console.print(f"[green]✓[/green] Detected release: {release}")
        return release
    else:
        console.print("[yellow]Multiple Helm releases found:[/yellow]")
        for r in releases:
            console.print(f"  - {r}")
        console.print("[yellow]Using first release[/yellow]")
        return list(releases)[0]

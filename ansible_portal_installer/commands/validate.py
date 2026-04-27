"""Validate command - Run health checks on deployment."""

import sys

import click
from rich.console import Console

from ..backends import BackendFactory, BackendType

console = Console()


@click.command()
@click.option(
    "--backend",
    type=click.Choice([b.value for b in BackendType]),
    default=BackendType.HELM.value,
    help="Deployment backend",
    envvar="DEPLOYMENT_BACKEND",
)
@click.option(
    "--namespace",
    "-n",
    help="Target namespace/location (auto-detect if not provided)",
    envvar="OCP_NAMESPACE",
)
@click.option(
    "--release-name",
    help="Deployment identifier (auto-detect if not provided)",
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
    backend: str,
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

    Specific checks vary by backend:
    - Helm: Kubernetes pod, service, route checks
    - Operator: Operator status, CR conditions
    - RHEL: systemd service status, port checks

    Exit codes:
    - 0: All checks passed
    - 1: Some checks failed
    - 2: Could not connect to target
    """
    console.print("[bold blue]Ansible Portal - Health Check[/bold blue]\n")

    try:
        deployer = BackendFactory.create(backend)

        # Auto-detection handled by backend implementation
        if not namespace:
            console.print("[blue]Auto-detecting namespace...[/blue]")

        all_passed = deployer.validate_deployment(
            namespace=namespace or "",  # Backend will auto-detect
            release_name=release_name,
            verbose=verbose,
            timeout=timeout,
        )

        # Exit with appropriate code
        sys.exit(0 if all_passed else 1)

    except NotImplementedError as e:
        console.print(f"[red]{e}[/red]")
        console.print(
            f"\n[yellow]Available backends: {', '.join(BackendFactory.list_implemented_backends())}[/yellow]"
        )
        sys.exit(2)
    except Exception as e:
        console.print(f"[red]Validation error: {e}[/red]")
        sys.exit(2)


def _auto_detect_namespace(k8s) -> str | None:
    """Auto-detect namespace with portal deployment.

    This function is kept for backward compatibility but is now
    delegated to the backend implementation.
    """
    from ..k8s import KubernetesClient

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


def _auto_detect_release(k8s, namespace: str) -> str | None:
    """Auto-detect Helm release name.

    This function is kept for backward compatibility but is now
    delegated to the backend implementation.
    """
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

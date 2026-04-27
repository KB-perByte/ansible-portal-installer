"""Teardown command - Remove portal deployment."""

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
    required=True,
    help="Target namespace/location",
    envvar="OCP_NAMESPACE",
)
@click.option(
    "--release-name",
    default="rhaap-portal-dev",
    help="Deployment identifier",
    envvar="RELEASE_NAME",
)
@click.option(
    "--clean-secrets",
    is_flag=True,
    help="Also delete secrets/credentials",
)
@click.option(
    "--clean-namespace",
    is_flag=True,
    help="Also delete the namespace (WARNING: deletes everything in namespace)",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompts",
)
def teardown(
    backend: str,
    namespace: str,
    release_name: str,
    clean_secrets: bool,
    clean_namespace: bool,
    yes: bool,
) -> None:
    """Remove portal deployment.

    This command:
    1. Removes the deployment
    2. Optionally removes secrets/credentials (--clean-secrets)
    3. Optionally deletes the namespace (--clean-namespace)

    WARNING: Use --clean-namespace with caution as it will delete
    EVERYTHING in the namespace/location, not just the portal.

    Exit codes:
    - 0: Successful teardown
    - 1: Teardown failed or aborted
    - 2: Could not connect to target
    """
    console.print("[bold blue]Ansible Portal - Teardown Deployment[/bold blue]\n")

    # Confirm actions
    if not yes:
        console.print("[yellow]This will remove the following:[/yellow]")
        console.print(f"  - Deployment: {release_name}")

        if clean_secrets:
            console.print("  - Secrets/credentials")

        if clean_namespace:
            console.print(f"  - [bold red]ENTIRE NAMESPACE: {namespace}[/bold red]")

        console.print()

        if not click.confirm("Do you want to continue?"):
            console.print("[yellow]Teardown aborted[/yellow]")
            sys.exit(0)

    try:
        deployer = BackendFactory.create(backend)

        # Remove deployment
        deployer.teardown(
            namespace=namespace,
            release_name=release_name,
            clean_data=clean_secrets,
        )

        # Delete namespace if requested (backend-specific)
        if clean_namespace:
            console.print(f"\n[bold red]Deleting namespace: {namespace}[/bold red]")

            if not yes:
                console.print(
                    "[yellow]WARNING: This will delete EVERYTHING in the namespace![/yellow]"
                )
                if not click.confirm("Are you absolutely sure?"):
                    console.print("[yellow]Namespace deletion skipped[/yellow]")
                else:
                    _delete_namespace(deployer, namespace)
            else:
                _delete_namespace(deployer, namespace)

        console.print("\n[bold green]✓ Teardown complete![/bold green]\n")

    except NotImplementedError as e:
        console.print(f"[red]{e}[/red]")
        console.print(
            f"\n[yellow]Available backends: {', '.join(BackendFactory.list_implemented_backends())}[/yellow]"
        )
        sys.exit(2)
    except Exception as e:
        console.print(f"[red]Teardown failed: {e}[/red]")
        sys.exit(1)


def _delete_namespace(deployer, namespace: str) -> None:
    """Delete namespace (backend-specific)."""
    # For Helm/K8s backends
    try:
        from ..k8s import KubernetesClient

        k8s = KubernetesClient()
        k8s.core_v1.delete_namespace(namespace)
        console.print(f"[green]✓[/green] Deleted namespace: {namespace}")
        console.print(
            "[yellow]Note: Namespace deletion may take a few moments to complete[/yellow]"
        )
    except Exception as e:
        console.print(f"[red]Failed to delete namespace: {e}[/red]")
        sys.exit(1)

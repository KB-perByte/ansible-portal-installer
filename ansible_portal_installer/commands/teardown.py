"""Teardown command - Remove portal deployment."""

import sys

import click
from rich.console import Console

from ..helm import HelmClient
from ..k8s import KubernetesClient

console = Console()


@click.command()
@click.option(
    "--namespace",
    "-n",
    required=True,
    help="OpenShift namespace",
    envvar="OCP_NAMESPACE",
)
@click.option(
    "--release-name",
    default="rhaap-portal-dev",
    help="Helm release name",
    envvar="RELEASE_NAME",
)
@click.option(
    "--clean-secrets",
    is_flag=True,
    help="Also delete secrets (AAP, SCM, registry auth)",
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
    namespace: str,
    release_name: str,
    clean_secrets: bool,
    clean_namespace: bool,
    yes: bool,
) -> None:
    """Remove portal deployment from OpenShift.

    This command:
    1. Uninstalls the Helm release
    2. Optionally removes secrets (--clean-secrets)
    3. Optionally deletes the namespace (--clean-namespace)

    WARNING: Use --clean-namespace with caution as it will delete
    EVERYTHING in the namespace, not just the portal.

    Exit codes:
    - 0: Successful teardown
    - 1: Teardown failed or aborted
    - 2: Could not connect to cluster
    """
    console.print("[bold blue]Ansible Portal - Teardown Deployment[/bold blue]\n")

    # Initialize clients
    try:
        k8s = KubernetesClient()
        helm = HelmClient()
    except RuntimeError as e:
        console.print(f"[red]Error connecting to cluster: {e}[/red]")
        sys.exit(2)

    # Check if namespace exists
    if not k8s.namespace_exists(namespace):
        console.print(f"[yellow]Namespace '{namespace}' does not exist[/yellow]")
        sys.exit(0)

    # Confirm actions
    if not yes:
        console.print("[yellow]This will remove the following:[/yellow]")
        console.print(f"  - Helm release: {release_name}")

        if clean_secrets:
            console.print("  - Secrets: secrets-rhaap-portal, secrets-scm, *-dynamic-plugins-registry-auth")

        if clean_namespace:
            console.print(f"  - [bold red]ENTIRE NAMESPACE: {namespace}[/bold red]")

        console.print()

        if not click.confirm("Do you want to continue?"):
            console.print("[yellow]Teardown aborted[/yellow]")
            sys.exit(0)

    # Uninstall Helm release
    console.print(f"\n[blue]Uninstalling Helm release: {release_name}[/blue]")

    if helm.release_exists(release_name, namespace):
        try:
            helm.uninstall(release_name, namespace)
        except Exception as e:
            console.print(f"[red]Failed to uninstall Helm release: {e}[/red]")
            sys.exit(1)
    else:
        console.print(f"[yellow]Release '{release_name}' not found, skipping[/yellow]")

    # Clean up secrets if requested
    if clean_secrets:
        console.print("\n[blue]Cleaning up secrets...[/blue]")
        _delete_secrets(k8s, namespace, release_name)

    # Delete namespace if requested
    if clean_namespace:
        console.print(f"\n[bold red]Deleting namespace: {namespace}[/bold red]")

        if not yes:
            console.print(
                "[yellow]WARNING: This will delete EVERYTHING in the namespace![/yellow]"
            )
            if not click.confirm("Are you absolutely sure?"):
                console.print("[yellow]Namespace deletion skipped[/yellow]")
            else:
                _delete_namespace(k8s, namespace)
        else:
            _delete_namespace(k8s, namespace)

    console.print("\n[bold green]✓ Teardown complete![/bold green]\n")


def _delete_secrets(k8s: KubernetesClient, namespace: str, release_name: str) -> None:
    """Delete portal-related secrets."""
    secrets_to_delete = [
        "secrets-rhaap-portal",
        "secrets-scm",
        f"{release_name}-dynamic-plugins-registry-auth",
    ]

    for secret_name in secrets_to_delete:
        try:
            if k8s.secret_exists(namespace, secret_name):
                k8s.core_v1.delete_namespaced_secret(secret_name, namespace)
                console.print(f"[green]✓[/green] Deleted secret: {secret_name}")
            else:
                console.print(f"[yellow]Secret not found, skipping: {secret_name}[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not delete secret {secret_name}: {e}[/yellow]")


def _delete_namespace(k8s: KubernetesClient, namespace: str) -> None:
    """Delete namespace."""
    try:
        k8s.core_v1.delete_namespace(namespace)
        console.print(f"[green]✓[/green] Deleted namespace: {namespace}")
        console.print(
            "[yellow]Note: Namespace deletion may take a few moments to complete[/yellow]"
        )
    except Exception as e:
        console.print(f"[red]Failed to delete namespace: {e}[/red]")
        sys.exit(1)

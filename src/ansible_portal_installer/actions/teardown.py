"""Teardown and cleanup actions."""

from ..config import Settings
from ..core import DeployError
from ..ui import (
    print_header,
    print_success,
    print_warning,
    print_error,
    console,
)
from ..utils import (
    run_command,
    oc_secret_exists,
)


def helm_teardown(
    settings: Settings,
    remove_secrets: bool = False,
    remove_namespace: bool = False,
    verbose: bool = False,
) -> None:
    """Teardown Helm deployment and optionally cleanup secrets/namespace.

    Args:
        settings: Application settings
        remove_secrets: Whether to delete secrets
        remove_namespace: Whether to delete the entire namespace/project
        verbose: Verbose output

    Raises:
        DeployError: If teardown fails
    """
    print_header(f"Tearing Down Deployment: {settings.helm_release_name}")

    namespace = settings.openshift_namespace
    release = settings.helm_release_name

    # Step 1: Uninstall Helm release
    console.print(f"\n[cyan]Uninstalling Helm release '{release}'...[/cyan]")
    try:
        run_command(
            ["helm", "uninstall", release, "-n", namespace],
            verbose=verbose,
        )
        print_success(f"Helm release '{release}' uninstalled")
    except Exception as e:
        print_warning(f"Helm uninstall failed (release may not exist): {e}")

    # Step 2: Remove secrets (optional)
    if remove_secrets:
        console.print(f"\n[cyan]Removing secrets...[/cyan]")
        secrets_to_remove = [
            "secrets-rhaap-portal",
            "secrets-scm",
            f"{release}-dynamic-plugins-registry-auth",
        ]

        for secret_name in secrets_to_remove:
            try:
                if oc_secret_exists(secret_name, namespace):
                    run_command(
                        ["oc", "delete", "secret", secret_name, "-n", namespace],
                        verbose=verbose,
                    )
                    print_success(f"Secret '{secret_name}' deleted")
                else:
                    print_warning(f"Secret '{secret_name}' not found (skipping)")
            except Exception as e:
                print_warning(f"Failed to delete secret '{secret_name}': {e}")

    # Step 3: Remove namespace/project (optional)
    if remove_namespace:
        console.print(f"\n[yellow]⚠️  Deleting entire namespace '{namespace}'...[/yellow]")
        try:
            run_command(
                ["oc", "delete", "project", namespace],
                verbose=verbose,
            )
            print_success(f"Namespace '{namespace}' deleted")
        except Exception as e:
            print_error(f"Failed to delete namespace: {e}")
            raise DeployError(f"Namespace deletion failed: {e}") from e

    # Summary
    console.print()
    print_success("Teardown completed successfully")

    if not remove_secrets:
        print_warning(
            "Secrets were NOT removed. "
            "Use --remove-secrets flag to delete them."
        )

    if not remove_namespace:
        console.print(
            f"\n[dim]Namespace '{namespace}' still exists. "
            f"Use --remove-namespace flag to delete it.[/dim]"
        )

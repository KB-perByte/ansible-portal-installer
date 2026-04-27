"""Build command - Build and push plugin OCI image."""

import subprocess
import tempfile
from pathlib import Path
from typing import List

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..config import DeploymentConfig, RegistryConfig
from ..k8s import OpenShiftClient
from ..registry import AuthSecretManager, RegistryClient

console = Console()

# List of plugins to build
PLUGINS = [
    "@ansible/plugin-backstage-rhaap",
    "@ansible/plugin-backstage-self-service",
    "@ansible/backstage-plugin-catalog-backend-module-rhaap",
    "@ansible/plugin-scaffolder-backend-module-backstage-rhaap",
    "@ansible/backstage-plugin-auth-backend-module-rhaap-provider",
]


@click.command()
@click.option(
    "--namespace",
    "-n",
    required=True,
    help="OpenShift namespace",
    envvar="OCP_NAMESPACE",
)
@click.option(
    "--plugins-path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path.cwd(),
    help="Path to ansible-rhdh-plugins repository",
    envvar="PLUGINS_PATH",
)
@click.option(
    "--registry",
    help="Registry URL (default: OpenShift internal registry)",
    envvar="PLUGIN_REGISTRY",
)
@click.option(
    "--tag",
    default="dev",
    help="Image tag",
    envvar="PLUGIN_IMAGE_TAG",
)
@click.option(
    "--release-name",
    default="rhaap-portal-dev",
    help="Helm release name (for auth secret)",
    envvar="RELEASE_NAME",
)
@click.option(
    "--skip-plugin-build",
    is_flag=True,
    help="Skip plugin build step (reuse existing tarballs)",
    envvar="SKIP_PLUGIN_BUILD",
)
def build(
    namespace: str,
    plugins_path: Path,
    registry: str | None,
    tag: str,
    release_name: str,
    skip_plugin_build: bool,
) -> None:
    """Build and push Ansible Portal plugin OCI image.

    This command:
    1. Builds all 5 plugins using yarn export-dynamic (unless --skip-plugin-build)
    2. Collects plugin tarballs from dist-dynamic/ directories
    3. Packages plugins into an OCI image
    4. Pushes image to the specified registry
    5. Creates auth secret for RHDH init container
    """
    console.print("[bold blue]Ansible Portal - Build Plugin Image[/bold blue]\n")

    # Validate prerequisites
    _check_prerequisites()

    # Determine registry URL
    if not registry:
        # Use OpenShift internal registry
        console.print("[blue]Auto-detecting OpenShift internal registry...[/blue]")
        registry_route = OpenShiftClient.get_registry_route()
        if registry_route:
            registry_url = f"{registry_route}/{namespace}"
            console.print(f"[green]✓[/green] Using external route: {registry_url}")
        else:
            registry_url = f"image-registry.openshift-image-registry.svc:5000/{namespace}"
            console.print(f"[green]✓[/green] Using internal service: {registry_url}")
    else:
        registry_url = f"{registry}/{namespace}" if not registry.endswith(namespace) else registry

    # Create registry config
    reg_config = RegistryConfig(
        url=registry_url.rsplit("/", 1)[0],
        namespace=namespace,
        tag=tag,
        insecure=True,  # Dev mode - skip TLS verification
    )

    # Build plugins
    if not skip_plugin_build:
        _build_plugins(plugins_path)
    else:
        console.print("[yellow]Skipping plugin build (--skip-plugin-build)[/yellow]")

    # Collect plugin tarballs
    tarballs = _collect_plugin_tarballs(plugins_path)

    if len(tarballs) != 5:
        console.print(
            f"[red]Error: Expected 5 plugin tarballs, found {len(tarballs)}[/red]"
        )
        console.print("[yellow]Run without --skip-plugin-build to rebuild plugins[/yellow]")
        raise click.Abort()

    # Build and push OCI image
    registry_client = RegistryClient(reg_config)
    registry_client.build_plugin_image(plugins_path, tarballs)
    registry_client.push_image()

    # Validate image
    registry_client.validate_image()

    # Create auth secret
    _create_auth_secret(namespace, release_name)

    console.print(
        f"\n[bold green]✓ Plugin image ready:[/bold green] "
        f"{reg_config.full_image_url_with_tag}\n"
    )


def _check_prerequisites() -> None:
    """Check if required tools are installed."""
    required_tools = {
        "yarn": "Node.js package manager",
        "podman": "Container tool",
        "oc": "OpenShift CLI",
    }

    missing = []
    for tool, desc in required_tools.items():
        import shutil

        if not shutil.which(tool):
            missing.append(f"{tool} ({desc})")

    if missing:
        console.print(f"[red]Missing required tools:[/red]")
        for tool in missing:
            console.print(f"  • {tool}")
        raise click.Abort()


def _build_plugins(plugins_path: Path) -> None:
    """Build all plugins using yarn export-dynamic."""
    console.print(f"[blue]Building plugins from source: {plugins_path}[/blue]")

    for plugin in PLUGINS:
        console.print(f"  • Building {plugin}...")

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(f"Building {plugin}...", total=None)

                subprocess.run(
                    ["yarn", "workspace", plugin, "run", "export-dynamic"],
                    cwd=plugins_path,
                    check=True,
                    capture_output=True,
                    text=True,
                )

            console.print(f"[green]✓[/green] Built {plugin}")

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Failed to build {plugin}[/red]")
            console.print(f"[red]{e.stderr}[/red]")
            raise click.Abort()

    console.print("[green]✓[/green] All plugins built successfully\n")


def _collect_plugin_tarballs(plugins_path: Path) -> List[Path]:
    """Collect plugin tarballs from dist-dynamic directories."""
    console.print("[blue]Collecting plugin tarballs...[/blue]")

    tarballs = list(plugins_path.glob("plugins/*/dist-dynamic/*.tgz"))

    for tarball in tarballs:
        console.print(f"  • {tarball.name}")

    console.print(f"[green]✓[/green] Found {len(tarballs)} plugin tarballs\n")

    return tarballs


def _create_auth_secret(namespace: str, release_name: str) -> None:
    """Create registry auth secret for RHDH init container."""
    console.print("[blue]Creating registry auth secret...[/blue]")

    secret_name = f"{release_name}-dynamic-plugins-registry-auth"

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as auth_file:
            auth_path = Path(auth_file.name)

        # Get auth from oc registry login
        AuthSecretManager.get_oc_registry_auth(auth_path)

        # Create secret using oc
        subprocess.run(
            [
                "oc",
                "create",
                "secret",
                "generic",
                secret_name,
                f"--from-file=auth.json={auth_path}",
                "-n",
                namespace,
                "--dry-run=client",
                "-o",
                "yaml",
            ],
            check=True,
            capture_output=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout

        # Apply the secret
        result = subprocess.run(
            [
                "oc",
                "create",
                "secret",
                "generic",
                secret_name,
                f"--from-file=auth.json={auth_path}",
                "-n",
                namespace,
                "--dry-run=client",
                "-o",
                "yaml",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        subprocess.run(
            ["oc", "apply", "-f", "-", "-n", namespace],
            input=result.stdout,
            check=True,
            capture_output=True,
            text=True,
        )

        console.print(f"[green]✓[/green] Created auth secret: {secret_name}")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to create auth secret[/red]")
        console.print(f"[red]{e.stderr}[/red]")
        raise click.Abort()
    finally:
        # Clean up auth file
        auth_path.unlink(missing_ok=True)

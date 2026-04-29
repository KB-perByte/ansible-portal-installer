"""Build command - Build and push plugin OCI image."""

import subprocess
import tempfile
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..config import RegistryConfig
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
        console.print("[red]Missing required tools:[/red]")
        for tool in missing:
            console.print(f"  • {tool}")
        raise click.Abort()


def _build_plugins(plugins_path: Path) -> None:
    """Build all plugins using rhdh-cli plugin package."""
    # Resolve to absolute path
    plugins_path = plugins_path.resolve()
    console.print(f"[blue]Building plugins from source: {plugins_path}[/blue]")

    # Add node_modules/.bin to PATH so rhdh-cli can be found
    import os
    env = os.environ.copy()
    node_bin = str(plugins_path / "node_modules" / ".bin")
    env["PATH"] = f"{node_bin}:{env.get('PATH', '')}"

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Build all plugins with yarn build
            progress.add_task("Running yarn build...", total=None)
            subprocess.run(
                ["yarn", "build"],
                cwd=plugins_path,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            # Export plugins with rhdh-cli
            progress.add_task("Exporting plugins with rhdh-cli...", total=None)
            export_dir = plugins_path.parent / "dynamic-plugins"
            export_dir.mkdir(exist_ok=True)

            subprocess.run(
                [str(plugins_path / "node_modules" / ".bin" / "rhdh-cli"), "plugin", "package", "--export-to", str(export_dir)],
                cwd=plugins_path,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

        console.print("[green]✓[/green] All plugins built and exported successfully\n")

    except subprocess.CalledProcessError as e:
        console.print("[red]Failed to build plugins[/red]")
        console.print(f"[red]{e.stderr}[/red]")
        raise click.Abort()



def _collect_plugin_tarballs(plugins_path: Path) -> list[Path]:
    """Collect plugin tarballs from dynamic-plugins export directory."""
    # Resolve to absolute path
    plugins_path = plugins_path.resolve()
    console.print("[blue]Creating plugin tarballs...[/blue]")

    # Plugins are exported as directories to dynamic-plugins (one level up from plugins_path)
    export_dir = plugins_path.parent / "dynamic-plugins"

    # Create tarballs from plugin directories
    tarballs = []
    for plugin_dir in export_dir.glob("ansible-*"):
        if plugin_dir.is_dir():
            tarball_path = export_dir / f"{plugin_dir.name}.tgz"

            # Create tarball
            subprocess.run(
                ["tar", "-czf", str(tarball_path), "-C", str(export_dir), plugin_dir.name],
                check=True,
                capture_output=True,
            )

            tarballs.append(tarball_path)
            console.print(f"  • Created {tarball_path.name}")

    console.print(f"[green]✓[/green] Created {len(tarballs)} plugin tarballs\n")

    return tarballs


def _create_auth_secret(namespace: str, release_name: str) -> None:
    """Create registry auth secret for RHDH init container."""
    console.print("[blue]Creating registry auth secret...[/blue]")

    secret_name = f"{release_name}-dynamic-plugins-registry-auth"

    try:
        # Use podman/docker auth file if it exists
        import json
        import os
        from pathlib import Path as PathlibPath

        # Try to find auth file in standard locations
        auth_paths = [
            PathlibPath.home() / ".docker" / "config.json",
            PathlibPath(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "containers" / "auth.json",
            PathlibPath.home() / ".config" / "containers" / "auth.json",
        ]

        auth_json = None
        for path in auth_paths:
            if path.exists():
                with open(path) as f:
                    auth_json = json.load(f)
                console.print(f"[green]✓[/green] Found auth config: {path}")
                break

        if not auth_json:
            # Fallback: try oc registry login
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as auth_file:
                auth_path = Path(auth_file.name)
            try:
                AuthSecretManager.get_oc_registry_auth(auth_path)
                with open(auth_path) as f:
                    auth_json = json.load(f)
            finally:
                auth_path.unlink(missing_ok=True)

        # Write auth.json to temp file for secret creation
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as auth_file:
            auth_path = Path(auth_file.name)
            json.dump(auth_json, auth_file)

        # Create secret using oc
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
        console.print("[red]Failed to create auth secret[/red]")
        console.print(f"[red]{e.stderr}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Failed to create auth secret: {e}[/red]")
        raise click.Abort()
    finally:
        # Clean up auth file
        if 'auth_path' in locals():
            auth_path.unlink(missing_ok=True)


def _build_and_push_plugins(
    plugins_path: Path,
    registry_config: RegistryConfig,
    image_tag: str,
    namespace: str,
    release_name: str,
    skip_plugin_build: bool = False,
) -> str:
    """Build and push plugins - helper function for deployer.

    Returns:
        Full image URL with tag (e.g., registry.example.com/namespace/image:tag)
    """
    console.print("[bold blue]Ansible Portal - Build Plugin Image[/bold blue]\n")

    # Validate prerequisites
    _check_prerequisites()

    # Update registry config with provided tag
    registry_config.tag = image_tag

    # Build plugins
    if not skip_plugin_build:
        _build_plugins(plugins_path)
    else:
        console.print("[yellow]Skipping plugin build (reusing existing)[/yellow]")

    # Collect plugin tarballs
    tarballs = _collect_plugin_tarballs(plugins_path)

    if len(tarballs) != 5:
        console.print(
            f"[red]Error: Expected 5 plugin tarballs, found {len(tarballs)}[/red]"
        )
        console.print("[yellow]Ensure all plugins are built before deploying[/yellow]")
        raise click.Abort()

    # Build and push OCI image
    registry_client = RegistryClient(registry_config)
    registry_client.build_plugin_image(plugins_path, tarballs)
    registry_client.push_image()

    # Validate image
    registry_client.validate_image()

    # Create auth secret
    _create_auth_secret(namespace, release_name)

    console.print(
        f"\n[bold green]✓ Plugin image ready:[/bold green] "
        f"{registry_config.full_image_url_with_tag}\n"
    )

    return registry_config.full_image_url_with_tag

"""Build command - Build and push plugin OCI image."""

import subprocess
import tempfile
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..config import RegistryConfig
from ..k8s import OpenShiftClient
from ..registry import RegistryClient

# Load .env file into environment variables for Click
load_dotenv()

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
    help="Path to ansible-rhdh-plugins repository (downstream)",
    envvar="PLUGINS_PATH",
)
@click.option(
    "--upstream-plugins-path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help="Path to ansible-backstage-plugins repository (upstream)",
    envvar="UPSTREAM_PLUGINS_PATH",
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
@click.option(
    "--registry-auth-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to registry auth.json file (optional, only needed for authenticated registries)",
    envvar="REGISTRY_AUTH_FILE",
)
def build(
    namespace: str,
    plugins_path: Path,
    upstream_plugins_path: Path,
    registry: str | None,
    tag: str,
    release_name: str,
    skip_plugin_build: bool,
    registry_auth_file: Path | None,
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

    # Determine registry URL and parse components
    if not registry:
        # Use OpenShift internal registry
        console.print("[blue]Auto-detecting OpenShift internal registry...[/blue]")
        registry_route = OpenShiftClient.get_registry_route()
        if registry_route:
            registry_url = registry_route
            registry_namespace = namespace
            image_name = "ansible-portal-plugins"
            console.print(f"[green]✓[/green] Using external route: {registry_url}/{registry_namespace}/{image_name}")
        else:
            registry_url = "image-registry.openshift-image-registry.svc:5000"
            registry_namespace = namespace
            image_name = "ansible-portal-plugins"
            console.print(f"[green]✓[/green] Using internal service: {registry_url}/{registry_namespace}/{image_name}")
    else:
        # Parse registry URL: quay.io/sagpaul/ansible-portal-plugins
        parts = registry.split("/")
        if len(parts) >= 3:
            registry_url = parts[0]
            registry_namespace = parts[1]
            image_name = "/".join(parts[2:])
        elif len(parts) == 2:
            registry_url = parts[0]
            registry_namespace = parts[1]
            image_name = "ansible-portal-plugins"
        else:
            registry_url = registry
            registry_namespace = namespace
            image_name = "ansible-portal-plugins"
        console.print(f"[green]✓[/green] Using registry: {registry_url}/{registry_namespace}/{image_name}")

    # Create registry config
    reg_config = RegistryConfig(
        url=registry_url,
        namespace=registry_namespace,
        image_name=image_name,
        tag=tag,
        insecure=True,  # Dev mode - skip TLS verification
    )

    # Build plugins
    if not skip_plugin_build:
        _build_plugins(plugins_path, upstream_plugins_path)
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

    # Create auth secret (optional, only if auth file provided)
    if registry_auth_file:
        _create_auth_secret(namespace, release_name, registry_auth_file)
    else:
        console.print("[dim]Skipping registry auth secret creation (no --registry-auth-file provided)[/dim]")

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


def _build_plugins(plugins_path: Path, upstream_plugins_path: Path, build_type: str = "portal") -> None:
    """Build all plugins using build.sh script.

    This matches the documented workflow in helm-chart-developer-guide.md.
    The build.sh script handles yarn install, tsc, build, and plugin export.

    Args:
        plugins_path: Path to ansible-rhdh-plugins repository (downstream)
        upstream_plugins_path: Path to ansible-backstage-plugins repository (upstream)
        build_type: Build type - "portal" (default), "rhdh", or "all"
    """
    # Resolve to absolute paths
    plugins_path = plugins_path.resolve()
    upstream_plugins_path = upstream_plugins_path.resolve()

    console.print(f"[blue]Downstream repo: {plugins_path}[/blue]")
    console.print(f"[blue]Upstream repo: {upstream_plugins_path}[/blue]")

    # Verify build.sh exists in downstream repo
    build_script = plugins_path / "build.sh"
    if not build_script.exists():
        console.print(f"[red]Error: build.sh not found at {build_script}[/red]")
        console.print("[yellow]Make sure plugins_path points to ansible-rhdh-plugins repo[/yellow]")
        raise click.Abort()

    # Verify upstream repo has package.json
    if not (upstream_plugins_path / "package.json").exists():
        console.print(f"[red]Error: package.json not found in upstream repo[/red]")
        console.print(f"[yellow]Check: {upstream_plugins_path}/package.json[/yellow]")
        raise click.Abort()

    # Create symlink to upstream repo
    upstream_link = plugins_path / "ansible-backstage-plugins"
    if upstream_link.exists():
        # Check if it's a symlink or directory
        if upstream_link.is_symlink():
            # It's a symlink - check if it points to the correct location
            if upstream_link.resolve() != upstream_plugins_path:
                console.print(f"[yellow]Removing existing symlink (points to wrong location)[/yellow]")
                console.print(f"[dim]Current: {upstream_link.resolve()}[/dim]")
                console.print(f"[dim]Expected: {upstream_plugins_path}[/dim]")
                upstream_link.unlink()
            else:
                console.print(f"[green]✓[/green] Symlink already exists and points to correct location")
        else:
            # It's a directory, not a symlink
            console.print(f"[red]Error: ansible-backstage-plugins exists as a directory, not a symlink[/red]")
            console.print(f"[yellow]Please remove it manually and re-run:[/yellow]")
            console.print(f"[dim]  rm -rf {upstream_link}[/dim]")
            console.print(f"[dim]Or if it contains work, move it elsewhere first[/dim]")
            raise click.Abort()

    if not upstream_link.exists():
        console.print(f"[blue]Creating symlink: ansible-backstage-plugins → {upstream_plugins_path}[/blue]")
        try:
            upstream_link.symlink_to(upstream_plugins_path)
            console.print(f"[green]✓[/green] Symlink created successfully")
        except Exception as e:
            console.print(f"[red]Failed to create symlink: {e}[/red]")
            raise click.Abort()

    # Verify symlink points to valid repo
    if not (upstream_link / "package.json").exists():
        console.print(f"[red]Error: Symlink exists but doesn't point to valid repo[/red]")
        console.print(f"[yellow]Check: {upstream_link} -> {upstream_link.resolve()}[/yellow]")
        raise click.Abort()

    import os
    env = os.environ.copy()
    env["BUILD_TYPE"] = build_type

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(f"Running build.sh (BUILD_TYPE={build_type})...", total=None)

            subprocess.run(
                ["./build.sh"],
                cwd=plugins_path,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

        console.print("[green]✓[/green] All plugins built and exported successfully\n")

    except subprocess.CalledProcessError as e:
        console.print("[red]Failed to build plugins[/red]")
        console.print(f"[red]STDOUT: {e.stdout}[/red]")
        console.print(f"[red]STDERR: {e.stderr}[/red]")
        raise click.Abort()



def _collect_plugin_tarballs(plugins_path: Path) -> list[Path]:
    """Collect plugin tarballs from dynamic-plugins export directory.

    Per helm-chart-developer-guide.md, build.sh exports to:
      ansible-rhdh-plugins/dynamic-plugins/

    Args:
        plugins_path: Path to ansible-rhdh-plugins repository

    Returns:
        List of tarball paths
    """
    # Resolve to absolute path
    plugins_path = plugins_path.resolve()
    console.print("[blue]Creating plugin tarballs...[/blue]")

    # build.sh exports plugins to dynamic-plugins/ within ansible-rhdh-plugins
    export_dir = plugins_path / "dynamic-plugins"

    if not export_dir.exists():
        console.print(f"[red]Error: Export directory not found: {export_dir}[/red]")
        console.print("[yellow]Run build without --skip-plugin-build first[/yellow]")
        raise click.Abort()

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


def _create_auth_secret(namespace: str, release_name: str, auth_file_path: Path) -> None:
    """Create registry auth secret for RHDH init container.

    Args:
        namespace: OpenShift namespace
        release_name: Helm release name
        auth_file_path: Path to auth.json file with registry credentials
    """
    console.print(f"[blue]Creating registry auth secret from: {auth_file_path}[/blue]")

    secret_name = f"{release_name}-dynamic-plugins-registry-auth"

    try:
        import json

        # Validate auth file
        with open(auth_file_path) as f:
            auth_json = json.load(f)

        if "auths" not in auth_json:
            console.print(f"[red]Invalid auth file: missing 'auths' key[/red]")
            console.print("[yellow]Expected format: {\"auths\": {\"registry.example.com\": {\"auth\": \"base64...\"}}}")
            raise click.Abort()

        # Create secret using oc
        # Note: Must be Opaque type with auth.json key for RHDH init container
        # The init container mounts this at /opt/app-root/src/.config/containers/auth.json
        result = subprocess.run(
            [
                "oc",
                "create",
                "secret",
                "generic",
                secret_name,
                f"--from-file=auth.json={auth_file_path}",
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


def _build_and_push_plugins(
    plugins_path: Path,
    upstream_plugins_path: Path,
    registry_config: RegistryConfig,
    image_tag: str,
    namespace: str,
    release_name: str,
    skip_plugin_build: bool = False,
    registry_auth_file: Path | None = None,
) -> str:
    """Build and push plugins - helper function for deployer.

    Args:
        plugins_path: Path to ansible-rhdh-plugins repository (downstream)
        upstream_plugins_path: Path to ansible-backstage-plugins repository (upstream)
        registry_config: Registry configuration
        image_tag: Image tag to use
        namespace: OpenShift namespace
        release_name: Helm release name
        skip_plugin_build: Skip plugin build step if True

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
        _build_plugins(plugins_path, upstream_plugins_path)
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

    # Create auth secret (optional, only if auth file provided)
    if registry_auth_file:
        _create_auth_secret(namespace, release_name, registry_auth_file)
    else:
        console.print("[dim]Skipping registry auth secret creation (no auth file provided)[/dim]")

    console.print(
        f"\n[bold green]✓ Plugin image ready:[/bold green] "
        f"{registry_config.full_image_url_with_tag}\n"
    )

    return registry_config.full_image_url_with_tag

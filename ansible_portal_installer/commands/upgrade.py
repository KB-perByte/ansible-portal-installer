"""Upgrade command - Upgrade existing portal deployment."""

from pathlib import Path

import click
from rich.console import Console

from ..helm import HelmClient
from ..k8s import OpenShiftClient
from .build import build as build_command

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
    "--chart-path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("../ansible-portal-chart"),
    help="Path to Helm chart",
    envvar="CHART_PATH",
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
    "--image-tag",
    default="dev",
    help="Plugin image tag",
    envvar="PLUGIN_IMAGE_TAG",
)
@click.option(
    "--skip-plugin-build",
    is_flag=True,
    help="Skip plugin build step",
    envvar="SKIP_PLUGIN_BUILD",
)
@click.option(
    "--values",
    "values_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Custom values file to use",
)
@click.pass_context
def upgrade(
    ctx: click.Context,
    namespace: str,
    release_name: str,
    chart_path: Path,
    plugins_path: Path,
    registry: str | None,
    image_tag: str,
    skip_plugin_build: bool,
    values_file: Path | None,
) -> None:
    """Upgrade existing portal deployment.

    This command:
    1. Checks that the Helm release exists
    2. Rebuilds and pushes plugin OCI image (unless --skip-plugin-build)
    3. Upgrades the Helm release with new image tag
    4. Waits for rollout to complete
    5. Displays updated portal URL

    Use --skip-plugin-build if you only want to change Helm values without rebuilding plugins.
    """
    console.print("[bold blue]Ansible Portal - Upgrade Deployment[/bold blue]\n")

    # Initialize clients
    helm = HelmClient()
    oc = OpenShiftClient()

    # Check if release exists
    console.print(f"[blue]Checking if release exists: {release_name}[/blue]")
    if not helm.release_exists(release_name, namespace):
        console.print(
            f"[red]Release '{release_name}' not found in namespace '{namespace}'[/red]"
        )
        console.print("[yellow]Use 'deploy' command to create a new deployment[/yellow]")
        raise click.Abort()

    console.print(f"[green]✓[/green] Release found: {release_name}\n")

    # Rebuild plugin image if needed
    if not skip_plugin_build:
        console.print("[bold blue]Rebuilding Plugin Image[/bold blue]\n")
        ctx.invoke(
            build_command,
            namespace=namespace,
            plugins_path=plugins_path,
            registry=registry,
            tag=image_tag,
            release_name=release_name,
            skip_plugin_build=False,
        )
    else:
        console.print("[yellow]Skipping plugin build (--skip-plugin-build)[/yellow]\n")

    # Get current values or use provided values file
    if values_file:
        console.print(f"[blue]Using custom values file: {values_file}[/blue]")
        import yaml

        with open(values_file) as f:
            values = yaml.safe_load(f)
    else:
        console.print("[blue]Getting current Helm values...[/blue]")
        values = helm.get_values(release_name, namespace)

        if not values:
            console.print("[yellow]Could not get current values, using minimal config[/yellow]")
            # Determine registry URL
            if not registry:
                registry_route = oc.get_registry_route()
                if registry_route:
                    registry_url = f"{registry_route}/{namespace}/automation-portal"
                else:
                    registry_url = f"image-registry.openshift-image-registry.svc:5000/{namespace}/automation-portal"
            else:
                registry_url = f"{registry}/{namespace}/automation-portal"

            cluster_router_base = oc.get_cluster_router_base()

            from ..helm import generate_portal_values

            values = generate_portal_values(
                registry_url=registry_url,
                image_tag=image_tag,
                cluster_router_base=cluster_router_base,
                release_name=release_name,
                admin_password_hash="",  # Keep existing
                check_ssl=False,
            )
        else:
            # Update image tag in existing values
            if "redhat-developer-hub" not in values:
                values["redhat-developer-hub"] = {}
            if "global" not in values["redhat-developer-hub"]:
                values["redhat-developer-hub"]["global"] = {}

            values["redhat-developer-hub"]["global"]["imageTagInfo"] = image_tag

    # Update Helm dependencies
    helm.dependency_update(chart_path)

    # Upgrade with Helm
    console.print(f"\n[bold blue]Upgrading Helm Release[/bold blue]\n")
    helm.install_or_upgrade(
        release_name=release_name,
        chart_path=chart_path,
        namespace=namespace,
        values=values,
        timeout="10m",
        wait=True,
    )

    # Get portal route
    console.print("\n[blue]Getting portal route...[/blue]")
    route_host = oc.get_route_host(namespace, "app.kubernetes.io/name=backstage")

    if route_host:
        portal_url = f"https://{route_host}"
        console.print(f"[green]✓[/green] Portal URL: {portal_url}\n")
    else:
        console.print("[yellow]Route not found (check manually)[/yellow]\n")

    console.print("[bold green]✓ Upgrade complete![/bold green]\n")

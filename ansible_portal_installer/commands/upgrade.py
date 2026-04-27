"""Upgrade command - Upgrade existing deployment."""

from pathlib import Path
from typing import Optional

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
    "--chart-path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Path to deployment configuration",
    envvar="CHART_PATH",
)
@click.option(
    "--skip-plugin-build",
    is_flag=True,
    help="Skip plugin rebuild (values-only upgrade)",
)
def upgrade(
    backend: str,
    namespace: str,
    release_name: str,
    chart_path: Optional[Path],
    skip_plugin_build: bool,
) -> None:
    """Upgrade existing portal deployment.

    This command upgrades an existing deployment with:
    - New plugin image (unless --skip-plugin-build)
    - Updated configuration values
    - Chart updates

    For Helm backend:
    - Rebuilds plugins and pushes new image
    - Updates Helm values
    - Runs 'helm upgrade'

    Exit codes:
    - 0: Successful upgrade
    - 1: Upgrade failed
    """
    try:
        deployer = BackendFactory.create(backend)
        deployer.upgrade(
            namespace=namespace,
            release_name=release_name,
            chart_path=chart_path,
            skip_build=skip_plugin_build,
        )

    except NotImplementedError as e:
        console.print(f"[red]{e}[/red]")
        console.print(
            f"\n[yellow]Available backends: {', '.join(BackendFactory.list_implemented_backends())}[/yellow]"
        )
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Upgrade failed: {e}[/red]")
        raise

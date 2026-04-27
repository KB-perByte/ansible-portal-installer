"""Deploy command - Deploy portal using selected backend."""

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..backends import BackendFactory, BackendType
from ..config import AAPConfig, DeploymentConfig, RegistryConfig, SCMConfig

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
    default=Path("../ansible-portal-chart"),
    help="Path to deployment configuration",
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
    "--aap-host",
    required=True,
    help="AAP controller URL",
    envvar="AAP_HOST_URL",
)
@click.option(
    "--aap-token",
    required=True,
    help="AAP API token",
    envvar="AAP_TOKEN",
)
@click.option(
    "--oauth-client-id",
    required=True,
    help="AAP OAuth client ID",
    envvar="OAUTH_CLIENT_ID",
)
@click.option(
    "--oauth-client-secret",
    required=True,
    help="AAP OAuth client secret",
    envvar="OAUTH_CLIENT_SECRET",
)
@click.option(
    "--github-token",
    help="GitHub personal access token",
    envvar="GITHUB_TOKEN",
)
@click.option(
    "--github-client-id",
    help="GitHub OAuth client ID",
    envvar="GITHUB_CLIENT_ID",
)
@click.option(
    "--github-client-secret",
    help="GitHub OAuth client secret",
    envvar="GITHUB_CLIENT_SECRET",
)
@click.option(
    "--gitlab-token",
    help="GitLab personal access token",
    envvar="GITLAB_TOKEN",
)
@click.option(
    "--registry",
    help="Registry URL (default: auto-detect)",
    envvar="PLUGIN_REGISTRY",
)
@click.option(
    "--image-tag",
    default="dev",
    help="Plugin image tag",
    envvar="PLUGIN_IMAGE_TAG",
)
@click.option(
    "--admin-password",
    help="Portal admin password (generated if not provided)",
    envvar="PORTAL_ADMIN_PASSWORD",
)
@click.option(
    "--skip-plugin-build",
    is_flag=True,
    help="Skip plugin build step",
    envvar="SKIP_PLUGIN_BUILD",
)
@click.option(
    "--check-ssl/--no-check-ssl",
    default=False,
    help="Enable/disable SSL verification for AAP",
)
def deploy(
    backend: str,
    namespace: str,
    release_name: str,
    chart_path: Path,
    plugins_path: Path,
    aap_host: str,
    aap_token: str,
    oauth_client_id: str,
    oauth_client_secret: str,
    github_token: str | None,
    github_client_id: str | None,
    github_client_secret: str | None,
    gitlab_token: str | None,
    registry: str | None,
    image_tag: str,
    admin_password: str | None,
    skip_plugin_build: bool,
    check_ssl: bool,
) -> None:
    """Deploy Ansible Portal using selected backend.

    This command performs a full deployment:
    1. Creates namespace/location if needed
    2. Builds and pushes plugin artifacts (unless --skip-plugin-build)
    3. Creates required secrets/credentials
    4. Deploys portal using the selected backend
    5. Waits for deployment to complete
    6. Displays portal URL and admin credentials

    Backends:
    - helm: Deploy to Kubernetes/OpenShift using Helm charts
    - operator: Deploy using OpenShift Operators (future)
    - rhel: Install as RHEL packages (future)
    """
    # Create configuration objects
    aap_config = AAPConfig(
        host_url=aap_host,
        token=aap_token,
        oauth_client_id=oauth_client_id,
        oauth_client_secret=oauth_client_secret,
        check_ssl=check_ssl,
    )

    scm_config = None
    if github_token or gitlab_token:
        scm_config = SCMConfig(
            github_token=github_token,
            github_client_id=github_client_id,
            github_client_secret=github_client_secret,
            gitlab_token=gitlab_token,
        )

    registry_config = None
    if registry:
        # Parse registry URL into components
        # Format: registry-url/namespace/image-name
        parts = registry.split("/")
        if len(parts) >= 2:
            registry_url = parts[0]
            registry_namespace = parts[1] if len(parts) >= 2 else namespace
            image_name = parts[2] if len(parts) >= 3 else "automation-portal"
        else:
            registry_url = registry
            registry_namespace = namespace
            image_name = "automation-portal"

        registry_config = RegistryConfig(
            url=registry_url,
            namespace=registry_namespace,
            image_name=image_name,
            tag=image_tag,
        )

    deployment_config = DeploymentConfig(
        backend=backend,
        namespace=namespace,
        release_name=release_name,
        chart_path=chart_path,
        plugins_path=plugins_path,
        registry=registry_config,
        aap=aap_config,
        scm=scm_config,
        image_tag=image_tag,
        admin_password=admin_password,
        skip_plugin_build=skip_plugin_build,
        check_ssl=check_ssl,
    )

    # Create backend and deploy
    try:
        deployer = BackendFactory.create(backend)
        result = deployer.deploy(deployment_config, skip_build=skip_plugin_build)

        # Print deployment summary
        _print_deployment_summary(result)

    except NotImplementedError as e:
        console.print(f"[red]{e}[/red]")
        console.print(
            f"\n[yellow]Available backends: {', '.join(BackendFactory.list_implemented_backends())}[/yellow]"
        )
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Deployment failed: {e}[/red]")
        raise


def _print_deployment_summary(result: dict) -> None:
    """Print deployment summary table."""
    table = Table(title="Deployment Summary", show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("Portal URL", result.get("url", "N/A"))
    table.add_row("Admin User", result.get("username", "admin"))
    table.add_row("Admin Password", f"[yellow]{result.get('password', 'N/A')}[/yellow]")
    table.add_row("Namespace", result.get("namespace", "N/A"))
    table.add_row("Release", result.get("release", "N/A"))

    console.print()
    console.print(
        Panel(table, title="[bold green]Deployment Complete[/bold green]", border_style="green")
    )
    console.print()
    console.print("[bold yellow]⚠️  Save the admin password securely![/bold yellow]\n")

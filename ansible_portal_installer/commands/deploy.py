"""Deploy command - Deploy portal to OpenShift."""

import secrets
import tempfile
from pathlib import Path

import bcrypt
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..config import AAPConfig, DeploymentConfig, RegistryConfig, SCMConfig
from ..helm import HelmClient, generate_portal_values
from ..k8s import KubernetesClient, OpenShiftClient
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
@click.pass_context
def deploy(
    ctx: click.Context,
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
    """Deploy Ansible Portal to OpenShift.

    This command performs a full deployment:
    1. Creates namespace if needed
    2. Builds and pushes plugin OCI image (unless --skip-plugin-build)
    3. Creates required secrets (AAP, SCM, admin credentials)
    4. Generates Helm values with settings management enabled
    5. Deploys portal via Helm
    6. Waits for rollout to complete
    7. Displays portal URL and admin credentials
    """
    console.print("[bold blue]Ansible Portal - Deploy to OpenShift[/bold blue]\n")

    # Initialize clients
    k8s = KubernetesClient()
    oc = OpenShiftClient()
    helm = HelmClient()

    # Check prerequisites
    if not oc.check_logged_in():
        console.print("[red]Not logged into OpenShift. Run 'oc login' first.[/red]")
        raise click.Abort()

    current_user = oc.get_current_user()
    console.print(f"[green]✓[/green] Logged in as: {current_user}\n")

    # Create namespace if needed
    if not k8s.namespace_exists(namespace):
        console.print(f"[blue]Creating namespace: {namespace}[/blue]")
        k8s.create_namespace(namespace)
    else:
        console.print(f"[green]✓[/green] Namespace exists: {namespace}")

    # Build and push plugin image
    if not skip_plugin_build:
        console.print("\n[bold blue]Building Plugin Image[/bold blue]\n")
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

    # Determine registry URL
    if not registry:
        registry_route = oc.get_registry_route()
        if registry_route:
            registry_url = f"{registry_route}/{namespace}/automation-portal"
        else:
            registry_url = (
                f"image-registry.openshift-image-registry.svc:5000/{namespace}/automation-portal"
            )
    else:
        registry_url = f"{registry}/{namespace}/automation-portal"

    # Auto-detect cluster router base
    console.print("[blue]Detecting cluster router base...[/blue]")
    cluster_router_base = oc.get_cluster_router_base()
    console.print(f"[green]✓[/green] Cluster router base: {cluster_router_base}\n")

    # Create AAP secrets
    console.print("[blue]Creating AAP secrets...[/blue]")
    _create_aap_secrets(k8s, namespace, aap_host, aap_token, oauth_client_id, oauth_client_secret)

    # Create SCM secrets if provided
    if github_token or gitlab_token:
        console.print("[blue]Creating SCM secrets...[/blue]")
        _create_scm_secrets(
            k8s,
            namespace,
            github_token,
            github_client_id,
            github_client_secret,
            gitlab_token,
        )

    # Generate admin password and hash
    if not admin_password:
        admin_password = _generate_password()
        console.print("[blue]Generated admin password[/blue]")
    else:
        console.print("[blue]Using provided admin password[/blue]")

    admin_password_hash = _hash_password(admin_password)

    # Generate Helm values
    console.print("[blue]Generating Helm values...[/blue]")
    values = generate_portal_values(
        registry_url=registry_url,
        image_tag=image_tag,
        cluster_router_base=cluster_router_base,
        release_name=release_name,
        admin_password_hash=admin_password_hash,
        check_ssl=check_ssl,
    )

    # Update Helm dependencies
    helm.dependency_update(chart_path)

    # Deploy with Helm
    console.print(f"\n[bold blue]Deploying with Helm[/bold blue]\n")
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
    else:
        portal_url = "Route not found (check manually)"

    # Print deployment summary
    _print_deployment_summary(
        namespace=namespace,
        release_name=release_name,
        portal_url=portal_url,
        admin_password=admin_password,
        registry_url=registry_url,
        image_tag=image_tag,
    )


def _create_aap_secrets(
    k8s: KubernetesClient,
    namespace: str,
    aap_host: str,
    aap_token: str,
    oauth_client_id: str,
    oauth_client_secret: str,
) -> None:
    """Create AAP credentials secret."""
    secret_data = {
        "aap-host-url": aap_host,
        "aap-token": aap_token,
        "oauth-client-id": oauth_client_id,
        "oauth-client-secret": oauth_client_secret,
    }
    k8s.create_secret(namespace, "secrets-rhaap-portal", secret_data)


def _create_scm_secrets(
    k8s: KubernetesClient,
    namespace: str,
    github_token: str | None,
    github_client_id: str | None,
    github_client_secret: str | None,
    gitlab_token: str | None,
) -> None:
    """Create SCM credentials secret."""
    secret_data = {}

    if github_token:
        secret_data["github-token"] = github_token
    if github_client_id:
        secret_data["github-client-id"] = github_client_id
    if github_client_secret:
        secret_data["github-client-secret"] = github_client_secret
    if gitlab_token:
        secret_data["gitlab-token"] = gitlab_token

    if secret_data:
        k8s.create_secret(namespace, "secrets-scm", secret_data)


def _generate_password(length: int = 16) -> str:
    """Generate a random password."""
    # Use secrets module for cryptographically strong random password
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    # Generate bcrypt hash with cost factor 10
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10))
    return hashed.decode()


def _print_deployment_summary(
    namespace: str,
    release_name: str,
    portal_url: str,
    admin_password: str,
    registry_url: str,
    image_tag: str,
) -> None:
    """Print deployment summary table."""
    table = Table(title="Deployment Summary", show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("Portal URL", portal_url)
    table.add_row("Admin User", "portal-admin")
    table.add_row("Admin Password", f"[yellow]{admin_password}[/yellow]")
    table.add_row("Namespace", namespace)
    table.add_row("Release Name", release_name)
    table.add_row("Plugin Image", f"{registry_url}:{image_tag}")

    console.print()
    console.print(Panel(table, title="[bold green]Deployment Complete[/bold green]", border_style="green"))
    console.print()
    console.print("[bold yellow]⚠️  Save the admin password securely![/bold yellow]\n")

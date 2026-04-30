"""Deploy command - Deploy portal using selected backend."""

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..backends import BackendFactory, BackendType
from ..config import AAPConfig, DeploymentConfig, RegistryConfig, SCMConfig
from ..oauth_setup import prompt_oauth_setup, validate_oauth_credentials

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
    "--skip-rollout-wait",
    is_flag=True,
    help="Do not wait for kubectl rollout after Helm (useful to debug slow/stuck pods)",
    envvar="SKIP_ROLLOUT_WAIT",
)
@click.option(
    "--rollout-timeout",
    default="40m",
    help="Timeout for kubectl rollout status (e.g. 30m, 1h). RHDH+plugin init is often slow.",
    envvar="ROLLOUT_TIMEOUT",
)
@click.option(
    "--check-ssl/--no-check-ssl",
    default=False,
    help="Enable/disable SSL verification for AAP",
)
@click.option(
    "--insecure-registry/--no-insecure-registry",
    default=True,
    help="Configure insecure registry support for OpenShift internal registry (default: enabled for dev)",
    envvar="INSECURE_REGISTRY",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show generated Helm values without deploying",
)
@click.option(
    "--values-output",
    type=click.Path(path_type=Path),
    help="Export generated Helm values to file (implies --dry-run)",
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
    skip_rollout_wait: bool,
    rollout_timeout: str,
    check_ssl: bool,
    insecure_registry: bool,
    dry_run: bool,
    values_output: Path | None,
) -> None:
    """Deploy Ansible Portal using selected backend.

    This command performs a full deployment:
    1. Creates namespace/location if needed
    2. Builds and pushes plugin artifacts (unless --skip-plugin-build)
    3. Creates required secrets/credentials
    4. Deploys portal using the selected backend
    5. Waits for deployment rollout (unless --skip-rollout-wait; tune with --rollout-timeout)
    6. Displays portal URL and admin credentials

    Backends:
    - helm: Deploy to Kubernetes/OpenShift using Helm charts
    - operator: Deploy using OpenShift Operators (future)
    - rhel: Install as RHEL packages (future)
    """
    # Validate OAuth credentials
    if not validate_oauth_credentials(aap_host, aap_token, oauth_client_id, oauth_client_secret):
        # Try to get cluster router base for portal route estimation
        from ..k8s import OpenShiftClient
        try:
            oc = OpenShiftClient()
            cluster_router_base = oc.get_cluster_router_base()
        except Exception:
            cluster_router_base = None

        # Prompt for OAuth setup guidance
        if not prompt_oauth_setup(namespace, cluster_router_base, release_name):
            raise click.Abort()

        console.print("[red]Please provide all required AAP credentials and try again.[/red]")
        raise click.Abort()

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
        wait_for_rollout=not skip_rollout_wait,
        rollout_timeout=rollout_timeout,
        check_ssl=check_ssl,
        insecure_registry=insecure_registry,
    )

    # Dry-run mode: show generated values without deploying
    if dry_run or values_output:
        _show_helm_values_preview(deployment_config, values_output)
        return

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


def _show_helm_values_preview(config: DeploymentConfig, output_path: Path | None = None) -> None:
    """Show or export generated Helm values without deploying.

    Args:
        config: Deployment configuration
        output_path: Optional path to export values YAML file
    """
    from ..backends.helm.client import generate_portal_values
    from ..k8s import OpenShiftClient

    console.print("[bold blue]Helm Values Preview (Dry-Run Mode)[/bold blue]\n")

    # Get cluster router base
    try:
        oc = OpenShiftClient()
        cluster_router_base = oc.get_cluster_router_base()
    except Exception:
        cluster_router_base = config.cluster_router_base or "apps.example.com"

    # Generate admin password
    import secrets
    admin_password = config.admin_password or secrets.token_urlsafe(16)

    # Hash password
    import bcrypt
    admin_password_hash = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt(rounds=10)).decode()

    # Generate backend secret
    backend_secret = secrets.token_urlsafe(32)

    # Determine registry URL
    registry_url = "quay.io/example/ansible-portal-plugins"  # Placeholder for dry-run
    if config.registry:
        registry_url = config.registry.full_image_url

    # Generate values
    values = generate_portal_values(
        registry_url=registry_url,
        image_tag=config.image_tag,
        cluster_router_base=cluster_router_base,
        release_name=config.release_name,
        admin_password_hash=admin_password_hash,
        backend_secret=backend_secret,
        check_ssl=config.check_ssl,
    )

    # Export to file if requested
    if output_path:
        import yaml
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            yaml.dump(values, f, default_flow_style=False, sort_keys=False)
        console.print(f"[green]✓[/green] Helm values exported to: {output_path}\n")

    # Print to console
    import yaml
    console.print(Panel("[bold]Generated Helm Values:[/bold]", border_style="cyan"))
    console.print(yaml.dump(values, default_flow_style=False, sort_keys=False))

    console.print("\n[bold yellow]Preview Mode - No Deployment Performed[/bold yellow]")
    console.print("[dim]Remove --dry-run or --values-output to proceed with deployment[/dim]\n")


def _print_deployment_summary(result: dict) -> None:
    """Print deployment summary table."""
    table = Table(title="Deployment Summary", show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    portal_url = result.get("url", "N/A")
    table.add_row("Portal URL", portal_url)
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

    # Print OAuth redirect URI update instructions
    console.print("[bold red]🔴 CRITICAL: Update OAuth Redirect URIs[/bold red]")
    console.print("[yellow]Authentication will fail until you complete this step![/yellow]\n")

    console.print("[bold]Update your AAP OAuth Application:[/bold]")
    console.print("  1. AAP Controller → Administration → OAuth Applications")
    console.print("  2. Edit your OAuth app and update redirect URIs to:")
    console.print(f"     • {portal_url}/api/auth/rhaap/handler/frame")
    console.print(f"     • {portal_url}/api/auth/github/handler/frame\n")

    console.print("[bold]Update your GitHub OAuth Application:[/bold]")
    console.print("  1. GitHub → Settings → Developer settings → OAuth Apps")
    console.print("  2. Edit your OAuth app and update Authorization callback URL to:")
    console.print(f"     • {portal_url}/api/auth/github/handler/frame\n")

    console.print("[dim]If redirect URIs don't match exactly, you'll see 'redirect_uri_mismatch' errors.[/dim]\n")

    # Print verification checklist
    _print_verification_checklist(portal_url)


def _print_verification_checklist(portal_url: str) -> None:
    """Print post-deployment verification checklist.

    Args:
        portal_url: Portal URL for testing
    """
    console.print("[bold cyan]📋 Verification Checklist[/bold cyan]\n")

    console.print("[bold]After updating OAuth redirect URIs, verify:[/bold]")
    console.print("  [ ] Portal loads in browser:")
    console.print(f"      {portal_url}")
    console.print("  [ ] AAP sign-in works (OAuth redirect to AAP login)")
    console.print("  [ ] After AAP login, you're redirected back to portal (no redirect_uri_mismatch)")
    console.print("  [ ] Templates visible at /create (ansible-rhdh-templates)")
    console.print("  [ ] Custom plugins loaded:")
    console.print("      Check init container logs: oc logs <pod> -c install-dynamic-plugins")
    console.print("  [ ] Content discovery working (if enabled):")
    console.print("      Check backend logs: oc logs <pod> -c backstage-backend | grep ansible-collections")
    console.print()
    console.print("[bold]Troubleshooting commands:[/bold]")
    console.print(f"  oc get pods        # Check pod status (should be 2/2 Running)")
    console.print(f"  oc get route       # Verify portal route")
    console.print(f"  oc logs <pod> -c install-dynamic-plugins --tail=100  # Plugin loading")
    console.print(f"  oc logs <pod> -c backstage-backend --tail=100        # Backend logs")
    console.print()

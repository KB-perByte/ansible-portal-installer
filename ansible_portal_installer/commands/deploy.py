"""Deploy command - Deploy portal using selected backend."""

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..backends import BackendFactory, BackendType
from ..config import AAPConfig, DeploymentConfig, PortalInstallerSettings, RegistryConfig, SCMConfig
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
    default=None,
    help="Target namespace/location (or set OCP_NAMESPACE in .env)",
    envvar="OCP_NAMESPACE",
)
@click.option(
    "--release-name",
    default=None,
    help="Deployment identifier (or set RELEASE_NAME in .env)",
    envvar="RELEASE_NAME",
)
@click.option(
    "--chart-path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Path to deployment configuration (or set CHART_PATH in .env)",
    envvar="CHART_PATH",
)
@click.option(
    "--plugins-path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Path to ansible-rhdh-plugins repository (downstream) (or set PLUGINS_PATH in .env)",
    envvar="PLUGINS_PATH",
)
@click.option(
    "--upstream-plugins-path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Path to ansible-backstage-plugins repository (upstream) (or set UPSTREAM_PLUGINS_PATH in .env)",
    envvar="UPSTREAM_PLUGINS_PATH",
)
@click.option(
    "--aap-host",
    default=None,
    help="AAP controller URL (or set AAP_HOST_URL in .env)",
    envvar="AAP_HOST_URL",
)
@click.option(
    "--aap-token",
    default=None,
    help="AAP API token (or set AAP_TOKEN in .env)",
    envvar="AAP_TOKEN",
)
@click.option(
    "--oauth-client-id",
    default=None,
    help="AAP OAuth client ID (or set OAUTH_CLIENT_ID in .env)",
    envvar="OAUTH_CLIENT_ID",
)
@click.option(
    "--oauth-client-secret",
    default=None,
    help="AAP OAuth client secret (or set OAUTH_CLIENT_SECRET in .env)",
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
    "--gitlab-client-id",
    help="GitLab OAuth client ID",
    envvar="GITLAB_CLIENT_ID",
)
@click.option(
    "--gitlab-client-secret",
    help="GitLab OAuth client secret",
    envvar="GITLAB_CLIENT_SECRET",
)
@click.option(
    "--registry",
    help="Registry URL (default: auto-detect)",
    envvar="PLUGIN_REGISTRY",
)
@click.option(
    "--image-tag",
    default=None,
    help="Plugin image tag (or set PLUGIN_IMAGE_TAG in .env)",
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
    "--registry-auth-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to registry auth.json file (optional, only needed for authenticated registries)",
    envvar="REGISTRY_AUTH_FILE",
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
    namespace: str | None,
    release_name: str | None,
    chart_path: Path | None,
    plugins_path: Path | None,
    upstream_plugins_path: Path | None,
    aap_host: str | None,
    aap_token: str | None,
    oauth_client_id: str | None,
    oauth_client_secret: str | None,
    github_token: str | None,
    github_client_id: str | None,
    github_client_secret: str | None,
    gitlab_token: str | None,
    gitlab_client_id: str | None,
    gitlab_client_secret: str | None,
    registry: str | None,
    image_tag: str | None,
    admin_password: str | None,
    skip_plugin_build: bool,
    registry_auth_file: Path | None,
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

    Configuration is loaded from (in order of precedence):
    1. Command-line flags (highest priority)
    2. Environment variables
    3. .env file in current directory
    4. Default values (lowest priority)

    Backends:
    - helm: Deploy to Kubernetes/OpenShift using Helm charts
    - operator: Deploy using OpenShift Operators (future)
    - rhel: Install as RHEL packages (future)
    """
    # Load settings from .env file (if it exists)
    try:
        settings = PortalInstallerSettings()
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load .env file: {e}[/yellow]")
        settings = None

    # Merge CLI args with .env settings (CLI args take precedence)
    # Only use .env value if CLI arg is None (not provided)
    if settings:
        namespace = namespace or settings.ocp_namespace
        release_name = release_name or settings.release_name
        chart_path = chart_path or Path(settings.chart_path)
        plugins_path = plugins_path or Path(settings.plugins_path)
        upstream_plugins_path = upstream_plugins_path or (Path(settings.upstream_plugins_path) if settings.upstream_plugins_path else None)
        aap_host = aap_host or settings.aap_host_url
        aap_token = aap_token or settings.aap_token
        oauth_client_id = oauth_client_id or settings.oauth_client_id
        oauth_client_secret = oauth_client_secret or settings.oauth_client_secret
        github_token = github_token or settings.github_token
        github_client_id = github_client_id or settings.github_client_id
        github_client_secret = github_client_secret or settings.github_client_secret
        gitlab_token = gitlab_token or settings.gitlab_token
        gitlab_client_id = gitlab_client_id or settings.gitlab_client_id
        gitlab_client_secret = gitlab_client_secret or settings.gitlab_client_secret
        registry = registry or settings.plugin_registry
        image_tag = image_tag or settings.plugin_image_tag
        registry_auth_file = registry_auth_file or (Path(settings.registry_auth_file) if settings.registry_auth_file else None)
        admin_password = admin_password or settings.portal_admin_password

    # Apply defaults for optional fields if still None
    namespace = namespace or None  # Will fail validation below if still None
    release_name = release_name or "rhaap-portal-dev"
    chart_path = chart_path or Path("../ansible-portal-chart")
    plugins_path = plugins_path or Path.cwd()
    image_tag = image_tag or "dev"

    # Validate required fields
    missing = []
    if not namespace:
        missing.append("--namespace (or OCP_NAMESPACE in .env)")
    if not aap_host:
        missing.append("--aap-host (or AAP_HOST_URL in .env)")
    if not aap_token:
        missing.append("--aap-token (or AAP_TOKEN in .env)")
    if not oauth_client_id:
        missing.append("--oauth-client-id (or OAUTH_CLIENT_ID in .env)")
    if not oauth_client_secret:
        missing.append("--oauth-client-secret (or OAUTH_CLIENT_SECRET in .env)")
    if not skip_plugin_build and not upstream_plugins_path:
        missing.append("--upstream-plugins-path (or UPSTREAM_PLUGINS_PATH in .env) - required when building plugins")

    if missing:
        console.print("[bold red]Missing required configuration:[/bold red]")
        for item in missing:
            console.print(f"  • {item}")
        console.print("\n[yellow]Provide values via CLI flags, environment variables, or .env file[/yellow]")
        console.print("[dim]Example .env file: cp .env.example .env (then edit)[/dim]\n")
        raise click.Abort()

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
            gitlab_client_id=gitlab_client_id,
            gitlab_client_secret=gitlab_client_secret,
        )

    registry_config = None
    if registry:
        # Parse registry URL into components
        # Format: registry-url/namespace/image-name or registry-url/namespace/project/image-name
        parts = registry.split("/")
        if len(parts) >= 3:
            registry_url = parts[0]
            registry_namespace = parts[1]
            # Join remaining parts as image name (handles multi-level paths like tenant/image-name)
            image_name = "/".join(parts[2:])
        elif len(parts) == 2:
            registry_url = parts[0]
            registry_namespace = parts[1]
            image_name = "automation-portal"
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
        upstream_plugins_path=upstream_plugins_path,
        registry=registry_config,
        registry_auth_file=registry_auth_file,
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

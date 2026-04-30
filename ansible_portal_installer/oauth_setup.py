"""OAuth setup guidance and validation for Ansible Portal deployment."""

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

console = Console()


def print_oauth_setup_guide(portal_route_guess: str | None = None) -> None:
    """Print OAuth application setup instructions.

    Args:
        portal_route_guess: Estimated portal route for placeholder redirect URIs
    """
    console.print("\n[bold cyan]OAuth Application Setup Required[/bold cyan]\n")

    console.print(
        "[yellow]Before deploying, you need to create OAuth applications in AAP and GitHub.[/yellow]\n"
    )

    # AAP OAuth Application
    console.print("[bold]Step 1: Create AAP OAuth Application[/bold]")
    console.print("  1. Open AAP Controller → Administration → OAuth Applications")
    console.print("  2. Click [bold]Add[/bold] to create a new OAuth Application")
    console.print("  3. Configure:")
    console.print("     • [cyan]Name[/cyan]: Ansible Portal Dev (or your choice)")
    console.print("     • [cyan]Authorization Grant Type[/cyan]: Authorization code")
    console.print("     • [cyan]Client Type[/cyan]: Confidential")

    if portal_route_guess:
        console.print("     • [cyan]Redirect URIs[/cyan] (placeholder - will update after deployment):")
        console.print(f"       {portal_route_guess}/api/auth/rhaap/handler/frame")
        console.print(f"       {portal_route_guess}/api/auth/github/handler/frame")
    else:
        console.print(
            "     • [cyan]Redirect URIs[/cyan]: Use placeholder https://PORTAL-ROUTE/api/auth/rhaap/handler/frame"
        )
        console.print("       (You'll update this with the actual route after deployment)")

    console.print("  4. Click [bold]Save[/bold]")
    console.print("  5. Copy the [bold yellow]Client ID[/bold yellow] and [bold yellow]Client Secret[/bold yellow]\n")

    # AAP API Token
    console.print("[bold]Step 2: Create AAP API Token[/bold]")
    console.print("  1. AAP Controller → your user profile → Tokens tab")
    console.print("  2. Click [bold]Add[/bold] to create a new token")
    console.print("  3. Configure:")
    console.print("     • [cyan]Description[/cyan]: Ansible Portal API Access")
    console.print("     • [cyan]Scope[/cyan]: Read + Write")
    console.print("  4. Click [bold]Save[/bold]")
    console.print("  5. Copy the [bold yellow]token[/bold yellow] (shown only once!)\n")

    # GitHub OAuth Application
    console.print("[bold]Step 3: Create GitHub OAuth Application (Optional)[/bold]")
    console.print("  1. GitHub.com → Settings → Developer settings → OAuth Apps")
    console.print("  2. Click [bold]New OAuth App[/bold]")
    console.print("  3. Configure:")
    console.print("     • [cyan]Application name[/cyan]: Ansible Portal Dev")
    console.print("     • [cyan]Homepage URL[/cyan]: Your AAP or portal URL")

    if portal_route_guess:
        console.print("     • [cyan]Authorization callback URL[/cyan]:")
        console.print(f"       {portal_route_guess}/api/auth/github/handler/frame")
    else:
        console.print(
            "     • [cyan]Authorization callback URL[/cyan]: https://PORTAL-ROUTE/api/auth/github/handler/frame"
        )

    console.print("  4. Click [bold]Register application[/bold]")
    console.print("  5. Copy the [bold yellow]Client ID[/bold yellow]")
    console.print("  6. Generate a new [bold yellow]Client Secret[/bold yellow] and copy it\n")

    # GitHub Personal Access Token
    console.print("[bold]Step 4: Create GitHub Personal Access Token (Optional)[/bold]")
    console.print("  1. GitHub.com → Settings → Developer settings → Personal access tokens → Tokens (classic)")
    console.print("  2. Click [bold]Generate new token (classic)[/bold]")
    console.print("  3. Configure:")
    console.print("     • [cyan]Note[/cyan]: Ansible Portal Integration")
    console.print("     • [cyan]Scopes[/cyan]: Select [bold]repo[/bold], [bold]read:org[/bold], [bold]user:email[/bold]")
    console.print("  4. Click [bold]Generate token[/bold]")
    console.print("  5. Copy the [bold yellow]token[/bold yellow] (shown only once!)\n")

    console.print(
        Panel(
            "[yellow]⚠️  After deployment, you MUST update the OAuth redirect URIs with the actual portal route![/yellow]",
            border_style="yellow",
        )
    )
    console.print()


def validate_oauth_credentials(
    aap_host: str | None,
    aap_token: str | None,
    oauth_client_id: str | None,
    oauth_client_secret: str | None,
) -> bool:
    """Validate that required OAuth credentials are provided.

    Args:
        aap_host: AAP controller URL
        aap_token: AAP API token
        oauth_client_id: AAP OAuth client ID
        oauth_client_secret: AAP OAuth client secret

    Returns:
        True if all required credentials are present
    """
    missing = []

    if not aap_host:
        missing.append("--aap-host (or AAP_HOST_URL env var)")
    if not aap_token:
        missing.append("--aap-token (or AAP_TOKEN env var)")
    if not oauth_client_id:
        missing.append("--oauth-client-id (or OAUTH_CLIENT_ID env var)")
    if not oauth_client_secret:
        missing.append("--oauth-client-secret (or OAUTH_CLIENT_SECRET env var)")

    if missing:
        console.print("[bold red]Missing required AAP credentials:[/bold red]")
        for item in missing:
            console.print(f"  • {item}")
        console.print()
        return False

    return True


def prompt_oauth_setup(namespace: str, cluster_router_base: str | None, release_name: str) -> bool:
    """Prompt user if they need OAuth setup guidance.

    Args:
        namespace: Deployment namespace
        cluster_router_base: Cluster router base domain
        release_name: Helm release name

    Returns:
        True if user wants to continue with deployment
    """
    # Estimate portal route
    portal_route_guess = None
    if cluster_router_base:
        portal_route_guess = f"https://{release_name}-{namespace}.{cluster_router_base}"

    console.print()
    need_help = Confirm.ask(
        "[cyan]Do you need help setting up OAuth applications?[/cyan]",
        default=False,
    )

    if need_help:
        print_oauth_setup_guide(portal_route_guess)

        ready = Confirm.ask(
            "[cyan]Have you created the OAuth applications and have your credentials ready?[/cyan]",
            default=True,
        )

        if not ready:
            console.print("[yellow]Deployment cancelled. Set up OAuth apps first.[/yellow]")
            return False

    return True

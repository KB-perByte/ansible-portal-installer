"""Main CLI entry point for ansible-portal-installer."""

import click
from rich.console import Console

from . import __version__
from .commands import build

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="ansible-portal-installer")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Ansible Portal Installer - Deploy Ansible Automation Portal to OpenShift.

    This tool helps you build, deploy, and manage the Ansible Automation Portal
    on OpenShift clusters using locally-built plugins in OCI mode.

    \b
    Common workflows:
        # Full deployment
        $ ansible-portal-installer deploy --namespace my-ns --aap-host https://aap.example.com

        # Just build plugins
        $ ansible-portal-installer build --namespace my-ns

        # Validate deployment
        $ ansible-portal-installer validate --namespace my-ns

        # Collect logs
        $ ansible-portal-installer collect-logs --namespace my-ns

    \b
    Environment variables:
        All CLI options can be set via environment variables.
        See --help for each command for details.
    """
    ctx.ensure_object(dict)


# Register commands
cli.add_command(build.build)


# Placeholder commands (to be implemented)
@cli.command()
@click.option("--namespace", "-n", required=True)
def deploy(namespace: str) -> None:
    """Deploy portal to OpenShift (WIP)."""
    console.print(f"[yellow]Deploy command not yet implemented for {namespace}[/yellow]")
    console.print("[blue]Use the build command to build plugin images[/blue]")


@cli.command()
@click.option("--namespace", "-n", required=True)
def upgrade(namespace: str) -> None:
    """Upgrade existing deployment (WIP)."""
    console.print(f"[yellow]Upgrade command not yet implemented for {namespace}[/yellow]")


@cli.command()
@click.option("--namespace", "-n", required=True)
def validate(namespace: str) -> None:
    """Run health checks (WIP)."""
    console.print(f"[yellow]Validate command not yet implemented for {namespace}[/yellow]")


@cli.command(name="collect-logs")
@click.option("--namespace", "-n", required=True)
def collect_logs(namespace: str) -> None:
    """Collect diagnostic logs (WIP)."""
    console.print(f"[yellow]Collect-logs command not yet implemented for {namespace}[/yellow]")


@cli.command()
@click.option("--namespace", "-n", required=True)
def teardown(namespace: str) -> None:
    """Remove deployment (WIP)."""
    console.print(f"[yellow]Teardown command not yet implemented for {namespace}[/yellow]")


if __name__ == "__main__":
    cli()

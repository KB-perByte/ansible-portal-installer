"""Main CLI entry point for ansible-portal-installer."""

import click
from dotenv import load_dotenv
from rich.console import Console

from . import __version__
from .commands import build, collect_logs, deploy, teardown, upgrade, validate

console = Console()

# Load .env file into environment variables for Click
load_dotenv()


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


# Register all commands
cli.add_command(build.build)
cli.add_command(deploy.deploy)
cli.add_command(upgrade.upgrade)
cli.add_command(validate.validate)
cli.add_command(collect_logs.collect_logs)
cli.add_command(teardown.teardown)


if __name__ == "__main__":
    cli()

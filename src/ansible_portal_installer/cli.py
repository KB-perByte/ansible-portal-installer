"""CLI entry point for Ansible Portal Installer."""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.panel import Panel

from . import __version__
from .actions import build_plugins, publish_image, deploy_helm, check_prerequisites, verify_deployment
from .config import Settings, get_settings
from .config.validation import validate_all
from .constants import EXIT_SUCCESS, EXIT_ERROR, EXIT_KEYBOARD_INTERRUPT
from .core import (
    InstallContext,
    InstallerError,
    ConfigurationError,
)
from .installers import HelmInstaller
from .ui import (
    console,
    print_header,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_panel,
    confirm,
)


@click.group()
@click.version_option(version=__version__, prog_name="ansible-portal-installer")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--dry-run", is_flag=True, help="Show what would be done without executing")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, dry_run: bool) -> None:
    """Ansible Portal Installer - TUI installer for Ansible Automation Portal.

    A comprehensive tool to build, publish, and deploy Ansible Portal plugins.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["dry_run"] = dry_run


@cli.command()
@click.option("--type", "build_type", type=click.Choice(["portal", "platform", "all"]), help="Build type")
@click.pass_context
def build(ctx: click.Context, build_type: Optional[str]) -> None:
    """Build dynamic plugins from source."""
    try:
        settings = get_settings()
        if build_type:
            settings.build_type = build_type

        settings.verbose = ctx.obj.get("verbose", False)
        settings.dry_run = ctx.obj.get("dry_run", False)

        # Validate configuration
        validate_all(settings, "build")

        context = InstallContext()

        if settings.dry_run:
            print_info("DRY RUN MODE - No changes will be made")
            print_info(f"Would build plugins from: {settings.ansible_backstage_plugins_path}")
            return

        build_plugins(settings, context)

        console.print()
        print_success("Build completed successfully!")
        sys.exit(EXIT_SUCCESS)

    except (InstallerError, ConfigurationError) as e:
        print_error(f"Build failed: {e}")
        sys.exit(EXIT_ERROR)
    except KeyboardInterrupt:
        print_warning("\nOperation cancelled by user")
        sys.exit(EXIT_KEYBOARD_INTERRUPT)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        if ctx.obj.get("verbose"):
            console.print_exception()
        sys.exit(EXIT_ERROR)


@cli.command()
@click.option("--registry", help="Container registry (default: from .env)")
@click.option("--tag", help="Image tag (default: dev-YYYYMMDD)")
@click.option("--skip-build", is_flag=True, help="Skip building plugins first")
@click.pass_context
def publish(ctx: click.Context, registry: Optional[str], tag: Optional[str], skip_build: bool) -> None:
    """Build and push plugin container image to registry."""
    try:
        settings = get_settings()
        if registry:
            settings.registry = registry
        if tag:
            settings.plugins_image_tag = tag

        settings.verbose = ctx.obj.get("verbose", False)
        settings.dry_run = ctx.obj.get("dry_run", False)

        # Validate configuration
        validate_all(settings, "publish")

        context = InstallContext()

        if settings.dry_run:
            print_info("DRY RUN MODE - No changes will be made")
            print_info(f"Would publish image: {settings.full_image_reference}")
            return

        publish_image(settings, context, build_first=not skip_build)

        console.print()
        print_success("Publish completed successfully!")
        sys.exit(EXIT_SUCCESS)

    except (InstallerError, ConfigurationError) as e:
        print_error(f"Publish failed: {e}")
        sys.exit(EXIT_ERROR)
    except KeyboardInterrupt:
        print_warning("\nOperation cancelled by user")
        sys.exit(EXIT_KEYBOARD_INTERRUPT)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        if ctx.obj.get("verbose"):
            console.print_exception()
        sys.exit(EXIT_ERROR)


@cli.command()
@click.option("--namespace", "-n", help="OpenShift namespace (default: from .env)")
@click.option("--release", "-r", help="Helm release name (default: from .env)")
@click.option("--skip-publish", is_flag=True, help="Skip publishing image first (OCI mode)")
@click.pass_context
def helm_deploy(ctx: click.Context, namespace: Optional[str], release: Optional[str], skip_publish: bool) -> None:
    """Deploy Ansible Portal to OpenShift using Helm."""
    try:
        settings = get_settings()
        if namespace:
            settings.openshift_namespace = namespace
        if release:
            settings.helm_release_name = release

        settings.verbose = ctx.obj.get("verbose", False)
        settings.dry_run = ctx.obj.get("dry_run", False)

        # Validate configuration
        validate_all(settings, "helm-deploy")

        context = InstallContext()

        if settings.dry_run:
            print_info("DRY RUN MODE - No changes will be made")
            print_info(f"Would deploy to: {settings.openshift_namespace}")
            print_info(f"Release name: {settings.helm_release_name}")
            return

        # Confirm deployment
        if not settings.skip_confirmations:
            if not confirm(f"Deploy to namespace '{settings.openshift_namespace}'?"):
                print_warning("Deployment cancelled")
                return

        deploy_helm(settings, context, publish_first=not skip_publish)

        console.print()
        print_success("Deployment completed successfully!")
        sys.exit(EXIT_SUCCESS)

    except (InstallerError, ConfigurationError) as e:
        print_error(f"Deployment failed: {e}")
        sys.exit(EXIT_ERROR)
    except KeyboardInterrupt:
        print_warning("\nOperation cancelled by user")
        sys.exit(EXIT_KEYBOARD_INTERRUPT)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        if ctx.obj.get("verbose"):
            console.print_exception()
        sys.exit(EXIT_ERROR)


@cli.command()
@click.option("--namespace", "-n", help="OpenShift namespace (default: from .env)")
@click.option("--release", "-r", help="Helm release name (default: from .env)")
@click.pass_context
def full_deploy(ctx: click.Context, namespace: Optional[str], release: Optional[str]) -> None:
    """Run complete workflow: build → publish → deploy."""
    try:
        settings = get_settings()
        if namespace:
            settings.openshift_namespace = namespace
        if release:
            settings.helm_release_name = release

        settings.verbose = ctx.obj.get("verbose", False)
        settings.dry_run = ctx.obj.get("dry_run", False)

        # Validate configuration
        validate_all(settings, "full-deploy")

        context = InstallContext()

        if settings.dry_run:
            print_info("DRY RUN MODE - No changes will be made")
            print_info("Would execute: build → publish → deploy")
            return

        # Confirm deployment
        if not settings.skip_confirmations:
            if not confirm("Run complete deployment workflow?"):
                print_warning("Deployment cancelled")
                return

        # Execute workflow
        print_header("Full Deployment Workflow")
        console.print()

        # Step 1: Build
        build_plugins(settings, context)
        console.print()

        # Step 2: Publish
        publish_image(settings, context, build_first=False)
        console.print()

        # Step 3: Deploy
        deploy_helm(settings, context, publish_first=False)
        console.print()

        # Summary
        print_panel(
            f"""
[bold green]✓[/bold green] Build completed
[bold green]✓[/bold green] Image published: {context.image_reference}
[bold green]✓[/bold green] Deployed to: {settings.openshift_namespace}
[bold green]✓[/bold green] Portal URL: {context.portal_route or 'Pending'}
""",
            title="Deployment Summary",
            style="green",
        )

        sys.exit(EXIT_SUCCESS)

    except (InstallerError, ConfigurationError) as e:
        print_error(f"Deployment failed: {e}")
        sys.exit(EXIT_ERROR)
    except KeyboardInterrupt:
        print_warning("\nOperation cancelled by user")
        sys.exit(EXIT_KEYBOARD_INTERRUPT)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        if ctx.obj.get("verbose"):
            console.print_exception()
        sys.exit(EXIT_ERROR)


@cli.command()
@click.pass_context
def verify(ctx: click.Context) -> None:
    """Verify installation and configuration."""
    try:
        settings = get_settings()
        settings.verbose = ctx.obj.get("verbose", False)

        # Check prerequisites
        prereqs = check_prerequisites()
        console.print()

        # Verify deployment if configured
        if settings.openshift_server and settings.openshift_token:
            results = verify_deployment(settings)
        else:
            print_warning("OpenShift credentials not configured - skipping deployment verification")
            results = {}

        # Exit with appropriate code
        all_checks_passed = all(prereqs.values()) and (not results or all(results.values()))
        sys.exit(EXIT_SUCCESS if all_checks_passed else EXIT_ERROR)

    except Exception as e:
        print_error(f"Verification failed: {e}")
        if ctx.obj.get("verbose"):
            console.print_exception()
        sys.exit(EXIT_ERROR)


@cli.command()
@click.option("--namespace", "-n", help="OpenShift namespace (default: from .env)")
@click.option("--release", "-r", help="Helm release name (default: from .env)")
@click.pass_context
def status(ctx: click.Context, namespace: Optional[str], release: Optional[str]) -> None:
    """Check current deployment status."""
    try:
        settings = get_settings()
        if namespace:
            settings.openshift_namespace = namespace
        if release:
            settings.helm_release_name = release

        settings.verbose = ctx.obj.get("verbose", False)

        context = InstallContext()
        installer = HelmInstaller(settings, context)
        installer.display_status()

        sys.exit(EXIT_SUCCESS)

    except Exception as e:
        print_error(f"Failed to get status: {e}")
        if ctx.obj.get("verbose"):
            console.print_exception()
        sys.exit(EXIT_ERROR)


@cli.command()
@click.option("--namespace", "-n", help="OpenShift namespace")
@click.option("--release", "-r", help="Helm release name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.pass_context
def cleanup(ctx: click.Context, namespace: Optional[str], release: Optional[str], yes: bool) -> None:
    """Clean up deployment and resources."""
    try:
        settings = get_settings()
        if namespace:
            settings.openshift_namespace = namespace
        if release:
            settings.helm_release_name = release

        settings.verbose = ctx.obj.get("verbose", False)

        # Confirm cleanup
        if not yes:
            if not confirm(f"Uninstall release '{settings.helm_release_name}' from '{settings.openshift_namespace}'?"):
                print_warning("Cleanup cancelled")
                return

        context = InstallContext()
        installer = HelmInstaller(settings, context)
        installer.uninstall()

        print_success("Cleanup completed successfully!")
        sys.exit(EXIT_SUCCESS)

    except Exception as e:
        print_error(f"Cleanup failed: {e}")
        if ctx.obj.get("verbose"):
            console.print_exception()
        sys.exit(EXIT_ERROR)


def main() -> None:
    """Main entry point."""
    try:
        cli(obj={})
    except Exception as e:
        print_error(f"Fatal error: {e}")
        sys.exit(EXIT_ERROR)


if __name__ == "__main__":
    main()

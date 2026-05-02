"""Helm upgrade action for existing deployments."""

from pathlib import Path
from typing import Optional
from datetime import datetime

from ..config import Settings
from ..core import UpgradeError, InstallContext
from ..ui import print_header, print_success, print_info, print_warning, console, create_progress
from ..utils import (
    helm_upgrade,
    oc_rollout_status,
    oc_get_route,
    oc_get_pods,
    oc_wait_for_pods,
    build_image,
    push_image,
    login_registry,
    get_container_tool,
    http_health_check,
)
from .build import build_plugins


def rebuild_and_push_plugins(
    settings: Settings, context: InstallContext, plugins_path: Path
) -> str:
    """Rebuild plugins from path and push new OCI image.

    Args:
        settings: Application settings
        context: Installation context
        plugins_path: Path to plugins source directory

    Returns:
        New image reference

    Raises:
        UpgradeError: If rebuild/push fails
    """
    print_info(f"Rebuilding plugins from: {plugins_path}")

    # Update settings to use provided plugins path
    original_path = settings.ansible_backstage_plugins_path
    settings.ansible_backstage_plugins_path = plugins_path

    try:
        # Build plugins
        build_plugins(settings, context)

        # Generate new image tag with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        new_tag = f"upgrade-{timestamp}"
        full_image_ref = f"{settings.registry}/{settings.registry_namespace}/{settings.plugins_image_name}:{new_tag}"

        print_info(f"New image tag: {new_tag}")

        # Authenticate to registry
        console.print()
        print_info("Authenticating to registry...")
        try:
            login_registry(
                registry=settings.registry,
                username=settings.registry_username,
                password=settings.registry_password,
            )
        except Exception as e:
            raise UpgradeError(f"Registry authentication failed: {e}") from e

        # Build container image
        console.print()
        print_info("Building container image...")
        try:
            build_image(
                context_dir=settings.dynamic_plugins_path,
                containerfile="Containerfile",
                tag=full_image_ref,
            )
        except Exception as e:
            raise UpgradeError(f"Image build failed: {e}") from e

        # Push to registry
        console.print()
        print_info("Pushing image to registry...")
        try:
            push_image(tag=full_image_ref)
        except Exception as e:
            raise UpgradeError(f"Image push failed: {e}") from e

        # Update context
        context.upgraded_image_reference = full_image_ref

        print_success(f"Image published: {full_image_ref}")
        return full_image_ref

    except Exception as e:
        if isinstance(e, UpgradeError):
            raise
        raise UpgradeError(f"Plugin rebuild failed: {e}") from e
    finally:
        # Restore original path
        settings.ansible_backstage_plugins_path = original_path


def upgrade_helm_release(
    settings: Settings,
    context: InstallContext,
    new_image_ref: Optional[str] = None,
    new_image_tag: Optional[str] = None,
) -> None:
    """Upgrade Helm release with new plugin image.

    Args:
        settings: Application settings
        context: Installation context
        new_image_ref: Full image reference (if rebuilt)
        new_image_tag: Just tag (if switching to existing image)

    Raises:
        UpgradeError: If upgrade fails
    """
    console.print()
    print_info("Upgrading Helm release...")

    # Build values for upgrade
    if new_image_ref:
        # Extract registry, org, image, tag from full reference
        # Format: registry/org/image:tag
        parts = new_image_ref.split("/")
        registry = parts[0]
        org_image = "/".join(parts[1:])
        org_image_parts = org_image.split(":")
        org_and_image = org_image_parts[0]
        tag = org_image_parts[1] if len(org_image_parts) > 1 else "latest"

        image_without_tag = f"{registry}/{org_and_image}"
    else:
        # Use existing image with new tag
        image_without_tag = f"{settings.registry}/{settings.registry_namespace}/{settings.plugins_image_name}"
        tag = new_image_tag

    # Helm values to update
    values = {
        "redhat-developer-hub": {
            "global": {
                "pluginMode": "oci",
                "ociPluginImage": image_without_tag,
                "imageTagInfo": tag,
            }
        }
    }

    try:
        # Run helm upgrade
        helm_upgrade(
            release_name=settings.helm_release_name,
            chart_path=str(settings.helm_chart_path),
            namespace=settings.openshift_namespace,
            values_dict=values,
        )

        # Update context
        context.upgraded_image_reference = f"{image_without_tag}:{tag}"
        print_success("Helm upgrade initiated")

    except Exception as e:
        raise UpgradeError(f"Helm upgrade failed: {e}") from e


def wait_for_rollout(settings: Settings, context: InstallContext) -> None:
    """Wait for rollout to complete after upgrade.

    Args:
        settings: Application settings
        context: Installation context

    Raises:
        UpgradeError: If rollout times out or fails
    """
    console.print()
    print_info("Waiting for rollout to complete...")

    namespace = settings.openshift_namespace
    deployment_name = f"{settings.helm_release_name}-rhaap-portal"

    try:
        # Wait for deployment rollout
        print_info(f"Checking deployment: {deployment_name}")
        oc_rollout_status(
            deployment_name=deployment_name,
            namespace=namespace,
            timeout=600,
        )

        # Wait for pods to be ready
        console.print()
        print_info("Waiting for pods to be ready...")
        oc_wait_for_pods(namespace=namespace, timeout=300)

        context.upgrade_rollout_status = "complete"
        print_success("Rollout completed successfully")

    except Exception as e:
        context.upgrade_rollout_status = "failed"
        raise UpgradeError(f"Rollout failed: {e}") from e


def verify_upgrade(settings: Settings, context: InstallContext) -> None:
    """Verify upgrade completed successfully.

    Args:
        settings: Application settings
        context: Installation context
    """
    console.print()
    print_info("Verifying upgrade...")

    namespace = settings.openshift_namespace

    # Check pod health
    try:
        pods = oc_get_pods(namespace=namespace)
        running_pods = [p for p in pods if p["status"] == "Running"]

        if not running_pods:
            print_warning("No pods are running yet")
        else:
            print_success(f"{len(running_pods)} pod(s) running")

    except Exception as e:
        print_warning(f"Could not verify pod status: {e}")

    # Get route
    try:
        route = oc_get_route(
            release_name=settings.helm_release_name,
            namespace=namespace,
        )

        if route:
            context.portal_route = route
            print_success(f"Portal route: {route}")

            # Basic HTTP health check
            if http_health_check(route, timeout=30):
                print_success("Portal is responding")
            else:
                print_warning("Portal is not responding yet (may take a few minutes)")
        else:
            print_warning("Portal route not found")

    except Exception as e:
        print_warning(f"Could not verify route: {e}")


def helm_upgrade_command(
    settings: Settings,
    context: InstallContext,
    plugins_path: Optional[Path] = None,
    image_tag: Optional[str] = None,
) -> None:
    """Execute Helm upgrade workflow.

    Args:
        settings: Application settings
        context: Installation context
        plugins_path: Path to rebuild plugins from
        image_tag: Existing image tag to switch to

    Raises:
        UpgradeError: If upgrade fails
    """
    print_header(f"Upgrading Helm Release: {settings.helm_release_name}")

    # Validate: exactly one of plugins_path or image_tag must be set
    if not plugins_path and not image_tag:
        raise UpgradeError("Must specify either plugins_path or image_tag")
    if plugins_path and image_tag:
        raise UpgradeError("Cannot specify both plugins_path and image_tag")

    console.print()

    # Execute workflow with progress
    with create_progress() as progress:
        if plugins_path:
            task = progress.add_task("Upgrading deployment...", total=4)

            # Step 1: Rebuild and push
            progress.update(task, description="Rebuilding plugins...")
            new_image_ref = rebuild_and_push_plugins(settings, context, plugins_path)
            progress.update(task, advance=1)

            # Step 2: Helm upgrade
            progress.update(task, description="Upgrading Helm release...")
            upgrade_helm_release(settings, context, new_image_ref=new_image_ref)
            progress.update(task, advance=1)

        else:  # image_tag
            task = progress.add_task("Upgrading deployment...", total=3)

            # Step 1: Helm upgrade
            progress.update(task, description="Upgrading Helm release...")
            upgrade_helm_release(settings, context, new_image_tag=image_tag)
            progress.update(task, advance=1)

        # Step 3: Wait for rollout
        progress.update(task, description="Waiting for rollout...")
        wait_for_rollout(settings, context)
        progress.update(task, advance=1)

        # Step 4: Verify
        progress.update(task, description="Verifying upgrade...")
        verify_upgrade(settings, context)
        progress.update(task, advance=1)

        # Mark complete
        context.upgrade_completed = True

    # Summary
    console.print()
    print_success("Upgrade completed successfully!")
    if context.upgraded_image_reference:
        print_info(f"Image: {context.upgraded_image_reference}")
    if context.portal_route:
        print_info(f"Portal: {context.portal_route}")

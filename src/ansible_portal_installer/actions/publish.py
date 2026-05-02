"""Container image publish action."""

from ..config import Settings
from ..core import PublishError, InstallContext
from ..ui import print_header, print_success, print_info, console, create_progress
from ..utils import (
    login_registry,
    build_image,
    push_image,
    get_container_tool,
)
from .build import build_plugins


def authenticate_registry(settings: Settings) -> None:
    """Authenticate with container registry.

    Args:
        settings: Application settings

    Raises:
        PublishError: If authentication fails
    """
    if not settings.registry_username or not settings.registry_password:
        raise PublishError("Registry credentials not configured")

    try:
        login_registry(
            registry=settings.registry,
            username=settings.registry_username,
            password=settings.registry_password,
        )
        print_success(f"Authenticated with {settings.registry}")
    except Exception as e:
        raise PublishError(f"Registry authentication failed: {e}") from e


def build_container_image(settings: Settings) -> None:
    """Build plugin container image.

    Args:
        settings: Application settings

    Raises:
        PublishError: If build fails
    """
    try:
        build_image(
            context_dir=settings.dynamic_plugins_path,
            containerfile="Containerfile",
            tag=settings.full_image_reference,
        )
        print_success(f"Built image: {settings.full_image_reference}")
    except Exception as e:
        raise PublishError(f"Image build failed: {e}") from e


def push_container_image(settings: Settings) -> None:
    """Push container image to registry.

    Args:
        settings: Application settings

    Raises:
        PublishError: If push fails
    """
    try:
        push_image(tag=settings.full_image_reference)
        print_success(f"Pushed image: {settings.full_image_reference}")
    except Exception as e:
        raise PublishError(f"Image push failed: {e}") from e


def publish_image(settings: Settings, context: InstallContext, build_first: bool = True) -> None:
    """Build and publish plugin container image.

    Args:
        settings: Application settings
        context: Installation context
        build_first: Build plugins first if not already built

    Raises:
        PublishError: If publish fails
    """
    print_header("Publishing Plugin Container Image")

    # Build plugins first if needed
    if build_first and not context.build_completed:
        print_info("Building plugins first...")
        build_plugins(settings, context)
        console.print()

    with create_progress() as progress:
        task = progress.add_task("Publishing image...", total=4)

        # Step 1: Check container tool
        progress.update(task, description="Checking container tool...")
        tool = get_container_tool()
        print_info(f"Using container tool: {tool}")
        progress.advance(task)

        # Step 2: Authenticate
        progress.update(task, description=f"Authenticating with {settings.registry}...")
        authenticate_registry(settings)
        context.registry_authenticated = True
        progress.advance(task)

        # Step 3: Build image
        progress.update(task, description="Building container image...")
        build_container_image(settings)
        progress.advance(task)

        # Step 4: Push image
        progress.update(task, description="Pushing image to registry...")
        push_container_image(settings)
        progress.advance(task)

    context.publish_completed = True
    context.image_reference = settings.full_image_reference

    print_success("Image published successfully")
    console.print(f"\n[bold]Image Reference:[/bold] {settings.full_image_reference}")

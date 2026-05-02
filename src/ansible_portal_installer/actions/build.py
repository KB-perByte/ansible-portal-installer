"""Plugin build action."""

import os
from pathlib import Path

from ..config import Settings
from ..core import BuildError, InstallContext
from ..ui import print_header, print_success, print_info, console, create_progress
from ..utils import run_command, ensure_tool_exists


def setup_symlink(settings: Settings) -> None:
    """Create symlink from ansible-rhdh-plugins to ansible-backstage-plugins.

    Args:
        settings: Application settings

    Raises:
        BuildError: If symlink creation fails
    """
    symlink_path = settings.ansible_rhdh_plugins_path / "ansible-backstage-plugins"

    # Remove existing symlink if it exists
    if symlink_path.is_symlink() or symlink_path.exists():
        symlink_path.unlink(missing_ok=True)

    try:
        symlink_path.symlink_to(settings.ansible_backstage_plugins_path)
        print_success(f"Created symlink: {symlink_path} -> {settings.ansible_backstage_plugins_path}")

        # Verify package.json exists
        package_json = symlink_path / "package.json"
        if not package_json.exists():
            raise BuildError(f"package.json not found at {package_json}")
        print_success("Verified package.json exists")

    except Exception as e:
        raise BuildError(f"Failed to create symlink: {e}") from e


def setup_node_environment(settings: Settings) -> dict[str, str]:
    """Setup Node.js environment.

    Args:
        settings: Application settings

    Returns:
        Environment variables dictionary

    Raises:
        BuildError: If setup fails
    """
    print_info(f"Using Node.js version {settings.node_version}")

    # Check if nvm is available
    env = os.environ.copy()

    # Enable corepack
    try:
        run_command(
            ["corepack", "enable"],
            cwd=settings.ansible_backstage_plugins_path,
            env=env,
        )
        print_success("Corepack enabled")
    except Exception as e:
        raise BuildError(f"Failed to enable corepack: {e}") from e

    # Verify yarn
    try:
        result = run_command(
            ["yarn", "--version"],
            cwd=settings.ansible_backstage_plugins_path,
            capture_output=True,
            env=env,
        )
        print_success(f"Yarn version: {result.stdout.strip()}")
    except Exception as e:
        raise BuildError(f"Failed to verify yarn: {e}") from e

    return env


def run_build_script(settings: Settings, env: dict[str, str]) -> None:
    """Run the build.sh script.

    Args:
        settings: Application settings
        env: Environment variables

    Raises:
        BuildError: If build fails
    """
    build_env = env.copy()
    if settings.build_type != "portal":
        build_env["BUILD_TYPE"] = settings.build_type

    try:
        run_command(
            ["./build.sh"],
            cwd=settings.ansible_rhdh_plugins_path,
            env=build_env,
        )
    except Exception as e:
        raise BuildError(f"Build script failed: {e}") from e


def verify_build_output(settings: Settings, context: InstallContext) -> None:
    """Verify build output and update context.

    Args:
        settings: Application settings
        context: Installation context

    Raises:
        BuildError: If verification fails
    """
    plugins_dir = settings.dynamic_plugins_path

    if not plugins_dir.exists():
        raise BuildError(f"Dynamic plugins directory not found: {plugins_dir}")

    # Find all plugin directories
    plugin_dirs = [d for d in plugins_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]

    if not plugin_dirs:
        raise BuildError("No plugins found in dynamic-plugins directory")

    # Update context
    context.plugins_built = [d.name for d in plugin_dirs]
    context.build_output_dir = plugins_dir

    print_success(f"Built {len(plugin_dirs)} plugins:")
    for plugin in context.plugins_built:
        console.print(f"  • {plugin}")


def build_plugins(settings: Settings, context: InstallContext) -> None:
    """Build dynamic plugins from source.

    Args:
        settings: Application settings
        context: Installation context

    Raises:
        BuildError: If build fails
    """
    print_header("Building Dynamic Plugins")

    with create_progress() as progress:
        task = progress.add_task("Building plugins...", total=5)

        # Step 1: Check prerequisites
        progress.update(task, description="Checking prerequisites...")
        ensure_tool_exists("yarn")
        ensure_tool_exists("git")
        progress.advance(task)

        # Step 2: Setup symlink
        progress.update(task, description="Setting up repository symlink...")
        setup_symlink(settings)
        progress.advance(task)

        # Step 3: Setup Node environment
        progress.update(task, description="Setting up Node.js environment...")
        env = setup_node_environment(settings)
        progress.advance(task)

        # Step 4: Run build script
        progress.update(task, description="Running build script (this may take several minutes)...")
        run_build_script(settings, env)
        progress.advance(task)

        # Step 5: Verify output
        progress.update(task, description="Verifying build output...")
        verify_build_output(settings, context)
        progress.advance(task)

    context.build_completed = True
    print_success("Plugin build completed successfully")

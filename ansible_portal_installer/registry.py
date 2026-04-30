"""OCI registry operations for plugin image management."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import RegistryConfig

console = Console()


class RegistryClient:
    """Client for OCI registry operations."""

    def __init__(self, config: RegistryConfig) -> None:
        """Initialize registry client."""
        self.config = config
        self._check_prerequisites()

    def _check_prerequisites(self) -> None:
        """Check if required tools are installed."""
        required_tools = ["podman"]
        missing = []

        for tool in required_tools:
            if not shutil.which(tool):
                missing.append(tool)

        if missing:
            raise RuntimeError(
                f"Missing required tools: {', '.join(missing)}. "
                "Please install them before continuing."
            )

    def build_plugin_image(
        self,
        plugins_path: Path,
        plugin_tarballs: list[Path],
    ) -> None:
        """Build OCI image from plugin directories.

        RHDH expects OCI images to contain extracted plugin directories with
        package.json, dist/, node_modules/, etc. - not tarballs.

        Args:
            plugins_path: Path to ansible-rhdh-plugins repository
            plugin_tarballs: List of tarball paths (used for verification only)
        """
        console.print(f"[blue]Building OCI image: {self.config.full_image_url_with_tag}[/blue]")

        # Build from the dynamic-plugins directory which contains:
        # - Extracted plugin directories (ansible-*/package.json, dist/, etc.)
        # - Containerfile
        # - LICENSE
        dynamic_plugins_dir = plugins_path / "dynamic-plugins"
        containerfile = dynamic_plugins_dir / "Containerfile"

        if not containerfile.exists():
            console.print(f"[red]Containerfile not found: {containerfile}[/red]")
            raise FileNotFoundError(f"Missing Containerfile at {containerfile}")

        # Verify plugin directories exist (not just tarballs)
        missing_dirs = []
        for tarball in plugin_tarballs:
            # tarball.stem removes .tgz extension
            plugin_dir = dynamic_plugins_dir / tarball.stem
            if not plugin_dir.exists():
                missing_dirs.append(plugin_dir)

        if missing_dirs:
            console.print(f"[red]Missing plugin directories: {', '.join(missing_dirs)}[/red]")
            console.print("[yellow]Tarballs exist but extracted directories are missing[/yellow]")
            raise FileNotFoundError(f"Plugin directories not found in {dynamic_plugins_dir}")

        # Build with podman using the existing Containerfile
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Building OCI image with plugin directories...", total=None)

                subprocess.run(
                    [
                        "podman",
                        "build",
                        "-t",
                        self.config.full_image_url_with_tag,
                        "-f",
                        str(containerfile),
                        str(dynamic_plugins_dir),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )

            console.print(
                f"[green]✓[/green] Built OCI image: {self.config.full_image_url_with_tag}"
            )

        except subprocess.CalledProcessError as e:
            console.print("[red]Failed to build OCI image[/red]")
            console.print(f"[red]{e.stderr}[/red]")
            raise

    def push_image(self) -> None:
        """Push OCI image to registry."""
        console.print(f"[blue]Pushing image to registry: {self.config.url}[/blue]")

        try:
            cmd = [
                "podman",
                "push",
                self.config.full_image_url_with_tag,
            ]

            if self.config.insecure:
                cmd.append("--tls-verify=false")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Pushing image...", total=None)

                subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                )

            console.print(f"[green]✓[/green] Pushed image: {self.config.full_image_url_with_tag}")

        except subprocess.CalledProcessError as e:
            console.print("[red]Failed to push image[/red]")
            console.print(f"[red]{e.stderr}[/red]")
            raise

    def inspect_image(self) -> dict | None:
        """Inspect OCI image in registry."""
        try:
            cmd = ["skopeo", "inspect", f"docker://{self.config.full_image_url_with_tag}"]

            if self.config.insecure:
                cmd.append("--tls-verify=false")

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )

            data = json.loads(result.stdout)
            if isinstance(data, dict):
                return data
            return None

        except subprocess.CalledProcessError:
            return None
        except FileNotFoundError:
            # skopeo not installed
            return None

    def validate_image(self) -> bool:
        """Validate OCI image exists and has correct format."""
        console.print("[blue]Validating OCI image...[/blue]")

        manifest = self.inspect_image()
        if not manifest:
            console.print("[yellow]Could not inspect image (skopeo not available or image not found)[/yellow]")
            return False

        # Check if image has layers
        # Note: With `FROM scratch` + `COPY . .`, all plugins are in 1-2 layers (not 5)
        # This is more efficient than separate layers per plugin
        layers = manifest.get("Layers", [])
        if len(layers) == 0:
            console.print("[red]Error: Image has no layers[/red]")
            return False

        console.print(f"[green]✓[/green] Image validated: {len(layers)} layer(s)")
        return True


class AuthSecretManager:
    """Manage registry authentication secrets for OpenShift."""

    @staticmethod
    def create_auth_json(registry_url: str, username: str, password: str) -> dict:
        """Create auth.json structure for registry authentication."""
        import base64

        auth_string = f"{username}:{password}"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()

        return {"auths": {registry_url: {"auth": auth_b64}}}

    @staticmethod
    def get_oc_registry_auth(output_file: Path) -> None:
        """Get registry auth from oc CLI."""
        try:
            subprocess.run(
                ["oc", "registry", "login", f"--to={output_file}"],
                check=True,
                capture_output=True,
                text=True,
            )
            console.print(f"[green]✓[/green] Generated registry auth: {output_file}")
        except subprocess.CalledProcessError as e:
            console.print("[red]Failed to get registry auth from oc[/red]")
            console.print(f"[red]{e.stderr}[/red]")
            raise

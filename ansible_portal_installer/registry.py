"""OCI registry operations for plugin image management."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

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
        plugin_tarballs: List[Path],
    ) -> None:
        """Build OCI image from plugin tarballs."""
        console.print(f"[blue]Building OCI image: {self.config.full_image_url_with_tag}[/blue]")

        # Create temporary build directory
        with tempfile.TemporaryDirectory() as tmpdir:
            build_dir = Path(tmpdir)

            # Copy plugin tarballs to build directory
            for tarball in plugin_tarballs:
                shutil.copy(tarball, build_dir / tarball.name)
                console.print(f"  • Copied {tarball.name}")

            # Create Containerfile
            containerfile = build_dir / "Containerfile"
            containerfile.write_text(
                "FROM scratch\n" "COPY *.tgz /\n",
                encoding="utf-8",
            )

            # Build with podman
            try:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    progress.add_task("Building OCI image...", total=None)

                    result = subprocess.run(
                        [
                            "podman",
                            "build",
                            "-t",
                            self.config.full_image_url_with_tag,
                            "-f",
                            str(containerfile),
                            str(build_dir),
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )

                console.print(
                    f"[green]✓[/green] Built OCI image: {self.config.full_image_url_with_tag}"
                )

            except subprocess.CalledProcessError as e:
                console.print(f"[red]Failed to build OCI image[/red]")
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
            console.print(f"[red]Failed to push image[/red]")
            console.print(f"[red]{e.stderr}[/red]")
            raise

    def inspect_image(self) -> Optional[dict]:
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

            return json.loads(result.stdout)

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

        # Check if image has layers (should have 5 for the 5 plugins)
        layers = manifest.get("Layers", [])
        if len(layers) != 5:
            console.print(
                f"[yellow]Warning: Expected 5 layers (plugins), found {len(layers)}[/yellow]"
            )

        console.print(f"[green]✓[/green] Image validated: {len(layers)} layers")
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
            console.print(f"[red]Failed to get registry auth from oc[/red]")
            console.print(f"[red]{e.stderr}[/red]")
            raise

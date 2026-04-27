"""Helm operations for deploying and managing the portal."""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


class HelmClient:
    """Client for Helm operations."""

    def __init__(self) -> None:
        """Initialize Helm client."""
        self._check_helm_installed()

    def _check_helm_installed(self) -> None:
        """Check if Helm is installed."""
        if not shutil.which("helm"):
            raise RuntimeError(
                "Helm CLI not found. Please install Helm 3.x before continuing."
            )

    def release_exists(self, release_name: str, namespace: str) -> bool:
        """Check if Helm release exists."""
        try:
            result = subprocess.run(
                ["helm", "list", "-n", namespace, "-q"],
                check=True,
                capture_output=True,
                text=True,
            )
            releases = result.stdout.strip().split("\n")
            return release_name in releases
        except subprocess.CalledProcessError:
            return False

    def dependency_update(self, chart_path: Path) -> None:
        """Update Helm chart dependencies."""
        console.print(f"[blue]Updating Helm dependencies for {chart_path}[/blue]")

        try:
            subprocess.run(
                ["helm", "dependency", "update", str(chart_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            console.print("[green]✓[/green] Helm dependencies updated")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Failed to update Helm dependencies[/red]")
            console.print(f"[red]{e.stderr}[/red]")
            raise

    def install_or_upgrade(
        self,
        release_name: str,
        chart_path: Path,
        namespace: str,
        values: Dict[str, Any],
        timeout: str = "10m",
        wait: bool = True,
    ) -> None:
        """Install or upgrade Helm release."""
        exists = self.release_exists(release_name, namespace)
        action = "upgrade" if exists else "install"

        console.print(
            f"[blue]{'Upgrading' if exists else 'Installing'} Helm release: "
            f"{release_name}[/blue]"
        )

        # Write values to temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as values_file:
            yaml.dump(values, values_file)
            values_path = Path(values_file.name)

        try:
            cmd = [
                "helm",
                action,
                release_name,
                str(chart_path),
                "-f",
                str(values_path),
                "-n",
                namespace,
                "--timeout",
                timeout,
            ]

            if wait:
                cmd.append("--wait")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(f"{'Upgrading' if exists else 'Installing'} chart...", total=None)

                result = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                )

            console.print(
                f"[green]✓[/green] Helm release {action}d successfully: {release_name}"
            )

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Helm {action} failed[/red]")
            console.print(f"[red]{e.stderr}[/red]")
            raise
        finally:
            # Clean up temporary values file
            values_path.unlink(missing_ok=True)

    def uninstall(self, release_name: str, namespace: str) -> None:
        """Uninstall Helm release."""
        if not self.release_exists(release_name, namespace):
            console.print(f"[yellow]Release {release_name} not found in {namespace}[/yellow]")
            return

        console.print(f"[blue]Uninstalling Helm release: {release_name}[/blue]")

        try:
            subprocess.run(
                ["helm", "uninstall", release_name, "-n", namespace],
                check=True,
                capture_output=True,
                text=True,
            )
            console.print(f"[green]✓[/green] Uninstalled release: {release_name}")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Failed to uninstall release[/red]")
            console.print(f"[red]{e.stderr}[/red]")
            raise

    def get_values(self, release_name: str, namespace: str) -> Optional[Dict[str, Any]]:
        """Get values for a Helm release."""
        try:
            result = subprocess.run(
                ["helm", "get", "values", release_name, "-n", namespace, "-o", "yaml"],
                check=True,
                capture_output=True,
                text=True,
            )
            return yaml.safe_load(result.stdout)
        except subprocess.CalledProcessError:
            return None

    def get_status(self, release_name: str, namespace: str) -> Optional[str]:
        """Get status of a Helm release."""
        try:
            result = subprocess.run(
                ["helm", "status", release_name, "-n", namespace],
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout
        except subprocess.CalledProcessError:
            return None


def generate_portal_values(
    registry_url: str,
    image_tag: str,
    cluster_router_base: str,
    release_name: str,
    admin_password_hash: str,
    check_ssl: bool = False,
) -> Dict[str, Any]:
    """Generate Helm values for portal deployment."""
    return {
        "redhat-developer-hub": {
            "global": {
                "clusterRouterBase": cluster_router_base,
                "pluginMode": "oci",
                "ociPluginImage": registry_url,
                "imageTagInfo": image_tag,
            },
            "upstream": {
                "backstage": {
                    "extraEnvVars": [
                        {"name": "ENABLE_CORE_ROOTCONFIG_OVERRIDE", "value": "true"},
                        {"name": "DEPLOYMENT_NAME", "value": release_name},
                        {"name": "PORTAL_ADMIN_PASSWORD_HASH", "value": admin_password_hash},
                        {
                            "name": "POSTGRESQL_ADMIN_PASSWORD",
                            "valueFrom": {
                                "secretKeyRef": {
                                    "name": f"{release_name}-postgresql",
                                    "key": "postgres-password",
                                }
                            },
                        },
                    ],
                    "appConfig": {
                        "ansible": {"rhaap": {"checkSSL": check_ssl}},
                        "auth": {"providers": {"rhaap": {"production": {"checkSSL": check_ssl}}}},
                    },
                }
            },
        }
    }

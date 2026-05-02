"""Helm-based installer for OpenShift."""

from ..actions import deploy_helm, verify_deployment
from ..config import Settings
from ..core import InstallContext, DeployError
from ..ui import print_header, print_success, console
from ..utils import helm_uninstall, helm_status, oc_get_pods, oc_get_route
from .base import BaseInstaller


class HelmInstaller(BaseInstaller):
    """Installer for Helm-based deployments on OpenShift."""

    def install(self) -> None:
        """Install Ansible Portal using Helm."""
        deploy_helm(self.settings, self.context, publish_first=True)

    def verify(self) -> bool:
        """Verify the Helm installation.

        Returns:
            True if verification passes, False otherwise
        """
        results = verify_deployment(self.settings)
        self.context.verification_passed = all(results.values())
        return self.context.verification_passed

    def uninstall(self) -> None:
        """Uninstall the Helm release."""
        print_header(f"Uninstalling Helm Release: {self.settings.helm_release_name}")

        try:
            helm_uninstall(
                release_name=self.settings.helm_release_name,
                namespace=self.settings.openshift_namespace,
            )
            print_success(f"Uninstalled release: {self.settings.helm_release_name}")
        except Exception as e:
            raise DeployError(f"Failed to uninstall: {e}") from e

    def get_status(self) -> dict[str, any]:
        """Get Helm installation status.

        Returns:
            Dictionary with status information
        """
        namespace = self.settings.openshift_namespace
        release_name = self.settings.helm_release_name

        status_dict = {
            "release_name": release_name,
            "namespace": namespace,
            "helm_status": None,
            "pods": [],
            "route": None,
        }

        # Get Helm status
        try:
            status_output = helm_status(release_name, namespace)
            status_dict["helm_status"] = "deployed" if "STATUS: deployed" in status_output else "unknown"
        except Exception:
            status_dict["helm_status"] = "not found"

        # Get pods
        try:
            pods = oc_get_pods(namespace)
            status_dict["pods"] = pods
        except Exception:
            pass

        # Get route
        try:
            route = oc_get_route(release_name, namespace)
            status_dict["route"] = route
        except Exception:
            pass

        return status_dict

    def display_status(self) -> None:
        """Display installation status in a formatted way."""
        print_header(f"Installation Status: {self.settings.helm_release_name}")

        status = self.get_status()

        console.print(f"[bold]Release:[/bold] {status['release_name']}")
        console.print(f"[bold]Namespace:[/bold] {status['namespace']}")
        console.print(f"[bold]Helm Status:[/bold] {status['helm_status']}")

        if status["route"]:
            console.print(f"[bold]Portal URL:[/bold] {status['route']}")

        if status["pods"]:
            console.print(f"\n[bold]Pods ({len(status['pods'])}):[/bold]")
            for pod in status["pods"]:
                status_icon = "✓" if pod["status"] == "Running" else "⋯"
                console.print(f"  [{status_icon}] {pod['name']}: {pod['status']}")

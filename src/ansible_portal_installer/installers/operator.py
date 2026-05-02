"""Operator-based installer (future implementation)."""

from ..config import Settings
from ..core import InstallContext, InstallerError
from .base import BaseInstaller


class OperatorInstaller(BaseInstaller):
    """Installer for Operator-based deployments (placeholder for future implementation)."""

    def install(self) -> None:
        """Install Ansible Portal using the Operator."""
        raise InstallerError("Operator installer is not yet implemented")

    def verify(self) -> bool:
        """Verify the Operator installation."""
        raise InstallerError("Operator installer is not yet implemented")

    def uninstall(self) -> None:
        """Uninstall the Operator deployment."""
        raise InstallerError("Operator installer is not yet implemented")

    def get_status(self) -> dict[str, any]:
        """Get Operator installation status."""
        raise InstallerError("Operator installer is not yet implemented")

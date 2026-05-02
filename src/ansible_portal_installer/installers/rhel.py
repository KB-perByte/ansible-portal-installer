"""RHEL-based installer (future implementation)."""

from ..config import Settings
from ..core import InstallContext, InstallerError
from .base import BaseInstaller


class RHELInstaller(BaseInstaller):
    """Installer for RHEL-based deployments (placeholder for future implementation)."""

    def install(self) -> None:
        """Install Ansible Portal on RHEL."""
        raise InstallerError("RHEL installer is not yet implemented")

    def verify(self) -> bool:
        """Verify the RHEL installation."""
        raise InstallerError("RHEL installer is not yet implemented")

    def uninstall(self) -> None:
        """Uninstall from RHEL."""
        raise InstallerError("RHEL installer is not yet implemented")

    def get_status(self) -> dict[str, any]:
        """Get RHEL installation status."""
        raise InstallerError("RHEL installer is not yet implemented")

"""Base installer class for all installation types."""

from abc import ABC, abstractmethod

from ..config import Settings
from ..core import InstallContext


class BaseInstaller(ABC):
    """Base class for all installers."""

    def __init__(self, settings: Settings, context: InstallContext) -> None:
        """Initialize installer.

        Args:
            settings: Application settings
            context: Installation context
        """
        self.settings = settings
        self.context = context

    @abstractmethod
    def install(self) -> None:
        """Execute the installation.

        Raises:
            InstallerError: If installation fails
        """
        pass

    @abstractmethod
    def verify(self) -> bool:
        """Verify the installation.

        Returns:
            True if verification passes, False otherwise
        """
        pass

    @abstractmethod
    def uninstall(self) -> None:
        """Remove the installation.

        Raises:
            InstallerError: If uninstall fails
        """
        pass

    @abstractmethod
    def get_status(self) -> dict[str, any]:
        """Get installation status.

        Returns:
            Dictionary with status information
        """
        pass

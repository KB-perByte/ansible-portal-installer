"""Custom exceptions for the installer."""


class InstallerError(Exception):
    """Base exception for all installer errors."""

    pass


class BuildError(InstallerError):
    """Raised when plugin build fails."""

    pass


class PublishError(InstallerError):
    """Raised when container image publish fails."""

    pass


class DeployError(InstallerError):
    """Raised when deployment fails."""

    pass


class ConfigurationError(InstallerError):
    """Raised when configuration is invalid or missing."""

    pass


class ValidationError(InstallerError):
    """Raised when validation fails."""

    pass


class ToolNotFoundError(InstallerError):
    """Raised when required tool is not found."""

    pass


class GitError(InstallerError):
    """Raised when git operation fails."""

    pass


class ContainerError(InstallerError):
    """Raised when container operation fails."""

    pass


class OpenShiftError(InstallerError):
    """Raised when OpenShift operation fails."""

    pass


class HelmError(InstallerError):
    """Raised when Helm operation fails."""

    pass

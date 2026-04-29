"""Abstract base classes for deployment backends."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ..config import DeploymentConfig


class DeploymentBackend(ABC):
    """Abstract base for deployment backends.

    This interface allows different deployment strategies:
    - Helm: Deploy to Kubernetes/OpenShift using Helm charts
    - Operator: Deploy using OpenShift Operators
    - RHEL: Install as RHEL packages on traditional servers
    """

    @abstractmethod
    def deploy(
        self,
        config: DeploymentConfig,
        skip_build: bool = False,
        timeout: str = "10m",
    ) -> dict[str, Any]:
        """Deploy the portal.

        Args:
            config: Deployment configuration
            skip_build: Skip plugin build step
            timeout: Deployment timeout

        Returns:
            Deployment details (URL, credentials, etc.)
        """
        pass

    @abstractmethod
    def upgrade(
        self,
        namespace: str,
        release_name: str,
        chart_path: Path | None = None,
        values: dict[str, Any] | None = None,
        skip_build: bool = False,
    ) -> None:
        """Upgrade existing deployment.

        Args:
            namespace: Target namespace/location
            release_name: Deployment identifier
            chart_path: Path to deployment configuration
            values: Configuration overrides
            skip_build: Skip rebuild step
        """
        pass

    @abstractmethod
    def teardown(
        self,
        namespace: str,
        release_name: str,
        clean_data: bool = False,
    ) -> None:
        """Remove deployment.

        Args:
            namespace: Target namespace/location
            release_name: Deployment identifier
            clean_data: Also remove persistent data
        """
        pass

    @abstractmethod
    def get_status(
        self,
        namespace: str,
        release_name: str,
    ) -> dict[str, Any] | None:
        """Get deployment status.

        Args:
            namespace: Target namespace/location
            release_name: Deployment identifier

        Returns:
            Status information or None if not found
        """
        pass

    @abstractmethod
    def get_values(
        self,
        namespace: str,
        release_name: str,
    ) -> dict[str, Any] | None:
        """Get deployment configuration values.

        Args:
            namespace: Target namespace/location
            release_name: Deployment identifier

        Returns:
            Configuration values or None if not found
        """
        pass

    @abstractmethod
    def validate_deployment(
        self,
        namespace: str,
        release_name: str | None = None,
        verbose: bool = False,
        timeout: int = 300,
    ) -> bool:
        """Validate deployment health.

        Args:
            namespace: Target namespace/location
            release_name: Deployment identifier (auto-detect if None)
            verbose: Show detailed output
            timeout: Health check timeout in seconds

        Returns:
            True if all checks pass, False otherwise
        """
        pass

    @abstractmethod
    def collect_logs(
        self,
        namespace: str,
        release_name: str | None,
        output_dir: Path,
        tail_lines: int = 1000,
    ) -> None:
        """Collect diagnostic logs.

        Args:
            namespace: Target namespace/location
            release_name: Deployment identifier (auto-detect if None)
            output_dir: Where to save logs
            tail_lines: Number of log lines to collect
        """
        pass


class BuildBackend(ABC):
    """Abstract base for plugin build backends.

    Different environments may require different build strategies:
    - OCI: Build OCI images for Kubernetes/OpenShift
    - NPM: Build and publish to npm registry
    - RPM: Package as RPM for RHEL installations
    """

    @abstractmethod
    def build_plugins(
        self,
        plugins_path: Path,
        output_path: Path,
        tag: str = "dev",
    ) -> None:
        """Build plugins.

        Args:
            plugins_path: Path to plugin source
            output_path: Where to put built artifacts
            tag: Build version tag
        """
        pass

    @abstractmethod
    def push_artifacts(
        self,
        source_path: Path,
        destination: str,
        tag: str = "dev",
    ) -> str:
        """Push built artifacts to registry/repository.

        Args:
            source_path: Path to built artifacts
            destination: Registry/repository URL
            tag: Artifact version tag

        Returns:
            Full URL/path to pushed artifacts
        """
        pass

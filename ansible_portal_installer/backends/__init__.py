"""Deployment backends for ansible-portal-installer.

This module provides a pluggable backend system for different deployment targets:
- Helm: Deploy to Kubernetes/OpenShift using Helm charts
- Operator: Deploy using OpenShift Operators (future)
- RHEL: Install as RHEL packages on traditional servers (future)
"""

from enum import Enum
from typing import TYPE_CHECKING

from .base import BuildBackend, DeploymentBackend

if TYPE_CHECKING:
    from .helm import HelmDeployer


class BackendType(str, Enum):
    """Supported deployment backend types."""

    HELM = "helm"
    OPERATOR = "operator"  # Future
    RHEL = "rhel"  # Future


class BackendFactory:
    """Factory for creating deployment backend instances."""

    @staticmethod
    def create(backend_type: str | BackendType) -> DeploymentBackend:
        """Create a deployment backend instance.

        Args:
            backend_type: Type of backend to create

        Returns:
            DeploymentBackend instance

        Raises:
            ValueError: If backend type is unknown or not implemented
        """
        if isinstance(backend_type, str):
            backend_type = BackendType(backend_type)

        if backend_type == BackendType.HELM:
            from .helm import HelmDeployer

            return HelmDeployer()

        elif backend_type == BackendType.OPERATOR:
            raise NotImplementedError(
                "Operator backend is not yet implemented. "
                "See ansible-portal-installer roadmap for planned features."
            )

        elif backend_type == BackendType.RHEL:
            raise NotImplementedError(
                "RHEL package backend is not yet implemented. "
                "See ansible-portal-installer roadmap for planned features."
            )

        else:
            raise ValueError(
                f"Unknown backend type: {backend_type}. "
                f"Supported: {', '.join(b.value for b in BackendType)}"
            )

    @staticmethod
    def list_backends() -> list[str]:
        """List all available backend types.

        Returns:
            List of backend type names
        """
        return [b.value for b in BackendType]

    @staticmethod
    def list_implemented_backends() -> list[str]:
        """List only implemented backend types.

        Returns:
            List of implemented backend type names
        """
        return [BackendType.HELM.value]


__all__ = [
    "BackendType",
    "BackendFactory",
    "DeploymentBackend",
    "BuildBackend",
]

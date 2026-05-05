"""Configuration validation."""

from pathlib import Path
from typing import Optional

from ..core.exceptions import ConfigurationError, ValidationError
from .settings import Settings


def validate_build_config(settings: Settings) -> None:
    """Validate build configuration.

    Args:
        settings: Application settings

    Raises:
        ConfigurationError: If configuration is invalid
    """
    errors = []

    # Check paths exist
    if not settings.ansible_rhdh_plugins_path.exists():
        errors.append(
            f"ansible-rhdh-plugins path does not exist: {settings.ansible_rhdh_plugins_path}"
        )

    if not settings.ansible_backstage_plugins_path.exists():
        errors.append(
            f"ansible-backstage-plugins path does not exist: {settings.ansible_backstage_plugins_path}"
        )

    # Check build script exists
    if not settings.build_script_path.exists():
        errors.append(f"Build script not found: {settings.build_script_path}")

    if errors:
        raise ConfigurationError("\n".join(errors))


def validate_publish_config(settings: Settings) -> None:
    """Validate publish/registry configuration.

    Args:
        settings: Application settings

    Raises:
        ConfigurationError: If configuration is invalid
    """
    errors = []

    if not settings.registry_username:
        errors.append("REGISTRY_USERNAME is required for publishing")

    if not settings.registry_password:
        errors.append("REGISTRY_PASSWORD is required for publishing")

    # Check dynamic plugins directory exists
    if not settings.dynamic_plugins_path.exists():
        errors.append(
            f"Dynamic plugins directory not found: {settings.dynamic_plugins_path}. "
            "Run 'build' command first."
        )

    if errors:
        raise ConfigurationError("\n".join(errors))


def validate_deploy_config(settings: Settings) -> None:
    """Validate deployment configuration.

    Args:
        settings: Application settings

    Raises:
        ConfigurationError: If configuration is invalid
    """
    errors = []

    # OpenShift configuration
    if not settings.openshift_server:
        errors.append("OPENSHIFT_SERVER is required for deployment")

    if not settings.openshift_token:
        errors.append("OPENSHIFT_TOKEN is required for deployment")

    # AAP configuration
    if not settings.aap_host_url:
        errors.append("AAP_HOST_URL is required for deployment")

    if not settings.aap_oauth_client_id:
        errors.append("AAP_OAUTH_CLIENT_ID is required for deployment")

    if not settings.aap_oauth_client_secret:
        errors.append("AAP_OAUTH_CLIENT_SECRET is required for deployment")

    if not settings.aap_token:
        errors.append("AAP_TOKEN is required for deployment")

    # GitHub configuration
    if not settings.github_token:
        errors.append("GITHUB_TOKEN is required for deployment")

    if not settings.github_client_id:
        errors.append("GITHUB_CLIENT_ID is required for deployment")

    if not settings.github_client_secret:
        errors.append("GITHUB_CLIENT_SECRET is required for deployment")

    # Cluster configuration
    if not settings.cluster_router_base:
        errors.append("CLUSTER_ROUTER_BASE is required for deployment")

    # Helm chart path
    if not settings.helm_chart_path.exists():
        errors.append(f"Helm chart path does not exist: {settings.helm_chart_path}")

    if errors:
        raise ConfigurationError("\n".join(errors))


def validate_all(settings: Settings, operation: str) -> None:
    """Validate configuration for a specific operation.

    Args:
        settings: Application settings
        operation: Operation to validate for (build, publish, deploy, helm-deploy, helm-upgrade)

    Raises:
        ConfigurationError: If configuration is invalid
    """
    if operation == "build":
        validate_build_config(settings)
    elif operation == "publish":
        validate_build_config(settings)
        validate_publish_config(settings)
    elif operation in ("deploy", "helm-deploy"):
        validate_deploy_config(settings)
    elif operation == "helm-upgrade":
        validate_deploy_config(settings)

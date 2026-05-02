"""Application settings using Pydantic."""

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Build Configuration
    ansible_rhdh_plugins_path: Path = Field(
        default=Path.home() / "Work/ansible-portal/ansible-rhdh-plugins",
        description="Path to ansible-rhdh-plugins repository",
    )
    ansible_backstage_plugins_path: Path = Field(
        default=Path.home() / "Work/ansible-portal/ansible-backstage-plugins",
        description="Path to ansible-backstage-plugins repository",
    )
    build_type: str = Field(
        default="portal",
        description="Build type: portal, platform, or all",
    )
    node_version: str = Field(
        default="20.20.2",
        description="Node.js version to use",
    )

    # Container Registry Configuration
    registry: str = Field(
        default="quay.io",
        description="Container registry",
    )
    registry_username: Optional[str] = Field(
        default=None,
        description="Registry username/organization",
    )
    registry_password: Optional[str] = Field(
        default=None,
        description="Registry password/token",
    )
    plugins_image_name: str = Field(
        default="ansible-portal-plugins",
        description="Plugin image name",
    )
    plugins_image_tag: str = Field(
        default=f"dev-{datetime.now().strftime('%Y%m%d')}",
        description="Plugin image tag",
    )

    # OpenShift/Kubernetes Configuration
    openshift_server: Optional[str] = Field(
        default=None,
        description="OpenShift server URL",
    )
    openshift_token: Optional[str] = Field(
        default=None,
        description="OpenShift authentication token",
    )
    openshift_namespace: str = Field(
        default="ansible-portal",
        description="Target namespace/project",
    )
    openshift_insecure_skip_tls_verify: bool = Field(
        default=False,
        description="Skip TLS verification",
    )

    # AAP Configuration
    aap_host_url: Optional[str] = Field(
        default=None,
        description="AAP host URL",
    )
    aap_oauth_client_id: Optional[str] = Field(
        default=None,
        description="AAP OAuth client ID",
    )
    aap_oauth_client_secret: Optional[str] = Field(
        default=None,
        description="AAP OAuth client secret",
    )
    aap_token: Optional[str] = Field(
        default=None,
        description="AAP API token",
    )
    aap_check_ssl: bool = Field(
        default=True,
        description="Check SSL certificates for AAP",
    )

    # GitHub Configuration
    github_token: Optional[str] = Field(
        default=None,
        description="GitHub personal access token",
    )
    github_client_id: Optional[str] = Field(
        default=None,
        description="GitHub OAuth client ID",
    )
    github_client_secret: Optional[str] = Field(
        default=None,
        description="GitHub OAuth client secret",
    )
    github_org: str = Field(
        default="ansible-collections",
        description="GitHub organization for content discovery",
    )

    # Helm Chart Configuration
    helm_chart_path: Path = Field(
        default=Path.home() / "Work/ansible-portal/ansible-portal-chart",
        description="Path to ansible-portal-chart repository",
    )
    helm_release_name: str = Field(
        default="my-portal",
        description="Helm release name",
    )
    cluster_router_base: Optional[str] = Field(
        default=None,
        description="OpenShift cluster router base",
    )
    plugin_mode: str = Field(
        default="oci",
        description="Plugin mode: oci or local",
    )
    ansible_git_contents_enabled: bool = Field(
        default=True,
        description="Enable Ansible Git Contents discovery",
    )

    # Dev Spaces Configuration (Optional)
    dev_spaces_base_url: Optional[str] = Field(
        default=None,
        description="Dev Spaces base URL",
    )
    creator_service_base_url: str = Field(
        default="localhost",
        description="Creator service base URL",
    )
    creator_service_port: str = Field(
        default="5000",
        description="Creator service port",
    )

    # Installer Behavior
    skip_confirmations: bool = Field(
        default=False,
        description="Skip confirmation prompts",
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose output",
    )
    dry_run: bool = Field(
        default=False,
        description="Dry run mode - show what would be done",
    )

    @field_validator("ansible_rhdh_plugins_path", "ansible_backstage_plugins_path", "helm_chart_path")
    @classmethod
    def expand_path(cls, v: Path) -> Path:
        """Expand user paths."""
        return v.expanduser().resolve()

    @field_validator("build_type")
    @classmethod
    def validate_build_type(cls, v: str) -> str:
        """Validate build type."""
        allowed = {"portal", "platform", "all"}
        if v not in allowed:
            raise ValueError(f"build_type must be one of {allowed}")
        return v

    @field_validator("plugin_mode")
    @classmethod
    def validate_plugin_mode(cls, v: str) -> str:
        """Validate plugin mode."""
        allowed = {"oci", "local"}
        if v not in allowed:
            raise ValueError(f"plugin_mode must be one of {allowed}")
        return v

    @property
    def full_image_reference(self) -> str:
        """Get the full container image reference."""
        image = f"{self.registry}/{self.registry_username}/{self.plugins_image_name}:{self.plugins_image_tag}"
        return image

    @property
    def dynamic_plugins_path(self) -> Path:
        """Get the dynamic plugins directory path."""
        return self.ansible_rhdh_plugins_path / "dynamic-plugins"

    @property
    def build_script_path(self) -> Path:
        """Get the build script path."""
        return self.ansible_rhdh_plugins_path / "build.sh"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

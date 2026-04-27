"""Configuration models and validation for Ansible Portal deployment."""

import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RegistryConfig(BaseModel):
    """Container registry configuration."""

    url: str = Field(..., description="Registry URL (host:port or host)")
    namespace: str = Field(..., description="Registry namespace/project")
    image_name: str = Field(default="automation-portal", description="Image name")
    tag: str = Field(default="dev", description="Image tag")
    insecure: bool = Field(default=False, description="Skip TLS verification")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate registry URL format."""
        # Remove protocol if present
        v = v.replace("https://", "").replace("http://", "")
        # Basic validation - should be hostname or hostname:port
        if not re.match(r"^[a-zA-Z0-9.-]+(:[0-9]+)?(/[a-zA-Z0-9._-]+)*$", v):
            raise ValueError(f"Invalid registry URL format: {v}")
        return v

    @field_validator("tag")
    @classmethod
    def validate_tag(cls, v: str) -> str:
        """Validate image tag format."""
        if not re.match(r"^[a-zA-Z0-9._-]{1,128}$", v):
            raise ValueError(
                f"Invalid tag format: {v}. Must be alphanumeric, dash, underscore, "
                "or dot (max 128 chars)"
            )
        return v

    @property
    def full_image_url(self) -> str:
        """Get full OCI image URL without tag."""
        return f"{self.url}/{self.namespace}/{self.image_name}"

    @property
    def full_image_url_with_tag(self) -> str:
        """Get full OCI image URL with tag."""
        return f"{self.full_image_url}:{self.tag}"


class AAPConfig(BaseModel):
    """Ansible Automation Platform configuration."""

    host_url: str = Field(..., description="AAP controller URL")
    token: str = Field(..., description="AAP API token")
    oauth_client_id: str = Field(..., description="AAP OAuth client ID")
    oauth_client_secret: str = Field(..., description="AAP OAuth client secret")
    check_ssl: bool = Field(default=False, description="Verify SSL certificates")

    @field_validator("host_url")
    @classmethod
    def validate_host_url(cls, v: str) -> str:
        """Validate AAP host URL."""
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"AAP host URL must start with http:// or https://: {v}")
        return v.rstrip("/")


class SCMConfig(BaseModel):
    """Source Control Management (GitHub/GitLab) configuration."""

    github_token: Optional[str] = Field(default=None, description="GitHub PAT")
    github_client_id: Optional[str] = Field(default=None, description="GitHub OAuth client ID")
    github_client_secret: Optional[str] = Field(
        default=None, description="GitHub OAuth client secret"
    )
    gitlab_token: Optional[str] = Field(default=None, description="GitLab PAT")
    gitlab_client_id: Optional[str] = Field(default=None, description="GitLab OAuth client ID")
    gitlab_client_secret: Optional[str] = Field(
        default=None, description="GitLab OAuth client secret"
    )


class DeploymentConfig(BaseModel):
    """Portal deployment configuration."""

    namespace: str = Field(..., description="OpenShift namespace")
    release_name: str = Field(default="rhaap-portal-dev", description="Helm release name")
    chart_path: Path = Field(
        default=Path("../ansible-portal-chart"), description="Path to Helm chart"
    )
    plugins_path: Path = Field(
        default=Path.cwd(), description="Path to ansible-rhdh-plugins repo"
    )
    cluster_router_base: Optional[str] = Field(
        default=None, description="OpenShift cluster router base domain"
    )
    admin_password: Optional[str] = Field(
        default=None, description="Portal admin password (generated if not provided)"
    )
    skip_plugin_build: bool = Field(default=False, description="Skip plugin build step")

    @field_validator("namespace")
    @classmethod
    def validate_namespace(cls, v: str) -> str:
        """Validate Kubernetes namespace format."""
        if not re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", v):
            raise ValueError(
                f"Invalid namespace: {v}. Must be lowercase alphanumeric with hyphens"
            )
        if len(v) > 63:
            raise ValueError(f"Namespace too long: {v}. Max 63 characters")
        return v

    @field_validator("chart_path", "plugins_path")
    @classmethod
    def validate_path_exists(cls, v: Path) -> Path:
        """Validate path exists."""
        # Don't validate during model construction, will validate at runtime
        return v

    @property
    def auth_secret_name(self) -> str:
        """Get the auth secret name for dynamic plugins."""
        return f"{self.release_name}-dynamic-plugins-registry-auth"


class PortalInstallerSettings(BaseSettings):
    """Global settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenShift cluster
    ocp_cluster_url: Optional[str] = Field(default=None, alias="OCP_CLUSTER_URL")
    ocp_namespace: Optional[str] = Field(default=None, alias="OCP_NAMESPACE")

    # Deployment
    release_name: str = Field(default="rhaap-portal-dev", alias="RELEASE_NAME")
    chart_path: str = Field(default="../ansible-portal-chart", alias="CHART_PATH")
    plugins_path: str = Field(default=".", alias="PLUGINS_PATH")

    # AAP
    aap_host_url: Optional[str] = Field(default=None, alias="AAP_HOST_URL")
    aap_token: Optional[str] = Field(default=None, alias="AAP_TOKEN")
    oauth_client_id: Optional[str] = Field(default=None, alias="OAUTH_CLIENT_ID")
    oauth_client_secret: Optional[str] = Field(default=None, alias="OAUTH_CLIENT_SECRET")

    # SCM
    github_token: Optional[str] = Field(default=None, alias="GITHUB_TOKEN")
    github_client_id: Optional[str] = Field(default=None, alias="GITHUB_CLIENT_ID")
    github_client_secret: Optional[str] = Field(default=None, alias="GITHUB_CLIENT_SECRET")
    gitlab_token: Optional[str] = Field(default=None, alias="GITLAB_TOKEN")
    gitlab_client_id: Optional[str] = Field(default=None, alias="GITLAB_CLIENT_ID")
    gitlab_client_secret: Optional[str] = Field(default=None, alias="GITLAB_CLIENT_SECRET")

    # Registry
    plugin_registry: Optional[str] = Field(default=None, alias="PLUGIN_REGISTRY")
    plugin_image_tag: str = Field(default="dev", alias="PLUGIN_IMAGE_TAG")

    # Portal admin
    portal_admin_password: Optional[str] = Field(default=None, alias="PORTAL_ADMIN_PASSWORD")

    # Flags
    skip_plugin_build: bool = Field(default=False, alias="SKIP_PLUGIN_BUILD")
    verbose: bool = Field(default=False, alias="VERBOSE")


class HealthCheckConfig(BaseModel):
    """Health check configuration."""

    namespace: str
    release_name: Optional[str] = None
    verbose: bool = False
    timeout_seconds: int = Field(default=300, description="Health check timeout")


class LogCollectionConfig(BaseModel):
    """Log collection configuration."""

    namespace: str
    release_name: Optional[str] = None
    output_dir: Optional[Path] = None
    tail_lines: int = Field(default=1000, description="Number of log lines to collect")

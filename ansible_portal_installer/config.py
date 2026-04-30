"""Configuration models and validation for Ansible Portal deployment."""

import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Forward reference to avoid circular import
def _get_default_backend() -> str:
    """Get default backend type."""
    return "helm"


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

    @property
    def base_url(self) -> str:
        """Alias for host_url for backward compatibility."""
        return self.host_url


class SCMConfig(BaseModel):
    """Source Control Management (GitHub/GitLab) configuration."""

    github_token: str | None = Field(default=None, description="GitHub PAT")
    github_client_id: str | None = Field(default=None, description="GitHub OAuth client ID")
    github_client_secret: str | None = Field(
        default=None, description="GitHub OAuth client secret"
    )
    gitlab_token: str | None = Field(default=None, description="GitLab PAT")
    gitlab_client_id: str | None = Field(default=None, description="GitLab OAuth client ID")
    gitlab_client_secret: str | None = Field(
        default=None, description="GitLab OAuth client secret"
    )


class DeploymentConfig(BaseModel):
    """Portal deployment configuration."""

    # Deployment target
    namespace: str = Field(..., description="Target namespace/location")
    release_name: str = Field(default="rhaap-portal-dev", description="Deployment identifier")
    backend: str = Field(
        default_factory=_get_default_backend,
        description="Deployment backend (helm, operator, rhel)",
    )

    # Paths
    chart_path: Path = Field(
        default=Path("../ansible-portal-chart"), description="Path to deployment configuration"
    )
    plugins_path: Path = Field(
        default=Path.cwd(), description="Path to ansible-rhdh-plugins repo (downstream)"
    )
    upstream_plugins_path: Path | None = Field(
        default=None, description="Path to ansible-backstage-plugins repo (upstream)"
    )

    # Configuration
    registry: Optional["RegistryConfig"] = Field(default=None, description="Registry configuration")
    registry_auth_file: Path | None = Field(default=None, description="Path to registry auth.json file")
    aap: Optional["AAPConfig"] = Field(default=None, description="AAP configuration")
    scm: Optional["SCMConfig"] = Field(default=None, description="SCM configuration")
    image_tag: str = Field(default="dev", description="Plugin image tag")
    check_ssl: bool = Field(default=False, description="Verify SSL certificates")

    # Portal settings
    cluster_router_base: str | None = Field(
        default=None, description="OpenShift cluster router base domain (auto-detect for K8s)"
    )
    admin_password: str | None = Field(
        default=None, description="Portal admin password (generated if not provided)"
    )
    skip_plugin_build: bool = Field(default=False, description="Skip plugin build step")
    wait_for_rollout: bool = Field(
        default=True, description="After Helm, wait for Kubernetes Deployment rollout"
    )
    rollout_timeout: str = Field(
        default="40m",
        description="Timeout for kubectl rollout status (e.g. 25m, 40m, 1h); RHDH+OCI is often slow",
    )
    insecure_registry: bool = Field(
        default=True,
        description="Configure insecure registry support for OpenShift internal registry (dev mode)",
    )

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
    ocp_cluster_url: str | None = Field(default=None, alias="OCP_CLUSTER_URL")
    ocp_namespace: str | None = Field(default=None, alias="OCP_NAMESPACE")

    # Deployment
    backend: str = Field(default="helm", alias="DEPLOYMENT_BACKEND")
    release_name: str = Field(default="rhaap-portal-dev", alias="RELEASE_NAME")
    chart_path: str = Field(default="../ansible-portal-chart", alias="CHART_PATH")
    plugins_path: str = Field(default=".", alias="PLUGINS_PATH")
    upstream_plugins_path: str | None = Field(default=None, alias="UPSTREAM_PLUGINS_PATH")

    # AAP
    aap_host_url: str | None = Field(default=None, alias="AAP_HOST_URL")
    aap_token: str | None = Field(default=None, alias="AAP_TOKEN")
    oauth_client_id: str | None = Field(default=None, alias="OAUTH_CLIENT_ID")
    oauth_client_secret: str | None = Field(default=None, alias="OAUTH_CLIENT_SECRET")

    # SCM
    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")
    github_client_id: str | None = Field(default=None, alias="GITHUB_CLIENT_ID")
    github_client_secret: str | None = Field(default=None, alias="GITHUB_CLIENT_SECRET")
    gitlab_token: str | None = Field(default=None, alias="GITLAB_TOKEN")
    gitlab_client_id: str | None = Field(default=None, alias="GITLAB_CLIENT_ID")
    gitlab_client_secret: str | None = Field(default=None, alias="GITLAB_CLIENT_SECRET")

    # Registry
    plugin_registry: str | None = Field(default=None, alias="PLUGIN_REGISTRY")
    plugin_image_tag: str = Field(default="dev", alias="PLUGIN_IMAGE_TAG")
    registry_auth_file: str | None = Field(default=None, alias="REGISTRY_AUTH_FILE")

    # Portal admin
    portal_admin_password: str | None = Field(default=None, alias="PORTAL_ADMIN_PASSWORD")

    # Flags
    skip_plugin_build: bool = Field(default=False, alias="SKIP_PLUGIN_BUILD")
    verbose: bool = Field(default=False, alias="VERBOSE")


class HealthCheckConfig(BaseModel):
    """Health check configuration."""

    namespace: str
    release_name: str | None = None
    verbose: bool = False
    timeout_seconds: int = Field(default=300, description="Health check timeout")


class LogCollectionConfig(BaseModel):
    """Log collection configuration."""

    namespace: str
    release_name: str | None = None
    output_dir: Path | None = None
    tail_lines: int = Field(default=1000, description="Number of log lines to collect")

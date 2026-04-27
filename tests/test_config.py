"""Tests for configuration models."""

import pytest
from pydantic import ValidationError

from ansible_portal_installer.config import (
    AAPConfig,
    DeploymentConfig,
    RegistryConfig,
)


class TestRegistryConfig:
    """Tests for RegistryConfig model."""

    def test_valid_registry_config(self) -> None:
        """Test creating a valid registry config."""
        config = RegistryConfig(
            url="registry.example.com:5000",
            namespace="my-namespace",
            tag="v1.0.0",
        )
        assert config.url == "registry.example.com:5000"
        assert config.namespace == "my-namespace"
        assert config.tag == "v1.0.0"
        assert config.image_name == "automation-portal"

    def test_full_image_url(self) -> None:
        """Test full image URL construction."""
        config = RegistryConfig(
            url="registry.example.com:5000",
            namespace="my-ns",
            tag="dev",
        )
        assert config.full_image_url == "registry.example.com:5000/my-ns/automation-portal"
        assert (
            config.full_image_url_with_tag
            == "registry.example.com:5000/my-ns/automation-portal:dev"
        )

    def test_invalid_tag(self) -> None:
        """Test invalid tag format."""
        with pytest.raises(ValidationError, match="Invalid tag format"):
            RegistryConfig(
                url="registry.example.com",
                namespace="my-ns",
                tag="invalid tag with spaces",
            )

    def test_url_normalization(self) -> None:
        """Test URL normalization (removes https://)."""
        config = RegistryConfig(
            url="https://registry.example.com",
            namespace="my-ns",
        )
        assert config.url == "registry.example.com"


class TestAAPConfig:
    """Tests for AAPConfig model."""

    def test_valid_aap_config(self) -> None:
        """Test creating a valid AAP config."""
        config = AAPConfig(
            host_url="https://aap.example.com",
            token="test-token",
            oauth_client_id="client-id",
            oauth_client_secret="client-secret",
        )
        assert config.host_url == "https://aap.example.com"
        assert config.token == "test-token"

    def test_host_url_validation(self) -> None:
        """Test AAP host URL validation."""
        with pytest.raises(ValidationError, match="must start with http"):
            AAPConfig(
                host_url="aap.example.com",  # Missing protocol
                token="test-token",
                oauth_client_id="client-id",
                oauth_client_secret="client-secret",
            )

    def test_host_url_trailing_slash_removed(self) -> None:
        """Test trailing slash removal from host URL."""
        config = AAPConfig(
            host_url="https://aap.example.com/",
            token="test-token",
            oauth_client_id="client-id",
            oauth_client_secret="client-secret",
        )
        assert config.host_url == "https://aap.example.com"


class TestDeploymentConfig:
    """Tests for DeploymentConfig model."""

    def test_valid_deployment_config(self) -> None:
        """Test creating a valid deployment config."""
        config = DeploymentConfig(
            namespace="my-namespace",
            release_name="my-release",
        )
        assert config.namespace == "my-namespace"
        assert config.release_name == "my-release"

    def test_invalid_namespace(self) -> None:
        """Test invalid namespace format."""
        with pytest.raises(ValidationError, match="Invalid namespace"):
            DeploymentConfig(
                namespace="My-Namespace",  # Uppercase not allowed
            )

        with pytest.raises(ValidationError, match="Invalid namespace"):
            DeploymentConfig(
                namespace="namespace_with_underscore",  # Underscores not allowed
            )

    def test_namespace_too_long(self) -> None:
        """Test namespace length limit."""
        with pytest.raises(ValidationError, match="Namespace too long"):
            DeploymentConfig(
                namespace="a" * 64,  # Max 63 characters
            )

    def test_auth_secret_name(self) -> None:
        """Test auth secret name generation."""
        config = DeploymentConfig(
            namespace="my-namespace",
            release_name="my-release",
        )
        assert config.auth_secret_name == "my-release-dynamic-plugins-registry-auth"

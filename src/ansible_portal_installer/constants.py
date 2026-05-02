"""Application constants."""

from pathlib import Path

APP_NAME = "ansible-portal-installer"
PKG_NAME = "ansible_portal_installer"

DEFAULT_OPENSHIFT_NAMESPACE = "ansible-portal"
DEFAULT_HELM_RELEASE_NAME = "my-portal"
DEFAULT_REGISTRY = "quay.io"
DEFAULT_BUILD_TYPE = "portal"
DEFAULT_PLUGIN_MODE = "oci"

REQUIRED_NODE_VERSIONS = ["20", "22"]
REQUIRED_TOOLS = ["yarn", "podman", "oc", "helm", "git", "skopeo"]

PLUGIN_SECRETS = {
    "rhaap": "secrets-rhaap-portal",
    "scm": "secrets-scm",
}

SECRET_FIELDS = {
    "secrets-rhaap-portal": [
        "aap-host-url",
        "oauth-client-id",
        "oauth-client-secret",
        "aap-token",
    ],
    "secrets-scm": [
        "github-token",
        "github-client-id",
        "github-client-secret",
    ],
}

DYNAMIC_PLUGINS_DIR = "dynamic-plugins"
BUILD_SCRIPT = "build.sh"
CONTAINER_FILE = "Containerfile"

EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_KEYBOARD_INTERRUPT = 130

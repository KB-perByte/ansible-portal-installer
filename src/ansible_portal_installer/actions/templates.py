"""Configuration template generation action."""

from pathlib import Path
from typing import Optional

from ..config import Settings
from ..core import TemplateError
from ..ui import print_header, print_success, print_info, console


def generate_ocp_values_template(settings: Settings, output_dir: Path) -> Path:
    """Generate ocp-dev-values.yaml.tmpl.

    Args:
        settings: Application settings
        output_dir: Output directory

    Returns:
        Path to generated template
    """
    template_content = """# OCP Development Values Template
# Replace {{PLACEHOLDERS}} with actual values

redhat-developer-hub:
  global:
    # The wildcard apps domain of your OpenShift cluster
    # Example: apps.mycluster.example.com
    clusterRouterBase: {{CLUSTER_ROUTER_BASE}}

    # Plugin configuration
    pluginMode: oci

    # OCI plugin image (without tag)
    # Example: quay.io/your-username/ansible-portal-plugins
    ociPluginImage: {{OCI_PLUGIN_IMAGE}}

    # Image tag
    # Example: dev-20260502
    imageTagInfo: {{IMAGE_TAG}}

ansible:
  rhaap:
    # SSL verification for AAP connections
    checkSSL: {{AAP_CHECK_SSL}}

auth:
  providers:
    rhaap:
      production:
        # SSL verification for AAP OAuth
        checkSSL: {{AAP_CHECK_SSL}}

ansibleGitContents:
  # Enable content discovery
  enabled: true

  # GitHub organization to sync
  orgs:
    - name: {{GITHUB_ORG}}
"""

    output_path = output_dir / "ocp-dev-values.yaml.tmpl"
    output_path.write_text(template_content)
    return output_path


def generate_secrets_env_example(settings: Settings, output_dir: Path) -> Path:
    """Generate ocp-secrets.env.example.

    Args:
        settings: Application settings
        output_dir: Output directory

    Returns:
        Path to generated example
    """
    example_content = """# OpenShift Secrets Environment Variables Example
# Copy this file to .env and fill in actual values

# ============================================================================
# AAP (Ansible Automation Platform) Configuration
# ============================================================================

# AAP Controller URL
# Where to find it: Your AAP Controller URL
# Example: https://aap-controller.example.com
AAP_HOST_URL=https://your-aap-controller.example.com

# AAP OAuth Client ID
# Where to find it: AAP Controller → Administration → OAuth Applications
# Create a new OAuth Application with:
#   - Authorization Grant Type: Authorization code
#   - Client Type: Confidential
#   - Redirect URIs: https://<PORTAL-ROUTE>/api/auth/rhaap/handler/frame
AAP_OAUTH_CLIENT_ID=your-oauth-client-id

# AAP OAuth Client Secret
# Where to find it: AAP Controller → Administration → OAuth Applications → Your App
# Copy the Client Secret (shown only once after creation)
AAP_OAUTH_CLIENT_SECRET=your-oauth-client-secret

# AAP API Token
# Where to find it: AAP Controller → Your User Profile → Tokens → Create Token
# Create with Read + Write scope
AAP_TOKEN=your-aap-api-token

# ============================================================================
# GitHub Configuration
# ============================================================================

# GitHub Personal Access Token
# Where to find it: GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
# Create with scopes: repo, read:org, user:email
GITHUB_TOKEN=ghp_your_github_token

# GitHub OAuth Client ID
# Where to find it: GitHub → Settings → Developer settings → OAuth Apps → New OAuth App
# Create with:
#   - Homepage URL: Your AAP or portal URL
#   - Authorization callback URL: https://<PORTAL-ROUTE>/api/auth/github/handler/frame
GITHUB_CLIENT_ID=your-github-client-id

# GitHub OAuth Client Secret
# Where to find it: GitHub → Settings → Developer settings → OAuth Apps → Your App
# Generate a new client secret
GITHUB_CLIENT_SECRET=your-github-client-secret

# ============================================================================
# Container Registry Configuration
# ============================================================================

# Registry username (e.g., Quay.io username)
REGISTRY_USERNAME=your-quay-username

# Registry password or token
REGISTRY_PASSWORD=your-quay-password

# ============================================================================
# OpenShift Configuration
# ============================================================================

# OpenShift API server URL
# Example: https://api.mycluster.example.com:6443
OPENSHIFT_SERVER=https://api.your-cluster.example.com:6443

# OpenShift authentication token
# Get it with: oc whoami -t
OPENSHIFT_TOKEN=sha256~your-openshift-token

# OpenShift namespace/project
OPENSHIFT_NAMESPACE=ansible-portal

# ============================================================================
# Helm Configuration
# ============================================================================

# Helm release name
HELM_RELEASE_NAME=my-portal

# Path to Helm chart directory
HELM_CHART_PATH=../ansible-portal-chart
"""

    output_path = output_dir / "ocp-secrets.env.example"
    output_path.write_text(example_content)
    return output_path


def generate_auth_json_example(settings: Settings, output_dir: Path) -> Path:
    """Generate auth.json format example for plugin registry.

    Args:
        settings: Application settings
        output_dir: Output directory

    Returns:
        Path to generated example
    """
    example_content = """{
  "auths": {
    "quay.io": {
      "auth": "BASE64_ENCODED_USERNAME:PASSWORD"
    }
  }
}

# To generate the base64 encoded auth string:
# echo -n "username:password" | base64

# Example:
# echo -n "myuser:mypassword" | base64
# Output: bXl1c2VyOm15cGFzc3dvcmQ=

# Then use in auth.json:
# {
#   "auths": {
#     "quay.io": {
#       "auth": "bXl1c2VyOm15cGFzc3dvcmQ="
#     }
#   }
# }

# To use this file with podman/skopeo:
# podman login quay.io --authfile auth.json
# skopeo inspect --authfile auth.json docker://quay.io/user/image:tag

# To create OpenShift pull secret:
# oc create secret generic my-portal-dynamic-plugins-registry-auth \\
#   --from-file=.dockerconfigjson=auth.json \\
#   --type=kubernetes.io/dockerconfigjson
"""

    output_path = output_dir / "auth.json.example"
    output_path.write_text(example_content)
    return output_path


def generate_config_command(
    settings: Settings,
    output_dir: Optional[Path] = None,
) -> None:
    """Execute template generation workflow.

    Args:
        settings: Application settings
        output_dir: Output directory (default: ./templates)

    Raises:
        TemplateError: If generation fails
    """
    print_header("Generating Configuration Templates")

    # Default output directory
    if output_dir is None:
        output_dir = Path.cwd() / "templates"

    # Create output directory
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        print_info(f"Output directory: {output_dir}")
        console.print()
    except Exception as e:
        raise TemplateError(f"Failed to create output directory: {e}") from e

    # Generate templates
    try:
        values_path = generate_ocp_values_template(settings, output_dir)
        print_success(f"Generated: {values_path.name}")

        secrets_path = generate_secrets_env_example(settings, output_dir)
        print_success(f"Generated: {secrets_path.name}")

        auth_path = generate_auth_json_example(settings, output_dir)
        print_success(f"Generated: {auth_path.name}")

        console.print()
        print_success("Template generation completed!")
        print_info(f"Templates saved to: {output_dir}")

    except Exception as e:
        raise TemplateError(f"Failed to generate templates: {e}") from e

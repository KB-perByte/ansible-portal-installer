"""Helm deployment action."""

import os
from pathlib import Path

from ..config import Settings
from ..core import DeployError, InstallContext
from ..constants import SECRET_FIELDS
from ..ui import (
    print_header,
    print_success,
    print_info,
    print_warning,
    console,
    create_progress,
    print_panel,
)
from ..utils import (
    oc_login,
    oc_project_exists,
    oc_create_project,
    oc_use_project,
    oc_create_secret,
    oc_secret_exists,
    oc_get_route,
    oc_get_pods,
    helm_upgrade,
)
from .publish import publish_image


def connect_openshift(settings: Settings) -> None:
    """Connect to OpenShift cluster.

    Args:
        settings: Application settings

    Raises:
        DeployError: If connection fails
    """
    if not settings.openshift_server or not settings.openshift_token:
        raise DeployError("OpenShift credentials not configured")

    try:
        oc_login(
            server=settings.openshift_server,
            token=settings.openshift_token,
            insecure_skip_tls_verify=settings.openshift_insecure_skip_tls_verify,
        )
        print_success(f"Connected to OpenShift: {settings.openshift_server}")
    except Exception as e:
        raise DeployError(f"OpenShift connection failed: {e}") from e


def setup_namespace(settings: Settings, context: InstallContext) -> None:
    """Setup OpenShift namespace/project.

    Args:
        settings: Application settings
        context: Installation context

    Raises:
        DeployError: If namespace setup fails
    """
    namespace = settings.openshift_namespace

    try:
        if oc_project_exists(namespace):
            print_info(f"Using existing project: {namespace}")
            oc_use_project(namespace)
        else:
            oc_create_project(namespace)
            print_success(f"Created project: {namespace}")
            context.namespace_created = True
    except Exception as e:
        raise DeployError(f"Failed to setup namespace: {e}") from e


def create_secrets(settings: Settings, context: InstallContext) -> None:
    """Create required secrets in OpenShift.

    Args:
        settings: Application settings
        context: Installation context

    Raises:
        DeployError: If secret creation fails
    """
    namespace = settings.openshift_namespace

    # AAP secrets
    rhaap_secret = "secrets-rhaap-portal"
    if not oc_secret_exists(rhaap_secret, namespace):
        rhaap_data = {
            "aap-host-url": settings.aap_host_url or "",
            "oauth-client-id": settings.aap_oauth_client_id or "",
            "oauth-client-secret": settings.aap_oauth_client_secret or "",
            "aap-token": settings.aap_token or "",
        }
        try:
            oc_create_secret(rhaap_secret, rhaap_data, namespace)
            print_success(f"Created secret: {rhaap_secret}")
            context.secrets_created.append(rhaap_secret)
        except Exception as e:
            raise DeployError(f"Failed to create AAP secret: {e}") from e
    else:
        print_info(f"Secret already exists: {rhaap_secret}")

    # SCM secrets
    scm_secret = "secrets-scm"
    if not oc_secret_exists(scm_secret, namespace):
        scm_data = {
            "github-token": settings.github_token or "",
            "github-client-id": settings.github_client_id or "",
            "github-client-secret": settings.github_client_secret or "",
        }
        try:
            oc_create_secret(scm_secret, scm_data, namespace)
            print_success(f"Created secret: {scm_secret}")
            context.secrets_created.append(scm_secret)
        except Exception as e:
            raise DeployError(f"Failed to create SCM secret: {e}") from e
    else:
        print_info(f"Secret already exists: {scm_secret}")

    # Registry pull secret (if using OCI plugins)
    if settings.plugin_mode == "oci":
        registry_secret = f"{settings.helm_release_name}-dynamic-plugins-registry-auth"
        if not oc_secret_exists(registry_secret, namespace):
            # Check if auth.json exists
            auth_json_path = Path.home() / ".config/containers/auth.json"
            if not auth_json_path.exists():
                auth_json_path = Path.home() / ".docker/config.json"

            if auth_json_path.exists():
                try:
                    from subprocess import run

                    run(
                        [
                            "oc",
                            "create",
                            "secret",
                            "generic",
                            registry_secret,
                            f"--from-file=.dockerconfigjson={auth_json_path}",
                            "--type=kubernetes.io/dockerconfigjson",
                            "-n",
                            namespace,
                        ],
                        check=True,
                    )
                    print_success(f"Created secret: {registry_secret}")
                    context.secrets_created.append(registry_secret)
                except Exception as e:
                    print_warning(f"Could not create registry secret: {e}")
            else:
                print_warning(f"Registry auth file not found at {auth_json_path}")
        else:
            print_info(f"Secret already exists: {registry_secret}")


def deploy_with_helm(settings: Settings, context: InstallContext) -> None:
    """Deploy using Helm.

    Args:
        settings: Application settings
        context: Installation context

    Raises:
        DeployError: If deployment fails
    """
    # Build Helm values
    values = {}

    if settings.plugin_mode == "oci":
        values["redhat-developer-hub.global.pluginMode"] = "oci"
        values["redhat-developer-hub.global.ociPluginImage"] = (
            f"{settings.registry}/{settings.registry_username}/{settings.plugins_image_name}"
        )
        values["redhat-developer-hub.global.imageTagInfo"] = settings.plugins_image_tag

    if settings.cluster_router_base:
        values["redhat-developer-hub.global.clusterRouterBase"] = settings.cluster_router_base

    if not settings.aap_check_ssl:
        values["ansible.rhaap.checkSSL"] = "false"

    if settings.ansible_git_contents_enabled:
        values["ansibleGitContents.enabled"] = "true"
        values["ansibleGitContents.orgs[0].name"] = settings.github_org

    try:
        helm_upgrade(
            release_name=settings.helm_release_name,
            chart_path=settings.helm_chart_path,
            namespace=settings.openshift_namespace,
            values=values,
            install=True,
        )
        print_success(f"Deployed Helm release: {settings.helm_release_name}")
        context.helm_release_name = settings.helm_release_name
    except Exception as e:
        raise DeployError(f"Helm deployment failed: {e}") from e


def verify_deployment(settings: Settings, context: InstallContext) -> None:
    """Verify deployment status.

    Args:
        settings: Application settings
        context: Installation context
    """
    namespace = settings.openshift_namespace

    # Get pods
    pods = oc_get_pods(namespace)
    if pods:
        print_info(f"Found {len(pods)} pod(s) in namespace {namespace}:")
        for pod in pods:
            status_icon = "✓" if pod["status"] == "Running" else "⋯"
            console.print(f"  [{status_icon}] {pod['name']}: {pod['status']}")
    else:
        print_warning("No pods found (yet)")

    # Get route
    route = oc_get_route(settings.helm_release_name, namespace)
    if route:
        context.portal_route = route
        print_success(f"Portal route: {route}")
    else:
        print_warning("Portal route not found (yet)")


def display_next_steps(settings: Settings, context: InstallContext) -> None:
    """Display next steps for the user.

    Args:
        settings: Application settings
        context: Installation context
    """
    next_steps = f"""
[bold cyan]Next Steps:[/bold cyan]

1. Wait for pods to be ready:
   [dim]oc get pods -w -n {settings.openshift_namespace}[/dim]

2. Access the portal:
   {context.portal_route or '[dim]Check route: oc get route -n ' + settings.openshift_namespace + '[/dim]'}

3. Update OAuth redirect URIs:
   - AAP OAuth app redirect URIs:
     {context.portal_route or '<PORTAL-ROUTE>'}/api/auth/rhaap/handler/frame
     {context.portal_route or '<PORTAL-ROUTE>'}/api/auth/github/handler/frame
   - GitHub OAuth app callback URL:
     {context.portal_route or '<PORTAL-ROUTE>'}/api/auth/github/handler/frame

4. Verify the deployment:
   [dim]ansible-portal-installer verify --namespace {settings.openshift_namespace}[/dim]
"""
    print_panel(next_steps, title="Deployment Complete", style="green")


def deploy_helm(
    settings: Settings, context: InstallContext, publish_first: bool = True
) -> None:
    """Deploy Ansible Portal using Helm.

    Args:
        settings: Application settings
        context: Installation context
        publish_first: Publish image first if using OCI mode

    Raises:
        DeployError: If deployment fails
    """
    print_header("Deploying Ansible Portal with Helm")

    # Publish image first if needed (OCI mode)
    if publish_first and settings.plugin_mode == "oci" and not context.publish_completed:
        print_info("Publishing image first (OCI mode)...")
        publish_image(settings, context, build_first=True)
        console.print()

    with create_progress() as progress:
        task = progress.add_task("Deploying...", total=6)

        # Step 1: Connect to OpenShift
        progress.update(task, description="Connecting to OpenShift...")
        connect_openshift(settings)
        progress.advance(task)

        # Step 2: Setup namespace
        progress.update(task, description="Setting up namespace...")
        setup_namespace(settings, context)
        progress.advance(task)

        # Step 3: Create secrets
        progress.update(task, description="Creating secrets...")
        create_secrets(settings, context)
        progress.advance(task)

        # Step 4: Deploy with Helm
        progress.update(task, description="Deploying with Helm...")
        deploy_with_helm(settings, context)
        progress.advance(task)

        # Step 5: Verify deployment
        progress.update(task, description="Verifying deployment...")
        verify_deployment(settings, context)
        progress.advance(task)

        # Step 6: Complete
        progress.advance(task)

    context.deploy_completed = True
    print_success("Deployment completed successfully")
    console.print()
    display_next_steps(settings, context)

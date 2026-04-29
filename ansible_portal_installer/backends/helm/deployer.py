"""Helm deployment backend implementation."""

import secrets
import subprocess
import sys
from pathlib import Path
from typing import Any

import bcrypt
from rich.console import Console

from ...config import AAPConfig, DeploymentConfig, RegistryConfig, SCMConfig
from ...k8s import KubernetesClient, OpenShiftClient
from ..base import DeploymentBackend
from .client import HelmClient, generate_portal_values

console = Console()


def _print_rollout_failure_hints(namespace: str, release_name: str) -> None:
    """Print kubectl/oc commands to debug a stuck or slow rollout."""
    console.print("\n[red]Deployment rollout did not complete in time.[/red]")
    console.print(
        "[dim]Common causes: OCI pull, install-dynamic-plugins, or readiness probe still failing.[/dim]\n"
    )
    console.print("[bold]Inspect:[/bold]")
    console.print(f"  oc get pods -n {namespace} -o wide")
    console.print(f"  oc describe deployment -n {namespace} {release_name}")
    console.print(
        f"  oc logs -n {namespace} deploy/{release_name} -c install-dynamic-plugins --tail=200"
    )
    console.print(
        f"  oc logs -n {namespace} deploy/{release_name} -c backstage-backend --tail=200"
    )


class HelmDeployer(DeploymentBackend):
    """Helm-based deployment backend for Kubernetes/OpenShift."""

    def __init__(self) -> None:
        """Initialize Helm deployer."""
        try:
            self.k8s = KubernetesClient()
            self.oc = OpenShiftClient()
            self.helm = HelmClient()
        except RuntimeError as e:
            console.print(f"[red]Error connecting to cluster: {e}[/red]")
            sys.exit(2)

    def deploy(
        self,
        config: DeploymentConfig,
        skip_build: bool = False,
        timeout: str = "15m",
    ) -> dict[str, Any]:
        """Deploy portal using Helm chart."""
        from ...commands.build import _build_and_push_plugins

        namespace = config.namespace
        release_name = config.release_name

        console.print("[bold blue]Ansible Portal - Helm Deployment[/bold blue]\n")

        # Ensure namespace exists
        if not self.k8s.namespace_exists(namespace):
            console.print(f"[blue]Creating namespace: {namespace}[/blue]")
            self.k8s.create_namespace(namespace)
        else:
            console.print(f"[green]✓[/green] Namespace exists: {namespace}")

        # Build and push plugins unless skipped
        registry_url = None
        if not skip_build:
            # Determine registry URL
            if config.registry:
                registry_config = config.registry
            else:
                # Use OpenShift external registry route for push (requires auth)
                # but will use internal service URL for Helm values (avoids TLS issues)
                registry_route = self.oc.get_registry_route()
                if registry_route:
                    registry_base_url = registry_route
                else:
                    registry_base_url = "image-registry.openshift-image-registry.svc:5000"

                registry_config = RegistryConfig(
                    url=registry_base_url,
                    namespace=namespace,
                    tag=config.image_tag,
                    insecure=True,
                )

            registry_url = _build_and_push_plugins(
                plugins_path=config.plugins_path,
                registry_config=registry_config,
                image_tag=config.image_tag,
                namespace=namespace,
                release_name=release_name,
            )
        else:
            console.print("[yellow]Skipping plugin build[/yellow]")
            # Use existing image
            if config.registry:
                registry_url = config.registry.full_image_url_with_tag
            else:
                console.print("[red]No registry config provided with --skip-build[/red]")
                sys.exit(1)

        if config.aap is None:
            console.print(
                "[red]AAP configuration is required. "
                "Provide --aap-host, --aap-token, and OAuth client options (or set env vars).[/red]"
            )
            sys.exit(1)

        # Create secrets
        self._create_secrets(namespace, release_name, config.aap, config.scm)

        # Create registries ConfigMap for internal registry TLS skip
        self._create_registries_configmap(namespace, release_name)

        # Generate admin password
        admin_password = config.admin_password or self._generate_password()
        admin_password_hash = self._hash_password(admin_password)

        # Generate backend secret for Backstage auth
        backend_secret = self._generate_password(32)

        # Get cluster router base
        cluster_router_base = self.oc.get_cluster_router_base()

        # Strip tag from registry_url if present (since image_tag is passed separately)
        # registry_url from build is full URL with tag, but Helm values need base URL only
        base_registry_url = registry_url.rsplit(":", 1)[0] if ":" in registry_url else registry_url

        # Use the external registry route for pod pulls (requires auth secret)
        # The external route allows proper authentication via the auth secret
        final_registry_url = base_registry_url

        # Generate Helm values
        values = generate_portal_values(
            registry_url=final_registry_url,
            image_tag=config.image_tag,
            cluster_router_base=cluster_router_base,
            release_name=release_name,
            admin_password_hash=admin_password_hash,
            backend_secret=backend_secret,
            check_ssl=config.check_ssl,
        )

        # Update Helm dependencies
        self.helm.dependency_update(config.chart_path)

        # Install or upgrade via Helm
        self.helm.install_or_upgrade(
            release_name=release_name,
            chart_path=config.chart_path,
            namespace=namespace,
            values=values,
            timeout=timeout,
            wait=False,  # Don't wait yet, we need to patch first
        )

        # Patch deployment to add registries config volume for insecure registry
        self._patch_deployment_for_insecure_registry(namespace, release_name)

        # Now wait for deployment to be ready (RHDH+OCI plugin init is often 15–30+ minutes)
        if config.wait_for_rollout:
            console.print(
                f"\n[blue]Waiting for deployment to be ready (timeout: {config.rollout_timeout})...[/blue]"
            )
            try:
                subprocess.run(
                    [
                        "kubectl",
                        "rollout",
                        "status",
                        f"deployment/{release_name}",
                        "-n",
                        namespace,
                        f"--timeout={config.rollout_timeout}",
                    ],
                    check=True,
                )
            except subprocess.CalledProcessError:
                _print_rollout_failure_hints(namespace, release_name)
                raise
            console.print("[green]✓[/green] Deployment ready")
        else:
            console.print(
                "\n[yellow]Skipped waiting for rollout (--skip-rollout-wait). "
                "Pods may still be starting.[/yellow]"
            )
            console.print(
                f"[dim]kubectl rollout status deployment/{release_name} -n {namespace} "
                f"--timeout={config.rollout_timeout}[/dim]"
            )

        # Get portal URL
        portal_url = f"https://{release_name}-{namespace}.{cluster_router_base}"

        return {
            "url": portal_url,
            "username": "admin",
            "password": admin_password,
            "namespace": namespace,
            "release": release_name,
        }

    def upgrade(
        self,
        namespace: str,
        release_name: str,
        chart_path: Path | None = None,
        values: dict[str, Any] | None = None,
        skip_build: bool = False,
    ) -> None:
        """Upgrade existing Helm deployment."""
        console.print("[bold blue]Ansible Portal - Helm Upgrade[/bold blue]\n")

        # Check if release exists
        if not self.helm.release_exists(release_name, namespace):
            console.print(
                f"[red]Release '{release_name}' not found in namespace '{namespace}'[/red]"
            )
            console.print("[yellow]Use 'deploy' command for initial deployment[/yellow]")
            sys.exit(1)

        # Get current values if not provided
        if values is None:
            console.print("[blue]Using current Helm values[/blue]")
            values = self.helm.get_values(release_name, namespace) or {}

        # Rebuild plugins if not skipped
        if not skip_build:

            console.print("[blue]Rebuilding plugins...[/blue]")
            # This will trigger the build command
            # In practice, you'd call the build logic directly
            console.print(
                "[yellow]Note: Run 'build' command separately for plugin updates[/yellow]"
            )

        # Use provided chart path or detect from current release
        if chart_path is None:
            chart_path = Path("../ansible-portal-chart")

        # Update dependencies
        self.helm.dependency_update(chart_path)

        # Upgrade
        self.helm.install_or_upgrade(
            release_name=release_name,
            chart_path=chart_path,
            namespace=namespace,
            values=values,
        )

        console.print("\n[bold green]✓ Upgrade complete![/bold green]\n")

    def teardown(
        self,
        namespace: str,
        release_name: str,
        clean_data: bool = False,
    ) -> None:
        """Remove Helm deployment."""
        console.print("[bold blue]Ansible Portal - Helm Teardown[/bold blue]\n")

        # Uninstall Helm release
        self.helm.uninstall(release_name, namespace)

        # Clean up secrets if requested
        if clean_data:
            console.print("\n[blue]Cleaning up secrets...[/blue]")
            secrets_to_delete = [
                "secrets-rhaap-portal",
                "secrets-scm",
                f"{release_name}-dynamic-plugins-registry-auth",
            ]

            for secret_name in secrets_to_delete:
                try:
                    if self.k8s.secret_exists(namespace, secret_name):
                        self.k8s.core_v1.delete_namespaced_secret(secret_name, namespace)
                        console.print(f"[green]✓[/green] Deleted secret: {secret_name}")
                except Exception as e:
                    console.print(
                        f"[yellow]Warning: Could not delete secret {secret_name}: {e}[/yellow]"
                    )

    def get_status(
        self,
        namespace: str,
        release_name: str,
    ) -> dict[str, Any] | None:
        """Get Helm release status."""
        if not self.helm.release_exists(release_name, namespace):
            return None

        status_text = self.helm.get_status(release_name, namespace)
        values = self.helm.get_values(release_name, namespace)

        return {"status": status_text, "values": values}

    def get_values(
        self,
        namespace: str,
        release_name: str,
    ) -> dict[str, Any] | None:
        """Get Helm values."""
        return self.helm.get_values(release_name, namespace)

    def validate_deployment(
        self,
        namespace: str,
        release_name: str | None = None,
        verbose: bool = False,
        timeout: int = 300,
    ) -> bool:
        """Validate Helm deployment health."""
        from ...config import HealthCheckConfig
        from ...validation import HealthChecker

        config = HealthCheckConfig(
            namespace=namespace,
            release_name=release_name,
            verbose=verbose,
            timeout_seconds=timeout,
        )

        checker = HealthChecker(config)
        return checker.run_all_checks()

    def collect_logs(
        self,
        namespace: str,
        release_name: str | None,
        output_dir: Path,
        tail_lines: int = 1000,
    ) -> None:
        """Collect diagnostic logs from Helm deployment."""

        console.print("[bold blue]Ansible Portal - Collect Diagnostic Logs[/bold blue]\n")

        # Implementation would mirror collect_logs command
        # Importing here to avoid circular dependencies
        from ...commands.collect_logs import (
            _collect_cluster_info,
            _collect_events,
            _collect_helm_status,
            _collect_pod_descriptions,
            _collect_pod_info,
            _collect_pod_logs,
            _collect_resources,
            _create_summary,
        )

        output_dir.mkdir(parents=True, exist_ok=True)

        _collect_cluster_info(self.oc, output_dir)
        _collect_pod_info(self.k8s, namespace, output_dir)
        _collect_pod_descriptions(self.k8s, namespace, output_dir)
        _collect_pod_logs(self.k8s, namespace, output_dir, tail_lines)
        _collect_events(self.k8s, namespace, output_dir)

        if release_name and release_name != "unknown":
            _collect_helm_status(self.helm, release_name, namespace, output_dir)

        _collect_resources(self.k8s, self.oc, namespace, output_dir)
        _create_summary(output_dir, namespace, release_name or "unknown")

    def _create_secrets(
        self,
        namespace: str,
        release_name: str,
        aap_config: AAPConfig,
        scm_config: SCMConfig | None,
    ) -> None:
        """Create Kubernetes secrets."""
        console.print("\n[blue]Creating secrets...[/blue]")

        # AAP secrets
        aap_secret_data = {
            "ANSIBLE_RHAAP_BASE_URL": aap_config.base_url,
            "ANSIBLE_RHAAP_TOKEN": aap_config.token,
            "ANSIBLE_RHAAP_CLIENT_ID": aap_config.oauth_client_id,
            "ANSIBLE_RHAAP_CLIENT_SECRET": aap_config.oauth_client_secret,
        }

        self.k8s.create_or_update_secret(
            namespace=namespace, name="secrets-rhaap-portal", data=aap_secret_data
        )
        console.print("[green]✓[/green] Created AAP secret")

        # SCM secrets (optional)
        if scm_config and (scm_config.github_token or scm_config.gitlab_token):
            scm_secret_data = {}

            if scm_config.github_token:
                scm_secret_data["GITHUB_TOKEN"] = scm_config.github_token
            if scm_config.github_client_id:
                scm_secret_data["AUTH_GITHUB_CLIENT_ID"] = scm_config.github_client_id
            if scm_config.github_client_secret:
                scm_secret_data["AUTH_GITHUB_CLIENT_SECRET"] = scm_config.github_client_secret
            if scm_config.gitlab_token:
                scm_secret_data["GITLAB_TOKEN"] = scm_config.gitlab_token

            self.k8s.create_or_update_secret(
                namespace=namespace, name="secrets-scm", data=scm_secret_data
            )
            console.print("[green]✓[/green] Created SCM secret")

    def _create_registries_configmap(self, namespace: str, release_name: str) -> None:
        """Create ConfigMap for container registries configuration to skip TLS verification."""
        console.print("\n[blue]Creating registries configuration...[/blue]")

        # Get external registry route
        external_registry = self.oc.get_registry_route() or "default-route-openshift-image-registry.apps.example.com"

        # Create registries.conf content to skip TLS verification for all OpenShift registries
        registries_conf = f"""[[registry]]
location = "{external_registry}"
insecure = true

[[registry]]
location = "image-registry.openshift-image-registry.svc:5000"
insecure = true

[[registry]]
location = "image-registry.openshift-image-registry.svc"
insecure = true
"""

        configmap_name = f"{release_name}-registries-conf"

        try:
            # Create ConfigMap using kubectl
            import subprocess
            import tempfile

            with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
                f.write(registries_conf)
                conf_file = Path(f.name)

            try:
                result = subprocess.run(
                    [
                        "kubectl", "create", "configmap", configmap_name,
                        "--from-file=10-internal-registry.conf=" + str(conf_file),
                        "-n", namespace,
                        "--dry-run=client",
                        "-o", "yaml"
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )

                subprocess.run(
                    ["kubectl", "apply", "-f", "-", "-n", namespace],
                    input=result.stdout,
                    check=True,
                    capture_output=True,
                    text=True,
                )

                console.print(f"[green]✓[/green] Created registries ConfigMap: {configmap_name}")
            finally:
                conf_file.unlink(missing_ok=True)

        except subprocess.CalledProcessError as e:
            console.print("[red]Failed to create registries ConfigMap[/red]")
            console.print(f"[red]{e.stderr}[/red]")
            raise

    def _generate_password(self, length: int = 16) -> str:
        """Generate a random password."""
        return secrets.token_urlsafe(length)

    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10))
        return hashed.decode()

    def _patch_deployment_for_insecure_registry(self, namespace: str, release_name: str) -> None:
        """Patch deployment to add registries config volume for insecure internal registry."""
        import json
        import subprocess

        console.print("[blue]Patching deployment for insecure registry support...[/blue]")

        # JSON patch to add volume and volume mount for registries config
        patch = {
            "spec": {
                "template": {
                    "spec": {
                        "volumes": [
                            {
                                "name": "registries-conf",
                                "configMap": {
                                    "name": f"{release_name}-registries-conf",
                                    "defaultMode": 420,
                                },
                            }
                        ],
                        "initContainers": [
                            {
                                "name": "install-dynamic-plugins",
                                "volumeMounts": [
                                    {
                                        "name": "registries-conf",
                                        "mountPath": "/etc/containers/registries.conf.d",
                                        "readOnly": True,
                                    }
                                ],
                            }
                        ],
                    }
                }
            }
        }

        try:
            # Apply strategic merge patch
            subprocess.run(
                [
                    "kubectl",
                    "patch",
                    "deployment",
                    release_name,
                    "-n",
                    namespace,
                    "--type=strategic",
                    "--patch",
                    json.dumps(patch),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            console.print("[green]✓[/green] Patched deployment for insecure registry support")
        except subprocess.CalledProcessError as e:
            console.print("[red]Failed to patch deployment[/red]")
            console.print(f"[red]{e.stderr}[/red]")
            raise

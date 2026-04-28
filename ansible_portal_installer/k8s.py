"""Kubernetes and OpenShift client operations."""

import subprocess
from typing import Any, Dict, List, Optional

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from rich.console import Console

console = Console()


class KubernetesClient:
    """Wrapper for Kubernetes API client operations."""

    def __init__(self) -> None:
        """Initialize Kubernetes client."""
        try:
            # Try in-cluster config first
            config.load_incluster_config()
        except config.ConfigException:
            # Fall back to kubeconfig
            try:
                config.load_kube_config()
            except config.ConfigException as e:
                raise RuntimeError(
                    "Could not load Kubernetes config. "
                    "Make sure you're logged into an OpenShift cluster."
                ) from e

        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.rbac_v1 = client.RbacAuthorizationV1Api()

    def get_current_context(self) -> str:
        """Get current Kubernetes context."""
        contexts, active_context = config.list_kube_config_contexts()
        if not active_context:
            raise RuntimeError("No active Kubernetes context found")
        return active_context["name"]

    def namespace_exists(self, namespace: str) -> bool:
        """Check if namespace exists."""
        try:
            self.core_v1.read_namespace(namespace)
            return True
        except ApiException as e:
            if e.status == 404:
                return False
            raise

    def create_namespace(self, namespace: str) -> None:
        """Create namespace if it doesn't exist."""
        if self.namespace_exists(namespace):
            console.print(f"[yellow]Namespace {namespace} already exists[/yellow]")
            return

        ns = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
        self.core_v1.create_namespace(ns)
        console.print(f"[green]✓[/green] Created namespace: {namespace}")

    def get_pods(
        self, namespace: str, label_selector: Optional[str] = None
    ) -> List[client.V1Pod]:
        """Get pods in namespace with optional label selector."""
        try:
            result = self.core_v1.list_namespaced_pod(
                namespace, label_selector=label_selector
            )
            return result.items
        except ApiException as e:
            console.print(f"[red]Failed to get pods: {e}[/red]")
            return []

    def get_pod_status(self, namespace: str, pod_name: str) -> Dict[str, Any]:
        """Get detailed pod status."""
        try:
            pod = self.core_v1.read_namespaced_pod(pod_name, namespace)
            return {
                "name": pod.metadata.name,
                "phase": pod.status.phase,
                "ready": all(
                    c.ready for c in pod.status.container_statuses or []
                ),
                "containers": [
                    {
                        "name": c.name,
                        "ready": c.ready,
                        "restart_count": c.restart_count,
                        "state": str(c.state),
                    }
                    for c in pod.status.container_statuses or []
                ],
                "init_containers": [
                    {
                        "name": c.name,
                        "ready": c.ready,
                        "state": str(c.state),
                    }
                    for c in pod.status.init_container_statuses or []
                ],
            }
        except ApiException as e:
            return {"error": str(e)}

    def get_pod_logs(
        self,
        namespace: str,
        pod_name: str,
        container: Optional[str] = None,
        tail_lines: int = 100,
        previous: bool = False,
    ) -> str:
        """Get pod logs."""
        try:
            return self.core_v1.read_namespaced_pod_log(
                pod_name,
                namespace,
                container=container,
                tail_lines=tail_lines,
                previous=previous,
            )
        except ApiException as e:
            return f"Error getting logs: {e}"

    def secret_exists(self, namespace: str, secret_name: str) -> bool:
        """Check if secret exists."""
        try:
            self.core_v1.read_namespaced_secret(secret_name, namespace)
            return True
        except ApiException as e:
            if e.status == 404:
                return False
            raise

    def create_secret(
        self, namespace: str, secret_name: str, data: Dict[str, str], secret_type: str = "Opaque"
    ) -> None:
        """Create or update a secret."""
        import base64

        # Base64 encode all values
        encoded_data = {k: base64.b64encode(v.encode()).decode() for k, v in data.items()}

        secret = client.V1Secret(
            metadata=client.V1ObjectMeta(name=secret_name),
            type=secret_type,
            data=encoded_data,
        )

        try:
            if self.secret_exists(namespace, secret_name):
                self.core_v1.replace_namespaced_secret(secret_name, namespace, secret)
                console.print(f"[green]✓[/green] Updated secret: {secret_name}")
            else:
                self.core_v1.create_namespaced_secret(namespace, secret)
                console.print(f"[green]✓[/green] Created secret: {secret_name}")
        except ApiException as e:
            raise RuntimeError(f"Failed to create/update secret {secret_name}: {e}") from e

    def create_or_update_secret(
        self, namespace: str, name: str = None, secret_name: str = None, data: Dict[str, str] = None, secret_type: str = "Opaque"
    ) -> None:
        """Alias for create_secret (which already does create-or-update)."""
        # Accept either 'name' or 'secret_name' parameter
        actual_name = name or secret_name
        if not actual_name:
            raise ValueError("Either 'name' or 'secret_name' must be provided")
        return self.create_secret(namespace, actual_name, data, secret_type)

    def get_deployment(self, namespace: str, deployment_name: str) -> Optional[client.V1Deployment]:
        """Get deployment by name."""
        try:
            return self.apps_v1.read_namespaced_deployment(deployment_name, namespace)
        except ApiException as e:
            if e.status == 404:
                return None
            raise

    def deployment_exists(self, namespace: str, deployment_name: str) -> bool:
        """Check if deployment exists."""
        return self.get_deployment(namespace, deployment_name) is not None


class OpenShiftClient:
    """OpenShift-specific operations using oc CLI."""

    @staticmethod
    def run_oc_command(args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run oc command and return result."""
        try:
            return subprocess.run(
                ["oc"] + args,
                check=check,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            console.print(f"[red]oc command failed: {' '.join(args)}[/red]")
            console.print(f"[red]Error: {e.stderr}[/red]")
            raise

    @classmethod
    def check_logged_in(cls) -> bool:
        """Check if user is logged into OpenShift."""
        try:
            result = cls.run_oc_command(["whoami"], check=False)
            return result.returncode == 0
        except FileNotFoundError:
            console.print("[red]oc command not found. Please install OpenShift CLI.[/red]")
            return False

    @classmethod
    def get_current_user(cls) -> str:
        """Get current OpenShift user."""
        result = cls.run_oc_command(["whoami"])
        return result.stdout.strip()

    @classmethod
    def get_cluster_router_base(cls) -> str:
        """Get OpenShift cluster router base domain."""
        result = cls.run_oc_command(
            ["get", "ingresses.config", "cluster", "-o", "jsonpath={.spec.domain}"]
        )
        return result.stdout.strip()

    @classmethod
    def get_registry_route(cls) -> Optional[str]:
        """Get OpenShift internal registry external route."""
        result = cls.run_oc_command(
            [
                "get",
                "route",
                "default-route",
                "-n",
                "openshift-image-registry",
                "-o",
                "jsonpath={.spec.host}",
            ],
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None

    @classmethod
    def registry_login(cls, auth_file: str) -> None:
        """Login to OpenShift registry and save credentials."""
        cls.run_oc_command(["registry", "login", f"--to={auth_file}"])

    @classmethod
    def create_project(cls, namespace: str) -> None:
        """Create OpenShift project (namespace)."""
        cls.run_oc_command(["new-project", namespace])

    @classmethod
    def get_route_host(cls, namespace: str, label_selector: str) -> Optional[str]:
        """Get route host by label selector."""
        result = cls.run_oc_command(
            [
                "get",
                "route",
                "-n",
                namespace,
                "-l",
                label_selector,
                "-o",
                "jsonpath={.items[0].spec.host}",
            ],
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None

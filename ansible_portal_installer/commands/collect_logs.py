"""Collect logs command - Collect diagnostic logs from deployment."""

import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console

from ..backends import BackendFactory, BackendType

console = Console()


@click.command(name="collect-logs")
@click.option(
    "--backend",
    type=click.Choice([b.value for b in BackendType]),
    default=BackendType.HELM.value,
    help="Deployment backend",
    envvar="DEPLOYMENT_BACKEND",
)
@click.option(
    "--namespace",
    "-n",
    help="Target namespace/location (auto-detect if not provided)",
    envvar="OCP_NAMESPACE",
)
@click.option(
    "--release-name",
    help="Deployment identifier (auto-detect if not provided)",
    envvar="RELEASE_NAME",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory (default: ./portal-logs-TIMESTAMP)",
)
@click.option(
    "--tail",
    default=1000,
    type=int,
    help="Number of log lines to collect",
)
def collect_logs(
    backend: str,
    namespace: str | None,
    release_name: str | None,
    output_dir: Path | None,
    tail: int,
) -> None:
    """Collect comprehensive diagnostic logs from portal deployment.

    This command collects:
    - All pod logs (main containers + init containers)
    - Pod descriptions and status
    - Namespace events
    - Deployment status and configuration
    - Resource manifests (deployments, services, routes, etc.)

    The collected logs are saved to a timestamped directory for troubleshooting.

    Log collection varies by backend:
    - Helm: Pod logs, Helm status, Kubernetes events
    - Operator: CR status, operator logs, conditions
    - RHEL: systemd journal, service logs, config files
    """
    console.print("[bold blue]Ansible Portal - Collect Diagnostic Logs[/bold blue]\n")

    # Create output directory
    if not output_dir:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = Path(f"./portal-logs-{timestamp}")

    output_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[green]✓[/green] Output directory: {output_dir}\n")

    try:
        deployer = BackendFactory.create(backend)

        # Auto-detection handled by backend
        if not namespace:
            console.print("[blue]Auto-detecting namespace...[/blue]")

        deployer.collect_logs(
            namespace=namespace or "",  # Backend will auto-detect
            release_name=release_name,
            output_dir=output_dir,
            tail_lines=tail,
        )

        console.print(f"\n[bold green]✓ Log collection complete![/bold green]")
        console.print(f"[blue]Logs saved to:[/blue] {output_dir}\n")
        console.print(f"[yellow]Review {output_dir}/SUMMARY.txt for an overview[/yellow]\n")

    except NotImplementedError as e:
        console.print(f"[red]{e}[/red]")
        console.print(
            f"\n[yellow]Available backends: {', '.join(BackendFactory.list_implemented_backends())}[/yellow]"
        )
        sys.exit(2)
    except Exception as e:
        console.print(f"[red]Log collection failed: {e}[/red]")
        sys.exit(1)


# Helper functions for Helm backend (imported by helm/deployer.py)


def _collect_cluster_info(oc, output_dir: Path) -> None:
    """Collect cluster information."""
    info_file = output_dir / "cluster-info.txt"

    try:
        user = oc.get_current_user()
        router_base = oc.get_cluster_router_base()

        with open(info_file, "w") as f:
            f.write("Cluster Information\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Current user: {user}\n")
            f.write(f"Router base: {router_base}\n")

    except Exception as e:
        console.print(f"[yellow]Warning: Could not collect cluster info: {e}[/yellow]")


def _collect_pod_info(k8s, namespace: str, output_dir: Path) -> None:
    """Collect pod list."""
    pods_file = output_dir / "pods.txt"

    try:
        pods = k8s.get_pods(namespace)

        with open(pods_file, "w") as f:
            f.write(f"Pods in namespace: {namespace}\n")
            f.write("=" * 40 + "\n\n")

            for pod in pods:
                f.write(f"Name: {pod.metadata.name}\n")
                f.write(f"Phase: {pod.status.phase}\n")
                f.write(f"Node: {pod.spec.node_name}\n")

                if pod.status.container_statuses:
                    f.write("Containers:\n")
                    for container in pod.status.container_statuses:
                        f.write(f"  - {container.name}: Ready={container.ready}\n")

                f.write("\n")

    except Exception as e:
        console.print(f"[yellow]Warning: Could not collect pod info: {e}[/yellow]")


def _collect_pod_descriptions(k8s, namespace: str, output_dir: Path) -> None:
    """Collect detailed pod descriptions."""
    try:
        pods = k8s.get_pods(namespace)

        for pod in pods:
            desc_file = output_dir / f"pod-describe-{pod.metadata.name}.txt"

            status = k8s.get_pod_status(namespace, pod.metadata.name)

            with open(desc_file, "w") as f:
                f.write(f"Pod: {pod.metadata.name}\n")
                f.write("=" * 40 + "\n\n")

                import yaml

                f.write(yaml.dump(status, default_flow_style=False))

    except Exception as e:
        console.print(f"[yellow]Warning: Could not collect pod descriptions: {e}[/yellow]")


def _collect_pod_logs(k8s, namespace: str, output_dir: Path, tail: int) -> None:
    """Collect pod logs."""
    try:
        pods = k8s.get_pods(namespace)

        for pod in pods:
            # Main containers
            if pod.status.container_statuses:
                for container in pod.status.container_statuses:
                    log_file = output_dir / f"pod-logs-{pod.metadata.name}-{container.name}.log"
                    logs = k8s.get_pod_logs(
                        namespace, pod.metadata.name, container.name, tail_lines=tail
                    )
                    log_file.write_text(logs)

                    # Previous logs if available
                    prev_logs = k8s.get_pod_logs(
                        namespace,
                        pod.metadata.name,
                        container.name,
                        tail_lines=tail,
                        previous=True,
                    )
                    if prev_logs and "Error" not in prev_logs[:100]:
                        prev_log_file = (
                            output_dir
                            / f"pod-logs-{pod.metadata.name}-{container.name}-previous.log"
                        )
                        prev_log_file.write_text(prev_logs)

            # Init containers
            if pod.status.init_container_statuses:
                for container in pod.status.init_container_statuses:
                    log_file = (
                        output_dir / f"pod-logs-{pod.metadata.name}-{container.name}-init.log"
                    )
                    logs = k8s.get_pod_logs(
                        namespace, pod.metadata.name, container.name, tail_lines=tail
                    )
                    log_file.write_text(logs)

    except Exception as e:
        console.print(f"[yellow]Warning: Could not collect pod logs: {e}[/yellow]")


def _collect_events(k8s, namespace: str, output_dir: Path) -> None:
    """Collect namespace events."""
    events_file = output_dir / "events.txt"

    try:
        events = k8s.core_v1.list_namespaced_event(namespace)

        with open(events_file, "w") as f:
            f.write(f"Events in namespace: {namespace}\n")
            f.write("=" * 40 + "\n\n")

            # Sort by timestamp
            sorted_events = sorted(
                events.items,
                key=lambda e: e.last_timestamp or e.event_time or datetime.min,
            )

            for event in sorted_events:
                f.write(f"Time: {event.last_timestamp or event.event_time}\n")
                f.write(f"Type: {event.type}\n")
                f.write(f"Reason: {event.reason}\n")
                f.write(f"Object: {event.involved_object.kind}/{event.involved_object.name}\n")
                f.write(f"Message: {event.message}\n")
                f.write("\n")

    except Exception as e:
        console.print(f"[yellow]Warning: Could not collect events: {e}[/yellow]")


def _collect_helm_status(helm, release_name: str, namespace: str, output_dir: Path) -> None:
    """Collect Helm release status."""
    helm_file = output_dir / "helm-status.txt"

    try:
        status = helm.get_status(release_name, namespace)
        values = helm.get_values(release_name, namespace)

        with open(helm_file, "w") as f:
            f.write(f"Helm Release: {release_name}\n")
            f.write("=" * 40 + "\n\n")

            if status:
                f.write("Status:\n")
                f.write(status)
                f.write("\n\n")

            if values:
                f.write("Values:\n")
                import yaml

                f.write(yaml.dump(values, default_flow_style=False))

    except Exception as e:
        console.print(f"[yellow]Warning: Could not collect Helm status: {e}[/yellow]")


def _collect_resources(k8s, oc, namespace: str, output_dir: Path) -> None:
    """Collect resource manifests."""
    resources_file = output_dir / "resources.txt"

    try:
        with open(resources_file, "w") as f:
            f.write(f"Resources in namespace: {namespace}\n")
            f.write("=" * 40 + "\n\n")

            # Deployments
            deployments = k8s.apps_v1.list_namespaced_deployment(namespace)
            f.write("Deployments:\n")
            for deploy in deployments.items:
                f.write(f"  - {deploy.metadata.name}\n")
            f.write("\n")

            # Services
            services = k8s.core_v1.list_namespaced_service(namespace)
            f.write("Services:\n")
            for svc in services.items:
                f.write(f"  - {svc.metadata.name}\n")
            f.write("\n")

            # Secrets
            secrets = k8s.core_v1.list_namespaced_secret(namespace)
            f.write("Secrets:\n")
            for secret in secrets.items:
                f.write(f"  - {secret.metadata.name}\n")
            f.write("\n")

            # ConfigMaps
            cms = k8s.core_v1.list_namespaced_config_map(namespace)
            f.write("ConfigMaps:\n")
            for cm in cms.items:
                f.write(f"  - {cm.metadata.name}\n")
            f.write("\n")

    except Exception as e:
        console.print(f"[yellow]Warning: Could not collect resources: {e}[/yellow]")


def _create_summary(output_dir: Path, namespace: str, release_name: str) -> None:
    """Create summary file."""
    summary_file = output_dir / "SUMMARY.txt"

    files = sorted(output_dir.glob("*"))

    with open(summary_file, "w") as f:
        f.write("Ansible Portal Log Collection Summary\n")
        f.write("=" * 40 + "\n\n")
        f.write(f"Collection time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Namespace: {namespace}\n")
        f.write(f"Release: {release_name}\n")
        f.write(f"Output directory: {output_dir}\n\n")
        f.write("Files collected:\n")

        for file in files:
            if file.is_file() and file.name != "SUMMARY.txt":
                size = file.stat().st_size
                f.write(f"  - {file.name} ({size:,} bytes)\n")

        f.write("\n")
        f.write("Common troubleshooting steps:\n")
        f.write("  1. Check pod-describe-* files for pod status and events\n")
        f.write("  2. Review init container logs (*-init.log) for plugin loading\n")
        f.write("  3. Check main container logs for application errors\n")
        f.write("  4. Review events.txt for cluster-level issues\n")
        f.write("  5. Verify deployment status and configuration\n")

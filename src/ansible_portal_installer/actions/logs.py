"""Log collection action for troubleshooting."""

from pathlib import Path
from datetime import datetime
from typing import Optional

from ..config import Settings
from ..core import LogCollectionError
from ..ui import print_header, print_success, print_info, console, create_progress
from ..utils import (
    oc_get_pods,
    oc_get_pod_logs,
    oc_describe_pod,
    oc_get_events,
    helm_status,
    helm_get_values,
)


def create_output_directory(output_dir: Optional[Path] = None) -> Path:
    """Create timestamped output directory.

    Args:
        output_dir: Base directory (default: ./logs)

    Returns:
        Path to created directory
    """
    if output_dir is None:
        output_dir = Path.cwd() / "logs"

    # Create timestamped subdirectory
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_dir = output_dir / f"logs-{timestamp}"

    # Create subdirectories
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "pods").mkdir(exist_ok=True)
    (log_dir / "events").mkdir(exist_ok=True)
    (log_dir / "helm").mkdir(exist_ok=True)

    return log_dir


def collect_pod_logs(
    settings: Settings, pods: list[dict], output_dir: Path
) -> None:
    """Collect logs from all containers in pods.

    Args:
        settings: Application settings
        pods: List of pod dicts from oc_get_pods()
        output_dir: Output directory
    """
    namespace = settings.openshift_namespace
    pods_dir = output_dir / "pods"

    for pod in pods:
        pod_name = pod["name"]

        # List of containers to try collecting logs from
        containers = [
            ("backstage-backend", f"{pod_name}-backstage.log"),
            ("install-dynamic-plugins", f"{pod_name}-init.log"),
            ("postgresql", f"{pod_name}-postgres.log"),
            ("ansible-dev-tools", f"{pod_name}-devtools.log"),
        ]

        # Collect logs from each container (ignore errors if container doesn't exist)
        for container_name, log_file in containers:
            try:
                logs = oc_get_pod_logs(
                    pod_name=pod_name,
                    container=container_name,
                    namespace=namespace,
                )
                (pods_dir / log_file).write_text(logs)
            except Exception:
                # Container may not exist in this pod, skip
                pass

        # Describe pod
        try:
            describe = oc_describe_pod(pod_name=pod_name, namespace=namespace)
            (pods_dir / f"{pod_name}-describe.txt").write_text(describe)
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to describe pod {pod_name}: {e}[/yellow]")


def collect_events(settings: Settings, output_dir: Path) -> None:
    """Collect cluster events.

    Args:
        settings: Application settings
        output_dir: Output directory
    """
    namespace = settings.openshift_namespace
    events_dir = output_dir / "events"

    try:
        events = oc_get_events(namespace=namespace)
        (events_dir / "namespace-events.txt").write_text(events)
    except Exception as e:
        console.print(f"[yellow]Warning: Failed to collect events: {e}[/yellow]")


def collect_helm_status(settings: Settings, output_dir: Path) -> None:
    """Collect Helm release status.

    Args:
        settings: Application settings
        output_dir: Output directory
    """
    release_name = settings.helm_release_name
    namespace = settings.openshift_namespace
    helm_dir = output_dir / "helm"

    # Get Helm status
    try:
        status = helm_status(release_name=release_name, namespace=namespace)
        (helm_dir / "status.txt").write_text(status)
    except Exception as e:
        console.print(f"[yellow]Warning: Failed to get Helm status: {e}[/yellow]")

    # Get Helm values
    try:
        values = helm_get_values(release_name=release_name, namespace=namespace)
        (helm_dir / "values.yaml").write_text(values)
    except Exception as e:
        console.print(f"[yellow]Warning: Failed to get Helm values: {e}[/yellow]")


def collect_logs_command(
    settings: Settings,
    output_dir: Optional[Path] = None,
) -> Path:
    """Execute log collection workflow.

    Args:
        settings: Application settings
        output_dir: Output directory override

    Returns:
        Path to output directory

    Raises:
        LogCollectionError: If collection fails
    """
    print_header(f"Collecting Logs: {settings.helm_release_name}")

    # Create output directory
    try:
        log_dir = create_output_directory(output_dir)
        print_info(f"Output directory: {log_dir}")
        console.print()
    except Exception as e:
        raise LogCollectionError(f"Failed to create output directory: {e}") from e

    # Get pods
    try:
        pods = oc_get_pods(namespace=settings.openshift_namespace)
        if not pods:
            console.print("[yellow]Warning: No pods found in namespace[/yellow]")
    except Exception as e:
        raise LogCollectionError(f"Failed to get pods: {e}") from e

    # Collect logs with progress bar
    with create_progress() as progress:
        task = progress.add_task("Collecting logs...", total=4)

        # Step 1: Pod logs
        progress.update(task, description="Collecting pod logs...")
        try:
            collect_pod_logs(settings, pods, log_dir)
            progress.update(task, advance=1)
        except Exception as e:
            console.print(f"[yellow]Warning: Some pod logs failed to collect: {e}[/yellow]")
            progress.update(task, advance=1)

        # Step 2: Events
        progress.update(task, description="Collecting events...")
        try:
            collect_events(settings, log_dir)
            progress.update(task, advance=1)
        except Exception as e:
            console.print(f"[yellow]Warning: Events collection failed: {e}[/yellow]")
            progress.update(task, advance=1)

        # Step 3: Helm status
        progress.update(task, description="Collecting Helm status...")
        try:
            collect_helm_status(settings, log_dir)
            progress.update(task, advance=1)
        except Exception as e:
            console.print(f"[yellow]Warning: Helm status collection failed: {e}[/yellow]")
            progress.update(task, advance=1)

        # Complete
        progress.update(task, description="Collection complete", advance=1)

    console.print()
    print_success("Log collection completed!")
    print_info(f"Logs saved to: {log_dir}")

    return log_dir

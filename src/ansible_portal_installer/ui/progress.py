"""Progress tracking UI components."""

from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich.spinner import Spinner

from .console import console


def create_progress() -> Progress:
    """Create a progress bar for tracking tasks.

    Returns:
        Progress instance
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def create_spinner(text: str) -> Spinner:
    """Create a spinner for indeterminate operations.

    Args:
        text: Spinner text

    Returns:
        Spinner instance
    """
    return Spinner("dots", text=text)

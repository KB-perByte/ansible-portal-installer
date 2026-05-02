"""Rich console wrapper for consistent output."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


console = Console()


def print_header(title: str) -> None:
    """Print a styled header.

    Args:
        title: Header title
    """
    console.print()
    console.rule(f"[bold blue]{title}[/bold blue]")
    console.print()


def print_success(message: str) -> None:
    """Print a success message.

    Args:
        message: Success message
    """
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    """Print an error message.

    Args:
        message: Error message
    """
    console.print(f"[red]✗[/red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message.

    Args:
        message: Warning message
    """
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_info(message: str) -> None:
    """Print an info message.

    Args:
        message: Info message
    """
    console.print(f"[blue]ℹ[/blue] {message}")


def print_panel(content: str, title: str, style: str = "blue") -> None:
    """Print content in a styled panel.

    Args:
        content: Panel content
        title: Panel title
        style: Panel border style
    """
    console.print(Panel(content, title=title, border_style=style))


def print_table(data: list[tuple[str, str]], title: str | None = None) -> None:
    """Print a two-column table.

    Args:
        data: List of (key, value) tuples
        title: Optional table title
    """
    table = Table(title=title, show_header=False, box=None)
    table.add_column("Key", style="cyan", width=30)
    table.add_column("Value", style="white")

    for key, value in data:
        table.add_row(key, str(value))

    console.print(table)


def print_status_table(items: dict[str, bool]) -> None:
    """Print a status table with checkmarks.

    Args:
        items: Dictionary of item names and their completion status
    """
    table = Table(show_header=False, box=None)
    table.add_column("Status", width=5)
    table.add_column("Item")

    for name, completed in items.items():
        status = "[green]✓[/green]" if completed else "[dim]○[/dim]"
        table.add_row(status, name)

    console.print(table)

"""Interactive prompts for user input."""

from typing import Optional

from rich.prompt import Prompt, Confirm

from .console import console


def confirm(message: str, default: bool = False) -> bool:
    """Prompt for yes/no confirmation.

    Args:
        message: Confirmation message
        default: Default value if user presses Enter

    Returns:
        True if confirmed, False otherwise
    """
    return Confirm.ask(message, default=default, console=console)


def prompt_text(
    message: str,
    default: Optional[str] = None,
    password: bool = False,
) -> str:
    """Prompt for text input.

    Args:
        message: Prompt message
        default: Default value
        password: Whether to hide input

    Returns:
        User input
    """
    return Prompt.ask(
        message,
        default=default,
        password=password,
        console=console,
    )


def prompt_choice(
    message: str,
    choices: list[str],
    default: Optional[str] = None,
) -> str:
    """Prompt for a choice from a list.

    Args:
        message: Prompt message
        choices: List of valid choices
        default: Default choice

    Returns:
        Selected choice
    """
    return Prompt.ask(
        message,
        choices=choices,
        default=default,
        console=console,
    )

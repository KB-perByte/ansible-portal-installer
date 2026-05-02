# Contributing to Ansible Portal Installer

Thank you for your interest in contributing to the Ansible Portal Installer!

## Development Setup

```bash
# Clone the repository
git clone <repository-url>
cd ansible-portal-installer

# Run installation script
./install.sh

# Or manual setup
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Code Style

This project uses:
- **black** for code formatting
- **ruff** for linting
- **mypy** for type checking

```bash
# Format code
make format

# Run linter
make lint

# Type check
make type-check

# Run all checks
make check
```

## Testing

```bash
# Run tests (when implemented)
make test

# With coverage
pytest --cov=ansible_portal_installer
```

## Adding New Features

### Adding a New Installer Type

1. Create installer class in `src/ansible_portal_installer/installers/`:

```python
from .base import BaseInstaller

class MyInstaller(BaseInstaller):
    def install(self) -> None:
        """Install implementation."""
        pass

    def verify(self) -> bool:
        """Verify implementation."""
        pass

    def uninstall(self) -> None:
        """Uninstall implementation."""
        pass

    def get_status(self) -> dict[str, any]:
        """Get status implementation."""
        pass
```

2. Add CLI command in `src/ansible_portal_installer/cli.py`:

```python
@cli.command()
def my_deploy():
    """Deploy using my installer."""
    installer = MyInstaller(settings, context)
    installer.install()
```

3. Update documentation

### Adding a New Action

1. Create action in `src/ansible_portal_installer/actions/`:

```python
def my_action(settings: Settings, context: InstallContext) -> None:
    """My action implementation."""
    pass
```

2. Use in installers or CLI commands

## Project Structure

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture information.

## Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run code quality checks: `make check`
5. Update documentation if needed
6. Submit pull request with clear description

## Code Review

All submissions require review. We use GitHub pull requests for this purpose.

## Questions?

Feel free to open an issue for questions or discussion.

# Ansible Portal Installer

A comprehensive TUI (Text User Interface) installer for Ansible Automation Portal that streamlines the build, publish, and deployment workflow.

## Features

- **Build**: Build dynamic plugins from ansible-backstage-plugins
- **Publish**: Push plugin container images to registries (Quay.io, etc.)
- **Deploy (Helm)**: Deploy to OpenShift using Helm charts
- **Interactive TUI**: Rich text-based interface with progress tracking
- **Environment Configuration**: `.env` file support for all configurations
- **Extensible**: Architecture ready for RHEL and Operator installation modes

## Installation

```bash
# Clone the repository
cd ansible-portal-installer

# Install dependencies (in virtual environment)
python -m venv venv
source venv/bin/activate
pip install -e .

# For development
pip install -e ".[dev]"
```

## Quick Start

### 1. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
vim .env
```

### 2. Run the Installer

```bash
# Interactive mode (TUI)
ansible-portal-installer

# Or specific commands
ansible-portal-installer plugins build
ansible-portal-installer plugins publish
ansible-portal-installer helm deploy
```

## Commands

### Plugin Commands (`plugins`)

#### `plugins build`

Build dynamic plugins from source.

```bash
ansible-portal-installer plugins build [--type portal|platform|all]
```

**What it does:**
- Links ansible-backstage-plugins repository
- Runs `yarn install` and `yarn build`
- Executes `build.sh` to generate dynamic plugins
- Validates plugin output in `dynamic-plugins/` directory

#### `plugins publish`

Build and push plugin container image to registry.

```bash
ansible-portal-installer plugins publish [--registry quay.io] [--tag dev-latest]
```

**What it does:**
- Builds plugins (if not already built)
- Authenticates with container registry
- Builds container image using `Containerfile`
- Pushes image to registry
- Outputs the full image reference

### Helm Commands (`helm`)

#### `helm deploy`

Deploy Ansible Portal to OpenShift using Helm.

```bash
ansible-portal-installer helm deploy [--namespace my-namespace] [--release my-portal]
```

**What it does:**
- Validates OpenShift connection
- Creates secrets (AAP credentials, GitHub credentials, registry auth)
- Configures Helm values (cluster router, plugin image, OAuth settings)
- Deploys or upgrades Helm release
- Verifies pod status and routes
- Displays portal URL and next steps

### Deployment Commands (`deployment`)

#### `deployment verify`

Verify installation and configuration.

```bash
ansible-portal-installer deployment verify
```

#### `deployment status`

Check current deployment status.

```bash
ansible-portal-installer deployment status [--namespace my-namespace]
```

## Configuration

All configuration is managed through environment variables in the `.env` file. See [`.env.example`](.env.example) for all available options.

### Key Configuration Sections

1. **Build Configuration**: Paths to repositories, Node version
2. **Container Registry**: Registry credentials and image details
3. **OpenShift/Kubernetes**: Cluster connection details
4. **AAP Configuration**: Ansible Automation Platform OAuth and API settings
5. **GitHub Configuration**: SCM integration tokens and OAuth
6. **Helm Chart**: Chart path, release name, cluster settings

## Architecture

```
src/ansible_portal_installer/
├── __init__.py
├── cli.py                      # Click CLI entry point
├── constants.py                # Application constants
├── config/
│   ├── __init__.py
│   ├── settings.py             # Pydantic settings (loads from .env)
│   └── validation.py           # Configuration validation
├── core/
│   ├── __init__.py
│   ├── context.py              # Installation context
│   └── exceptions.py           # Custom exceptions
├── installers/
│   ├── __init__.py
│   ├── base.py                 # Base installer class
│   ├── helm.py                 # Helm deployment installer
│   ├── rhel.py                 # RHEL installer (future)
│   └── operator.py             # Operator installer (future)
├── actions/
│   ├── __init__.py
│   ├── build.py                # Plugin build action
│   ├── publish.py              # Container publish action
│   ├── deploy.py               # Deployment actions
│   └── verify.py               # Verification actions
├── ui/
│   ├── __init__.py
│   ├── console.py              # Rich console wrapper
│   ├── prompts.py              # Interactive prompts
│   └── progress.py             # Progress tracking
└── utils/
    ├── __init__.py
    ├── shell.py                # Shell command execution
    ├── git.py                  # Git operations
    ├── container.py            # Podman/Docker operations
    ├── openshift.py            # OpenShift CLI operations
    └── helm.py                 # Helm operations
```

## Extending for New Installation Types

The installer is designed to be easily extensible. To add a new installation type (e.g., RHEL or Operator):

1. Create a new installer class in `src/ansible_portal_installer/installers/`:

```python
from .base import BaseInstaller

class RHELInstaller(BaseInstaller):
    """RHEL package installation."""

    def install(self) -> None:
        """Install portal on RHEL."""
        # Implementation here
        pass
```

2. Register the installer in CLI commands:

```python
@cli.command()
def rhel_deploy():
    """Deploy Ansible Portal on RHEL."""
    installer = RHELInstaller(config)
    installer.install()
```

## Development

### Project Structure

The project follows the ansible-navigator pattern with clear separation of concerns:

- **Config**: Environment and settings management
- **Core**: Shared context and exceptions
- **Installers**: Installation strategy implementations
- **Actions**: Discrete operations (build, publish, etc.)
- **UI**: User interface components
- **Utils**: Utility functions and helpers

### Running Tests

```bash
pytest
pytest --cov=ansible_portal_installer
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## Troubleshooting

### Build failures

- Ensure `ansible-backstage-plugins` is linked correctly
- Check Node.js version (requires 20 or 22)
- Verify `yarn` is enabled via `corepack enable`

### Registry push failures

- Verify registry credentials in `.env`
- Ensure repository exists and is accessible
- Check network connectivity to registry

### Helm deployment failures

- Verify OpenShift token is valid: `oc whoami`
- Check namespace exists: `oc get namespace <namespace>`
- Ensure secrets are created correctly
- Verify OAuth redirect URIs match actual portal route

## License

Apache-2.0

## Support

For issues and questions, see:
- [Helm Chart Developer Guide](../ansible-rhdh-plugins/docs/guides/helm-chart-developer-guide.md)
- [ansible-backstage-plugins](https://github.com/ansible/ansible-backstage-plugins)
- [ansible-rhdh-plugins](https://github.com/ansible/ansible-rhdh-plugins)

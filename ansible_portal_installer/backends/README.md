# Deployment Backends

This directory contains pluggable deployment backends for `ansible-portal-installer`. Each backend implements a different deployment strategy for the Ansible Automation Portal.

## Architecture

```
backends/
├── base.py              # Abstract base classes (DeploymentBackend, BuildBackend)
├── __init__.py          # BackendFactory and BackendType enum
├── helm/                # Helm backend (Kubernetes/OpenShift)
│   ├── __init__.py
│   ├── client.py        # HelmClient wrapper
│   └── deployer.py      # HelmDeployer implementation
├── operator/            # Future: Operator-based deployment
│   └── deployer.py
└── rhel/                # Future: RHEL package installation
    └── deployer.py
```

## Available Backends

### Helm (Implemented)

Deploy to Kubernetes/OpenShift using Helm charts.

**Features:**
- OCI plugin image building and pushing
- OpenShift internal registry support
- Helm chart deployment with dependency management
- Health checks for pods, routes, and services
- Diagnostic log collection

**Usage:**
```bash
ansible-portal-installer deploy --backend helm \
  --namespace my-ns \
  --aap-host https://aap.example.com \
  --aap-token <token> \
  --oauth-client-id <id> \
  --oauth-client-secret <secret>
```

### Operator (Planned)

Deploy using OpenShift Operators and Custom Resources.

**Features (planned):**
- Operator Lifecycle Manager integration
- Custom Resource-based configuration
- Operator-managed upgrades
- OpenShift-native deployment

**Status:** Not yet implemented

### RHEL (Planned)

Install as RHEL packages on traditional servers.

**Features (planned):**
- RPM package installation
- systemd service management
- Traditional server deployment (non-containerized)
- RHEL/Fedora compatibility

**Status:** Not yet implemented

## Adding a New Backend

To add a new deployment backend:

### 1. Create Backend Directory

```bash
mkdir -p ansible_portal_installer/backends/mybackend
touch ansible_portal_installer/backends/mybackend/__init__.py
touch ansible_portal_installer/backends/mybackend/deployer.py
```

### 2. Implement DeploymentBackend Interface

```python
# ansible_portal_installer/backends/mybackend/deployer.py

from pathlib import Path
from typing import Any, Dict, Optional

from ..base import DeploymentBackend
from ...config import DeploymentConfig


class MyBackendDeployer(DeploymentBackend):
    """My custom deployment backend."""

    def deploy(
        self,
        config: DeploymentConfig,
        skip_build: bool = False,
        timeout: str = "10m",
    ) -> Dict[str, Any]:
        """Deploy the portal."""
        # Implementation here
        return {
            "url": "https://portal.example.com",
            "username": "admin",
            "password": "generated-password",
            "namespace": config.namespace,
            "release": config.release_name,
        }

    def upgrade(self, namespace: str, release_name: str, **kwargs) -> None:
        """Upgrade existing deployment."""
        # Implementation here
        pass

    def teardown(self, namespace: str, release_name: str, clean_data: bool = False) -> None:
        """Remove deployment."""
        # Implementation here
        pass

    def get_status(self, namespace: str, release_name: str) -> Optional[Dict[str, Any]]:
        """Get deployment status."""
        # Implementation here
        return None

    def get_values(self, namespace: str, release_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration values."""
        # Implementation here
        return None

    def validate_deployment(
        self,
        namespace: str,
        release_name: Optional[str] = None,
        verbose: bool = False,
        timeout: int = 300,
    ) -> bool:
        """Validate deployment health."""
        # Implementation here
        return True

    def collect_logs(
        self,
        namespace: str,
        release_name: Optional[str],
        output_dir: Path,
        tail_lines: int = 1000,
    ) -> None:
        """Collect diagnostic logs."""
        # Implementation here
        pass
```

### 3. Register Backend in Factory

```python
# ansible_portal_installer/backends/__init__.py

class BackendType(str, Enum):
    HELM = "helm"
    OPERATOR = "operator"
    RHEL = "rhel"
    MYBACKEND = "mybackend"  # Add your backend


class BackendFactory:
    @staticmethod
    def create(backend_type: str | BackendType) -> DeploymentBackend:
        # ... existing code ...

        elif backend_type == BackendType.MYBACKEND:
            from .mybackend import MyBackendDeployer
            return MyBackendDeployer()

        # ... rest of code ...
```

### 4. Update list_implemented_backends()

```python
@staticmethod
def list_implemented_backends() -> list[str]:
    """List only implemented backend types."""
    return [
        BackendType.HELM.value,
        BackendType.MYBACKEND.value,  # Add here
    ]
```

### 5. Test Your Backend

```bash
ansible-portal-installer deploy --backend mybackend --namespace test-ns ...
```

## Design Principles

1. **Backend Independence**: Each backend is self-contained and doesn't depend on others
2. **Shared Utilities**: Common code (k8s, registry) is in the parent package
3. **Type Safety**: All backends implement the same interface with type hints
4. **Graceful Degradation**: Unimplemented backends return NotImplementedError
5. **Configuration Flexibility**: DeploymentConfig supports all backend types

## Backend Selection

Backends can be selected via:

1. **CLI flag**: `--backend helm`
2. **Environment variable**: `export DEPLOYMENT_BACKEND=helm`
3. **Default**: `helm` (if not specified)

## Testing

Each backend should include:

- Unit tests for core functionality
- Integration tests for actual deployments
- Mock tests for external dependencies

```bash
# Test backend factory
python3 -c "from ansible_portal_installer.backends import BackendFactory; \
  print(BackendFactory.list_backends())"

# Test backend creation
python3 -c "from ansible_portal_installer.backends import BackendFactory; \
  backend = BackendFactory.create('helm'); \
  print(type(backend).__name__)"
```

## Future Enhancements

- **Multi-backend deployments**: Deploy to multiple targets simultaneously
- **Backend migration**: Migrate from one backend to another
- **Custom backends**: Plugin system for third-party backends
- **Backend-specific validation**: Different health checks per backend

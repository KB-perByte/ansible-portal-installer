# ansible-portal-installer Architecture

## Overview

The `ansible-portal-installer` is a Python CLI tool that deploys the Ansible Automation Portal using a **pluggable backend architecture**. This design allows for multiple deployment strategies while maintaining a consistent user interface.

## Design Philosophy

1. **Backend Independence**: Each deployment backend is self-contained
2. **Single Responsibility**: Backends focus only on their deployment strategy
3. **Interface Consistency**: All backends implement the same abstract interface
4. **Easy Extension**: New backends can be added without modifying existing code
5. **Graceful Degradation**: Unimplemented backends provide clear error messages

## Project Structure

```
ansible-portal-installer/
├── pyproject.toml                   # Project metadata & dependencies
├── README.md                        # User-facing documentation
├── ARCHITECTURE.md                  # This file
├── ansible_portal_installer/
│   ├── __init__.py                  # Package version
│   ├── cli.py                       # Main CLI entry point
│   │
│   ├── config.py                    # Pydantic configuration models
│   │   ├── RegistryConfig           # Container registry settings
│   │   ├── AAPConfig                # AAP connection settings
│   │   ├── SCMConfig                # GitHub/GitLab settings
│   │   ├── DeploymentConfig         # Deployment parameters
│   │   └── PortalInstallerSettings  # Global settings from env vars
│   │
│   ├── backends/                    # Pluggable deployment backends
│   │   ├── README.md                # Backend development guide
│   │   ├── __init__.py              # BackendFactory & BackendType
│   │   ├── base.py                  # Abstract base classes
│   │   │   ├── DeploymentBackend    # Interface for deployment ops
│   │   │   └── BuildBackend         # Interface for build ops
│   │   │
│   │   ├── helm/                    # Helm backend (Kubernetes/OpenShift)
│   │   │   ├── __init__.py
│   │   │   ├── client.py            # Helm CLI wrapper
│   │   │   └── deployer.py          # HelmDeployer implementation
│   │   │
│   │   ├── operator/                # Future: Operator backend
│   │   │   └── deployer.py          # OperatorDeployer (not implemented)
│   │   │
│   │   └── rhel/                    # Future: RHEL package backend
│   │       └── deployer.py          # RHELDeployer (not implemented)
│   │
│   ├── commands/                    # CLI command implementations
│   │   ├── __init__.py
│   │   ├── build.py                 # Build plugin OCI image
│   │   ├── deploy.py                # Deploy portal (backend-aware)
│   │   ├── upgrade.py               # Upgrade deployment (backend-aware)
│   │   ├── validate.py              # Health checks (backend-aware)
│   │   ├── collect_logs.py          # Diagnostic logs (backend-aware)
│   │   └── teardown.py              # Remove deployment (backend-aware)
│   │
│   ├── k8s.py                       # Kubernetes client wrappers
│   │   ├── KubernetesClient         # Python K8s API wrapper
│   │   └── OpenShiftClient          # oc CLI wrapper
│   │
│   ├── registry.py                  # OCI registry client
│   │   └── RegistryClient           # Image push/pull operations
│   │
│   └── validation.py                # Health check system
│       └── HealthChecker            # Validation logic
│
└── tests/                           # Test suite
    └── test_config.py               # Configuration validation tests
```

## Core Abstractions

### DeploymentBackend Interface

All deployment backends implement this interface:

```python
class DeploymentBackend(ABC):
    @abstractmethod
    def deploy(config: DeploymentConfig, skip_build: bool) -> Dict[str, Any]:
        """Deploy the portal. Returns deployment details."""

    @abstractmethod
    def upgrade(namespace: str, release_name: str, **kwargs) -> None:
        """Upgrade existing deployment."""

    @abstractmethod
    def teardown(namespace: str, release_name: str, clean_data: bool) -> None:
        """Remove deployment."""

    @abstractmethod
    def get_status(namespace: str, release_name: str) -> Optional[Dict]:
        """Get deployment status."""

    @abstractmethod
    def get_values(namespace: str, release_name: str) -> Optional[Dict]:
        """Get configuration values."""

    @abstractmethod
    def validate_deployment(namespace: str, ...) -> bool:
        """Run health checks."""

    @abstractmethod
    def collect_logs(namespace: str, output_dir: Path, ...) -> None:
        """Collect diagnostic logs."""
```

### BackendFactory

The factory pattern provides backend selection:

```python
# Create backend from type
deployer = BackendFactory.create("helm")

# List all backends
BackendFactory.list_backends()
# => ['helm', 'operator', 'rhel']

# List implemented backends
BackendFactory.list_implemented_backends()
# => ['helm']
```

## Data Flow

### Deployment Flow

```
User Input (CLI args + env vars)
    ↓
Click Command Parsing
    ↓
Configuration Objects (Pydantic models)
    ├── DeploymentConfig
    ├── AAPConfig
    ├── SCMConfig
    └── RegistryConfig
    ↓
BackendFactory.create(backend_type)
    ↓
Backend.deploy(config)
    ├── Validate prerequisites
    ├── Build plugins (if needed)
    ├── Create secrets
    ├── Deploy via backend-specific method
    └── Return deployment details
    ↓
Display results to user
```

### Backend Selection Priority

1. CLI flag: `--backend helm`
2. Environment variable: `DEPLOYMENT_BACKEND=helm`
3. Default: `helm`

## Supported Backends

### Helm Backend (Implemented)

**Target**: Kubernetes/OpenShift clusters  
**Method**: Helm charts with OCI plugin images  
**Status**: ✅ Fully implemented

**Features**:
- OCI plugin image building
- OpenShift internal registry support
- Helm chart dependency management
- Pod/route/service health checks
- Comprehensive log collection

**Usage**:
```bash
ansible-portal-installer deploy \
  --backend helm \
  --namespace my-ns \
  --aap-host https://aap.example.com \
  --aap-token <token> \
  --oauth-client-id <id> \
  --oauth-client-secret <secret>
```

### Operator Backend (Planned)

**Target**: OpenShift clusters with OLM  
**Method**: Custom Resources + Operator  
**Status**: ⏳ Not yet implemented

**Planned Features**:
- Operator Lifecycle Manager integration
- Custom Resource-based configuration
- Operator-managed upgrades
- OpenShift-native deployment

### RHEL Backend (Planned)

**Target**: Traditional RHEL/Fedora servers  
**Method**: RPM packages + systemd services  
**Status**: ⏳ Not yet implemented

**Planned Features**:
- RPM package installation
- systemd service management
- Non-containerized deployment
- Traditional server architecture

## Configuration System

### Pydantic Models

All configuration uses Pydantic for type safety and validation:

```python
class DeploymentConfig(BaseModel):
    namespace: str                      # Target namespace/location
    release_name: str                   # Deployment identifier
    backend: str                        # Backend type
    chart_path: Path                    # Config path
    plugins_path: Path                  # Plugin source
    registry: Optional[RegistryConfig]  # Registry config
    aap: Optional[AAPConfig]            # AAP config
    scm: Optional[SCMConfig]            # SCM config
    # ... more fields
```

### Environment Variable Loading

Settings are automatically loaded from:

1. `.env` file in current directory
2. System environment variables
3. CLI flags (highest priority)

Example `.env`:
```bash
DEPLOYMENT_BACKEND=helm
OCP_NAMESPACE=my-portal-dev
AAP_HOST_URL=https://aap.example.com
AAP_TOKEN=my-token
OAUTH_CLIENT_ID=my-client-id
OAUTH_CLIENT_SECRET=my-secret
```

## Extension Points

### Adding a New Backend

1. **Create backend directory**:
   ```bash
   mkdir -p ansible_portal_installer/backends/mybackend
   ```

2. **Implement DeploymentBackend**:
   ```python
   # ansible_portal_installer/backends/mybackend/deployer.py
   from ..base import DeploymentBackend
   
   class MyBackendDeployer(DeploymentBackend):
       def deploy(self, config, skip_build):
           # Implementation
           pass
       # ... implement other methods
   ```

3. **Register in BackendFactory**:
   ```python
   # backends/__init__.py
   class BackendType(str, Enum):
       MYBACKEND = "mybackend"
   
   class BackendFactory:
       @staticmethod
       def create(backend_type):
           if backend_type == BackendType.MYBACKEND:
               from .mybackend import MyBackendDeployer
               return MyBackendDeployer()
   ```

4. **No changes needed** to commands or CLI!

### Adding a New Command

Commands use backends via the factory:

```python
@click.command()
@click.option("--backend", type=click.Choice([...]))
def my_command(backend: str, ...):
    deployer = BackendFactory.create(backend)
    deployer.my_operation(...)
```

## Testing Strategy

### Unit Tests
- Configuration validation
- Backend factory
- Individual backend methods (mocked)

### Integration Tests
- Full deployment workflows
- Health check systems
- Log collection

### Backend-Specific Tests
- Each backend has its own test suite
- Mock external dependencies (K8s API, Helm CLI)

## Dependencies

### Core
- **click**: CLI framework
- **rich**: Terminal UI/progress
- **pydantic**: Configuration models
- **pyyaml**: YAML parsing

### Kubernetes/OpenShift
- **kubernetes**: Python K8s API client
- **httpx**: HTTP client (registry ops)

### Security
- **bcrypt**: Password hashing

### Build (Dev)
- **pytest**: Testing
- **mypy**: Type checking
- **ruff**: Linting
- **black**: Code formatting

## Design Decisions

### Why Pluggable Backends?

**Problem**: Different deployment targets (K8s, Operators, RHEL) require different approaches.

**Solution**: Abstract interface + factory pattern allows:
- Adding new backends without modifying existing code
- Testing backends in isolation
- Swapping backends via configuration
- Backend-specific optimizations

### Why Pydantic for Config?

- Type safety with runtime validation
- Automatic env var loading
- Clear error messages for invalid config
- Documentation via field descriptions

### Why Direct K8s API vs oc CLI?

- **Structured data**: Parse JSON, not text
- **Type safety**: Python objects, not strings
- **Error handling**: Exceptions, not exit codes
- **Performance**: No subprocess overhead

(Still use `oc` for OpenShift-specific operations like routes)

## Future Enhancements

### Planned Features
- **Multi-backend deployments**: Deploy to multiple targets simultaneously
- **Backend migration**: Migrate from Helm to Operator
- **Custom backends**: Plugin system for third-party backends
- **Interactive wizard**: Guided deployment setup
- **Configuration templates**: Pre-configured deployment profiles

### Extensibility
- Backend-specific health checks
- Backend-specific log formats
- Backend-specific upgrade strategies
- Backend-specific validation rules

## Contributing

When adding new features:

1. **Backend-agnostic features**: Add to `DeploymentBackend` interface
2. **Backend-specific features**: Add to specific backend implementations
3. **New backends**: Follow the extension guide in `backends/README.md`
4. **Tests**: Add tests for new functionality
5. **Documentation**: Update relevant docs (README, ARCHITECTURE, etc.)

## Resources

- [README.md](README.md) - User documentation
- [backends/README.md](ansible_portal_installer/backends/README.md) - Backend development guide
- [config.py](ansible_portal_installer/config.py) - Configuration reference
- [GitHub Repository](https://github.com/KB-perByte/ansible-portal-installer)

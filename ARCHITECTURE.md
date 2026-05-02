# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  Ansible Portal Installer                        │
│                         (CLI/TUI)                                │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐     ┌──────────────┐
│   Build      │      │   Publish    │     │   Deploy     │
│   Actions    │      │   Actions    │     │   Actions    │
└──────────────┘      └──────────────┘     └──────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐     ┌──────────────┐
│   Plugins    │──────▶│  Container   │──────▶│  OpenShift  │
│   Source     │       │  Registry    │       │  Cluster    │
└──────────────┘      └──────────────┘     └──────────────┘
```

## Module Structure

```
ansible_portal_installer/
│
├── cli.py                    # Click-based CLI entry point
│   ├── Commands:
│   │   ├── build              # Build plugins
│   │   ├── publish            # Publish container image
│   │   ├── helm-deploy        # Deploy with Helm
│   │   ├── full-deploy        # Complete workflow
│   │   ├── verify             # Verify installation
│   │   ├── status             # Check deployment status
│   │   └── cleanup            # Remove deployment
│
├── config/                   # Configuration management
│   ├── settings.py             # Pydantic settings (reads .env)
│   └── validation.py           # Configuration validation
│
├── core/                     # Core components
│   ├── context.py              # Installation state tracking
│   └── exceptions.py           # Custom exceptions
│
├── actions/                  # Discrete operations
│   ├── build.py                # Plugin build logic
│   ├── publish.py              # Container publish logic
│   ├── deploy.py               # Deployment logic
│   └── verify.py               # Verification logic
│
├── installers/               # Installation strategies
│   ├── base.py                 # Base installer interface
│   ├── helm.py                 # Helm installer (implemented)
│   ├── rhel.py                 # RHEL installer (future)
│   └── operator.py             # Operator installer (future)
│
├── ui/                       # User interface components
│   ├── console.py              # Rich console wrapper
│   ├── progress.py             # Progress bars/spinners
│   └── prompts.py              # Interactive prompts
│
└── utils/                    # Utility functions
    ├── shell.py                # Command execution
    ├── git.py                  # Git operations
    ├── container.py            # Podman/Docker operations
    ├── openshift.py            # OpenShift CLI operations
    └── helm.py                 # Helm operations
```

## Data Flow

### Build Flow

```
1. User runs: ansible-portal-installer build

2. Load configuration from .env
   ├── Validate paths exist
   ├── Check Node.js version
   └── Verify build script

3. Setup symlink
   ansible-rhdh-plugins/ansible-backstage-plugins
   -> ~/Work/ansible-portal/ansible-backstage-plugins

4. Run build script
   ├── cd ansible-rhdh-plugins
   ├── ./build.sh
   └── Generates: dynamic-plugins/

5. Update context
   ├── Mark build completed
   ├── Track plugins built
   └── Store output directory
```

### Publish Flow

```
1. User runs: ansible-portal-installer publish

2. Build plugins (if not already built)

3. Authenticate with registry
   podman login quay.io

4. Build container image
   ├── cd dynamic-plugins/
   ├── podman build -f Containerfile
   └── Tag: quay.io/user/ansible-portal-plugins:dev-YYYYMMDD

5. Push to registry
   podman push quay.io/user/ansible-portal-plugins:dev-YYYYMMDD

6. Update context
   ├── Mark publish completed
   └── Store image reference
```

### Deploy Flow

```
1. User runs: ansible-portal-installer helm-deploy

2. Publish image (if OCI mode and not already published)

3. Connect to OpenShift
   oc login --server=... --token=...

4. Setup namespace
   ├── Check if exists
   ├── Create if needed
   └── Switch to namespace

5. Create secrets
   ├── secrets-rhaap-portal (AAP credentials)
   ├── secrets-scm (GitHub credentials)
   └── registry pull secret (if OCI mode)

6. Deploy with Helm
   ├── Build Helm values
   ├── helm upgrade --install
   └── Wait for deployment

7. Verify deployment
   ├── Check pods status
   ├── Get route URL
   └── Display next steps

8. Update context
   ├── Mark deploy completed
   ├── Store release name
   └── Store portal route
```

## Configuration System

### Environment Variables -> Pydantic Settings

```python
.env file
   |
Settings (Pydantic)
   |
Validation
   |
Used by Actions/Installers
```

**Benefits:**
- Type safety with Pydantic
- Automatic validation
- Sensible defaults
- Environment variable precedence

## Extensibility Design

### Adding New Installation Type (e.g., RHEL)

1. **Create installer class**:
   ```python
   # src/ansible_portal_installer/installers/rhel.py
   class RHELInstaller(BaseInstaller):
       def install(self) -> None:
           # RHEL-specific installation logic
           pass
   ```

2. **Add CLI command**:
   ```python
   # src/ansible_portal_installer/cli.py
   @cli.command()
   def rhel_deploy():
       installer = RHELInstaller(settings, context)
       installer.install()
   ```

3. **Add configuration** (if needed):
   ```python
   # src/ansible_portal_installer/config/settings.py
   rhel_specific_setting: str = Field(...)
   ```

### Adding New Action

1. **Create action module**:
   ```python
   # src/ansible_portal_installer/actions/custom.py
   def custom_action(settings: Settings, context: InstallContext) -> None:
       # Action logic
       pass
   ```

2. **Use in CLI or installer**:
   ```python
   from .actions import custom_action
   custom_action(settings, context)
   ```

## Error Handling Strategy

```
User Action
    |
Try:
    Validate Configuration
        |
    Execute Operation
        |
    Update Context
        |
    Display Success
Except:
    ConfigurationError -> Show config issues
    BuildError -> Show build failures
    PublishError -> Show registry issues
    DeployError -> Show deployment issues
    InstallerError -> Show general errors
    KeyboardInterrupt -> Show cancellation
    Exception -> Show unexpected error (with stack trace if verbose)
```

## UI/UX Design

### Progress Tracking

- **Spinners** for indeterminate operations
- **Progress bars** for multi-step operations
- **Status icons** (✓, ✗, ⚠, ℹ) for clarity
- **Colors**:
  - Green for success
  - Red for errors
  - Yellow for warnings
  - Blue for info

### Interactive Prompts

- **Confirmations** for destructive operations
- **Skip confirmations** with `--yes` flag or `SKIP_CONFIRMATIONS=true`
- **Dry run mode** to preview actions

### Output Formatting

- **Headers** for sections
- **Panels** for important information
- **Tables** for status and configuration
- **Clean separation** between operations

## Testing Strategy (Future)

```
tests/
├── unit/
│   ├── test_config.py       # Configuration tests
│   ├── test_utils.py        # Utility function tests
│   └── test_actions.py      # Action logic tests
│
├── integration/
│   ├── test_build.py        # End-to-end build tests
│   ├── test_publish.py      # Registry integration tests
│   └── test_deploy.py       # Deployment tests (requires cluster)
│
└── fixtures/
    ├── .env.test            # Test environment
    └── mock_responses.py    # Mock API responses
```

## Security Considerations

1. **Secrets Management**:
   - Never log sensitive values
   - Use environment variables
   - Support for `.env` files (gitignored)

2. **Credential Handling**:
   - Tokens masked in output
   - Registry authentication ephemeral
   - OpenShift token never persisted

3. **Validation**:
   - Validate all inputs
   - Check file paths before operations
   - Confirm destructive actions

## Performance Considerations

1. **Caching**:
   - Settings cached with `@lru_cache`
   - Container tool auto-detection cached

2. **Parallel Operations**:
   - Future: parallel plugin builds
   - Future: concurrent image pushes

3. **Resource Management**:
   - Stream output for long operations
   - Clean up temporary resources
   - Reuse connections where possible

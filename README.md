# Ansible Portal Installer

A Python CLI tool for deploying the Ansible Automation Portal to OpenShift with locally-built plugins in OCI mode.

## Features

- 🚀 **Build & Deploy**: Build plugins from source and deploy to OpenShift
- 🐳 **OCI Mode**: Package plugins as OCI images (production-like workflow)
- ✅ **Health Checks**: Comprehensive validation of deployments
- 📋 **Log Collection**: Automated diagnostic log gathering
- 🔧 **Configuration Management**: Pydantic-based config with validation
- 🎨 **Rich CLI**: Beautiful terminal output with progress indicators

## Installation

### For Development

```bash
# Clone the repository
cd /home/kbperbyte/Work/ansible-portal/ansible-portal-installer

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Verify installation
ansible-portal-installer --version
```

### For Users (Future)

```bash
# Install from PyPI (when published)
pipx install ansible-portal-installer

# Or with pip
pip install ansible-portal-installer
```

## Prerequisites

### Required Tools

- **Python 3.9+**: Runtime environment
- **oc**: OpenShift CLI
- **helm**: Helm 3.x
- **podman**: Container tool
- **yarn**: Node.js package manager (for plugin builds)
- **htpasswd**: For generating password hashes (usually pre-installed)

### Required Access

- **OpenShift cluster**: With namespace-admin or cluster-admin permissions
- **AAP instance**: Running Ansible Automation Platform controller
- **Optional**: GitHub/GitLab accounts for SCM integrations

## Quick Start

### 1. Login to OpenShift

```bash
oc login <cluster-api-url>
oc new-project rhaap-portal-dev
```

### 2. Set Environment Variables

```bash
export AAP_HOST_URL="https://aap.example.com"
export AAP_TOKEN="<your-aap-token>"
export OAUTH_CLIENT_ID="<oauth-client-id>"
export OAUTH_CLIENT_SECRET="<oauth-client-secret>"
export OCP_NAMESPACE="rhaap-portal-dev"
```

### 3. Build Plugin Image

```bash
ansible-portal-installer build \
  --namespace rhaap-portal-dev \
  --plugins-path /path/to/ansible-rhdh-plugins
```

### 4. Deploy Portal (Coming Soon)

```bash
ansible-portal-installer deploy \
  --namespace rhaap-portal-dev \
  --aap-host "$AAP_HOST_URL" \
  --aap-token "$AAP_TOKEN"
```

## Commands

### `build`

Build and push Ansible Portal plugin OCI image.

```bash
ansible-portal-installer build [OPTIONS]

Options:
  -n, --namespace TEXT        OpenShift namespace [required]
  --plugins-path PATH         Path to ansible-rhdh-plugins repo
  --registry TEXT             Registry URL (default: auto-detect)
  --tag TEXT                  Image tag [default: dev]
  --release-name TEXT         Helm release name [default: rhaap-portal-dev]
  --skip-plugin-build         Skip plugin build (reuse tarballs)
  --help                      Show help message
```

**Example:**

```bash
ansible-portal-installer build \
  --namespace my-dev-ns \
  --plugins-path ~/work/ansible-rhdh-plugins \
  --tag feature-xyz
```

### `deploy` (WIP)

Deploy portal to OpenShift.

### `upgrade` (WIP)

Upgrade existing deployment with new plugin image.

### `validate` (WIP)

Run comprehensive health checks on deployment.

### `collect-logs` (WIP)

Collect diagnostic logs for troubleshooting.

### `teardown` (WIP)

Remove portal deployment.

## Configuration

### Environment Variables

All CLI options can be set via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `OCP_CLUSTER_URL` | OpenShift cluster API URL | - |
| `OCP_NAMESPACE` | Target namespace | - |
| `RELEASE_NAME` | Helm release name | `rhaap-portal-dev` |
| `CHART_PATH` | Path to Helm chart | `../ansible-portal-chart` |
| `PLUGINS_PATH` | Path to plugins repo | `.` |
| `AAP_HOST_URL` | AAP controller URL | - |
| `AAP_TOKEN` | AAP API token | - |
| `OAUTH_CLIENT_ID` | AAP OAuth client ID | - |
| `OAUTH_CLIENT_SECRET` | AAP OAuth client secret | - |
| `GITHUB_TOKEN` | GitHub PAT | - |
| `PLUGIN_REGISTRY` | Plugin registry URL | Auto-detect |
| `PLUGIN_IMAGE_TAG` | Plugin image tag | `dev` |
| `PORTAL_ADMIN_PASSWORD` | Initial admin password | Generated |
| `SKIP_PLUGIN_BUILD` | Skip plugin build | `false` |
| `VERBOSE` | Verbose output | `false` |

### `.env` File

Create a `.env` file in your working directory:

```bash
# OpenShift
OCP_NAMESPACE=rhaap-portal-dev
RELEASE_NAME=my-portal

# AAP
AAP_HOST_URL=https://aap.example.com
AAP_TOKEN=your-token-here
OAUTH_CLIENT_ID=your-client-id
OAUTH_CLIENT_SECRET=your-client-secret

# GitHub (optional)
GITHUB_TOKEN=ghp_...
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
```

The tool will automatically load this file.

## Development

### Project Structure

```
ansible-portal-installer/
├── pyproject.toml              # Project metadata and dependencies
├── ansible_portal_installer/
│   ├── __init__.py
│   ├── cli.py                  # Main CLI entry point
│   ├── config.py               # Pydantic configuration models
│   ├── k8s.py                  # Kubernetes client wrappers
│   ├── registry.py             # OCI registry operations
│   ├── helm.py                 # Helm operations
│   ├── validation.py           # Health checks
│   └── commands/               # Command implementations
│       ├── build.py
│       ├── deploy.py
│       ├── upgrade.py
│       ├── validate.py
│       └── collect_logs.py
├── tests/                      # Test suite
└── README.md
```

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov

# Type checking
mypy ansible_portal_installer

# Linting
ruff check ansible_portal_installer
black --check ansible_portal_installer
```

### Code Style

This project uses:
- **Black**: Code formatting (100 char line length)
- **Ruff**: Fast linting
- **MyPy**: Static type checking

```bash
# Format code
black ansible_portal_installer

# Fix linting issues
ruff check --fix ansible_portal_installer

# Type check
mypy ansible_portal_installer
```

## Architecture

### Key Design Decisions

1. **OCI Mode Only**: Standardized on OCI plugin delivery (no tarball mode)
2. **Pydantic Configuration**: Type-safe config with validation
3. **Rich Console Output**: Beautiful terminal UX with progress indicators
4. **Kubernetes Native**: Direct K8s API access via Python client
5. **Click CLI Framework**: Mature, battle-tested CLI framework

### Comparison with Bash Scripts

| Feature | Bash Scripts | Python CLI |
|---------|-------------|------------|
| **Error Handling** | Basic (`set -e`) | Structured exceptions |
| **Config Validation** | Manual checks | Pydantic models |
| **K8s Integration** | Parse `oc` output | Direct API access |
| **Testing** | Integration only | Unit + integration |
| **Code Reuse** | Script sourcing | Python modules |
| **Type Safety** | None | MyPy static typing |
| **Progress Indicators** | Basic echo | Rich progress bars |

## Roadmap

### v0.1.0 (Current)
- [x] Project structure and setup
- [x] Build command (plugin OCI image)
- [x] Configuration models
- [x] K8s client wrappers
- [x] Registry client
- [ ] Deploy command
- [ ] Validate command
- [ ] Collect-logs command

### v0.2.0
- [ ] Upgrade command
- [ ] Teardown command
- [ ] Comprehensive test suite
- [ ] CI/CD integration

### v0.3.0
- [ ] Interactive setup wizard
- [ ] Configuration templates
- [ ] Auto-completion support
- [ ] Performance optimizations

### v1.0.0
- [ ] Production-ready
- [ ] Published to PyPI
- [ ] Full documentation
- [ ] Migration guide from bash scripts

## Troubleshooting

### "Could not load Kubernetes config"

Make sure you're logged into OpenShift:
```bash
oc login <cluster-url>
oc whoami  # Verify
```

### "Missing required tools"

Install missing dependencies:
```bash
# Fedora/RHEL
sudo dnf install podman skopeo httpd-tools

# macOS
brew install podman skopeo httpd
```

### "Plugin build failed"

Ensure you have Node.js 20+ and yarn installed:
```bash
node --version  # Should be >= 20
yarn --version
```

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass (`pytest`)
5. Format code (`black`, `ruff`)
6. Submit a pull request

## License

Apache-2.0

## Related Documentation

- [OpenShift Deployment Guide](../ansible-rhdh-plugins/docs/deployment/openshift/dev-guide-ocp-deployment.md)
- [Tooling Specification](../ansible-rhdh-plugins/docs/deployment/openshift/spec-ocp-dev-tooling.md)
- [ADR: Plugin Delivery Standardization](../ansible-rhdh-plugins/docs/deployment/openshift/adr-ocp-plugin-delivery-standardization.md)

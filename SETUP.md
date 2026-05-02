# Setup Guide

Quick setup guide for the Ansible Portal Installer.

## Prerequisites

- Python 3.10 or higher
- Git
- Node.js 20 or 22
- Yarn (via corepack)
- Podman or Docker
- OpenShift CLI (`oc`)
- Helm 3.x

## Installation

### 1. Create Virtual Environment

```bash
cd ansible-portal-installer
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Package

```bash
# For development (editable install with dev dependencies)
pip install -e ".[dev]"

# Or for production
pip install -e .
```

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
vim .env  # or use your preferred editor
```

**Key configurations to update in `.env`:**

- **Paths**: Update repository paths to match your local setup
- **Registry**: Set your Quay.io (or other registry) credentials
- **OpenShift**: Add your cluster URL and token
- **AAP**: Configure Ansible Automation Platform OAuth and API credentials
- **GitHub**: Set up GitHub tokens and OAuth credentials
- **Helm**: Update cluster router base for your OpenShift cluster

### 4. Verify Installation

```bash
# Check that the CLI is available
ansible-portal-installer --version

# Check prerequisites
ansible-portal-installer verify
```

## Quick Start

### Option 1: Full Automated Deployment

```bash
# Run everything: build -> publish -> deploy
ansible-portal-installer full-deploy
```

This command will:
1. Build dynamic plugins from source
2. Build and push container image to registry
3. Deploy to OpenShift using Helm
4. Display portal URL and next steps

### Option 2: Step-by-Step

```bash
# Step 1: Build plugins
ansible-portal-installer build

# Step 2: Publish container image
ansible-portal-installer publish

# Step 3: Deploy with Helm
ansible-portal-installer helm-deploy
```

### Option 3: Individual Operations

```bash
# Just build plugins
ansible-portal-installer build --type portal

# Just publish (builds first if needed)
ansible-portal-installer publish --tag dev-latest

# Just deploy (publishes first if needed)
ansible-portal-installer helm-deploy --namespace my-namespace
```

## Troubleshooting

### Tool Not Found Errors

If you get "tool not found" errors, ensure all prerequisites are installed:

```bash
# Check tools
which yarn podman oc helm

# For Node.js/Yarn
nvm use 20.20.2  # or your preferred version
corepack enable

# For OpenShift CLI
oc version

# For Helm
helm version
```

### Configuration Errors

If you get configuration errors:

```bash
# Verify your .env file
cat .env

# Make sure paths exist
ls -la ~/Work/ansible-portal/ansible-rhdh-plugins
ls -la ~/Work/ansible-portal/ansible-backstage-plugins
ls -la ~/Work/ansible-portal/ansible-portal-chart
```

### OpenShift Connection Issues

```bash
# Test OpenShift connection
oc whoami
oc get projects

# Get a new token if needed
oc whoami -t
```

### Build Failures

```bash
# Check Node version
node --version

# Enable yarn
corepack enable
yarn --version

# Try manual build
cd ~/Work/ansible-portal/ansible-backstage-plugins
yarn install
cd ~/Work/ansible-portal/ansible-rhdh-plugins
./build.sh
```

## Usage Examples

### Development Workflow

```bash
# Make code changes in ansible-backstage-plugins
cd ~/Work/ansible-portal/ansible-backstage-plugins
# ... edit files ...

# Build and deploy changes
cd ~/Work/ansible-portal/ansible-portal-installer
source venv/bin/activate
ansible-portal-installer full-deploy
```

### Testing Different Configurations

```bash
# Deploy to different namespace
ansible-portal-installer helm-deploy --namespace test-env --release test-portal

# Check status
ansible-portal-installer status --namespace test-env
```

### Cleanup

```bash
# Remove deployment
ansible-portal-installer cleanup --namespace my-namespace --release my-portal

# Or with confirmation skip
ansible-portal-installer cleanup --yes
```

## Environment Variables Reference

See [.env.example](.env.example) for complete list of environment variables.

**Most important variables:**

| Variable | Description | Example |
|----------|-------------|---------|
| `ANSIBLE_RHDH_PLUGINS_PATH` | Path to downstream repo | `/home/user/Work/ansible-portal/ansible-rhdh-plugins` |
| `ANSIBLE_BACKSTAGE_PLUGINS_PATH` | Path to upstream repo | `/home/user/Work/ansible-portal/ansible-backstage-plugins` |
| `REGISTRY_USERNAME` | Container registry username | `your-quay-username` |
| `REGISTRY_PASSWORD` | Container registry password | `your-quay-password` |
| `OPENSHIFT_SERVER` | OpenShift API URL | `https://api.example.com:6443` |
| `OPENSHIFT_TOKEN` | OpenShift auth token | `sha256~...` |
| `AAP_HOST_URL` | AAP controller URL | `https://aap.example.com` |
| `CLUSTER_ROUTER_BASE` | OpenShift apps domain | `apps.example.com` |

## Next Steps

After successful deployment:

1. **Wait for pods**: `oc get pods -w -n <namespace>`
2. **Get portal URL**: `oc get route -n <namespace>`
3. **Update OAuth redirects** in AAP and GitHub
4. **Test authentication** by accessing the portal

See [README.md](README.md) for detailed command reference and architecture information.

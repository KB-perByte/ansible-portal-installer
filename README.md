# Ansible Portal Installer

Automated deployment tool for Ansible Automation Portal (based on Red Hat Developer Hub).

This installer automates the manual workflow documented in the [Helm Chart Developer Guide](https://github.com/ansible/ansible-rhdh-plugins/blob/main/docs/guides/helm-chart-developer-guide.md).

## Quick Start

```bash
# Install the tool
pip install -e .

# Deploy portal with minimal configuration
ansible-portal-installer deploy \
  --namespace my-portal \
  --aap-host https://aap.example.com \
  --aap-token <token> \
  --oauth-client-id <client-id> \
  --oauth-client-secret <client-secret>
```

## Features

- ✅ Automated plugin build using upstream `build.sh` script
- ✅ OCI image packaging and push to OpenShift internal registry
- ✅ Kubernetes secret creation with correct key names
- ✅ Helm deployment with auto-generated values
- ✅ OAuth application setup guidance
- ✅ Post-deployment verification checklist
- ✅ Configurable insecure registry support for dev environments
- ✅ Values preview and export (dry-run mode)

## Prerequisites

- OpenShift cluster access with `oc` CLI
- Helm 3.x
- Podman or Docker
- Node.js 20 or 22
- Yarn (via corepack)
- AAP OAuth application and API token (see Setup below)
- Optional: GitHub OAuth application and PAT for GitHub integration

## Repository Setup

The installer expects this directory structure:

```
.
├── ansible-rhdh-plugins/          # Downstream repo (build scripts, Containerfile)
│   ├── build.sh
│   ├── dynamic-plugins/           # Build output directory
│   └── ansible-backstage-plugins@ -> ../ansible-backstage-plugins
├── ansible-backstage-plugins/     # Upstream repo (plugin source code)
│   └── plugins/
├── ansible-portal-chart/          # Helm chart
└── ansible-portal-installer/      # This tool
```

Setup:

```bash
# Clone repositories
git clone https://github.com/ansible/ansible-rhdh-plugins.git
git clone https://github.com/ansible/ansible-backstage-plugins.git
git clone https://github.com/ansible-automation-platform/ansible-portal-chart.git

# Create symlink (required by build.sh)
cd ansible-rhdh-plugins
ln -sfn ../ansible-backstage-plugins ansible-backstage-plugins
```

## OAuth Application Setup

Before deploying, create OAuth applications in AAP and optionally GitHub.

### Option 1: Interactive Guidance

Run the deploy command without credentials to get step-by-step setup instructions:

```bash
ansible-portal-installer deploy --namespace my-portal
```

The installer will detect missing credentials and guide you through OAuth setup.

### Option 2: Manual Setup

See the interactive guidance output for detailed steps, or refer to the [Helm Chart Developer Guide Phase 3](https://github.com/ansible/ansible-rhdh-plugins/blob/main/docs/guides/helm-chart-developer-guide.md#phase-3-oauth-applications-setup).

## Deployment

### Basic Deployment

```bash
ansible-portal-installer deploy \
  --namespace my-portal \
  --aap-host https://aap.example.com \
  --aap-token <aap-token> \
  --oauth-client-id <oauth-client-id> \
  --oauth-client-secret <oauth-client-secret>
```

### With GitHub Integration

```bash
ansible-portal-installer deploy \
  --namespace my-portal \
  --aap-host https://aap.example.com \
  --aap-token <aap-token> \
  --oauth-client-id <oauth-client-id> \
  --oauth-client-secret <oauth-client-secret> \
  --github-token <github-token> \
  --github-client-id <github-client-id> \
  --github-client-secret <github-client-secret>
```

### Using Environment Variables

```bash
export AAP_HOST_URL=https://aap.example.com
export AAP_TOKEN=<token>
export OAUTH_CLIENT_ID=<client-id>
export OAUTH_CLIENT_SECRET=<client-secret>
export GITHUB_TOKEN=<token>
export GITHUB_CLIENT_ID=<client-id>
export GITHUB_CLIENT_SECRET=<client-secret>

ansible-portal-installer deploy --namespace my-portal
```

### Preview Generated Values (Dry-Run)

```bash
# Print values to console
ansible-portal-installer deploy \
  --namespace my-portal \
  --dry-run \
  <...other options...>

# Export values to file
ansible-portal-installer deploy \
  --namespace my-portal \
  --values-output ./my-values.yaml \
  <...other options...>
```

### Advanced Options

```bash
ansible-portal-installer deploy \
  --namespace my-portal \
  --release-name custom-portal \
  --chart-path ../ansible-portal-chart \
  --plugins-path ../ansible-rhdh-plugins \
  --registry quay.io/myuser \
  --image-tag v1.0.0 \
  --check-ssl \
  --no-insecure-registry \
  --skip-plugin-build \
  --skip-rollout-wait \
  --rollout-timeout 60m \
  <...credentials...>
```

## Command Options

| Option | Description | Default | Env Var |
|--------|-------------|---------|---------|
| `--namespace` | Target OpenShift namespace | Required | `OCP_NAMESPACE` |
| `--release-name` | Helm release name | `rhaap-portal-dev` | `RELEASE_NAME` |
| `--chart-path` | Path to Helm chart | `../ansible-portal-chart` | `CHART_PATH` |
| `--plugins-path` | Path to ansible-rhdh-plugins | `.` | `PLUGINS_PATH` |
| `--aap-host` | AAP controller URL | Required | `AAP_HOST_URL` |
| `--aap-token` | AAP API token | Required | `AAP_TOKEN` |
| `--oauth-client-id` | AAP OAuth client ID | Required | `OAUTH_CLIENT_ID` |
| `--oauth-client-secret` | AAP OAuth client secret | Required | `OAUTH_CLIENT_SECRET` |
| `--github-token` | GitHub PAT | None | `GITHUB_TOKEN` |
| `--github-client-id` | GitHub OAuth client ID | None | `GITHUB_CLIENT_ID` |
| `--github-client-secret` | GitHub OAuth client secret | None | `GITHUB_CLIENT_SECRET` |
| `--gitlab-token` | GitLab PAT | None | `GITLAB_TOKEN` |
| `--registry` | Plugin registry URL | Auto-detect | `PLUGIN_REGISTRY` |
| `--image-tag` | Plugin image tag | `dev` | `PLUGIN_IMAGE_TAG` |
| `--admin-password` | Portal admin password | Generated | `PORTAL_ADMIN_PASSWORD` |
| `--check-ssl` | Enable SSL verification for AAP | Disabled | N/A |
| `--insecure-registry` | Configure insecure registry | Enabled | `INSECURE_REGISTRY` |
| `--skip-plugin-build` | Skip plugin build step | Disabled | `SKIP_PLUGIN_BUILD` |
| `--skip-rollout-wait` | Don't wait for rollout | Disabled | `SKIP_ROLLOUT_WAIT` |
| `--rollout-timeout` | Rollout timeout | `40m` | `ROLLOUT_TIMEOUT` |
| `--dry-run` | Preview values without deploying | Disabled | N/A |
| `--values-output` | Export values to file | None | N/A |

## What the Installer Does

The installer automates these steps from the [Helm Chart Developer Guide](https://github.com/ansible/ansible-rhdh-plugins/blob/main/docs/guides/helm-chart-developer-guide.md):

1. **Phase 1: Repository Setup** - Validates symlink exists
2. **Phase 2: Build Plugin Container**
   - Runs `build.sh` with `BUILD_TYPE=portal`
   - Creates plugin tarballs in `ansible-rhdh-plugins/dynamic-plugins/`
   - Builds OCI image with Podman
   - Pushes to OpenShift internal registry or specified registry
3. **Phase 3: OAuth Setup** - Provides interactive guidance if credentials missing
4. **Phase 4: OpenShift Deployment**
   - Creates namespace if needed
   - Creates secrets with correct key names matching Helm chart expectations
   - Optionally creates insecure registry ConfigMap (dev mode)
   - Generates Helm values matching chart expectations
   - Runs `helm upgrade --install`
   - Optionally patches deployment for insecure registry
   - Waits for rollout with configurable timeout
5. **Phase 5: Verification** - Displays checklist and OAuth update instructions

## Post-Deployment: Update OAuth Redirect URIs

**CRITICAL:** After deployment completes, you MUST update your OAuth applications with the actual portal route.

The installer prints the exact URLs you need. Authentication will fail without this step.

## Verification

After updating OAuth redirect URIs, use the verification checklist printed by the installer to confirm:

- Portal loads in browser
- AAP sign-in works
- Templates are visible
- Plugins loaded correctly
- Content discovery working (if enabled)

## Troubleshooting

### Plugin Build Fails

**Error**: `build.sh not found` or `ansible-backstage-plugins not found`

**Solution**: Verify repository setup and symlink exists

### Authentication Fails (redirect_uri_mismatch)

**Cause**: OAuth redirect URIs don't match the actual portal route

**Solution**: Update OAuth applications with the exact URLs printed after deployment

### OCI Image Pull Fails

**Cause**: Wrong registry auth secret type or missing auth

**Solution**: Ensure you're logged in (`podman login` or `oc registry login`) and `--insecure-registry` is enabled for internal registry

### Rollout Timeout

**Cause**: RHDH + OCI plugin init is slow (can take 30-40 minutes)

**Solution**: Increase timeout with `--rollout-timeout 60m` or use `--skip-rollout-wait`

## Alignment with Helm Chart Developer Guide

This installer implements the exact workflow documented in the [Helm Chart Developer Guide](https://github.com/ansible/ansible-rhdh-plugins/blob/main/docs/guides/helm-chart-developer-guide.md).

See [ALIGNMENT_ANALYSIS.md](ALIGNMENT_ANALYSIS.md) and [FIXES_APPLIED.md](FIXES_APPLIED.md) for detailed comparison and changes made.

## License

Apache License 2.0

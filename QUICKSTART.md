# Quick Start Guide

Get the Ansible Portal Installer up and running in 5 minutes.

## Prerequisites Check

```bash
# Check required tools
which python3  # Python 3.10+
which node     # Node.js 20 or 22
which yarn     # Via corepack
which podman   # Or docker
which oc       # OpenShift CLI
which helm     # Helm 3.x
```

## 1. Install (30 seconds)

```bash
cd ansible-portal-installer
./install.sh
```

Or manually:
```bash
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## 2. Configure (2 minutes)

```bash
# Copy template
cp .env.example .env

# Edit configuration
vim .env
```

**Minimum required configuration:**

```bash
# Repository paths (update to your local paths)
ANSIBLE_RHDH_PLUGINS_PATH=/home/user/Work/ansible-portal/ansible-rhdh-plugins
ANSIBLE_BACKSTAGE_PLUGINS_PATH=/home/user/Work/ansible-portal/ansible-backstage-plugins
HELM_CHART_PATH=/home/user/Work/ansible-portal/ansible-portal-chart

# Registry credentials
REGISTRY_USERNAME=your-quay-username
REGISTRY_PASSWORD=your-quay-password

# OpenShift
OPENSHIFT_SERVER=https://api.example.com:6443
OPENSHIFT_TOKEN=sha256~your-token
CLUSTER_ROUTER_BASE=apps.example.com

# AAP
AAP_HOST_URL=https://aap.example.com
AAP_OAUTH_CLIENT_ID=your-client-id
AAP_OAUTH_CLIENT_SECRET=your-client-secret
AAP_TOKEN=your-aap-token

# GitHub
GITHUB_TOKEN=ghp_your-token
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
```

## 3. Verify (30 seconds)

```bash
source venv/bin/activate
ansible-portal-installer verify
```

Expected output:
```
════════════════════════════════════════════
Checking Prerequisites
════════════════════════════════════════════

✓ yarn is installed
✓ podman is installed
✓ oc is installed
✓ helm is installed
✓ git is installed
```

## 4. Deploy! (5-10 minutes)

### Option A: Full Automated Deployment

```bash
ansible-portal-installer full-deploy
```

This runs:
1. Build plugins (~3 min)
2. Publish image (~1 min)
3. Deploy to OpenShift (~2 min)

### Option B: Step-by-Step

```bash
# Build plugins
ansible-portal-installer build

# Publish to registry
ansible-portal-installer publish

# Deploy with Helm
ansible-portal-installer helm-deploy
```

## What to Expect

### During Build
```
════════════════════════════════════════════
Building Dynamic Plugins
════════════════════════════════════════════

⠹ Running build script (this may take several minutes)...
```

### During Publish
```
════════════════════════════════════════════
Publishing Plugin Container Image
════════════════════════════════════════════

✓ Authenticated with quay.io
✓ Built image: quay.io/user/ansible-portal-plugins:dev-20260502
✓ Pushed image: quay.io/user/ansible-portal-plugins:dev-20260502

Image Reference: quay.io/user/ansible-portal-plugins:dev-20260502
```

### During Deploy
```
════════════════════════════════════════════
Deploying Ansible Portal with Helm
════════════════════════════════════════════

✓ Connected to OpenShift: https://api.example.com:6443
✓ Created project: ansible-portal
✓ Created secret: secrets-rhaap-portal
✓ Created secret: secrets-scm
✓ Deployed Helm release: my-portal
✓ Portal route: https://my-portal-rhaap-portal-ansible-portal.apps.example.com
```

## After Deployment

1. **Wait for pods to be ready** (2-5 minutes):
   ```bash
   oc get pods -w -n ansible-portal
   ```

2. **Access the portal**:
   ```bash
   oc get route -n ansible-portal
   # Open the URL in your browser
   ```

3. **Update OAuth redirect URIs**:
   - AAP OAuth app: Update redirect URIs with actual portal URL
   - GitHub OAuth app: Update callback URL with actual portal URL

4. **Test authentication**:
   - Open portal in browser
   - Click sign in
   - Should redirect to AAP login

## Common Commands

```bash
# Check deployment status
ansible-portal-installer status

# Verify deployment
ansible-portal-installer verify

# Cleanup deployment
ansible-portal-installer cleanup

# Deploy to different namespace
ansible-portal-installer helm-deploy --namespace test-env

# Rebuild and redeploy
ansible-portal-installer full-deploy
```

## Troubleshooting

### Build Fails

```bash
# Check Node.js version
node --version  # Should be 20.x or 22.x

# Enable corepack
corepack enable
yarn --version

# Try manual build
cd ~/Work/ansible-portal/ansible-backstage-plugins
yarn install
cd ~/Work/ansible-portal/ansible-rhdh-plugins
./build.sh
```

### Publish Fails

```bash
# Test registry authentication
podman login quay.io

# Check image exists
podman images | grep ansible-portal-plugins
```

### Deploy Fails

```bash
# Test OpenShift connection
oc whoami
oc get projects

# Check secrets
oc get secrets -n ansible-portal

# View Helm release
helm list -n ansible-portal
```

## Next Steps

- Read [README.md](README.md) for detailed command reference
- Read [ARCHITECTURE.md](ARCHITECTURE.md) for design details
- Read [SETUP.md](SETUP.md) for advanced configuration

## Need Help?

1. Check configuration: `cat .env`
2. Run with verbose: `ansible-portal-installer --verbose <command>`
3. Check logs: `oc logs <pod-name> -n ansible-portal`
4. Review helm chart guide: `../ansible-rhdh-plugins/docs/guides/helm-chart-developer-guide.md`

---

**Ready to deploy?**

```bash
source venv/bin/activate
ansible-portal-installer full-deploy
```

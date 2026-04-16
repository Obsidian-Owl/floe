# Spec: Fix DevPod Hetzner Configuration

**Work ID**: `debug-devpod-hetzner`
**Type**: Bugfix (infrastructure)
**Files**: 3 (devcontainer.json, Dockerfile, devpod-setup.sh)

## Acceptance Criteria

### AC-1: DevPod workspace creates successfully on Hetzner
- `devpod up . --provider hetzner --ide none` completes with exit code 0
- SSH into workspace works: `devpod ssh floe -- "echo ok"`
- Docker-in-Docker functional inside container

### AC-2: TOKEN deprecation warning understood and documented
- Provider v1.0.1 schema requires `TOKEN` (not `HCLOUD_TOKEN`)
- Deprecation warning comes from hcloud SDK binary, NOT the provider option schema
- `HCLOUD_TOKEN` is NOT a valid provider option (confirmed: "Option HCLOUD_TOKEN was specified but is not defined")
- Comment in setup script corrected to explain this

### AC-3: Inactivity timeout prevents premature deletion
- Provider configured with `INACTIVITY_TIMEOUT=120m`
- VM survives E2E test runs (typically 15-30 minutes)

## Changes

### 1. `.devcontainer/devcontainer.json`
- Change `"remoteUser": "node"` to `"remoteUser": "root"`
- Update `containerEnv.CLAUDE_CONFIG_DIR` from `/home/node/.claude` to `/root/.claude`
- Update `containerEnv.KUBECONFIG` from `/home/node/.kube/config` to `/root/.kube/config`
- Update mount target from `/home/node/.claude` to `/root/.claude`

### 2. `.devcontainer/Dockerfile`
- Remove or simplify sudoers rules that are no longer needed with root user
- Update any `/home/node` path references to `/root`

### 3. `scripts/devpod-setup.sh`
- Keep `-o TOKEN=` (provider schema requires it despite SDK warning)
- Correct comment to explain TOKEN vs HCLOUD_TOKEN confusion
- Add `-o INACTIVITY_TIMEOUT=120m` to provider options

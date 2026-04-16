# Diagnosis: DevPod Hetzner Failures

**Work ID**: `debug-devpod-hetzner`
**Date**: 2026-04-02
**Confidence**: HIGH (confirmed by DevPod source code analysis + multiple GitHub issues)

## Problem

DevPod on Hetzner (provider v1.0.1) fails with two issues:

1. **"error parsing workspace info: rerun as root: exit status 1"** — devcontainer
   builds successfully but workspace bootstrap fails, triggering VM auto-deletion
2. **"TOKEN envvar is deprecated in favour of HCLOUD_TOKEN"** — warning on every
   provider operation

## Root Cause

### Issue 1: Agent privilege escalation failure

The DevPod agent runs on the Hetzner VM as the SSH user (`devpod`). During bootstrap,
it checks if Docker is accessible (`docker ps`). If the SSH user lacks Docker group
membership, the agent sets `dockerRootRequired = true` and attempts `sudo --preserve-env`
to re-run itself as root. If sudo fails (exit status 1), the error propagates as
"error parsing workspace info: rerun as root".

**Key insight**: This error occurs on the **host VM**, not inside the devcontainer.
The `remoteUser: "node"` setting in `devcontainer.json` is a **secondary** issue —
it affects agent operations **inside** the container after the host-level bootstrap.

The Hetzner provider's `docker-ce` disk image provisions Docker but may not add the
`devpod` SSH user to the `docker` group, or the user's session doesn't pick up the
group membership without re-login.

**Evidence**:
- DevPod issues #459, #928, #1878 — identical error traced to Docker socket access
- DevPod source `pkg/agent/agent.go` — `rerunAsRoot` function confirms mechanism
- Our logs: "Done creating devcontainer" followed by "rerun as root: exit status 1"

### Issue 2: Deprecated TOKEN option

`scripts/devpod-setup.sh` passes `-o TOKEN=...` but the provider renamed this to
`HCLOUD_TOKEN` in v0.4.0 (February 2024). The provider accepts both via backwards
compatibility, but emits a warning. The comment on line 78 claiming "doesn't accept
HCLOUD_TOKEN yet" is factually incorrect.

## Blast Radius

### Affected
- `scripts/devpod-setup.sh` — TOKEN option name (2 occurrences)
- `.devcontainer/devcontainer.json` — `remoteUser` setting
- `.devcontainer/Dockerfile` — sudoers rules, paths referencing `/home/node`

### Not Affected
- All application code, tests, CI pipelines
- Local Kind cluster workflow
- Docker dagster-demo image build
- Any runtime code

## Fix Approach

### Issue 1: Two options

**Option A: Change `remoteUser` to `root` (recommended)**
- The container already runs `--privileged` with `NET_ADMIN`, `NET_RAW`, `SYS_PTRACE`
- Running as root inside an already-privileged container adds no security exposure
- Simplifies sudoers rules (most become unnecessary)
- Changes: `devcontainer.json` (remoteUser, containerEnv paths, mount targets),
  `Dockerfile` (remove/simplify sudoers)

**Option B: Add user to docker group**
- `RUN usermod -aG docker node` in Dockerfile
- Less certain to fix — agent may need root for operations beyond Docker socket
- Docker group created at runtime by DinD feature, may not exist at build time

### Issue 2: Rename TOKEN to HCLOUD_TOKEN
- Mechanical: change `-o TOKEN=` to `-o HCLOUD_TOKEN=` in 2 places
- Remove incorrect comment on line 78

### Issue 3: Inactivity timeout
- Already fixed in this session: bumped from 10m to 120m
- Should be persisted in `devpod-setup.sh`

## Alternatives Considered

1. **Switch to official loft-sh Hetzner provider** — doesn't exist; mrsimonemms is
   the community provider
2. **Use Docker provider instead of Hetzner** — defeats the purpose (need remote compute)
3. **Run DevPod agent as root on host** — provider controls this, not us
4. **File upstream issue** — could take months; we need E2E testing now

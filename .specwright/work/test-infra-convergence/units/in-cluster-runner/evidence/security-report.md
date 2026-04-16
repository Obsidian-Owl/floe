# Gate: Security Report

**Generated**: 2026-04-07T06:55:00Z
**Status**: WARN

## Scope

Changed files on `feat/in-cluster-runner` vs `main`:
- `testing/ci/test-e2e-cluster.sh`
- `testing/ci/test-e2e-full.sh`
- `testing/Dockerfile`
- `.claude/hooks/check-e2e-ports.sh`
- `Makefile`

## Secrets Detection

No hardcoded credentials found. All credential handling uses environment variables.

## Findings

### WARN-1: dbt installer script not integrity-verified (pre-existing)
- **Location**: `testing/Dockerfile:53-55`
- **CWE**: CWE-494
- **Note**: Pre-existing in Dockerfile. The `--update` flag fetches latest version.
  Mitigated by: download-then-execute (not pipe-to-shell), HTTPS-only, non-root runtime.
- **Action**: Track as tech-debt for vendoring or checksum pinning.

### WARN-2: /root/.local artifacts may persist in image layer (pre-existing)
- **Location**: `testing/Dockerfile:57`
- **CWE**: CWE-272
- **Note**: After `cp /root/.local/bin/dbt /usr/local/bin/dbt`, the `/root/.local` tree
  remains in the image layer. Our change improved this (was symlink, now copy), but
  cleanup of `/root/.local` would be better.
- **Action**: Add `rm -rf /root/.local /root/.cache` after the copy.

### WARN-3: SSH host key verification for DevPod transfers
- **Location**: `testing/ci/test-e2e-cluster.sh:79,92`
- **CWE**: CWE-297
- **Note**: DevPod manages SSH config and host keys. This is a developer-workstation
  path, not CI. Risk is low but documentation would help.

### INFO-1: kubectl version resolved dynamically at build time (pre-existing)
- **Location**: `testing/Dockerfile:24`
- **Note**: Pre-existing pattern. kubectl SHA-256 checksum is verified.

### INFO-2: JOB_TIMEOUT not integer-validated
- **Location**: `testing/ci/test-e2e-cluster.sh:23`
- **Note**: Low risk — `set -euo pipefail` would catch malformed values.

### INFO-3: Pod log output unbounded
- **Location**: `testing/ci/test-e2e-cluster.sh:183`
- **Note**: Consider `--limit-bytes` for CI disk safety.

## Verdict

WARN — no BLOCK findings. All HIGH findings are pre-existing Dockerfile patterns,
not introduced by this work unit. No secrets or injection vulnerabilities found in
new code.

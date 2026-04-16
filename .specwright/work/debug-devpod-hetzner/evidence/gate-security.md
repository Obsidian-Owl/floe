# Gate: Security
**Status**: PASS
**Date**: 2026-04-02

## Findings
- 0 BLOCK, 0 WARN, 1 INFO

## Evidence
- Removed NOPASSWD sudoers rules (security improvement — no longer granting passwordless sudo to non-root user for docker-init.sh, dockerd, groupmod, socat, tee, rm)
- No hardcoded secrets in changed files
- Token handling via env vars (DEVPOD_HETZNER_TOKEN from .env, never exposed in logs — trace suppressed with `{ set +x; }`)
- Container runs --privileged (unchanged, required for DinD)

## INFO
- Running as root inside --privileged container: no change to security boundary (container was already fully privileged). Real isolation is the Hetzner VM and firewall.

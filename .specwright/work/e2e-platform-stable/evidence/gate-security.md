# Gate: Security
**Status**: PASS (with WARNs)
**Timestamp**: 2026-03-26T15:15:00Z

## Scope
Changed files: `docker/dagster-demo/Dockerfile`, `charts/floe-platform/values.yaml`, `charts/floe-platform/values-test.yaml`, `Makefile`

## Findings (related to changed code)

### WARN-1: DOCKER_IP not validated as IPv4 before sed substitution
- **File**: `Makefile:149`
- **CWE**: CWE-20 (Improper Input Validation)
- **Severity**: WARN
- **Detail**: `DOCKER_IP` from `docker inspect` is used in `sed` without format validation. Low risk since env vars are developer-controlled, not user input.
- **Fix**: Add IPv4 regex validation after docker inspect

### WARN-2: dagster-k8s installed without hash verification
- **File**: `docker/dagster-demo/Dockerfile:121-126`
- **CWE**: CWE-494
- **Severity**: WARN
- **Detail**: The pip install block (lines 121-126) installs without `--require-hashes`, unlike the main requirements.txt in Stage 1. Pre-existing pattern for all dagster ecosystem packages.
- **Fix**: Future work — consolidate into uv-exported requirements

## Pre-existing findings (not introduced by this PR)
- Hardcoded test credentials in values-test.yaml (allowlisted with pragma)
- `automountServiceAccountToken: true` default
- `minio/minio:latest` unpinned tag
- OTel→Jaeger TLS disabled in base values
- curl|sh without hash verification in Makefile install-dbt target

## Verdict
No new security issues introduced. Two WARNs on the new Makefile target and existing pip install pattern.

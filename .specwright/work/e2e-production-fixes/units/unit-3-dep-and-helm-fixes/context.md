# Context: Unit 3 — Dependency Bump + Helm Hook Deadline

## Problem A: requests CVE
- `requests` 2.32.5 has GHSA-gc5v-m9x4-r6x2 (predictable temp file, CVSS 4.4, local-only)
- Direct dependency at `pyproject.toml` line 26: `"requests>=2.31"`
- Fix: bump to `>=2.33.0`, run `uv lock --upgrade-package requests`

## Problem B: Helm hook deadline
- `activeDeadlineSeconds: 300` hardcoded in pre-upgrade hook template line 74
- Includes pod scheduling + image pull time, not just script execution
- Flakes when `bitnami/kubectl:1.32.0` preload fails silently
- Helm unittest at `hook-pre-upgrade_test.yaml` line 81 hardcodes `value: 300`

## Key Files
- `pyproject.toml` line 26: requests constraint
- `charts/floe-platform/templates/hooks/pre-upgrade-statefulset-cleanup.yaml` line 74
- `charts/floe-platform/values.yaml` — `postgresql.preUpgradeCleanup` section
- `charts/floe-platform/values-test.yaml` — needs `activeDeadlineSeconds: 600`
- `charts/floe-platform/tests/hook-pre-upgrade_test.yaml` line 81

## Design Decisions
- D3: Simple constraint bump (no breaking changes)
- D4: Parameterize deadline via values, 600s for CI

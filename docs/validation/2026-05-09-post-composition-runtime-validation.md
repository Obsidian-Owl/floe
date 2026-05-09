# Post-Composition Runtime Validation

Date: 2026-05-09
Repo: `/Users/dmccarthy/Projects/floe`
Branch: `main`
Workspace: `floe-postcomp-audit`

## Scope

This runtime lane validated remote DevPod/Hetzner behavior for the post-composition audit without changing product code. Local `main` was ahead of `origin/main` by audit-document commits only; the remote DevPod source resolved to `git:https://github.com/Obsidian-Owl/floe@main`, so the runtime product result validates `origin/main` product code at `d9e3582a4d7d76ffaaf0b3b40bed96247fc39938`.

## Command Ledger

| Lane | Command | Result | Classification |
| --- | --- | --- | --- |
| Preflight | `git status --short --branch` | `## main...origin/main [ahead 6]` | Evidence |
| Preflight | `git rev-parse HEAD` | `ad8a27e088c565fee93f0cc7b9ef4c82a228b0ac` | Evidence |
| Preflight | `git rev-parse origin/main` | `d9e3582a4d7d76ffaaf0b3b40bed96247fc39938` | Evidence |
| Preflight | `command -v devpod && devpod version` | `/Users/dmccarthy/.local/bin/devpod`; `v0.6.15` | Evidence |
| Preflight | `devpod provider list` | Hetzner provider `v1.0.1`, default `true`, initialized `true` | Evidence |
| Preflight | `devpod list` | No workspaces listed | Evidence |
| Hetzner pre-run inventory | Direct Hetzner Cloud API for servers, volumes, and SSH keys matching `floe-postcomp-audit` | No matches | Infra pass |
| Remote E2E | `DEVPOD_WORKSPACE=floe-postcomp-audit make devpod-test` | Passed; artifacts saved to `test-artifacts/devpod-run-20260509T030016Z-21729`; exit code `0`; final pytest result `261 passed, 86 deselected, 7 warnings in 1034.53s (0:17:14)` | Product pass |
| Remote source resolution | Captured by `make devpod-test` output | Cloned `https://github.com/Obsidian-Owl/floe`, branch `main`; Flux waited for revision `d9e3582a4d7d76ffaaf0b3b40bed96247fc39938` | Product evidence for `origin/main` |
| Remote teardown | Captured by `make devpod-test` output | DevPod emitted `Error tunneling to container: wait: remote command exited without exit status or exit signal` after the remote command finished, but artifacts were saved and `E2E tests PASSED` was reported | Tooling warning |
| DevPod cleanup | `make devpod-test` Step 5 plus `devpod list` | Workspace `floe-postcomp-audit` and machine `floe-postc-a353f` deleted; post-run `devpod list` empty | Infra pass |
| Hetzner post-run inventory | Direct Hetzner Cloud API for servers, volumes, and SSH keys matching `floe-postcomp-audit` or `floe-postc-a353f` | No matches; no manual deletion required | Infra pass |

## Artifact Summary

Local artifact directory: `test-artifacts/devpod-run-20260509T030016Z-21729`

Key files:

- `exit-code` -> `0`
- `output.log` records Flux settlement, rollout success, test runner build, in-cluster E2E execution, and final remote exit `0`.
- `artifacts/e2e-output.log` records the pytest result: `261 passed, 86 deselected, 7 warnings in 1034.53s (0:17:14)`.

## Result Classification

| Area | Result | Notes |
| --- | --- | --- |
| Product runtime E2E | Pass | Remote E2E passed against `origin/main` product code at `d9e3582a4d7d76ffaaf0b3b40bed96247fc39938`. This does not erase the separately recorded local unit/contract baseline product failures for stale S3 alias and strict MinIO rename contracts. |
| Infrastructure provisioning | Pass | Hetzner machine and volume creation succeeded; Kind, Flux, and platform rollouts settled before tests ran. |
| Tooling | Warn | DevPod tunnel teardown emitted a non-fatal error after successful remote execution. Artifacts and exit code confirm the remote lane passed. |
| Cleanup and billing exposure | Pass | DevPod workspace deletion succeeded and direct Hetzner inventory found no current-run servers, volumes, or SSH keys remaining. |

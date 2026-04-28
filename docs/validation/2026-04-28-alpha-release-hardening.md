# Alpha Release Hardening Evidence - 2026-04-28

## Baseline

- Branch: `release/alpha-hardening-e2e`
- Base: `72c3dcf7e2737053130ad925c312b686c2222ca6`
- Alpha blockers: #265, #264, #260
- Release-scope decisions: #263, #214

## Validation Runs

| Gate | Command / URL | Result | Notes |
| --- | --- | --- | --- |
| Baseline main Helm CI | https://github.com/Obsidian-Owl/floe/actions/runs/25027006173 | FAIL | Helm CI integration failed on #265 |
| #264 Dependabot critical/high baseline | `gh api 'repos/Obsidian-Owl/floe/dependabot/alerts?state=open&per_page=100' ... > /tmp/floe-critical-high-dependabot.json` | CAPTURED | 15 open critical/high findings before remediation: root `GitPython` x2, root `dagster`, floe-core `protobuf`, `pyasn1`, `pyopenssl`, agent-memory `cbor2`, `litellm` x5, `lupa`, `pillow` x2 |
| #264 dependency audit | `./testing/ci/uv-security-audit.sh` | PASS | Root, floe-core, and agent-memory lockfiles report no unignored vulnerabilities; `diskcache` no-fix advisory explicitly accepted for devtool-only agent-memory |
| #264 lockfile consistency | `uv lock --check`; `cd packages/floe-core && uv lock --check`; `cd devtools/agent-memory && uv lock --check` | PASS | All three lockfiles are current with their project metadata |

## Decisions

- 2026-04-28: Accepted `GHSA-w8v5-vhqr-4h9v` for `diskcache` 5.6.3 because no patched version is available and the dependency is confined to the optional agent-memory devtool, not runtime platform images. Revisit before beta or when a patched release exists.
- 2026-04-28: #214 remains a release-review validation item, not a static alpha blocker. The issue body's root cause is stale on this branch: generated demo definitions now call `load_product_definitions(...)`, and the runtime loader path wires a real lineage resource plus pipeline START/COMPLETE and per-model lineage event emission. Do not close #214 until DevPod + Hetzner E2E proves Marquez exposes fresh pipeline and dbt model lifecycle evidence.
- 2026-04-28: #263 remains real architecture debt, but is not blocking `v0.1.0-alpha.1` because the alpha validation profile intentionally includes Iceberg/floe-iceberg and no failing production path is currently known for that profile. Keep it open as release-review/post-alpha architecture work; promote it only if alpha validation requires `floe-orchestrator-dagster` to run without `floe-iceberg` installed when Iceberg export is disabled.

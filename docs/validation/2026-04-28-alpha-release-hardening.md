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

- Pending.
- 2026-04-28: Accepted `GHSA-w8v5-vhqr-4h9v` for `diskcache` 5.6.3 because no patched version is available and the dependency is confined to the optional agent-memory devtool, not runtime platform images. Revisit before beta or when a patched release exists.

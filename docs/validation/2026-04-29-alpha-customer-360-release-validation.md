# Alpha Customer 360 Release Validation - 2026-04-29

This file is a validation evidence template for `v0.1.0-alpha.1`. It is not proof that validation has passed until each gate is updated with command output, workflow links, or manual evidence.

## Release Context

- Date: 2026-04-29
- Branch: `docs/alpha-docs-demo-release-gate`
- Commit: `TODO: record with git rev-parse HEAD before tagging`
- Release candidate: `v0.1.0-alpha.1`

## Automated Gates

| Gate | Evidence Source | Required | Status | Evidence / Notes |
| --- | --- | --- | --- | --- |
| Docs build | `uv run mkdocs build --strict` | Yes | Not run | Record command output or CI link. |
| Docs validation | `make docs-validate` | Yes | Not run | Record command output or CI link. |
| Unit tests | `make test-unit` | Yes | Not run | Record command output or CI link. |
| Helm CI | GitHub Actions Helm CI run URL | Yes | Not run | Record workflow URL and result. |
| CI | GitHub Actions CI run URL | Yes | Not run | Record workflow URL and result. |
| Security | GitHub Actions security scan URL or local security command output | Yes | Not run | Record scan URL, command output, or accepted non-blocking limitation. |
| Customer 360 validation | `make demo-customer-360-validate` | Yes | Not run | Record generated validation summary and key evidence. |
| DevPod + Hetzner E2E | `make devpod-test` | Yes | Not run | Record workspace source commit, run output, and cleanup status. |

## Manual UI Evidence

| Service | URL | Evidence Required | Status | Evidence / Notes |
| --- | --- | --- | --- | --- |
| Dagster | http://localhost:3100 | Latest Customer 360 run succeeded. | Not run | Add screenshot path, run ID, or notes. |
| MinIO | http://localhost:9001 | Customer 360 output objects are visible. | Not run | Add screenshot path, bucket/object path, or notes. |
| Marquez | http://localhost:5100 | Customer 360 namespace, job, and dataset lineage are visible. | Not run | Add screenshot path, namespace/job names, or notes. |
| Jaeger | http://localhost:16686 | Customer 360 trace evidence is visible. | Not run | Add screenshot path, trace ID, or notes. |
| Polaris | http://localhost:8181 | Customer 360 tables are registered in the catalog. | Not run | Add screenshot path, API response, table names, or notes. |

## #263 Posture

Status: Known post-alpha architecture debt.

Alpha posture: #263 is not blocking `v0.1.0-alpha.1` because the alpha Customer 360 stack intentionally includes Iceberg and `floe-iceberg`.

The alpha release does not promise Dagster runs without `floe-iceberg` installed when Iceberg export is disabled.

Promotion rule: if the alpha promise changes to support Dagster without Iceberg, #263 becomes blocking before tagging.

## Release Decision

Alpha tag is blocked until every required gate is PASS or classified as a non-blocking known limitation.

Decision: `TODO: PASS / BLOCKED`

Decision notes:

- `TODO: Record final release decision and links to evidence.`

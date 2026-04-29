# Alpha Customer 360 Release Validation - 2026-04-29

This file is a validation evidence template for `v0.1.0-alpha.1`. It is not proof that validation has passed until each gate is updated with command output, workflow links, or manual evidence.

## Release Context

- Date: 2026-04-29
- Branch: `docs/alpha-docs-demo-release-gate`
- Local functional validation commit: `650a9ef71c10aeef09b0e1d917d2f0dbbbd1a2be`
- Release candidate: `v0.1.0-alpha.1`

## Automated Gates

| Gate | Evidence Source | Required | Status | Evidence / Notes |
| --- | --- | --- | --- | --- |
| Docs build | `uv run mkdocs build --strict` | Yes | PASS | Covered by `make docs-validate`; MkDocs strict build completed successfully. Existing MkDocs Material 2.x theme warning is non-blocking. Repository-wide link validation is not claimed because `mkdocs.yml` intentionally disables some link checks. |
| Docs validation | `make docs-validate` | Yes | PASS | Passed locally on 2026-04-29. The command completed strict docs build and alpha-required documentation navigation validation. |
| Focused release-hardening tests | `uv run pytest testing/ci/tests/test_validate_docs_navigation.py testing/ci/tests/test_github_actions_node24_pins.py testing/tests/unit/test_customer360_validator.py testing/tests/unit/test_demo_makefile_kubeconfig.py -q` | Yes | PASS | Passed locally on 2026-04-29: 39 passed. |
| Unit tests | `make test-unit` | Yes | PASS | Passed locally on 2026-04-29: 10035 passed, 1 skipped, 1 xfailed, 2 warnings; total coverage 87.63%. |
| Helm lint | `make helm-lint` | Yes | PASS | Passed locally on 2026-04-29 for `charts/floe-platform` and `charts/floe-jobs`; Helm reported icon recommendations only. |
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

Issue: https://github.com/Obsidian-Owl/floe/issues/263

Alpha posture: #263 has a release-scope triage comment classifying it as non-blocking for `v0.1.0-alpha.1` only while the alpha Customer 360 stack intentionally includes Iceberg and `floe-iceberg`.

The alpha release does not promise Dagster runs without `floe-iceberg` installed when Iceberg export is disabled.

Promotion rule: before tagging, confirm that the #263 issue still records this non-blocking alpha posture. If the alpha promise changes to support Dagster without Iceberg, #263 becomes blocking.

## Release Decision

Alpha tag is blocked until every required validation gate is PASS. #263 is the only known architecture debt item currently classified as non-blocking for the alpha promise in this evidence record.

Decision: `BLOCKED`

Decision notes:

- Local branch validation has passed for docs, targeted release-hardening tests, unit tests, and Helm lint.
- The release remains blocked until GitHub CI, security scanning, live Customer 360 validation, manual UI evidence, and DevPod + Hetzner E2E evidence are recorded.

# Alpha Customer 360 Release Validation - 2026-04-29

> Historical warning: this record was captured before the Starlight docs migration and before final
> alpha release-candidate validation. Do not use it as the current `v0.1.0-alpha.1` tag gate without
> rerunning the listed commands against the current merged release-candidate commit.

This file is a validation evidence template for `v0.1.0-alpha.1`. It is not proof that validation has passed until each gate is updated with command output, workflow links, or manual evidence.

## Release Context

- Date: 2026-04-29
- Branch: `main`
- Merged main baseline: commit `c1f26a1c3a9ed5c75e4920ec2db4e19246f7beb5`
- Live Customer 360 validation candidate: pre-merge hardening candidate copied into DevPod workspace and built as `floe-dagster-demo:validation-fix`
- Release candidate: `v0.1.0-alpha.1`

## Automated Gates

| Gate | Evidence Source | Required | Status | Evidence / Notes |
| --- | --- | --- | --- | --- |
| Docs build | GitHub Actions Docs run | Yes | PASS | Passed on commit `c1f26a1c3a9ed5c75e4920ec2db4e19246f7beb5`: https://github.com/Obsidian-Owl/floe/actions/runs/25092354316 |
| Docs validation | GitHub Actions Docs run | Yes | PASS | Docs navigation validation passed before the docs build on commit `c1f26a1c3a9ed5c75e4920ec2db4e19246f7beb5`: https://github.com/Obsidian-Owl/floe/actions/runs/25092354316 |
| Focused release-hardening tests | `uv run pytest testing/ci/tests/test_validate_docs_navigation.py testing/ci/tests/test_github_actions_node24_pins.py testing/tests/unit/test_customer360_validator.py testing/tests/unit/test_demo_makefile_kubeconfig.py -q` | Yes | PASS | Passed locally on 2026-04-29: 39 passed. |
| Unit tests | GitHub Actions CI unit matrix | Yes | PASS | Python 3.10, 3.11, and 3.12 unit-test jobs passed on commit `c1f26a1c3a9ed5c75e4920ec2db4e19246f7beb5`: https://github.com/Obsidian-Owl/floe/actions/runs/25092354309 |
| Helm lint | `make helm-lint` | Yes | PASS | Passed locally on 2026-04-29 for `charts/floe-platform` and `charts/floe-jobs`; Helm reported icon recommendations only. |
| Helm CI | GitHub Actions Helm CI run URL | Yes | PASS | Passed on commit `c1f26a1c3a9ed5c75e4920ec2db4e19246f7beb5`: https://github.com/Obsidian-Owl/floe/actions/runs/25092354317 |
| CI | GitHub Actions CI run URL | Yes | PASS | Passed on commit `c1f26a1c3a9ed5c75e4920ec2db4e19246f7beb5`: https://github.com/Obsidian-Owl/floe/actions/runs/25092354309 |
| Security | GitHub Actions security scan URL or local security command output | Yes | PASS | CI Security Scan passed Bandit and vulnerability audit; Helm CI Security Scan passed rendered-manifest kubesec scan: https://github.com/Obsidian-Owl/floe/actions/runs/25092354309 and https://github.com/Obsidian-Owl/floe/actions/runs/25092354317 |
| Customer 360 validation | `uv run python -m testing.ci.validate_customer_360_demo` in DevPod + Hetzner | Yes | PASS | Passed on 2026-04-29 against `floe-dagster-demo:validation-fix`; evidence captured in `/tmp/customer360-validation.out`. |
| DevPod + Hetzner E2E | `make devpod-test` | Yes | PASS | DevPod workspace source `git:https://github.com/Obsidian-Owl/floe@main`; local artifact `test-artifacts/devpod-run-20260429T052830Z-82411/output.log`; result: 250 passed, 82 deselected, 110 warnings in 749.82s. |

## Customer 360 Validator Evidence

Command:

```bash
uv run python -m testing.ci.validate_customer_360_demo
```

DevPod + Hetzner output:

```text
status=PASS
evidence.business.customer_count=500
evidence.business.total_lifetime_value=1194501.08
evidence.dagster.customer_360_run=true
evidence.lineage.marquez_customer_360=true
evidence.platform.ready=true
evidence.storage.customer_360_outputs=true
evidence.tracing.jaeger_customer_360=true
```

Run evidence:

- Dagster run ID: `a8b931f3-08f4-4222-9ddb-c3abfe0eb98e`
- Demo image: `floe-dagster-demo:validation-fix`
- Helm release: `floe-platform`
- Namespace: `floe-dev`
- Validation environment: DevPod workspace `floe` on Hetzner, Kind cluster inside DevPod
- Note: this validates the hardening candidate before merge. It is not evidence for a release tag until the candidate is merged and the lane is rerun on the merged commit.
- #275 candidate fix evidence: after Customer 360 run `a8b931f3-08f4-4222-9ddb-c3abfe0eb98e`, Marquez contains `model.customer_360.mart_customer_360` in both lineage events and namespace jobs. The run pod logs show final mart materialization, Iceberg export, thirteen successful Marquez lineage POSTs, and no `lineage_emit_timeout` or pending-task destruction.

## Manual UI Evidence

| Service | URL | Evidence Required | Status | Evidence / Notes |
| --- | --- | --- | --- | --- |
| Dagster | http://localhost:3100 | Latest Customer 360 run succeeded. | API validated | Validator found the Customer 360 run and the trigger script reported `SUCCESS` for run `a8b931f3-08f4-4222-9ddb-c3abfe0eb98e`. Manual browser screenshot not captured in this run. |
| MinIO | http://localhost:9001 | Customer 360 output objects are visible. | API validated | Validator confirmed `evidence.storage.customer_360_outputs=true`. Manual browser screenshot not captured in this run. |
| Marquez | http://localhost:5100 | Customer 360 namespace, job, and dataset lineage are visible. | API validated | Marquez API validated final `model.customer_360.mart_customer_360` job lineage after run `a8b931f3-08f4-4222-9ddb-c3abfe0eb98e`. Manual browser screenshot not captured in this run. |
| Jaeger | http://localhost:16686 | Customer 360 trace evidence is visible. | API validated | Validator confirmed `evidence.tracing.jaeger_customer_360=true`. Manual browser screenshot not captured in this run. |
| Polaris | http://localhost:8181 | Customer 360 tables are registered in the catalog. | API validated | Validator confirmed Iceberg outputs via Polaris-backed catalog access. Manual browser screenshot not captured in this run. |

## #263 Posture

Status: Known post-alpha architecture debt.

Issue: https://github.com/Obsidian-Owl/floe/issues/263

Alpha posture: #263 has a release-scope triage comment classifying it as non-blocking for `v0.1.0-alpha.1` only while the alpha Customer 360 stack intentionally includes Iceberg and `floe-iceberg`.

The alpha release does not promise Dagster runs without `floe-iceberg` installed when Iceberg export is disabled.

Promotion rule: before tagging, confirm that the #263 issue still records this non-blocking alpha posture. If the alpha promise changes to support Dagster without Iceberg, #263 becomes blocking.

## Release Decision

Alpha tag is blocked until every required validation gate is PASS on the merged release commit. #263 is the only known architecture debt item currently classified as non-blocking for the alpha promise in this evidence record.

Decision: `BLOCKED`

Decision notes:

- Commit `c1f26a1c3a9ed5c75e4920ec2db4e19246f7beb5` was green for Docs, CI, Helm CI, Security Scan, and Helm Security Scan.
- DevPod + Hetzner E2E passed on commit `c1f26a1c3a9ed5c75e4920ec2db4e19246f7beb5`: 250 passed, 82 deselected, 110 warnings.
- Live Customer 360 validation passed on the pre-merge hardening candidate copied into DevPod and built as `floe-dagster-demo:validation-fix`.
- The release remains blocked until the hardening candidate is committed, merged, and the same CI plus DevPod + Hetzner validation evidence is regenerated against the merged commit.
- Manual browser screenshots for Dagster, MinIO, Marquez, Jaeger, and Polaris were not captured in this run; API validation is recorded above.
- #275 is fixed in the release-hardening patch: final mart-level Marquez lineage is now visible and the validator requires `mart_customer_360` evidence.

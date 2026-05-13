# CI/CD Pipelines

Floe separates fast PR confidence from live validation and release confidence.
The alpha release cutline is declared in `release/floe-release.yaml`, and CI
validates that manifest before release-specific workflows publish artifacts.

## Topology

| Lane | Workflow | Trigger | Purpose |
|---|---|---|---|
| Fast PR | `ci.yml` | PRs and pushes to `main` | Lint, formatting, strict typing, unit tests, contract tests, security, traceability, and release manifest structure. |
| Chart PR | `helm-ci.yaml` | Chart PRs and pushes to `main` | Merge-confidence Helm linting, rendering, schema, unit, diff, and Kind chart validation. |
| Live validation | `e2e.yml` | Merge queue, manual dispatch, `run-e2e` label, or infrastructure/release-manifest path changes | Full Kind E2E validation with artifacts uploaded on every run. |
| Release | `release.yml` | Version tags | Release validation and GitHub Release creation. |
| Package release | `pypi-publish.yml` | Release/publish trigger | Publish only packages declared by the release manifest. |
| Helm release | `helm-release.yaml` | Helm release trigger | Publish the chart list/version allowed by the release manifest Helm policy. |
| Scheduled maintenance | `weekly.yml`, `security.yml`, `codspeed.yml` | Schedules or manual dispatch | Dependency drift, compatibility, security, and performance signals outside default PR CI. |

## PR CI (`ci.yml`)

The required PR gate is `ci-success`. It summarizes these jobs:

| Job | Purpose |
|---|---|
| `lint-typecheck` | Ruff lint, Ruff format check, `mypy --strict`, sleep checks, dbt version requirements. |
| `release-manifest` | Validates `release/floe-release.yaml` with `testing.release.cli validate`. |
| `security` | Bandit and dependency audit. |
| `unit-tests` | Unit test matrix across Python 3.10, 3.11, and 3.12. |
| `contract-tests` | Cross-package contract validation. |
| `traceability` | Requirement marker coverage. |

PR CI stays fast and structural. It does not run live cloud/provider validation.

## E2E (`e2e.yml`)

E2E runs only when explicitly requested or when paths that can affect the live
platform change:

- `merge_group`
- `workflow_dispatch`
- PR label `run-e2e`
- Infra path filter, including charts, tests, packages/plugins, workflow files,
  `release/floe-release.yaml`, and `testing/release/**`

Failures should be classified as product, infrastructure, credential/setup, or
cleanup failures before deciding whether to rerun or block the release.

## Release Confidence

`release.yml`, `pypi-publish.yml`, and `helm-release.yaml` form the release
confidence lanes. They should fail before publishing when the release manifest,
package cutline, artifact counts, version normalization, Helm policy, or release
evidence is invalid.

For the alpha Helm lane, `release/floe-release.yaml` is the publish contract:
`helm.alpha_policy` must be `publish`, `release.helm_version` supplies the
default chart package version, and `helm.charts` supplies the exact chart paths.
Manual Helm release dispatch may explicitly override the version only; it does
not replace the manifest-declared chart list or policy. Chart metadata is live
release input for `helm-release.yaml`, while `helm-ci.yaml` remains the
merge-confidence lane for validating chart changes before they reach release.

`weekly.yml`, `security.yml`, and `codspeed.yml` remain scheduled or manual
maintenance lanes. They provide drift, security, and performance signal without
turning every PR into an expensive live-validation run.

## Local Checks

```bash
uv run pytest testing/tests/unit/test_ci_workflows.py testing/ci/tests/test_github_actions_node24_pins.py -q
uv run python -m testing.release.cli validate --manifest release/floe-release.yaml
```

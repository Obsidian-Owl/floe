# CI/CD Pipelines

Floe separates fast PR confidence from live validation and release confidence.
The alpha release cutline is declared in `release/floe-release.yaml`, and CI
validates that manifest before release-specific workflows publish artifacts.

## Quick Reference

| Trigger | Workflow | Purpose |
|---|---|---|
| Pull request | `ci.yml` | Fast PR confidence plus release manifest structure |
| Manual | `e2e.yml` | Opt-in full E2E validation outside PR and release lanes |
| Manual | `prepare-release.yml` | Runs all release gates, creates tag and GitHub Release only on success |
| Successful Prepare Release / manual `release_tag` backfill | `pypi-publish.yml` | Builds and publishes the manifest package set |
| Manual | `release.yml` | Release-validation smoke only; does not create tags or GitHub Releases |
| Tag `helm-v*` / `charts-v*` / manual | `helm-release.yaml` | Helm chart release when manifest policy allows |
| Schedule / manual | `weekly.yml`, `security.yml`, `codspeed.yml` | Drift, security, performance maintenance |

`helm-ci.yaml` remains the merge-confidence chart lane for pull requests and
pushes to `main`; it validates chart linting, rendering, schema, unit, diff,
and Kind behavior before chart changes reach a release workflow.

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

E2E runs only when explicitly requested with `workflow_dispatch`. Weekly
validation owns scheduled long-running coverage, and `prepare-release.yml` owns
release-blocking E2E/live validation. Pull requests and merge queues do not run
the long E2E lane automatically.

Failures should be classified as product, infrastructure, credential/setup, or
cleanup failures before deciding whether to rerun or block the release.

## Prepare Release

`prepare-release.yml` is the release authority. Maintainers dispatch it with a
version. The workflow runs static gates, package build dry-run, Kind
integration, full DevPod+Hetzner E2E, AWS S3+Glue live validation, cleanup
verification, and evidence generation. It creates the tag and GitHub Release
only after all gates pass.

Dry runs execute the same gates without creating a tag, GitHub Release, or PyPI
publication. Real runs use `dry_run=false`; that successful workflow run uploads
the release metadata consumed by `pypi-publish.yml`.

If a GitHub Release already exists and PyPI publication needs to be retried
after fixing the publish workflow, maintainers may dispatch `pypi-publish.yml`
with an existing `release_tag` and `dry_run=false`. The workflow still validates
the manifest and publishes only `python_packages.publish`.

If a release gate fails, the workflow creates or updates a GitHub issue and
records which outputs were skipped. Product, infrastructure, credential/setup,
and cleanup failures must remain separate in triage.

## Release Confidence

`prepare-release.yml`, `pypi-publish.yml`, and `helm-release.yaml` form the
release confidence lanes. They should fail before publishing when the release
manifest, package cutline, artifact counts, version normalization, Helm policy,
or release evidence is invalid.

For the alpha Helm lane, `release/floe-release.yaml` is the publish contract:
`helm.alpha_policy` must be `publish`, `release.helm_version` supplies the
default chart package version, and `helm.charts` supplies the exact chart paths.
Manual Helm release dispatch may explicitly override the version only; it does
not replace the manifest-declared chart list or policy. Chart metadata is live
release input for `helm-release.yaml`, while `helm-ci.yaml` remains the
merge-confidence lane for validating chart changes before they reach release.

`release.yml` remains a manual release-validation smoke workflow for maintainers
who want a narrower integration check. It does not create release tags, GitHub
Releases, or PyPI publications.

`weekly.yml`, `security.yml`, and `codspeed.yml` remain scheduled or manual
maintenance lanes. They provide drift, security, and performance signal without
turning every PR into an expensive live-validation run. Weekly long-running
validation failures create or update GitHub issues.

## Local Checks

```bash
uv run pytest testing/tests/unit/test_ci_workflows.py testing/ci/tests/test_github_actions_node24_pins.py -q
uv run python -m testing.release.cli validate --manifest release/floe-release.yaml
```

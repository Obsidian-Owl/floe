# Alpha Release Hardening Evidence - 2026-04-28

## Baseline

- Branch: `feat/alpha-hardening-e2e`
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
| #214 demo artifact lineage guard | `make compile-demo`; `uv run pytest testing/ci/tests/test_validate_demo_compiled_artifacts.py testing/ci/tests/test_render_demo_image_values.py testing/ci/tests/test_helm_ci_demo_image_wiring.py -q` | PASS | Demo generation now fails if generated `compiled_artifacts.json` does not preserve `plugins.lineage_backend` from `demo/manifest.yaml`; generated local demo artifacts resolve Marquez |
| Lint | `make lint` | PASS | Ruff check and format check passed |
| Typecheck | `make typecheck` | PASS | mypy strict passed for `packages/ testing/` |
| Unit tests | `make test-unit` | PASS | 9974 passed, 1 skipped, 1 xfailed; coverage 87.64% |
| Helm lint | `make helm-lint` | PASS | `floe-platform` and `floe-jobs` linted successfully |
| Helm schema validation | `make helm-validate` | PASS | kubeconform validated production defaults and test values |
| Helm unit tests | `make helm-test-unit` | PASS | 16 suites, 171 tests passed |
| DevPod + Hetzner E2E attempt 1 | `make devpod-test` | FAIL | Demo image build failed at `RUN pip check`: Dockerfile hardcoded Dagster 1.12.14 / dagster-k8s 0.28.14 after `uv.lock` exported Dagster 1.13.2 / dagster-dbt 0.29.2 / dagster-dlt 0.29.2. Workspace cleanup completed and Hetzner machine `floe-d4ab4` was deleted. |
| Demo image dependency preflight | `DOCKER_PLATFORM=linux/amd64 scripts/with-public-docker-config.sh docker build -f docker/dagster-demo/Dockerfile --build-arg FLOE_PLUGINS="$(.venv/bin/python scripts/resolve-demo-plugins.py --manifest demo/manifest.yaml)" --platform linux/amd64 -t floe-dagster-demo:dependency-check .` | PASS | Build reached `pip check` with no broken requirements, passed smoke imports for Dagster/webserver/k8s/floe packages, and completed container-side `dbt parse` for all three demo products. |
| Demo image dependency regressions | `uv run pytest testing/tests/unit/test_demo_packaging.py testing/ci/tests/test_helm_ci_demo_image_wiring.py testing/ci/tests/test_render_demo_image_values.py testing/ci/tests/test_validate_demo_compiled_artifacts.py -q` | PASS | 142 passed. Guards now forbid dependency-resolving Dockerfile `pip install` after the hash-verified uv export and require Docker runtime dependencies to come from project metadata / `uv.lock`. |

## Decisions

- 2026-04-28: Accepted `GHSA-w8v5-vhqr-4h9v` for `diskcache` 5.6.3 because no patched version is available and the dependency is confined to the optional agent-memory devtool, not runtime platform images. Revisit before beta or when a patched release exists.
- 2026-04-28: #214 is alpha-blocking until DevPod + Hetzner E2E proves Marquez lifecycle evidence. The issue body's old demo-definition root cause is stale, but independent review found the generated runtime artifacts can still be stale/ignored with `plugins.lineage_backend: null`, forcing `NoOpLineageResource`. Added a manifest-driven `compile-demo` guard so generated demo artifacts must preserve the Marquez lineage backend selected in `demo/manifest.yaml`.
- 2026-04-28: #263 remains real architecture debt, but is not blocking `v0.1.0-alpha.1` because the alpha validation profile intentionally includes Iceberg/floe-iceberg and no failing production path is currently known for that profile. Keep it open as release-review/post-alpha architecture work; promote it only if alpha validation requires `floe-orchestrator-dagster` to run without `floe-iceberg` installed when Iceberg export is disabled.
- 2026-04-28: Demo image runtime dependencies must be metadata/lock driven, not Dockerfile driven. Dagster runtime packages (`dagster-webserver`, `dagster-postgres`, `dagster-k8s`) are now exported via root/orchestrator `docker` extras; S3 FileIO comes from `floe-storage-s3` declaring `pyiceberg[s3fs]`; `sqlalchemy<2.1` is encoded as a uv constraint rather than a Dockerfile post-install override.

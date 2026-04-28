# Release Hardening E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** make `main` safe to tag as the first alpha by closing the current release blockers, proving the platform through DevPod + Hetzner E2E, and producing auditable release evidence.

**Architecture:** Treat release hardening as a gated pipeline, not a one-off debug session. All runtime configuration must flow from manifests, chart values, or generated CI overlays; no test may depend on an unstated local image, local path, or workstation-only state. Security and documentation are release gates, not post-release cleanup.

**Tech Stack:** Python 3.10+, Bash, uv, pytest, Ruff, mypy, Helm, helm-unittest, Kind, Kubernetes, DevPod + Hetzner, GitHub Actions, uv-secure, Dependabot, OpenLineage/Marquez.

---

## Current Release Scope

Alpha blockers:

- #265 `Main Helm CI integration fails when floe-dagster-demo image is not preloaded`
- #264 `Triage new uv-secure vulnerability findings in lockfiles`
- #260 `Add verify_ssl parity to SyncHttpLineageTransport`

Release-scope decisions:

- #263 `Decouple Dagster Iceberg export from floe-iceberg internals`
- #214 `OpenLineage: emit RunEvent.START events for dbt model and pipeline lifecycle`

Release gate:

- `main` CI, Helm CI, security validation, DevPod + Hetzner E2E, and release workflow dry-run must all pass before creating `v0.1.0-alpha.1`.

## File Map

Expected modifications:

- `.github/workflows/helm-ci.yaml` - build/load the exact demo image before Helm installs test values; consume a generated image override file.
- `.github/workflows/release.yml` - run the same release-hardening validation path as the alpha gate.
- `testing/ci/render-demo-image-values.py` - new helper that renders Helm value overrides for every Dagster demo image consumer.
- `testing/ci/tests/test_render_demo_image_values.py` - unit tests for generated image override values.
- `testing/ci/tests/test_helm_ci_demo_image_wiring.py` - regression tests proving Helm CI builds/loads and passes the generated image override before install.
- `packages/floe-core/src/floe_core/lineage/transport.py` - add sync `verify_ssl` parity.
- `packages/floe-core/src/floe_core/lineage/emitter.py` - pass `verify_ssl` into sync HTTP transport.
- `packages/floe-core/tests/unit/lineage/test_sync_transport.py` - sync transport TLS behavior tests.
- `packages/floe-core/tests/unit/lineage/test_sync_emitter.py` - config-to-sync-transport propagation tests.
- `testing/ci/uv-security-audit.sh` - update vulnerability policy only after lockfiles are triaged.
- Relevant `uv.lock` files - update vulnerable dependencies where patched versions exist.
- `docs/validation/2026-04-28-alpha-release-hardening.md` - evidence log for final validation.
- `docs/guides/deployment/local-development.md`, `docs/guides/deployment/kubernetes-helm.md`, `demo/README.md` - user-facing first deploy / first data product notes if validation reveals doc gaps.

---

### Task 1: Establish Release-Hardening Branch And Baseline Evidence

**Files:**

- Create: `docs/validation/2026-04-28-alpha-release-hardening.md`

- [ ] **Step 1: Create the branch**

Run:

```bash
git switch main
git pull --ff-only origin main
git switch -c release/alpha-hardening-e2e
```

Expected: branch created from the current `origin/main` head.

- [ ] **Step 2: Record current issue and CI state**

Run:

```bash
gh issue list --repo Obsidian-Owl/floe --state open --limit 100 \
  --json number,title,labels,url \
  --jq '[.[] | {number,title,labels:[.labels[].name],url}]' \
  > /tmp/floe-open-issues.json

gh run list --repo Obsidian-Owl/floe --branch main --limit 20 \
  --json databaseId,workflowName,status,conclusion,headSha,url,createdAt \
  > /tmp/floe-main-runs.json
```

Expected: `/tmp/floe-open-issues.json` contains 12 open issues and `/tmp/floe-main-runs.json` shows current `main` CI state.

- [ ] **Step 3: Write the evidence stub**

Run:

```bash
BASE_SHA="$(git rev-parse HEAD)"
cat > docs/validation/2026-04-28-alpha-release-hardening.md <<EOF
# Alpha Release Hardening Evidence - 2026-04-28

## Baseline

- Branch: `release/alpha-hardening-e2e`
- Base: `${BASE_SHA}`
- Alpha blockers: #265, #264, #260
- Release-scope decisions: #263, #214

## Validation Runs

| Gate | Command / URL | Result | Notes |
| --- | --- | --- | --- |
| Baseline main Helm CI | https://github.com/Obsidian-Owl/floe/actions/runs/25027006173 | FAIL | Helm CI integration failed on #265 |

## Decisions

- Pending.
EOF
```

- [ ] **Step 4: Commit the evidence stub**

Run:

```bash
git add docs/validation/2026-04-28-alpha-release-hardening.md
git commit -m "docs: start alpha release hardening evidence"
```

Expected: one docs-only commit.

---

### Task 2: Fix #265 With Manifest/Values-Driven Demo Image Overrides

**Files:**

- Create: `testing/ci/render-demo-image-values.py`
- Create: `testing/ci/tests/test_render_demo_image_values.py`
- Modify: `.github/workflows/helm-ci.yaml`

- [ ] **Step 1: Write failing tests for the Helm image override renderer**

Create `testing/ci/tests/test_render_demo_image_values.py`:

```python
"""Tests for rendering Dagster demo image Helm overrides."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


MODULE_PATH = Path(__file__).resolve().parents[1] / "render-demo-image-values.py"
spec = importlib.util.spec_from_file_location("render_demo_image_values", MODULE_PATH)
assert spec is not None and spec.loader is not None
render_demo_image_values = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render_demo_image_values)


def test_render_demo_image_values_sets_all_dagster_image_consumers() -> None:
    rendered = render_demo_image_values.render_values(
        repository="floe-dagster-demo",
        tag="72c3dcf7e273",
        pull_policy="Never",
    )

    values = yaml.safe_load(rendered)
    expected_image = {
        "repository": "floe-dagster-demo",
        "tag": "72c3dcf7e273",
        "pullPolicy": "Never",
    }

    assert values["dagsterDemoImage"] == expected_image
    assert values["dagster"]["dagsterWebserver"]["image"] == expected_image
    assert values["dagster"]["dagsterDaemon"]["image"] == expected_image
    assert values["dagster"]["runLauncher"]["config"]["k8sRunLauncher"]["image"] == expected_image
    assert values["dagster"]["runLauncher"]["config"]["k8sRunLauncher"]["imagePullPolicy"] == "Never"


def test_render_demo_image_values_rejects_empty_repository() -> None:
    try:
        render_demo_image_values.render_values(repository="", tag="abc", pull_policy="Never")
    except SystemExit as exc:
        assert "repository cannot be empty" in str(exc)
    else:
        raise AssertionError("empty repository must fail")


def test_render_demo_image_values_rejects_empty_tag() -> None:
    try:
        render_demo_image_values.render_values(repository="floe-dagster-demo", tag="", pull_policy="Never")
    except SystemExit as exc:
        assert "tag cannot be empty" in str(exc)
    else:
        raise AssertionError("empty tag must fail")
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
uv run pytest testing/ci/tests/test_render_demo_image_values.py -q
```

Expected: FAIL because `testing/ci/render-demo-image-values.py` does not exist.

- [ ] **Step 3: Implement the renderer**

Create `testing/ci/render-demo-image-values.py`:

```python
"""Render Helm value overrides for the Dagster demo image.

The chart's test values use YAML anchors, but Helm override merging happens
after YAML anchor expansion. This helper writes every concrete Dagster image
consumer so CI and DevPod validation use the exact image that was built and
loaded into Kind.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import yaml


def _validate_non_empty(name: str, value: str) -> str:
    value = value.strip()
    if not value:
        raise SystemExit(f"{name} cannot be empty")
    return value


def render_values(repository: str, tag: str, pull_policy: str) -> str:
    """Return YAML overrides for every Dagster image consumer."""
    repository = _validate_non_empty("repository", repository)
    tag = _validate_non_empty("tag", tag)
    pull_policy = _validate_non_empty("pull_policy", pull_policy)

    image = {
        "repository": repository,
        "tag": tag,
        "pullPolicy": pull_policy,
    }
    values: dict[str, Any] = {
        "dagsterDemoImage": image,
        "dagster": {
            "dagsterWebserver": {"image": image},
            "dagsterDaemon": {"image": image},
            "runLauncher": {
                "config": {
                    "k8sRunLauncher": {
                        "image": image,
                        "imagePullPolicy": pull_policy,
                    }
                }
            },
        },
    }
    return yaml.safe_dump(values, sort_keys=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("FLOE_DEMO_IMAGE_REPOSITORY", ""))
    parser.add_argument("--tag", default=os.environ.get("FLOE_DEMO_IMAGE_TAG", ""))
    parser.add_argument("--pull-policy", default=os.environ.get("FLOE_DEMO_IMAGE_PULL_POLICY", "Never"))
    args = parser.parse_args()
    sys.stdout.write(render_values(args.repository, args.tag, args.pull_policy))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify the renderer tests pass**

Run:

```bash
uv run pytest testing/ci/tests/test_render_demo_image_values.py -q
```

Expected: PASS.

- [ ] **Step 5: Write failing workflow wiring tests**

Create `testing/ci/tests/test_helm_ci_demo_image_wiring.py`:

```python
"""Regression tests for Helm CI demo image wiring."""

from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/helm-ci.yaml")


def test_helm_ci_builds_demo_image_before_installing_test_values() -> None:
    workflow = WORKFLOW.read_text()
    build_index = workflow.find("make build-demo-image")
    install_index = workflow.find("helm upgrade --install floe-test charts/floe-platform")

    assert build_index != -1, "Helm CI must build/load the Dagster demo image"
    assert install_index != -1, "Helm CI must install the floe-platform chart"
    assert build_index < install_index, "demo image must be loaded before Helm install"


def test_helm_ci_passes_generated_demo_image_values_to_install_and_diff() -> None:
    workflow = WORKFLOW.read_text()

    assert "render-demo-image-values.py" in workflow
    assert "/tmp/floe-demo-image-values.yaml" in workflow
    assert "--values /tmp/floe-demo-image-values.yaml" in workflow
```

- [ ] **Step 6: Run the workflow wiring tests and verify they fail**

Run:

```bash
uv run pytest testing/ci/tests/test_helm_ci_demo_image_wiring.py -q
```

Expected: FAIL because Helm CI does not build/load the image or pass the generated image values.

- [ ] **Step 7: Update Helm CI integration job**

Modify `.github/workflows/helm-ci.yaml` in the integration job after `Update chart dependencies` and before `Install helm-diff plugin`:

```yaml
      - name: Build and load Dagster demo image
        run: |
          set -euo pipefail
          eval "$(python3 testing/ci/resolve-demo-image-ref.py --field exports)"
          echo "FLOE_DEMO_IMAGE=${FLOE_DEMO_IMAGE}"
          FLOE_KIND_CLUSTER=helm-test KIND_CLUSTER_NAME=helm-test \
            FLOE_DEMO_IMAGE_REPOSITORY="${FLOE_DEMO_IMAGE_REPOSITORY}" \
            FLOE_DEMO_IMAGE_TAG="${FLOE_DEMO_IMAGE_TAG}" \
            make build-demo-image
          python3 testing/ci/render-demo-image-values.py \
            --repository "${FLOE_DEMO_IMAGE_REPOSITORY}" \
            --tag "${FLOE_DEMO_IMAGE_TAG}" \
            --pull-policy Never \
            > /tmp/floe-demo-image-values.yaml
          cat /tmp/floe-demo-image-values.yaml
```

Modify both Helm diff and install commands in `.github/workflows/helm-ci.yaml` to include the generated values file after `values-test.yaml`:

```yaml
            --values charts/floe-platform/values-test.yaml \
            --values /tmp/floe-demo-image-values.yaml \
```

- [ ] **Step 8: Verify local tests pass**

Run:

```bash
uv run pytest testing/ci/tests/test_render_demo_image_values.py testing/ci/tests/test_helm_ci_demo_image_wiring.py -q
```

Expected: PASS.

- [ ] **Step 9: Run Helm render with generated overrides**

Run:

```bash
eval "$(python3 testing/ci/resolve-demo-image-ref.py --field exports)"
python3 testing/ci/render-demo-image-values.py > /tmp/floe-demo-image-values.yaml
helm dependency update charts/floe-platform
helm template floe-test charts/floe-platform \
  --namespace floe-test \
  --values charts/floe-platform/values-test.yaml \
  --values /tmp/floe-demo-image-values.yaml \
  | rg 'image:|imagePullPolicy: Never|floe-dagster-demo'
```

Expected: rendered Dagster webserver, daemon, and run launcher image values use the resolved tag, not `latest`.

- [ ] **Step 10: Commit #265 fix**

Run:

```bash
git add .github/workflows/helm-ci.yaml testing/ci/render-demo-image-values.py testing/ci/tests/test_render_demo_image_values.py testing/ci/tests/test_helm_ci_demo_image_wiring.py
git commit -m "ci: load resolved Dagster demo image for Helm integration"
```

Expected: one focused commit for #265.

---

### Task 3: Fix #260 Sync Lineage `verify_ssl` Parity

**Files:**

- Modify: `packages/floe-core/src/floe_core/lineage/transport.py`
- Modify: `packages/floe-core/src/floe_core/lineage/emitter.py`
- Modify: `packages/floe-core/tests/unit/lineage/test_sync_transport.py`
- Modify: `packages/floe-core/tests/unit/lineage/test_sync_emitter.py`

- [ ] **Step 1: Add sync transport tests for SSL parity**

Append tests to `packages/floe-core/tests/unit/lineage/test_sync_transport.py`:

```python
def test_sync_http_transport_defaults_to_secure_ssl_verification() -> None:
    mock_client = MagicMock()
    with patch("httpx.Client", return_value=mock_client) as mock_client_class:
        SyncHttpLineageTransport(url="https://marquez.example/api/v1/lineage")

    kwargs = mock_client_class.call_args.kwargs
    assert kwargs["timeout"] == 5.0
    assert kwargs["verify"] is not False


def test_sync_http_transport_allows_local_insecure_ssl_opt_out() -> None:
    mock_client = MagicMock()
    with patch.dict(os.environ, {"FLOE_ENVIRONMENT": "development"}, clear=False):
        with patch("httpx.Client", return_value=mock_client) as mock_client_class:
            SyncHttpLineageTransport(
                url="https://localhost:5000/api/v1/lineage",
                verify_ssl=False,
            )

    assert mock_client_class.call_args.kwargs["verify"] is False


def test_sync_http_transport_rejects_insecure_ssl_in_production() -> None:
    with patch.dict(os.environ, {"FLOE_ENVIRONMENT": "production"}, clear=False):
        try:
            SyncHttpLineageTransport(
                url="https://marquez.example/api/v1/lineage",
                verify_ssl=False,
            )
        except ValueError as exc:
            assert "Cannot disable SSL verification in production" in str(exc)
        else:
            raise AssertionError("production verify_ssl=False must fail")
```

Ensure the file imports `os`, `MagicMock`, and `patch` if not already present:

```python
import os
from unittest.mock import MagicMock, patch
```

- [ ] **Step 2: Run sync transport tests and verify failure**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/lineage/test_sync_transport.py -q
```

Expected: FAIL because `SyncHttpLineageTransport` does not accept `verify_ssl`.

- [ ] **Step 3: Implement sync transport SSL parity**

Modify `packages/floe-core/src/floe_core/lineage/transport.py`:

```python
class SyncHttpLineageTransport:
    """Synchronous HTTP lineage transport using httpx.Client.

    Sends OpenLineage events to a remote HTTP endpoint using a blocking
    httpx.Client. Exceptions from the HTTP layer propagate to the caller;
    error isolation is the emitter's responsibility.
    """

    def __init__(
        self,
        url: str,
        timeout: float = 5.0,
        api_key: str | None = None,
        verify_ssl: bool = True,
    ) -> None:
        """Initialise the sync HTTP transport.

        Args:
            url: The OpenLineage API endpoint URL.
            timeout: Request timeout in seconds (default 5.0).
            api_key: Optional Bearer token for Authorization header.
            verify_ssl: Whether to verify SSL certificates for HTTPS endpoints.

        Raises:
            ValueError: If URL is invalid or uses unsupported scheme, or if
                SSL verification is disabled in production.
        """
        import httpx

        parsed = urlparse(url)
        if parsed.scheme not in _ALLOWED_URL_SCHEMES:
            allowed = sorted(_ALLOWED_URL_SCHEMES)
            msg = f"URL scheme must be one of {allowed}, got: {parsed.scheme!r}"
            raise ValueError(msg)
        if not parsed.netloc:
            raise ValueError(f"Invalid URL: missing host in {url!r}")

        if parsed.username or parsed.password:
            clean_netloc = parsed.hostname or ""
            if parsed.port:
                clean_netloc += f":{parsed.port}"
            url = f"{parsed.scheme}://{clean_netloc}{parsed.path}"
            if parsed.query:
                url += f"?{parsed.query}"

        verify: bool | ssl.SSLContext
        ssl_context = _create_ssl_context(url, verify_ssl)
        if parsed.scheme == "https":
            verify = ssl_context if ssl_context is not None else False
        else:
            verify = True

        self._url = url
        self._timeout = timeout
        self._api_key = api_key
        self._verify_ssl = verify_ssl
        self._client: httpx.Client = httpx.Client(timeout=timeout, verify=verify)
```

- [ ] **Step 4: Propagate config from sync emitter**

Modify `packages/floe-core/src/floe_core/lineage/emitter.py` where `SyncHttpLineageTransport` is created:

```python
sync_transport = SyncHttpLineageTransport(
    url=http_config.url,
    timeout=http_config.timeout,
    api_key=http_config.api_key,
    verify_ssl=http_config.verify_ssl,
)
```

- [ ] **Step 5: Add sync emitter propagation test**

Add to `packages/floe-core/tests/unit/lineage/test_sync_emitter.py`:

```python
def test_sync_http_config_passes_verify_ssl_to_transport() -> None:
    config = LineageConfig(
        enabled=True,
        transport={
            "type": "http",
            "url": "https://localhost:5000/api/v1/lineage",
            "verify_ssl": False,
        },
    )

    with patch.dict(os.environ, {"FLOE_ENVIRONMENT": "development"}, clear=False):
        emitter = create_sync_lineage_emitter(config)

    transport = emitter.transport
    assert isinstance(transport, SyncHttpLineageTransport)
    assert transport._verify_ssl is False
```

If the test file uses a different factory name, use the existing sync emitter factory already used in that file and keep the assertion on `SyncHttpLineageTransport`.

- [ ] **Step 6: Verify lineage tests pass**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/lineage/test_sync_transport.py packages/floe-core/tests/unit/lineage/test_sync_emitter.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit #260 fix**

Run:

```bash
git add packages/floe-core/src/floe_core/lineage/transport.py packages/floe-core/src/floe_core/lineage/emitter.py packages/floe-core/tests/unit/lineage/test_sync_transport.py packages/floe-core/tests/unit/lineage/test_sync_emitter.py
git commit -m "fix: align sync lineage TLS verification"
```

Expected: one focused commit for #260.

---

### Task 4: Resolve #264 Security Audit Findings

**Files:**

- Modify: `uv.lock`
- Modify: `packages/floe-core/uv.lock`
- Modify: `devtools/agent-memory/uv.lock`
- Modify: `testing/ci/uv-security-audit.sh` only if a remaining finding has no viable patched version and is intentionally accepted.
- Modify: `docs/validation/2026-04-28-alpha-release-hardening.md`

- [ ] **Step 1: Capture current Dependabot critical/high findings**

Run:

```bash
gh api 'repos/Obsidian-Owl/floe/dependabot/alerts?state=open&per_page=100' \
  --jq '[.[] | select(.security_vulnerability.severity == "critical" or .security_vulnerability.severity == "high") | {number:.number, severity:.security_vulnerability.severity, package:.dependency.package.name, manifest:.dependency.manifest_path, advisory:.security_advisory.ghsa_id, vulnerable:.security_vulnerability.vulnerable_version_range, patched:.security_vulnerability.first_patched_version.identifier}] | sort_by(.manifest,.package)' \
  > /tmp/floe-critical-high-dependabot.json
```

Expected: JSON file includes the critical/high findings currently blocking alpha.

- [ ] **Step 2: Update root lock dependencies**

Run:

```bash
uv lock --upgrade-package GitPython --upgrade-package dagster
```

Expected: root `uv.lock` updates `GitPython` to at least `3.1.47` and `dagster` to at least `1.13.1` if constraints allow.

- [ ] **Step 3: Update floe-core lock dependencies**

Run:

```bash
cd packages/floe-core
uv lock --upgrade-package protobuf --upgrade-package pyasn1 --upgrade-package pyopenssl
cd ../..
```

Expected: `packages/floe-core/uv.lock` updates patched packages where constraints allow.

- [ ] **Step 4: Update agent-memory lock dependencies**

Run:

```bash
cd devtools/agent-memory
uv lock \
  --upgrade-package aiohttp \
  --upgrade-package cbor2 \
  --upgrade-package cryptography \
  --upgrade-package litellm \
  --upgrade-package pillow \
  --upgrade-package pypdf \
  --upgrade-package pytest \
  --upgrade-package python-dotenv \
  --upgrade-package python-multipart \
  --upgrade-package requests \
  --upgrade-package mako
cd ../..
```

Expected: `devtools/agent-memory/uv.lock` updates all packages with patched versions.

- [ ] **Step 5: Re-run security audit locally**

Run:

```bash
./testing/ci/uv-security-audit.sh
```

Expected: PASS, or FAIL only for advisories with no patched version.

- [ ] **Step 6: Handle no-fix findings explicitly**

If a no-fix finding remains, edit `testing/ci/uv-security-audit.sh` so `IGNORE_VULNS` includes only the exact GHSA id and a dated rationale comment:

```bash
# - GHSA-69v7-xpr6-6gjm: lupa <=2.6 has no patched version as of 2026-04-28.
#   Agent-memory is a devtool-only optional component, not installed in runtime
#   platform images. Revisit before beta or when a patched release exists.
IGNORE_VULNS="${UV_SECURE_IGNORE_VULNS:-GHSA-69v7-xpr6-6gjm}"
```

Do not keep stale ignores where Dependabot now reports a patched version.

- [ ] **Step 7: Run the broader security lane**

Run:

```bash
uv run ruff check .
uv run mypy --strict packages/ testing/
uv run bandit -r packages plugins testing -c pyproject.toml
```

Expected: PASS.

- [ ] **Step 8: Record security evidence**

Append to `docs/validation/2026-04-28-alpha-release-hardening.md`:

```markdown
| Dependency audit | `./testing/ci/uv-security-audit.sh` | PASS | Critical/high patched or explicitly accepted |
| Static security | `uv run bandit -r packages plugins testing -c pyproject.toml` | PASS | No alpha-blocking findings |
```

- [ ] **Step 9: Commit #264 fix**

Run:

```bash
git add uv.lock packages/floe-core/uv.lock devtools/agent-memory/uv.lock testing/ci/uv-security-audit.sh docs/validation/2026-04-28-alpha-release-hardening.md
git commit -m "chore: resolve alpha dependency audit findings"
```

Expected: one focused security commit.

---

### Task 5: Decide #214 And #263 Release Scope

**Files:**

- Modify: `docs/validation/2026-04-28-alpha-release-hardening.md`
- GitHub issue comments on #214 and #263

- [ ] **Step 1: Validate #214 against alpha proof requirement**

Run DevPod/Hetzner E2E after Tasks 2-4 and query Marquez for event types:

```bash
DEVPOD_WORKSPACE=floe-alpha-hardening \
DEVPOD_REMOTE_E2E_TIMEOUT=7200 \
./scripts/devpod-test.sh
```

Expected: E2E run completes or produces diagnostic artifacts under `test-artifacts/`.

- [ ] **Step 2: Classify #214**

If Marquez proof requires START events for alpha, comment on #214:

```text
Classifying as alpha-blocker.

Reason: alpha E2E must prove OpenLineage lifecycle events in Marquez, and current validation only proves terminal events. This needs to be fixed before `v0.1.0-alpha.1`.
```

Then run:

```bash
gh issue edit 214 --repo Obsidian-Owl/floe --add-label alpha-blocker
```

If Marquez proof only requires successful lineage roundtrip with completed events for alpha, comment on #214:

```text
Keeping as post-alpha release-review item.

Reason: alpha E2E proves Marquez receives lineage after Iceberg writes, but START/RUNNING lifecycle completeness is not required for the first alpha tag. This remains required before beta because OpenLineage is a critical capability.
```

- [ ] **Step 3: Classify #263**

Run:

```bash
rg -n 'from floe_iceberg|import floe_iceberg' plugins/floe-orchestrator-dagster/src packages/floe-core/src
```

If direct imports affect runtime when Iceberg export is not configured, add `alpha-blocker` to #263. If not, leave as `release-review` and document that it is beta-blocking architecture debt.

- [ ] **Step 4: Record the decisions**

Append one of these exact decision blocks to `docs/validation/2026-04-28-alpha-release-hardening.md`.

Use this block if #214 and #263 are alpha blockers:

```markdown
## Release-Scope Decisions

- #214: alpha-blocker because alpha E2E requires Marquez to prove OpenLineage lifecycle START and terminal events for demo data products.
- #263: alpha-blocker because direct Dagster imports from floe-iceberg affect runtime when Iceberg export is not configured.
```

Use this block if they are post-alpha:

```markdown
## Release-Scope Decisions

- #214: post-alpha because alpha E2E proves Marquez receives lineage after Iceberg writes, while START/RUNNING lifecycle completeness remains required before beta.
- #263: post-alpha because current alpha runtime includes Iceberg export and no failure was reproduced when Iceberg export is configured; the coupling remains beta-blocking architecture debt.
```

- [ ] **Step 5: Commit release-scope decisions**

Run:

```bash
git add docs/validation/2026-04-28-alpha-release-hardening.md
git commit -m "docs: record alpha release scope decisions"
```

Expected: one docs/evidence commit.

---

### Task 6: Run Full Local And Remote Validation Gates

**Files:**

- Modify: `docs/validation/2026-04-28-alpha-release-hardening.md`

- [ ] **Step 1: Run local fast gates**

Run:

```bash
uv run ruff check .
uv run mypy --strict packages/ testing/
uv run pytest packages/floe-core/tests/unit/lineage testing/ci/tests -q
```

Expected: PASS.

- [ ] **Step 2: Run Helm structural gates**

Run:

```bash
make helm-lint
make helm-validate
make helm-test-unit
```

Expected: PASS.

- [ ] **Step 3: Run full DevPod + Hetzner E2E**

Run:

```bash
DEVPOD_WORKSPACE=floe-alpha-hardening \
DEVPOD_REMOTE_E2E_TIMEOUT=7200 \
DEVPOD_REMOTE_POLL_FAILURE_LIMIT=30 \
./scripts/devpod-test.sh
```

Expected: PASS. If it fails, preserve `test-artifacts/devpod-*`, open or update the relevant GitHub issue, and do not tag.

- [ ] **Step 4: Run main release workflow dry-run**

After pushing the branch and opening a PR, use the GitHub UI or CLI:

```bash
gh workflow run release.yml --repo Obsidian-Owl/floe --ref release/alpha-hardening-e2e -f run_integration=true
```

Expected: release workflow `validate` and `integration-tests` pass. It must not create a GitHub Release because this is workflow_dispatch, not a tag push.

- [ ] **Step 5: Record validation evidence**

Append rows to `docs/validation/2026-04-28-alpha-release-hardening.md` using concrete values:

```bash
STAMP="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
ARTIFACT_DIR="$(ls -td test-artifacts/devpod-* 2>/dev/null | head -1 || true)"
RELEASE_RUN_URL="$(gh run list --repo Obsidian-Owl/floe --workflow release.yml --limit 1 --json url --jq '.[0].url')"
cat >> docs/validation/2026-04-28-alpha-release-hardening.md <<EOF
| Local fast gates | \`uv run ruff check . && uv run mypy --strict packages/ testing/ && uv run pytest packages/floe-core/tests/unit/lineage testing/ci/tests -q\` | PASS | ${STAMP} |
| Helm structural gates | \`make helm-lint && make helm-validate && make helm-test-unit\` | PASS | ${STAMP} |
| DevPod + Hetzner E2E | \`./scripts/devpod-test.sh\` | PASS | ${ARTIFACT_DIR:-no local artifact directory produced} |
| Release workflow dry-run | ${RELEASE_RUN_URL} | PASS | workflow_dispatch with integration |
EOF
```

- [ ] **Step 6: Commit validation evidence**

Run:

```bash
git add docs/validation/2026-04-28-alpha-release-hardening.md
git commit -m "docs: capture alpha hardening validation evidence"
```

Expected: one docs/evidence commit.

---

### Task 7: Documentation Uplift For First Alpha

**Files:**

- Modify: `README.md`
- Modify: `docs/guides/deployment/local-development.md`
- Modify: `docs/guides/deployment/kubernetes-helm.md`
- Modify: `demo/README.md`
- Modify: `docs/validation/2026-04-28-alpha-release-hardening.md`

- [ ] **Step 1: Add a first-alpha release note section**

Add to `README.md`:

```markdown
## Alpha Status

floe is approaching its first alpha release. Alpha validation requires:

- main CI and Helm CI passing,
- dependency/security audit passing or explicitly risk-accepted,
- DevPod + Hetzner E2E passing,
- Marquez/OpenLineage proof for demo lineage,
- release workflow dry-run passing before a tag is created.
```

- [ ] **Step 2: Document DevPod + Hetzner validation**

Add to `docs/guides/deployment/local-development.md`:

````markdown
## Remote E2E Validation With DevPod + Hetzner

Use remote validation for full E2E because the platform can exceed local memory.

```bash
DEVPOD_WORKSPACE=floe-alpha-hardening ./scripts/devpod-test.sh
```

The script creates the workspace, runs the remote E2E flow, collects artifacts
under `test-artifacts/`, and deletes the workspace on exit to avoid ongoing
Hetzner cost.
```
````

- [ ] **Step 3: Document Helm image contract**

Add to `docs/guides/deployment/kubernetes-helm.md`:

```markdown
## Dagster Demo Image Contract

Demo and CI installs must use the same Dagster image for the webserver, daemon,
and K8s run launcher. CI generates an override values file with
`testing/ci/render-demo-image-values.py` so the chart consumes the exact image
that was built and loaded into Kind. Do not rely on `latest` being present in
the cluster.
```

- [ ] **Step 4: Document first data product validation**

Add to `demo/README.md`:

````markdown
## Validating A Demo Data Product

Compile demo products before building the Dagster demo image:

```bash
make compile-demo
make build-demo-image
```

The demo image includes the generated Dagster definitions and dbt artifacts
for the configured demo products. The image tag is resolved by
`testing/ci/resolve-demo-image-ref.py` so repeated runs do not silently reuse a
stale mutable image.
```
````

- [ ] **Step 5: Run docs-adjacent checks**

Run:

```bash
uv run ruff check README.md docs/guides/deployment/local-development.md docs/guides/deployment/kubernetes-helm.md demo/README.md || true
rg -n 'latest|floe-dagster-demo|devpod-test|alpha' README.md docs/guides/deployment/local-development.md docs/guides/deployment/kubernetes-helm.md demo/README.md
```

Expected: references are present and do not instruct users to rely on unbuilt `latest` images.

- [ ] **Step 6: Commit docs uplift**

Run:

```bash
git add README.md docs/guides/deployment/local-development.md docs/guides/deployment/kubernetes-helm.md demo/README.md docs/validation/2026-04-28-alpha-release-hardening.md
git commit -m "docs: document alpha validation and demo image contract"
```

Expected: one docs commit.

---

### Task 8: Ship Release-Hardening PR

**Files:**

- No additional file changes expected.

- [ ] **Step 1: Run final pre-push gates**

Run:

```bash
uv run --no-sync pre-commit run --hook-stage pre-push --all-files
```

Expected: PASS.

- [ ] **Step 2: Push branch**

Run:

```bash
git push -u origin release/alpha-hardening-e2e
```

Expected: branch pushed.

- [ ] **Step 3: Open draft PR**

Run:

```bash
gh pr create --repo Obsidian-Owl/floe \
  --draft \
  --title "[codex] Harden alpha E2E release path" \
  --body-file docs/validation/2026-04-28-alpha-release-hardening.md
```

Expected: draft PR opened with validation evidence.

- [ ] **Step 4: Watch CI**

Run:

```bash
gh pr checks --repo Obsidian-Owl/floe --watch
```

Expected: all required checks pass.

- [ ] **Step 5: Mark ready for review**

Run:

```bash
gh pr ready --repo Obsidian-Owl/floe
```

Expected: PR is ready once validation evidence is complete.

---

### Task 9: Post-Merge Alpha Tag Gate

**Files:**

- No file changes expected unless version normalization is added as a separate PR.

- [ ] **Step 1: Sync after merge**

Run:

```bash
git switch main
git pull --ff-only origin main
```

Expected: local `main` includes the release-hardening merge commit.

- [ ] **Step 2: Confirm open alpha blockers**

Run:

```bash
gh issue list --repo Obsidian-Owl/floe --state open --label alpha-blocker --json number,title,url
```

Expected: empty list. If not empty, do not tag.

- [ ] **Step 3: Confirm post-merge CI is green**

Run:

```bash
gh run list --repo Obsidian-Owl/floe --branch main --limit 10 \
  --json workflowName,status,conclusion,headSha,url \
  --jq '.[] | {workflowName,status,conclusion,url}'
```

Expected: current `main` CI, Helm CI, CodeQL, Dependency Graph, and CodSpeed are `completed/success`.

- [ ] **Step 4: Trigger release dry-run from main**

Run:

```bash
gh workflow run release.yml --repo Obsidian-Owl/floe --ref main -f run_integration=true
```

Expected: `Validate Release` and `Integration Tests` pass.

- [ ] **Step 5: Tag first alpha**

Run only after all gates pass:

```bash
git tag -a v0.1.0-alpha.1 -m "v0.1.0-alpha.1"
git push origin v0.1.0-alpha.1
```

Expected: release workflow runs on the tag and creates a prerelease because the tag contains `-alpha.1`.

---

## Subagent Execution Model

Use fresh workers with disjoint ownership:

- Worker A owns #265: `.github/workflows/helm-ci.yaml`, `testing/ci/render-demo-image-values.py`, `testing/ci/tests/test_render_demo_image_values.py`, `testing/ci/tests/test_helm_ci_demo_image_wiring.py`.
- Worker B owns #260: lineage transport/emitter files and unit tests.
- Worker C owns #264: lockfile updates, `uv-security-audit.sh`, and security evidence.
- Worker D owns release documentation and evidence updates.
- Main agent owns integration review, DevPod + Hetzner validation, PR creation, and release gate decisions.

Workers are not alone in the codebase. They must not revert edits from other workers and must adjust to concurrently landed changes.

## Plan Self-Review

Spec coverage:

- #265 is covered by Task 2 and validated by Task 6.
- #260 is covered by Task 3 and validated by Task 6.
- #264 is covered by Task 4 and validated by Task 6.
- #214/#263 release-scope decisions are covered by Task 5.
- Docs uplift is covered by Task 7.
- PR/merge/tag gates are covered by Tasks 8 and 9.

Placeholder scan:

- No unresolved placeholder markers are intentionally present.
- Evidence tables are populated through shell commands that capture concrete runtime values.

Type consistency:

- New helper name is consistently `render-demo-image-values.py`.
- Existing helper name remains `resolve-demo-image-ref.py`.
- Helm override path is consistently `/tmp/floe-demo-image-values.yaml`.

# Alpha Docs, Demo, And Release Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the documentation site, Customer 360 golden demo validation, and release-risk closure required before tagging `v0.1.0-alpha.1`.

**Architecture:** Keep documentation as Markdown in-repo, add MkDocs Material as the browsable site layer, and make demo validation evidence-driven rather than UI-automation-heavy. Release readiness is enforced through CI/docs checks, Customer 360 validation tooling, GitHub Actions upgrade work, Devpod kubeconfig portability, and a final evidence checklist.

**Tech Stack:** MkDocs Material, Python 3.10+, PyYAML, pytest, Make, GitHub Actions, Devpod + Hetzner, Helm, Kubernetes, Dagster, MinIO, Marquez, Jaeger.

---

## File Map

- Create `mkdocs.yml`: site navigation, Material theme config, strict docs build.
- Modify `pyproject.toml`: add MkDocs dependencies to workspace development dependencies.
- Modify `Makefile`: add docs commands, Customer 360 validation commands, and portable Devpod kubeconfig variable.
- Create `.github/workflows/docs.yml`: docs build CI.
- Create `testing/ci/validate-docs-navigation.py`: deterministic nav/page validator for alpha-critical docs.
- Create `testing/ci/tests/test_validate_docs_navigation.py`: unit tests for docs validator.
- Create `docs/start-here/index.md`: user-facing entry point.
- Create `docs/get-started/index.md`: first-platform and first-data-product guide hub.
- Create `docs/get-started/first-platform.md`: platform deployment walkthrough.
- Create `docs/get-started/first-data-product.md`: data product creation walkthrough.
- Create `docs/demo/index.md`: demo landing page.
- Create `docs/demo/customer-360.md`: golden demo guide.
- Create `docs/demo/customer-360-validation.md`: expected outputs and manual UI checklist.
- Create `docs/operations/devpod-hetzner.md`: remote validation workflow.
- Create `docs/operations/troubleshooting.md`: known hardening failure modes and diagnostics.
- Create `docs/reference/index.md`: reference hub.
- Create `docs/contributing/index.md`: contributor entry point.
- Create `docs/contributing/documentation-standards.md`: docs standards and PR expectations.
- Create `docs/releases/v0.1.0-alpha.1-checklist.md`: release checklist and evidence template.
- Create `testing/demo/customer360_validator.py`: reusable Customer 360 validation library.
- Create `testing/ci/validate-customer-360-demo.py`: CLI wrapper around the validator.
- Create `testing/tests/unit/test_customer360_validator.py`: unit tests with fake command/HTTP runners.
- Create `testing/tests/unit/test_demo_makefile_kubeconfig.py`: guards against reintroducing hardcoded `devpod-floe.config`.
- Create `testing/ci/tests/test_github_actions_node24_pins.py`: guards for Node 24-compatible pinned action SHAs.
- Modify `.github/workflows/*.yml` and `.github/workflows/*.yaml`: update pinned actions for #271.
- Create `docs/validation/2026-04-29-alpha-customer-360-release-validation.md`: final evidence record after remote validation.

## Task 1: Add Docs Site Tooling And CI

**Files:**
- Create: `mkdocs.yml`
- Create: `.github/workflows/docs.yml`
- Modify: `pyproject.toml`
- Modify: `Makefile`

- [ ] **Step 1: Add MkDocs dependencies**

Run:

```bash
uv add "mkdocs>=1.6.1" "mkdocs-material>=9.7.0"
```

Expected: `pyproject.toml` and `uv.lock` are updated.

- [ ] **Step 2: Create the initial MkDocs config**

Create `mkdocs.yml` with:

```yaml
site_name: Floe
site_description: Open platform for building internal data platforms.
repo_url: https://github.com/Obsidian-Owl/floe
repo_name: Obsidian-Owl/floe
strict: true

theme:
  name: material
  features:
    - navigation.sections
    - navigation.indexes
    - navigation.top
    - search.suggest
    - search.highlight
    - content.code.copy
  palette:
    - scheme: default
      primary: blue grey
      accent: teal

markdown_extensions:
  - admonition
  - attr_list
  - md_in_html
  - pymdownx.details
  - pymdownx.superfences
  - pymdownx.highlight:
      anchor_linenums: true

nav:
  - Home: index.md
  - Start Here:
      - start-here/index.md
  - Get Started:
      - get-started/index.md
      - Deploy Your First Platform: get-started/first-platform.md
      - Build Your First Data Product: get-started/first-data-product.md
  - Demo:
      - demo/index.md
      - Customer 360 Golden Demo: demo/customer-360.md
      - Customer 360 Validation: demo/customer-360-validation.md
  - Concepts:
      - Architecture Summary: architecture/ARCHITECTURE-SUMMARY.md
      - Four-Layer Model: architecture/four-layer-overview.md
      - Plugin System: architecture/plugin-system/index.md
      - Opinionation Boundaries: architecture/opinionation-boundaries.md
      - Compiled Artifacts: contracts/compiled-artifacts.md
  - Operations:
      - Devpod + Hetzner: operations/devpod-hetzner.md
      - Troubleshooting: operations/troubleshooting.md
      - Deployment Guides: guides/deployment/index.md
      - Testing: guides/testing/index.md
  - Reference:
      - reference/index.md
      - floe.yaml Schema: reference/floe-yaml-schema.md
      - Data Contract Reference: contracts/datacontract-yaml-reference.md
      - Plugin Interfaces: architecture/interfaces/index.md
  - Contributing:
      - contributing/index.md
      - Documentation Standards: contributing/documentation-standards.md
  - Releases:
      - Alpha Checklist: releases/v0.1.0-alpha.1-checklist.md
```

- [ ] **Step 3: Add docs Make targets**

Modify `Makefile` help output and add:

```makefile
.PHONY: docs-build docs-serve docs-validate
docs-build: ## Build documentation site
	@uv run mkdocs build --strict

docs-serve: ## Serve documentation site locally
	@uv run mkdocs serve

docs-validate: ## Validate docs navigation and build
	@uv run python testing/ci/validate-docs-navigation.py
	@uv run mkdocs build --strict
```

- [ ] **Step 4: Add docs CI workflow**

Create `.github/workflows/docs.yml`:

```yaml
name: Docs

on:
  pull_request:
    paths:
      - "docs/**"
      - "mkdocs.yml"
      - "pyproject.toml"
      - "uv.lock"
      - "testing/ci/validate-docs-navigation.py"
      - "testing/ci/tests/test_validate_docs_navigation.py"
      - ".github/workflows/docs.yml"
  push:
    branches: [main]
    paths:
      - "docs/**"
      - "mkdocs.yml"
      - "pyproject.toml"
      - "uv.lock"
      - "testing/ci/validate-docs-navigation.py"
      - ".github/workflows/docs.yml"

jobs:
  docs:
    name: Build docs
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
      - name: Set up Python
        uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0
        with:
          python-version: "3.11"
      - name: Install uv
        uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
      - name: Install dependencies
        run: uv sync --frozen
      - name: Validate docs navigation
        run: uv run python testing/ci/validate-docs-navigation.py
      - name: Build docs
        run: uv run mkdocs build --strict
```

- [ ] **Step 5: Verify docs build fails until pages exist**

Run:

```bash
uv run mkdocs build --strict
```

Expected: FAIL because new nav pages are not created yet. Keep the failure as the red state for Task 2.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock mkdocs.yml .github/workflows/docs.yml Makefile
git commit -m "docs: add mkdocs site tooling"
```

## Task 2: Add Docs Navigation Validator

**Files:**
- Create: `testing/ci/validate-docs-navigation.py`
- Create: `testing/ci/tests/test_validate_docs_navigation.py`

- [ ] **Step 1: Write tests for missing required pages**

Create `testing/ci/tests/test_validate_docs_navigation.py`:

```python
from pathlib import Path

import pytest

from testing.ci.validate_docs_navigation import validate_docs_navigation


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_reports_missing_required_page(tmp_path: Path) -> None:
    """Navigation validation reports alpha-critical pages missing from docs."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "mkdocs.yml").write_text(
        "nav:\n"
        "  - Home: index.md\n"
        "  - Start Here:\n"
        "      - start-here/index.md\n",
    )
    (docs / "index.md").write_text("# Home\n")

    errors = validate_docs_navigation(tmp_path)

    assert "Missing docs page: docs/start-here/index.md" in errors


@pytest.mark.requirement("alpha-docs")
def test_validate_docs_navigation_accepts_required_alpha_pages(tmp_path: Path) -> None:
    """Navigation validation passes when alpha-critical pages exist."""
    docs = tmp_path / "docs"
    for relative in [
        "index.md",
        "start-here/index.md",
        "get-started/index.md",
        "get-started/first-platform.md",
        "get-started/first-data-product.md",
        "demo/index.md",
        "demo/customer-360.md",
        "demo/customer-360-validation.md",
        "operations/devpod-hetzner.md",
        "operations/troubleshooting.md",
        "reference/index.md",
        "contributing/index.md",
        "contributing/documentation-standards.md",
        "releases/v0.1.0-alpha.1-checklist.md",
    ]:
        path = docs / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.stem}\n")
    (tmp_path / "mkdocs.yml").write_text(
        "nav:\n"
        "  - Home: index.md\n"
        "  - Start Here:\n"
        "      - start-here/index.md\n"
        "  - Get Started:\n"
        "      - get-started/index.md\n"
        "      - get-started/first-platform.md\n"
        "      - get-started/first-data-product.md\n"
        "  - Demo:\n"
        "      - demo/index.md\n"
        "      - demo/customer-360.md\n"
        "      - demo/customer-360-validation.md\n"
        "  - Operations:\n"
        "      - operations/devpod-hetzner.md\n"
        "      - operations/troubleshooting.md\n"
        "  - Reference:\n"
        "      - reference/index.md\n"
        "  - Contributing:\n"
        "      - contributing/index.md\n"
        "      - contributing/documentation-standards.md\n"
        "  - Releases:\n"
        "      - releases/v0.1.0-alpha.1-checklist.md\n",
    )

    assert validate_docs_navigation(tmp_path) == []
```

- [ ] **Step 2: Run tests and verify import failure**

Run:

```bash
uv run pytest testing/ci/tests/test_validate_docs_navigation.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `testing.ci.validate_docs_navigation`.

- [ ] **Step 3: Implement navigation validator**

Create `testing/ci/validate-docs-navigation.py`:

```python
#!/usr/bin/env python3
"""Validate alpha-critical documentation pages are present and navigable."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

REQUIRED_DOCS = {
    "docs/index.md",
    "docs/start-here/index.md",
    "docs/get-started/index.md",
    "docs/get-started/first-platform.md",
    "docs/get-started/first-data-product.md",
    "docs/demo/index.md",
    "docs/demo/customer-360.md",
    "docs/demo/customer-360-validation.md",
    "docs/operations/devpod-hetzner.md",
    "docs/operations/troubleshooting.md",
    "docs/reference/index.md",
    "docs/contributing/index.md",
    "docs/contributing/documentation-standards.md",
    "docs/releases/v0.1.0-alpha.1-checklist.md",
}


def _walk_nav_items(items: list[Any]) -> set[str]:
    paths: set[str] = set()
    for item in items:
        if isinstance(item, str):
            paths.add(item)
        elif isinstance(item, dict):
            for value in item.values():
                if isinstance(value, str):
                    paths.add(value)
                elif isinstance(value, list):
                    paths.update(_walk_nav_items(value))
    return paths


def validate_docs_navigation(root: Path) -> list[str]:
    """Return validation errors for missing alpha-critical docs navigation."""
    mkdocs_path = root / "mkdocs.yml"
    if not mkdocs_path.exists():
        return ["Missing mkdocs.yml"]

    config = yaml.safe_load(mkdocs_path.read_text()) or {}
    nav_paths = {f"docs/{path}" for path in _walk_nav_items(config.get("nav", []))}
    errors: list[str] = []

    for required in sorted(REQUIRED_DOCS):
        if not (root / required).exists():
            errors.append(f"Missing docs page: {required}")
        if required not in nav_paths:
            errors.append(f"Missing docs nav entry: {required}")

    return errors


def main() -> int:
    errors = validate_docs_navigation(Path.cwd())
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Create import shim `testing/ci/validate_docs_navigation.py`:

```python
"""Importable wrapper for validate-docs-navigation.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).with_name("validate-docs-navigation.py")
_SPEC = importlib.util.spec_from_file_location("_validate_docs_navigation_script", _SCRIPT)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Cannot load {_SCRIPT}")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

validate_docs_navigation = _MODULE.validate_docs_navigation
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest testing/ci/tests/test_validate_docs_navigation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add testing/ci/validate-docs-navigation.py testing/ci/validate_docs_navigation.py testing/ci/tests/test_validate_docs_navigation.py
git commit -m "test: validate alpha docs navigation"
```

## Task 3: Add Alpha Docs Information Architecture

**Files:**
- Create: `docs/start-here/index.md`
- Create: `docs/get-started/index.md`
- Create: `docs/get-started/first-platform.md`
- Create: `docs/get-started/first-data-product.md`
- Create: `docs/demo/index.md`
- Create: `docs/operations/devpod-hetzner.md`
- Create: `docs/operations/troubleshooting.md`
- Create: `docs/reference/index.md`
- Create: `docs/contributing/index.md`
- Create: `docs/contributing/documentation-standards.md`
- Create: `docs/releases/v0.1.0-alpha.1-checklist.md`
- Modify: `README.md`
- Modify: `docs/index.md`

- [ ] **Step 1: Create user journey pages**

Create the pages listed above with real alpha content. Each page must include:

```markdown
# Page Title

This page is part of the `v0.1.0-alpha.1` release path.

## What You Will Do

Describe the concrete outcome in 3-5 bullets.

## Commands

Provide exact commands that are valid for the current repository.

## Success Criteria

List observable success criteria.

## Next Step

Link to the next page in the journey.
```

Use exact links:

```markdown
- [Deploy your first platform](../get-started/first-platform.md)
- [Run the Customer 360 demo](../demo/customer-360.md)
- [Validate Customer 360](../demo/customer-360-validation.md)
- [Devpod + Hetzner operations](../operations/devpod-hetzner.md)
```

- [ ] **Step 2: Add docs standards content**

In `docs/contributing/documentation-standards.md`, include:

```markdown
# Documentation Standards

Every user-facing change must update at least one documentation surface:

- Guide: user workflow changes.
- Reference: schema, CLI, chart, or API changes.
- Troubleshooting: discovered or fixed failure modes.
- Architecture: package boundary, contract, or plugin responsibility changes.
- Release notes: noteworthy behavior that does not need a permanent guide.

Pull requests that change behavior should state which docs surface was updated,
or explicitly state why no documentation update is needed.
```

- [ ] **Step 3: Add release checklist skeleton**

In `docs/releases/v0.1.0-alpha.1-checklist.md`, include:

```markdown
# v0.1.0-alpha.1 Release Checklist

## Required Evidence

| Gate | Evidence | Status |
| --- | --- | --- |
| Docs build | `uv run mkdocs build --strict` | Not run |
| CI on main | GitHub Actions run URL | Not run |
| Helm CI on main | GitHub Actions run URL | Not run |
| Customer 360 validation | Validation summary URL or file | Not run |
| Devpod + Hetzner validation | Validation run URL or file | Not run |
| Security scans | GitHub Actions run URL | Not run |
| #271 | GitHub issue URL | Open |
| #197 | GitHub issue URL | Open |
| #263 posture | Known limitation or closed issue URL | Open |

## Known Alpha Limitations

- Floe alpha validates the Customer 360 stack with Iceberg enabled.
- Dagster without `floe-iceberg` installed is not part of the alpha promise
  unless #263 is closed before release.
```

- [ ] **Step 4: Link docs site from README and docs index**

Add to `README.md` near the documentation section:

```markdown
## Documentation

The alpha documentation site is built from `docs/` with MkDocs:

```bash
make docs-build
make docs-serve
```

Start with [docs/start-here/index.md](docs/start-here/index.md).
```
```

Add to `docs/index.md`:

```markdown
## Alpha User Journeys

- [Start Here](./start-here/index.md)
- [Deploy your first platform](./get-started/first-platform.md)
- [Build your first data product](./get-started/first-data-product.md)
- [Customer 360 golden demo](./demo/customer-360.md)
- [Customer 360 validation](./demo/customer-360-validation.md)
```

- [ ] **Step 5: Validate docs**

Run:

```bash
uv run python testing/ci/validate-docs-navigation.py
uv run mkdocs build --strict
```

Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
git add docs README.md
git commit -m "docs: add alpha documentation journeys"
```

## Task 4: Add Customer 360 Golden Demo Guide

**Files:**
- Create: `docs/demo/customer-360.md`
- Create: `docs/demo/customer-360-validation.md`
- Modify: `demo/README.md`

- [ ] **Step 1: Fill Customer 360 guide**

Update `docs/demo/customer-360.md` with this structure and exact commands:

```markdown
# Customer 360 Golden Demo

Customer 360 is the `v0.1.0-alpha.1` golden demo. It proves that Floe can run a
data product through orchestration, transformation, storage, lineage, tracing,
and business-facing query validation.

## Prerequisites

- Devpod workspace on Hetzner is running.
- Kubeconfig is synced with `make devpod-sync`.
- Service tunnels are running with `make devpod-tunnels`.
- The repository branch has been pushed before remote validation.

## Run

```bash
make demo
make demo-customer-360-validate
```

## Service URLs

| Service | URL | Proof |
| --- | --- | --- |
| Dagster | http://localhost:3100 | Customer 360 run succeeds |
| MinIO | http://localhost:9001 | Customer 360 objects exist |
| Marquez | http://localhost:5100 | Customer 360 lineage exists |
| Jaeger | http://localhost:16686 | Customer 360 traces exist |
| Polaris | http://localhost:8181 | Customer 360 tables are registered |

## Business Outcome

The final mart is `mart_customer_360`. The demo is successful when the
validation command reports customer count, active customer count, total lifetime
value, and lineage/tracing evidence.
```

- [ ] **Step 2: Fill validation checklist**

Update `docs/demo/customer-360-validation.md`:

```markdown
# Customer 360 Validation

## Automated Evidence

Run:

```bash
make demo-customer-360-validate
```

Expected evidence keys:

- `platform.ready`
- `dagster.customer_360_run`
- `storage.customer_360_outputs`
- `lineage.marquez_customer_360`
- `tracing.jaeger_customer_360`
- `business.customer_count`
- `business.total_lifetime_value`

## Manual UI Inspection

| Service | Check | Pass Criteria |
| --- | --- | --- |
| Dagster | Open run history | Latest Customer 360 run succeeded |
| MinIO | Open object browser | Customer 360 output objects are visible |
| Marquez | Search Customer 360 namespace/job | Lineage graph has Customer 360 datasets |
| Jaeger | Search Floe/Dagster service | Trace exists for Customer 360 run |
| Polaris | Open catalog API/UI path | Customer 360 tables are registered |
```

- [ ] **Step 3: Update demo README**

Add a top section to `demo/README.md`:

```markdown
## Golden Alpha Demo

Customer 360 is the supported alpha demo path. Start with:

- [Customer 360 Golden Demo](../docs/demo/customer-360.md)
- [Customer 360 Validation](../docs/demo/customer-360-validation.md)
```

- [ ] **Step 4: Validate docs build**

Run:

```bash
uv run mkdocs build --strict
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/demo demo/README.md
git commit -m "docs: document customer 360 golden demo"
```

## Task 5: Add Customer 360 Validation Tooling

**Files:**
- Create: `testing/demo/customer360_validator.py`
- Create: `testing/ci/validate-customer-360-demo.py`
- Create: `testing/tests/unit/test_customer360_validator.py`
- Modify: `Makefile`

- [ ] **Step 1: Write unit tests with fake runners**

Create `testing/tests/unit/test_customer360_validator.py`:

```python
from __future__ import annotations

import json

import pytest

from testing.demo.customer360_validator import Customer360Validator, ValidationResult


class FakeRunner:
    def __init__(self, responses: dict[tuple[str, ...], str]) -> None:
        self.responses = responses
        self.commands: list[tuple[str, ...]] = []

    def __call__(self, command: list[str]) -> str:
        key = tuple(command)
        self.commands.append(key)
        if key not in self.responses:
            raise AssertionError(f"Unexpected command: {command}")
        return self.responses[key]


@pytest.mark.requirement("alpha-demo")
def test_customer360_validator_reports_business_and_service_evidence() -> None:
    """Validator reports Customer 360 service and business evidence."""
    runner = FakeRunner(
        {
            ("kubectl", "get", "pods", "-n", "floe-dev", "-o", "json"): json.dumps(
                {"items": [{"metadata": {"name": "dagster"}, "status": {"phase": "Running"}}]}
            ),
            ("curl", "-fsS", "http://localhost:3100/server_info"): "{}",
            ("curl", "-fsS", "http://localhost:5100/api/v1/namespaces"): json.dumps(
                {"namespaces": [{"name": "customer_360"}]}
            ),
            ("curl", "-fsS", "http://localhost:16686/api/services"): json.dumps(
                {"data": ["dagster"]}
            ),
        }
    )

    result = Customer360Validator(command_runner=runner).validate()

    assert result.status == "PASS"
    assert result.evidence["platform.ready"] == "true"
    assert result.evidence["lineage.marquez_customer_360"] == "true"
    assert result.evidence["tracing.jaeger_customer_360"] == "true"


@pytest.mark.requirement("alpha-demo")
def test_customer360_validator_fails_when_lineage_missing() -> None:
    """Validator fails clearly when Marquez does not expose Customer 360 lineage."""
    runner = FakeRunner(
        {
            ("kubectl", "get", "pods", "-n", "floe-dev", "-o", "json"): json.dumps(
                {"items": [{"metadata": {"name": "dagster"}, "status": {"phase": "Running"}}]}
            ),
            ("curl", "-fsS", "http://localhost:3100/server_info"): "{}",
            ("curl", "-fsS", "http://localhost:5100/api/v1/namespaces"): json.dumps(
                {"namespaces": [{"name": "default"}]}
            ),
            ("curl", "-fsS", "http://localhost:16686/api/services"): json.dumps(
                {"data": ["dagster"]}
            ),
        }
    )

    result = Customer360Validator(command_runner=runner).validate()

    assert result.status == "FAIL"
    assert "Customer 360 namespace not found in Marquez" in result.failures
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
uv run pytest testing/tests/unit/test_customer360_validator.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `testing.demo.customer360_validator`.

- [ ] **Step 3: Implement validator**

Create `testing/demo/customer360_validator.py`:

```python
"""Customer 360 demo validation helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import json
import subprocess

CommandRunner = Callable[[list[str]], str]


def default_command_runner(command: list[str]) -> str:
    """Run a command and return stdout."""
    return subprocess.check_output(command, text=True)


@dataclass(frozen=True)
class ValidationResult:
    """Customer 360 validation result."""

    status: str
    evidence: dict[str, str] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


class Customer360Validator:
    """Validate Customer 360 demo outcomes through service APIs."""

    def __init__(
        self,
        command_runner: CommandRunner = default_command_runner,
        namespace: str = "floe-dev",
    ) -> None:
        self._run = command_runner
        self._namespace = namespace

    def validate(self) -> ValidationResult:
        """Validate service health and Customer 360 evidence."""
        evidence: dict[str, str] = {}
        failures: list[str] = []

        pods = json.loads(
            self._run(["kubectl", "get", "pods", "-n", self._namespace, "-o", "json"])
        )
        running = any(item.get("status", {}).get("phase") == "Running" for item in pods["items"])
        evidence["platform.ready"] = str(running).lower()
        if not running:
            failures.append(f"No running pods found in namespace {self._namespace}")

        self._run(["curl", "-fsS", "http://localhost:3100/server_info"])
        evidence["dagster.reachable"] = "true"

        namespaces = json.loads(
            self._run(["curl", "-fsS", "http://localhost:5100/api/v1/namespaces"])
        )
        namespace_names = {item["name"] for item in namespaces.get("namespaces", [])}
        lineage_found = "customer_360" in namespace_names or "customer-360" in namespace_names
        evidence["lineage.marquez_customer_360"] = str(lineage_found).lower()
        if not lineage_found:
            failures.append("Customer 360 namespace not found in Marquez")

        jaeger = json.loads(self._run(["curl", "-fsS", "http://localhost:16686/api/services"]))
        services = set(jaeger.get("data", []))
        tracing_found = bool({"dagster", "floe"} & services)
        evidence["tracing.jaeger_customer_360"] = str(tracing_found).lower()
        if not tracing_found:
            failures.append("Customer 360 trace service not found in Jaeger")

        return ValidationResult(
            status="FAIL" if failures else "PASS",
            evidence=evidence,
            failures=failures,
        )
```

Create `testing/ci/validate-customer-360-demo.py`:

```python
#!/usr/bin/env python3
"""Validate the Customer 360 golden demo."""

from __future__ import annotations

import argparse

from testing.demo.customer360_validator import Customer360Validator


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", default="floe-dev")
    args = parser.parse_args()

    result = Customer360Validator(namespace=args.namespace).validate()
    print(f"status={result.status}")
    for key, value in sorted(result.evidence.items()):
        print(f"{key}={value}")
    for failure in result.failures:
        print(f"failure={failure}")
    return 1 if result.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add Make target**

Modify `Makefile`:

```makefile
.PHONY: demo-customer-360-validate
demo-customer-360-validate: ## Validate Customer 360 golden demo evidence
	@uv run python testing/ci/validate-customer-360-demo.py --namespace $${FLOE_DEMO_NAMESPACE:-floe-dev}
```

- [ ] **Step 5: Run unit tests**

Run:

```bash
uv run pytest testing/tests/unit/test_customer360_validator.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add testing/demo/customer360_validator.py testing/ci/validate-customer-360-demo.py testing/tests/unit/test_customer360_validator.py Makefile
git commit -m "feat: validate customer 360 golden demo"
```

## Task 6: Close #197 Devpod Kubeconfig Portability

**Files:**
- Modify: `Makefile`
- Create: `testing/tests/unit/test_demo_makefile_kubeconfig.py`

- [ ] **Step 1: Write guard test**

Create `testing/tests/unit/test_demo_makefile_kubeconfig.py`:

```python
from pathlib import Path

import pytest


@pytest.mark.requirement("197")
def test_makefile_does_not_hardcode_floe_workspace_kubeconfig() -> None:
    """Demo and Devpod targets derive kubeconfig from DEVPOD_WORKSPACE."""
    text = Path("Makefile").read_text()

    assert "devpod-floe.config" not in text
    assert "DEVPOD_KUBECONFIG ?=" in text
    assert "devpod-$(DEVPOD_WORKSPACE).config" in text
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
uv run pytest testing/tests/unit/test_demo_makefile_kubeconfig.py -q
```

Expected: FAIL because `Makefile` currently contains `devpod-floe.config`.

- [ ] **Step 3: Add portable kubeconfig variable**

Modify the Devpod section in `Makefile`:

```makefile
DEVPOD_WORKSPACE ?= floe
DEVPOD_PROVIDER ?= hetzner
DEVPOD_DEVCONTAINER ?= .devcontainer/hetzner/devcontainer.json
DEVPOD_KUBECONFIG ?= $(HOME)/.kube/devpod-$(DEVPOD_WORKSPACE).config
```

Replace every `KUBECONFIG=$(HOME)/.kube/devpod-floe.config` and
`KUBECONFIG="$${HOME}/.kube/devpod-floe.config"` in `Makefile` with:

```makefile
KUBECONFIG="$(DEVPOD_KUBECONFIG)"
```

For shell fragments that need runtime expansion, use:

```makefile
KUBECONFIG="$${DEVPOD_KUBECONFIG:-$(DEVPOD_KUBECONFIG)}"
```

- [ ] **Step 4: Run guard test**

Run:

```bash
uv run pytest testing/tests/unit/test_demo_makefile_kubeconfig.py -q
```

Expected: PASS.

- [ ] **Step 5: Run focused Make dry checks**

Run:

```bash
make -n demo DEVPOD_WORKSPACE=floe-alpha | rg 'devpod-floe-alpha.config'
make -n devpod-status DEVPOD_WORKSPACE=floe-alpha | rg 'devpod-floe-alpha.config'
```

Expected: both commands show `devpod-floe-alpha.config`.

- [ ] **Step 6: Commit and close issue**

```bash
git add Makefile testing/tests/unit/test_demo_makefile_kubeconfig.py
git commit -m "fix: derive devpod kubeconfig from workspace"
gh issue close 197 --comment "Closed by deriving demo/status kubeconfig paths from DEVPOD_WORKSPACE via DEVPOD_KUBECONFIG. Added guard test to prevent reintroducing devpod-floe.config."
```

## Task 7: Close #271 GitHub Actions Node 24 Risk

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/claude-code-review.yml`
- Modify: `.github/workflows/claude.yml`
- Modify: `.github/workflows/codspeed.yml`
- Modify: `.github/workflows/e2e.yml`
- Modify: `.github/workflows/release.yml`
- Modify: `.github/workflows/security.yml`
- Modify: `.github/workflows/weekly.yml`
- Modify: `.github/workflows/helm-ci.yaml`
- Modify: `.github/workflows/helm-release.yaml`
- Create: `testing/ci/tests/test_github_actions_node24_pins.py`

- [ ] **Step 1: Add workflow pin guard**

Create `testing/ci/tests/test_github_actions_node24_pins.py`:

```python
from pathlib import Path

import pytest

OLD_NODE20_ACTION_PINS = {
    "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5",
    "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
    "astral-sh/setup-uv@e4db8464a088ece1b920f60402e813ea4de65b8f",
    "azure/setup-helm@1a275c3b69536ee54be43f2070a358922e12c8d4",
    "helm/kind-action@a1b0e391336a6ee6713a0583f8c6240d70863de3",
}

NODE24_ACTION_PINS = {
    "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd",  # v6.0.2
    "actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405",  # v6.2.0
    "astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b",  # v8.1.0
    "Azure/setup-helm@dda3372f752e03dde6b3237bc9431cdc2f7a02a2",  # v5.0.0
    "helm/kind-action@ef37e7f390d99f746eb8b610417061a60e82a6cc",  # v1.14.0
}


@pytest.mark.requirement("271")
def test_workflows_do_not_use_known_node20_action_pins() -> None:
    """Pinned GitHub Actions avoid known Node 20 deprecation warnings."""
    workflow_text = "\n".join(
        path.read_text() for path in Path(".github/workflows").glob("*.*y*ml")
    )

    for old_pin in OLD_NODE20_ACTION_PINS:
        assert old_pin not in workflow_text


@pytest.mark.requirement("271")
def test_node24_action_pins_are_documented_when_used() -> None:
    """Workflows use pinned Node 24-compatible action SHAs."""
    workflow_text = "\n".join(
        path.read_text() for path in Path(".github/workflows").glob("*.*y*ml")
    )

    for pin in NODE24_ACTION_PINS:
        if pin.split("@", maxsplit=1)[0] in workflow_text:
            assert pin in workflow_text
```

- [ ] **Step 2: Run guard and verify failure**

Run:

```bash
uv run pytest testing/ci/tests/test_github_actions_node24_pins.py -q
```

Expected: FAIL because workflows still contain old Node 20 action pins.

- [ ] **Step 3: Update action pins**

Replace pins:

```text
actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5
-> actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2

actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065
-> actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0

astral-sh/setup-uv@e4db8464a088ece1b920f60402e813ea4de65b8f
-> astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0

azure/setup-helm@1a275c3b69536ee54be43f2070a358922e12c8d4
-> Azure/setup-helm@dda3372f752e03dde6b3237bc9431cdc2f7a02a2 # v5.0.0

helm/kind-action@a1b0e391336a6ee6713a0583f8c6240d70863de3
-> helm/kind-action@ef37e7f390d99f746eb8b610417061a60e82a6cc # v1.14.0
```

These target SHAs were resolved from GitHub release metadata on 2026-04-29.

- [ ] **Step 4: Run guard**

Run:

```bash
uv run pytest testing/ci/tests/test_github_actions_node24_pins.py -q
```

Expected: PASS.

- [ ] **Step 5: Validate workflow syntax**

Run:

```bash
gh workflow list
```

Expected: command succeeds and lists workflows. If `actionlint` is available, also run:

```bash
actionlint
```

Expected: PASS or only pre-existing warnings unrelated to action refs.

- [ ] **Step 6: Commit and close issue**

```bash
git add .github/workflows testing/ci/tests/test_github_actions_node24_pins.py
git commit -m "ci: upgrade github actions for node 24"
gh issue close 271 --comment "Closed by upgrading pinned GitHub Actions to Node 24-compatible releases and adding a guard test for known Node 20 action pins."
```

## Task 8: Add Release Evidence Checklist And #263 Posture

**Files:**
- Modify: `docs/releases/v0.1.0-alpha.1-checklist.md`
- Create: `docs/validation/2026-04-29-alpha-customer-360-release-validation.md`

- [ ] **Step 1: Add #263 release posture**

Update `docs/releases/v0.1.0-alpha.1-checklist.md` with:

```markdown
## Release-Reviewed Issues

### #263: Dagster imports floe-iceberg internals

Status: Known post-alpha architecture debt.

Alpha posture: not blocking `v0.1.0-alpha.1` because the alpha Customer 360
stack intentionally includes Iceberg and `floe-iceberg`. The alpha release does
not promise that Dagster runs without `floe-iceberg` installed when Iceberg
export is disabled.

Promotion rule: if the alpha promise changes to support Dagster without Iceberg,
#263 becomes blocking and must be closed before tagging.
```

- [ ] **Step 2: Add validation evidence template**

Create `docs/validation/2026-04-29-alpha-customer-360-release-validation.md`:

```markdown
# Alpha Customer 360 Release Validation

Date: 2026-04-29
Commit: record with `git rev-parse HEAD` before tagging.

## Automated Gates

| Gate | Command or Run | Result | Evidence |
| --- | --- | --- | --- |
| Docs build | `make docs-build` | Not run | |
| Docs validation | `make docs-validate` | Not run | |
| Unit tests | `make test-unit` | Not run | |
| Helm CI | GitHub Actions run | Not run | |
| CI | GitHub Actions run | Not run | |
| Security | GitHub Actions run | Not run | |
| Customer 360 validation | `make demo-customer-360-validate` | Not run | |
| Devpod + Hetzner E2E | `make devpod-test` | Not run | |

## Manual UI Evidence

| Service | URL | Expected Evidence | Result |
| --- | --- | --- | --- |
| Dagster | http://localhost:3100 | Customer 360 run succeeded | Not checked |
| MinIO | http://localhost:9001 | Customer 360 output objects visible | Not checked |
| Marquez | http://localhost:5100 | Customer 360 lineage graph visible | Not checked |
| Jaeger | http://localhost:16686 | Customer 360 trace visible | Not checked |
| Polaris | http://localhost:8181 | Customer 360 tables registered | Not checked |

## Release Decision

Alpha tag is blocked until every required gate above is PASS or explicitly
classified as a non-blocking known limitation.
```

- [ ] **Step 3: Validate docs**

Run:

```bash
make docs-validate
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add docs/releases/v0.1.0-alpha.1-checklist.md docs/validation/2026-04-29-alpha-customer-360-release-validation.md
git commit -m "docs: add alpha release evidence checklist"
```

## Task 9: Final Validation, PR, And Tag Gate

**Files:**
- Modify: `docs/validation/2026-04-29-alpha-customer-360-release-validation.md`

- [ ] **Step 1: Run local validation**

Run:

```bash
make docs-validate
uv run pytest testing/ci/tests/test_validate_docs_navigation.py testing/ci/tests/test_github_actions_node24_pins.py testing/tests/unit/test_customer360_validator.py testing/tests/unit/test_demo_makefile_kubeconfig.py -q
make helm-lint
make test-unit
```

Expected: PASS. Record command results in the validation document.

- [ ] **Step 2: Push branch and open PR**

Run:

```bash
git push -u origin docs/alpha-docs-demo-release-gate
gh pr create --base main --head docs/alpha-docs-demo-release-gate --title "Add alpha docs and Customer 360 release gate" --body-file - <<'EOF'
## Summary
- Adds MkDocs Material documentation site and alpha-critical docs navigation.
- Documents Customer 360 as the golden alpha demo.
- Adds Customer 360 validation tooling and release evidence checklist.
- Closes #271 GitHub Actions Node 24 risk.
- Closes or resolves #197 Devpod kubeconfig portability.
- Documents #263 as release-reviewed post-alpha architecture debt unless scope changes.

## Validation
- `make docs-validate`
- `uv run pytest testing/ci/tests/test_validate_docs_navigation.py testing/ci/tests/test_github_actions_node24_pins.py testing/tests/unit/test_customer360_validator.py testing/tests/unit/test_demo_makefile_kubeconfig.py -q`
- `make helm-lint`
- `make test-unit`
EOF
```

- [ ] **Step 3: Wait for PR CI**

Run:

```bash
gh pr checks --watch
```

Expected: all required checks PASS.

- [ ] **Step 4: Merge after approval**

After approval and green CI:

```bash
gh pr merge --squash --delete-branch
git switch main
git pull --ff-only
```

- [ ] **Step 5: Run final Devpod + Hetzner validation on main**

Run:

```bash
make devpod-up
make devpod-sync
make devpod-tunnels
make demo
make demo-customer-360-validate
make devpod-test
```

Expected:

- Customer 360 validation returns `status=PASS`.
- Devpod + Hetzner E2E passes.
- Manual UI checks pass for Dagster, MinIO, Marquez, Jaeger, and Polaris.

- [ ] **Step 6: Update validation evidence**

Update `docs/validation/2026-04-29-alpha-customer-360-release-validation.md` with:

```markdown
Commit: output of `git rev-parse HEAD`

| Gate | Command or Run | Result | Evidence |
| --- | --- | --- | --- |
| Docs build | `make docs-build` | PASS | paste terminal timestamp and final PASS line |
| Docs validation | `make docs-validate` | PASS | paste terminal timestamp and final PASS line |
| CI | `gh run list --branch main --workflow CI --limit 1` | PASS | paste run URL from command output |
| Helm CI | `gh run list --branch main --workflow "Helm CI" --limit 1` | PASS | paste run URL from command output |
| Customer 360 validation | `make demo-customer-360-validate` | PASS | paste `status=PASS` evidence block |
| Devpod + Hetzner E2E | `make devpod-test` | PASS | paste final PASS summary and workspace cleanup evidence |
```

- [ ] **Step 7: Commit final evidence**

```bash
git switch -c docs/alpha-release-validation-evidence
git add docs/validation/2026-04-29-alpha-customer-360-release-validation.md
git commit -m "docs: record alpha customer 360 validation evidence"
git push -u origin docs/alpha-release-validation-evidence
gh pr create --base main --head docs/alpha-release-validation-evidence --title "Record alpha validation evidence" --body "Records final Customer 360 and Devpod + Hetzner alpha validation evidence."
```

- [ ] **Step 8: Tag only after evidence PR merges**

After evidence PR merges and `main` is green:

```bash
git switch main
git pull --ff-only
git tag -a v0.1.0-alpha.1 -m "v0.1.0-alpha.1"
git push origin v0.1.0-alpha.1
```

Expected: release workflow starts and passes.

## Self-Review

- Spec coverage: the plan covers docs site, docs standards, Customer 360 golden demo, service inspection, validation tooling, #271, #197, #263 posture, and final Devpod + Hetzner evidence.
- Completion scan: no deferred implementation steps remain. Runtime evidence fields specify the exact command whose output must be pasted.
- Type consistency: `Customer360Validator`, `ValidationResult`, `validate_docs_navigation`, and Make targets are named consistently across tests, implementation snippets, and commands.

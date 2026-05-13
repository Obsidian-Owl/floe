# Alpha Release Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a manifest-driven alpha release system that publishes only the evidence-approved package cutline and makes versioning, release gates, CI topology, live validation, and distribution behavior explicit.

**Architecture:** `release/floe-release.yaml` is the source of truth. Repo-native Python helpers under `testing/release/` load and validate that manifest, generate package lists for CI, validate versions and package metadata, create release evidence, and keep GitHub Actions workflows from carrying their own package truth. Workflow edits consume these helpers instead of hardcoded package arrays.

**Tech Stack:** Python 3.10+, PyYAML, tomli for Python 3.10 TOML reads, pytest, GitHub Actions, uv, Python build, Helm, DevPod+Hetzner, AWS S3+Glue live validation.

---

## Worktree And PR Map

Execute this as a sequence of small PRs from trunk. The first task creates the shared contract, so run it first. After Task 1 lands, Tasks 2, 3, 4, and 5 can run in separate worktrees if desired.

| Task | Suggested branch | Primary ownership |
|---|---|---|
| 1. Manifest and validator | `release/alpha-manifest-validator` | `release/`, `testing/release/`, validator tests |
| 2. Version and PyPI distribution automation | `release/alpha-pypi-distribution` | package `pyproject.toml` files, `pypi-publish.yml`, build helper |
| 3. CI topology review and optimization | `release/ci-topology-audit` | `.github/workflows/*`, `.github/CI.md`, CI audit docs |
| 4. Release validation and evidence bundle | `release/alpha-validation-gate` | `release.yml`, release evidence helper, DevPod/AWS gate docs |
| 5. Helm alpha policy | `release/alpha-helm-policy` | `helm-release.yaml`, Helm release docs |
| 6. Maintainer and contributor docs | `release/alpha-release-docs` | `RELEASING.md`, PyPI/AWS/release checklist docs |
| 7. Release candidate validation | `release/alpha-rc-validation` | validation evidence under `docs/validation/` and `docs/releases/` |

Do not tag an alpha release until Task 7 is complete and all evidence points at the intended `main` SHA.

## File Structure

### Create

- `release/floe-release.yaml`: canonical alpha release manifest.
- `testing/release/__init__.py`: package marker for release helpers.
- `testing/release/manifest.py`: manifest data model, YAML loading, TOML metadata reads, version normalization, and validation errors.
- `testing/release/cli.py`: command-line entry point for validation, package-list output, evidence checks, and build dry-run orchestration.
- `testing/release/build_packages.py`: package build helper that reads the manifest and writes wheel/sdist outputs.
- `testing/release/evidence.py`: release evidence bundle helpers and product-vs-infra result classification.
- `testing/release/ci_inventory.py`: workflow inventory helper for CI topology review.
- `testing/tests/unit/test_release_manifest.py`: manifest validation tests.
- `testing/tests/unit/test_release_build_packages.py`: package list and build helper tests.
- `testing/tests/unit/test_release_evidence.py`: evidence bundle and failure taxonomy tests.
- `testing/tests/unit/test_release_ci_inventory.py`: workflow inventory tests.
- `docs/analysis/2026-05-13-ci-release-topology-review.md`: CI review output and optimization recommendations.
- `docs/validation/2026-05-13-alpha-release-candidate-validation.md`: release candidate evidence record.

### Modify

- `pyproject.toml`: add direct `tomli` dependency for Python 3.10 release helper TOML reads.
- Alpha-published package `pyproject.toml` files: set alpha package versions and alpha-compatible `floe-core` dependency ranges.
- `.github/workflows/pypi-publish.yml`: derive packages and artifact counts from manifest.
- `.github/workflows/release.yml`: validate manifest and attach release evidence.
- `.github/workflows/e2e.yml`: replace dormant E2E guard with explicit path/label/manual release gating.
- `.github/workflows/helm-release.yaml`: enforce declared Helm alpha policy and version normalization.
- `.github/CI.md`: document optimized CI topology and release lanes.
- `RELEASING.md`: document manifest-first alpha release process.
- `docs/guides/pypi-trusted-publishers.md`: align pending publisher list with alpha cutline.
- `docs/contributing/aws-provider-testing.md`: link AWS live validation evidence expectations to release gate.
- `docs/releases/v0.1.0-alpha.1-checklist.md`: replace stale 24-package assumptions and historical-only evidence.
- `docs/releases/v0.1.0-alpha.1-release-notes.md`: update package and Helm distribution claims after the cutline is enforced.

## Task 1: Release Manifest And Validator

**Files:**
- Create: `release/floe-release.yaml`
- Create: `testing/release/__init__.py`
- Create: `testing/release/manifest.py`
- Create: `testing/release/cli.py`
- Create: `testing/tests/unit/test_release_manifest.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add failing manifest tests**

Create `testing/tests/unit/test_release_manifest.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from testing.release.manifest import (
    ReleaseManifestError,
    load_release_manifest,
    normalize_tag_to_python_version,
    validate_release_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / "release" / "floe-release.yaml"

ALPHA_PUBLISH = {
    "floe-core",
    "floe-iceberg",
    "floe-orchestrator-dagster",
    "floe-catalog-polaris",
    "floe-storage-minio",
    "floe-compute-duckdb",
    "floe-dbt-core",
    "floe-ingestion-dlt",
    "floe-telemetry-jaeger",
    "floe-rbac-k8s",
    "floe-network-security-k8s",
    "floe-lineage-marquez",
    "floe-quality-gx",
    "floe-storage-aws-s3",
    "floe-catalog-glue",
}

ALPHA_EXCLUDED = {
    "floe-alert-slack",
    "floe-alert-email",
    "floe-alert-alertmanager",
    "floe-alert-webhook",
    "floe-identity-keycloak",
    "floe-secrets-infisical",
    "floe-secrets-k8s",
    "floe-semantic-cube",
    "floe-dbt-fusion",
    "floe-telemetry-console",
    "floe-quality-dbt",
}


def test_normalizes_alpha_git_tag_to_pep440() -> None:
    assert normalize_tag_to_python_version("v0.1.0-alpha.1") == "0.1.0a1"


def test_release_manifest_exists_and_matches_cutline() -> None:
    manifest = load_release_manifest(MANIFEST)

    publish_names = {pkg.name for pkg in manifest.python_packages.publish}
    excluded_names = {pkg.name for pkg in manifest.python_packages.exclude}

    assert publish_names == ALPHA_PUBLISH
    assert excluded_names == ALPHA_EXCLUDED
    assert publish_names.isdisjoint(excluded_names)


def test_release_manifest_detects_current_version_mismatch_before_alpha_versions_are_applied() -> None:
    manifest = load_release_manifest(MANIFEST)

    with pytest.raises(ReleaseManifestError, match="package version mismatch"):
        validate_release_manifest(manifest, repo_root=REPO_ROOT, tag="v0.1.0-alpha.1")


def test_release_manifest_rejects_secret_like_values(tmp_path: Path) -> None:
    manifest_path = tmp_path / "floe-release.yaml"
    manifest_path.write_text(
        """
release:
  train: alpha
  git_tag: v0.1.0-alpha.1
  python_version: 0.1.0a1
  helm_version: 0.1.0-alpha.1
python_packages:
  publish:
    - path: packages/floe-core
      name: floe-core
      evidence: current-main
  exclude: []
helm:
  alpha_policy: publish
  charts: []
validation:
  require_current_main_ci: true
  require_package_build_dry_run: true
  require_full_devpod_e2e: true
  require_aws_provider_live: true
  allow_accepted_historical_evidence: true
aws_secret_access_key: not-allowed
""",
        encoding="utf-8",
    )

    with pytest.raises(ReleaseManifestError, match="secret-like key"):
        load_release_manifest(manifest_path)
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run:

```bash
uv run pytest testing/tests/unit/test_release_manifest.py -q
```

Expected: fails because `testing.release` and `release/floe-release.yaml` do not exist.

- [ ] **Step 3: Add direct Python 3.10 TOML dependency**

Modify the root `pyproject.toml` dependencies list by adding this item near the existing YAML/JSON tooling dependencies:

```toml
    "tomli>=2.0; python_version < '3.11'",  # TOML reader for release helpers on Python 3.10
```

Run:

```bash
uv lock
```

Expected: `uv.lock` remains valid and records no unrelated dependency churn beyond lock normalization for the direct dependency.

- [ ] **Step 4: Create the alpha release manifest**

Create `release/floe-release.yaml`:

```yaml
release:
  train: alpha
  git_tag: v0.1.0-alpha.1
  python_version: 0.1.0a1
  helm_version: 0.1.0-alpha.1

python_packages:
  publish:
    - path: packages/floe-core
      name: floe-core
      evidence: current-main
    - path: packages/floe-iceberg
      name: floe-iceberg
      evidence: current-main
    - path: plugins/floe-orchestrator-dagster
      name: floe-orchestrator-dagster
      evidence: current-main
    - path: plugins/floe-catalog-polaris
      name: floe-catalog-polaris
      evidence: current-main
    - path: plugins/floe-storage-minio
      name: floe-storage-minio
      evidence: current-main
    - path: plugins/floe-compute-duckdb
      name: floe-compute-duckdb
      evidence: current-main
    - path: plugins/floe-dbt-core
      name: floe-dbt-core
      evidence: current-main
    - path: plugins/floe-ingestion-dlt
      name: floe-ingestion-dlt
      evidence: current-main
    - path: plugins/floe-telemetry-jaeger
      name: floe-telemetry-jaeger
      evidence: current-main
    - path: plugins/floe-rbac-k8s
      name: floe-rbac-k8s
      evidence: current-main
    - path: plugins/floe-network-security-k8s
      name: floe-network-security-k8s
      evidence: current-main
    - path: plugins/floe-lineage-marquez
      name: floe-lineage-marquez
      evidence: root-e2e-required
    - path: plugins/floe-quality-gx
      name: floe-quality-gx
      evidence: root-e2e-required
    - path: plugins/floe-storage-aws-s3
      name: floe-storage-aws-s3
      evidence: aws-live-required
    - path: plugins/floe-catalog-glue
      name: floe-catalog-glue
      evidence: aws-live-required
  exclude:
    - path: plugins/floe-alert-slack
      name: floe-alert-slack
      reason: no-composed-alpha-runtime-path
    - path: plugins/floe-alert-email
      name: floe-alert-email
      reason: no-composed-alpha-runtime-path
    - path: plugins/floe-alert-alertmanager
      name: floe-alert-alertmanager
      reason: no-composed-alpha-runtime-path
    - path: plugins/floe-alert-webhook
      name: floe-alert-webhook
      reason: no-composed-alpha-runtime-path
    - path: plugins/floe-identity-keycloak
      name: floe-identity-keycloak
      reason: no-alpha-identity-composition-path
    - path: plugins/floe-secrets-infisical
      name: floe-secrets-infisical
      reason: no-alpha-secret-backend-path
    - path: plugins/floe-secrets-k8s
      name: floe-secrets-k8s
      reason: no-alpha-secret-backend-path
    - path: plugins/floe-semantic-cube
      name: floe-semantic-cube
      reason: no-alpha-semantic-layer-e2e-path
    - path: plugins/floe-dbt-fusion
      name: floe-dbt-fusion
      reason: not-alpha-dbt-runtime-path
    - path: plugins/floe-telemetry-console
      name: floe-telemetry-console
      reason: dev-utility-evidence-only
    - path: plugins/floe-quality-dbt
      name: floe-quality-dbt
      reason: no-composed-alpha-quality-path

helm:
  alpha_policy: publish
  charts:
    - charts/floe-platform
    - charts/floe-jobs

validation:
  require_current_main_ci: true
  require_package_build_dry_run: true
  require_full_devpod_e2e: true
  require_aws_provider_live: true
  allow_accepted_historical_evidence: true
```

- [ ] **Step 5: Implement manifest loading and validation**

Create `testing/release/__init__.py`:

```python
"""Release validation helpers for Floe."""
```

Create `testing/release/manifest.py` with these public APIs:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from packaging.version import Version
import yaml

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


SECRET_KEY_RE = re.compile(r"(secret|access_key|token|password|private_key)", re.IGNORECASE)
ALPHA_TAG_RE = re.compile(r"^v?(\d+\.\d+\.\d+)-alpha\.(\d+)$")


class ReleaseManifestError(ValueError):
    """Raised when the release manifest is invalid."""


@dataclass(frozen=True)
class ReleaseInfo:
    train: str
    git_tag: str
    python_version: str
    helm_version: str


@dataclass(frozen=True)
class PackageEntry:
    path: str
    name: str
    evidence: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class PythonPackages:
    publish: tuple[PackageEntry, ...]
    exclude: tuple[PackageEntry, ...]


@dataclass(frozen=True)
class HelmInfo:
    alpha_policy: str
    charts: tuple[str, ...]


@dataclass(frozen=True)
class ValidationPolicy:
    require_current_main_ci: bool
    require_package_build_dry_run: bool
    require_full_devpod_e2e: bool
    require_aws_provider_live: bool
    allow_accepted_historical_evidence: bool


@dataclass(frozen=True)
class ReleaseManifest:
    release: ReleaseInfo
    python_packages: PythonPackages
    helm: HelmInfo
    validation: ValidationPolicy


@dataclass(frozen=True)
class ManifestValidationResult:
    git_tag: str
    python_version: str
    helm_version: str
    publish_count: int
    exclude_count: int
    publish_names: tuple[str, ...]


def normalize_tag_to_python_version(tag: str) -> str:
    match = ALPHA_TAG_RE.fullmatch(tag)
    if not match:
        raise ReleaseManifestError(f"unsupported alpha tag format: {tag}")
    version = f"{match.group(1)}a{match.group(2)}"
    Version(version)
    return version


def load_release_manifest(path: Path) -> ReleaseManifest:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    _reject_secret_like_keys(raw)

    release = raw["release"]
    python_packages = raw["python_packages"]
    helm = raw["helm"]
    validation = raw["validation"]

    return ReleaseManifest(
        release=ReleaseInfo(
            train=release["train"],
            git_tag=release["git_tag"],
            python_version=str(release["python_version"]),
            helm_version=str(release["helm_version"]),
        ),
        python_packages=PythonPackages(
            publish=tuple(PackageEntry(**entry) for entry in python_packages["publish"]),
            exclude=tuple(PackageEntry(**entry) for entry in python_packages["exclude"]),
        ),
        helm=HelmInfo(
            alpha_policy=helm["alpha_policy"],
            charts=tuple(helm["charts"]),
        ),
        validation=ValidationPolicy(**validation),
    )


def validate_release_manifest(
    manifest: ReleaseManifest,
    *,
    repo_root: Path,
    tag: str | None = None,
) -> ManifestValidationResult:
    expected_python_version = normalize_tag_to_python_version(tag or manifest.release.git_tag)
    if manifest.release.python_version != expected_python_version:
        raise ReleaseManifestError(
            "manifest python_version does not match normalized git tag: "
            f"{manifest.release.python_version} != {expected_python_version}",
        )

    publish_names = [pkg.name for pkg in manifest.python_packages.publish]
    excluded_names = [pkg.name for pkg in manifest.python_packages.exclude]
    overlap = sorted(set(publish_names).intersection(excluded_names))
    if overlap:
        raise ReleaseManifestError(f"packages cannot be both published and excluded: {overlap}")

    for pkg in (*manifest.python_packages.publish, *manifest.python_packages.exclude):
        project_path = repo_root / pkg.path
        pyproject_path = project_path / "pyproject.toml"
        if not pyproject_path.exists():
            raise ReleaseManifestError(f"package path missing pyproject.toml: {pkg.path}")
        metadata = _read_project_metadata(pyproject_path)
        if metadata["name"] != pkg.name:
            raise ReleaseManifestError(
                f"package name mismatch for {pkg.path}: {metadata['name']} != {pkg.name}",
            )

    for pkg in manifest.python_packages.publish:
        metadata = _read_project_metadata(repo_root / pkg.path / "pyproject.toml")
        if metadata["version"] != manifest.release.python_version:
            raise ReleaseManifestError(
                f"package version mismatch for {pkg.name}: "
                f"{metadata['version']} != {manifest.release.python_version}",
            )

    for chart_path in manifest.helm.charts:
        if not (repo_root / chart_path / "Chart.yaml").exists():
            raise ReleaseManifestError(f"chart path missing Chart.yaml: {chart_path}")

    return ManifestValidationResult(
        git_tag=manifest.release.git_tag,
        python_version=manifest.release.python_version,
        helm_version=manifest.release.helm_version,
        publish_count=len(manifest.python_packages.publish),
        exclude_count=len(manifest.python_packages.exclude),
        publish_names=tuple(publish_names),
    )


def _read_project_metadata(path: Path) -> dict[str, str]:
    with path.open("rb") as handle:
        project = tomllib.load(handle)["project"]
    return {"name": str(project["name"]), "version": str(project["version"])}


def _reject_secret_like_keys(value: Any, prefix: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            current = f"{prefix}.{key_text}" if prefix else key_text
            if SECRET_KEY_RE.search(key_text):
                raise ReleaseManifestError(f"manifest contains secret-like key: {current}")
            _reject_secret_like_keys(child, current)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_like_keys(child, f"{prefix}[{index}]")
```

- [ ] **Step 6: Implement the validation CLI**

Create `testing/release/cli.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from testing.release.manifest import load_release_manifest, validate_release_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Floe release manifest")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--manifest", default="release/floe-release.yaml")
    validate_parser.add_argument("--tag", default=None)

    list_parser = subparsers.add_parser("package-list")
    list_parser.add_argument("--manifest", default="release/floe-release.yaml")
    list_parser.add_argument("--format", choices=("json", "lines", "bash"), default="lines")

    args = parser.parse_args()
    repo_root = Path.cwd()
    manifest = load_release_manifest(repo_root / args.manifest)

    if args.command == "validate":
        result = validate_release_manifest(manifest, repo_root=repo_root, tag=args.tag)
        print(
            json.dumps(
                {
                    "git_tag": result.git_tag,
                    "python_version": result.python_version,
                    "helm_version": result.helm_version,
                    "publish_count": result.publish_count,
                    "exclude_count": result.exclude_count,
                    "publish_names": list(result.publish_names),
                },
                indent=2,
                sort_keys=True,
            ),
        )
        return

    if args.command == "package-list":
        packages = [pkg.path for pkg in manifest.python_packages.publish]
        if args.format == "json":
            print(json.dumps(packages, indent=2))
        elif args.format == "bash":
            print(" ".join(packages))
        else:
            print("\n".join(packages))
        return


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run focused tests and confirm the intentional version gate**

Run:

```bash
uv run pytest testing/tests/unit/test_release_manifest.py -q
uv run python -m testing.release.cli package-list --manifest release/floe-release.yaml --format lines
uv run ruff check testing/release testing/tests/unit/test_release_manifest.py
uv run mypy --strict testing/release
```

Expected: tests, package-list output, Ruff, and mypy pass.

Then run:

```bash
uv run python -m testing.release.cli validate --manifest release/floe-release.yaml --tag v0.1.0-alpha.1
```

Expected: this command fails on package version mismatch because alpha-published packages still declare `0.1.0`. Keep the validator behavior. Task 2 fixes the package metadata and updates the manifest test to expect a successful result.

- [ ] **Step 8: Commit the manifest scaffold**

Commit only files from Task 1:

```bash
git add release/floe-release.yaml testing/release/__init__.py testing/release/manifest.py testing/release/cli.py testing/tests/unit/test_release_manifest.py pyproject.toml uv.lock
git commit -m "Add alpha release manifest validator"
```

## Task 2: Version And PyPI Distribution Automation

**Files:**
- Modify: alpha-published package `pyproject.toml` files listed in `release/floe-release.yaml`
- Create: `testing/release/build_packages.py`
- Modify: `testing/release/cli.py`
- Create: `testing/tests/unit/test_release_build_packages.py`
- Modify: `.github/workflows/pypi-publish.yml`

- [ ] **Step 1: Add failing package build helper tests**

Create `testing/tests/unit/test_release_build_packages.py`:

```python
from __future__ import annotations

from pathlib import Path

from testing.release.build_packages import artifact_counts, package_paths_from_manifest
from testing.release.manifest import load_release_manifest

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / "release" / "floe-release.yaml"


def test_package_paths_from_manifest_excludes_unsupported_plugins() -> None:
    manifest = load_release_manifest(MANIFEST)

    package_paths = package_paths_from_manifest(manifest)

    assert len(package_paths) == 15
    assert "plugins/floe-storage-aws-s3" in package_paths
    assert "plugins/floe-catalog-glue" in package_paths
    assert "plugins/floe-alert-slack" not in package_paths
    assert "plugins/floe-dbt-fusion" not in package_paths


def test_artifact_counts_match_manifest_package_count(tmp_path: Path) -> None:
    for name in ("floe_core-0.1.0a1-py3-none-any.whl", "floe-core-0.1.0a1.tar.gz"):
        (tmp_path / name).write_text("artifact", encoding="utf-8")

    counts = artifact_counts(tmp_path)

    assert counts == {"wheels": 1, "sdists": 1}
```

- [ ] **Step 2: Run tests and confirm they fail**

Run:

```bash
uv run pytest testing/tests/unit/test_release_build_packages.py -q
```

Expected: fails because `testing.release.build_packages` does not exist.

- [ ] **Step 3: Update alpha package versions and alpha-compatible core dependencies**

Modify each alpha-published project in `release/floe-release.yaml`:

- Set `[project] version = "0.1.0a1"`.
- For every alpha-published non-core package that depends on `floe-core>=0.1.0`, change it to `floe-core>=0.1.0a1,<0.2.0`.
- For alpha-published packages that depend on another alpha-published Floe package, use the same lower bound style for that dependency.
- Do not change excluded package versions in this task.

Use this command to list files that must be edited:

```bash
uv run python -m testing.release.cli package-list --manifest release/floe-release.yaml --format lines
```

After editing, run:

```bash
rg -n '^version = "0.1.0a1"|floe-core>=0.1.0a1,<0.2.0' \
  packages/floe-core/pyproject.toml \
  packages/floe-iceberg/pyproject.toml \
  plugins/floe-orchestrator-dagster/pyproject.toml \
  plugins/floe-catalog-polaris/pyproject.toml \
  plugins/floe-storage-minio/pyproject.toml \
  plugins/floe-compute-duckdb/pyproject.toml \
  plugins/floe-dbt-core/pyproject.toml \
  plugins/floe-ingestion-dlt/pyproject.toml \
  plugins/floe-telemetry-jaeger/pyproject.toml \
  plugins/floe-rbac-k8s/pyproject.toml \
  plugins/floe-network-security-k8s/pyproject.toml \
  plugins/floe-lineage-marquez/pyproject.toml \
  plugins/floe-quality-gx/pyproject.toml \
  plugins/floe-storage-aws-s3/pyproject.toml \
  plugins/floe-catalog-glue/pyproject.toml
```

Expected: every alpha-published package file reports `version = "0.1.0a1"`; non-core alpha packages report an alpha-compatible `floe-core` dependency.

- [ ] **Step 4: Update the manifest validation test to expect success**

Modify `testing/tests/unit/test_release_manifest.py` by replacing `test_release_manifest_detects_current_version_mismatch_before_alpha_versions_are_applied` with:

```python
def test_release_manifest_validates_repo_paths_and_versions() -> None:
    manifest = load_release_manifest(MANIFEST)

    result = validate_release_manifest(manifest, repo_root=REPO_ROOT, tag="v0.1.0-alpha.1")

    assert result.publish_count == 15
    assert result.exclude_count == 11
    assert result.python_version == "0.1.0a1"
    assert result.git_tag == "v0.1.0-alpha.1"
```

- [ ] **Step 5: Implement package build helper**

Create `testing/release/build_packages.py`:

```python
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from testing.release.manifest import ReleaseManifest


def package_paths_from_manifest(manifest: ReleaseManifest) -> list[str]:
    return [pkg.path for pkg in manifest.python_packages.publish]


def artifact_counts(dist_dir: Path) -> dict[str, int]:
    return {
        "wheels": len(list(dist_dir.glob("*.whl"))),
        "sdists": len(list(dist_dir.glob("*.tar.gz"))),
    }


def build_packages(manifest: ReleaseManifest, *, repo_root: Path, dist_dir: Path) -> None:
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True)

    for package_path in package_paths_from_manifest(manifest):
        subprocess.run(
            ["python", "-m", "build", str(repo_root / package_path), "--outdir", str(dist_dir)],
            check=True,
        )
```

Extend `testing/release/cli.py` with a `build` subcommand:

```python
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--manifest", default="release/floe-release.yaml")
    build_parser.add_argument("--dist-dir", default="dist")
```

Add this branch before the end of `main()`:

```python
    if args.command == "build":
        from testing.release.build_packages import artifact_counts, build_packages

        validate_release_manifest(manifest, repo_root=repo_root, tag=None)
        dist_dir = repo_root / args.dist_dir
        build_packages(manifest, repo_root=repo_root, dist_dir=dist_dir)
        counts = artifact_counts(dist_dir)
        expected = len(manifest.python_packages.publish)
        if counts["wheels"] != expected or counts["sdists"] != expected:
            raise SystemExit(
                f"expected {expected} wheels and {expected} sdists, "
                f"got {counts['wheels']} wheels and {counts['sdists']} sdists",
            )
        print(json.dumps(counts, sort_keys=True))
        return
```

- [ ] **Step 6: Refactor PyPI workflow to use the manifest**

Modify `.github/workflows/pypi-publish.yml`:

- In `Install build tools`, install the workspace dependencies instead of only `build`:

```yaml
      - name: Install dependencies
        run: uv sync --all-extras --dev
```

- Replace the `PACKAGES=(...)` shell array and hardcoded `24` assertions with:

```yaml
      - name: Validate release manifest
        env:
          REF_NAME: ${{ github.ref_name }}
          REF_TYPE: ${{ github.ref_type }}
        run: |
          set -euo pipefail
          if [[ "${REF_TYPE}" == "tag" ]]; then
            uv run python -m testing.release.cli validate \
              --manifest release/floe-release.yaml \
              --tag "${REF_NAME}"
          else
            uv run python -m testing.release.cli validate \
              --manifest release/floe-release.yaml
          fi

      - name: Build manifest packages
        run: |
          set -euo pipefail
          uv run python -m testing.release.cli build \
            --manifest release/floe-release.yaml \
            --dist-dir dist
          echo "=== Built artifacts ==="
          ls -la dist/
```

- In `Verify artifacts`, replace `24` with manifest-derived count:

```yaml
          EXPECTED_COUNT=$(python - <<'PY'
from pathlib import Path
from testing.release.manifest import load_release_manifest
manifest = load_release_manifest(Path("release/floe-release.yaml"))
print(len(manifest.python_packages.publish))
PY
)
          WHEEL_COUNT=$(find dist/ -name '*.whl' | wc -l)
          echo "Wheels: ${WHEEL_COUNT}"
          if [[ "${WHEEL_COUNT}" -ne "${EXPECTED_COUNT}" ]]; then
            echo "::error::Expected ${EXPECTED_COUNT} wheels, got ${WHEEL_COUNT}"
            exit 1
          fi
```

- [ ] **Step 7: Validate package manifest and build dry-run**

Run:

```bash
uv run pytest testing/tests/unit/test_release_manifest.py testing/tests/unit/test_release_build_packages.py -q
uv run python -m testing.release.cli validate --manifest release/floe-release.yaml --tag v0.1.0-alpha.1
uv run python -m testing.release.cli build --manifest release/floe-release.yaml --dist-dir /tmp/floe-alpha-dist
find /tmp/floe-alpha-dist -name '*.whl' | wc -l
find /tmp/floe-alpha-dist -name '*.tar.gz' | wc -l
```

Expected: tests pass, validation prints publish count `15`, and build dry-run produces `15` wheels and `15` sdists.

- [ ] **Step 8: Commit distribution automation**

Commit:

```bash
git add \
  .github/workflows/pypi-publish.yml \
  packages/floe-core/pyproject.toml \
  packages/floe-iceberg/pyproject.toml \
  plugins/floe-orchestrator-dagster/pyproject.toml \
  plugins/floe-catalog-polaris/pyproject.toml \
  plugins/floe-storage-minio/pyproject.toml \
  plugins/floe-compute-duckdb/pyproject.toml \
  plugins/floe-dbt-core/pyproject.toml \
  plugins/floe-ingestion-dlt/pyproject.toml \
  plugins/floe-telemetry-jaeger/pyproject.toml \
  plugins/floe-rbac-k8s/pyproject.toml \
  plugins/floe-network-security-k8s/pyproject.toml \
  plugins/floe-lineage-marquez/pyproject.toml \
  plugins/floe-quality-gx/pyproject.toml \
  plugins/floe-storage-aws-s3/pyproject.toml \
  plugins/floe-catalog-glue/pyproject.toml \
  testing/release/build_packages.py \
  testing/release/cli.py \
  testing/tests/unit/test_release_build_packages.py \
  uv.lock
git commit -m "Use release manifest for alpha package builds"
```

## Task 3: CI Topology Review And Optimization

**Files:**
- Create: `testing/release/ci_inventory.py`
- Create: `testing/tests/unit/test_release_ci_inventory.py`
- Create: `docs/analysis/2026-05-13-ci-release-topology-review.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/e2e.yml`
- Modify: `.github/CI.md`

- [ ] **Step 1: Add failing CI inventory tests**

Create `testing/tests/unit/test_release_ci_inventory.py`:

```python
from __future__ import annotations

from pathlib import Path

from testing.release.ci_inventory import classify_workflows, workflow_files

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_workflow_inventory_includes_release_and_live_validation_lanes() -> None:
    files = workflow_files(REPO_ROOT / ".github" / "workflows")
    names = {path.name for path in files}

    assert "ci.yml" in names
    assert "e2e.yml" in names
    assert "release.yml" in names
    assert "pypi-publish.yml" in names
    assert "helm-release.yaml" in names


def test_workflow_classification_separates_pr_release_live_and_scheduled() -> None:
    classes = classify_workflows(REPO_ROOT / ".github" / "workflows")

    assert classes["ci.yml"] == "fast-pr"
    assert classes["release.yml"] == "release"
    assert classes["pypi-publish.yml"] == "release"
    assert classes["helm-release.yaml"] == "release"
    assert classes["e2e.yml"] == "live-validation"
    assert classes["weekly.yml"] == "scheduled-maintenance"
```

- [ ] **Step 2: Run tests and confirm they fail**

Run:

```bash
uv run pytest testing/tests/unit/test_release_ci_inventory.py -q
```

Expected: fails because `testing.release.ci_inventory` does not exist.

- [ ] **Step 3: Implement CI inventory helper**

Create `testing/release/ci_inventory.py`:

```python
from __future__ import annotations

from pathlib import Path


def workflow_files(workflows_dir: Path) -> list[Path]:
    return sorted(
        [*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")],
        key=lambda path: path.name,
    )


def classify_workflows(workflows_dir: Path) -> dict[str, str]:
    classes: dict[str, str] = {}
    for path in workflow_files(workflows_dir):
        name = path.name
        if name == "ci.yml":
            classes[name] = "fast-pr"
        elif name in {"release.yml", "pypi-publish.yml", "helm-release.yaml"}:
            classes[name] = "release"
        elif name == "e2e.yml":
            classes[name] = "live-validation"
        elif name in {"weekly.yml", "codspeed.yml", "security.yml"}:
            classes[name] = "scheduled-maintenance"
        else:
            classes[name] = "supporting"
    return classes
```

- [ ] **Step 4: Write the CI topology review**

Create `docs/analysis/2026-05-13-ci-release-topology-review.md` with this structure:

```markdown
# CI Release Topology Review

Date: 2026-05-13

## Summary

CI must keep fast PR confidence separate from release and live-provider confidence. The alpha release gate depends on the release manifest, so workflow package lists, artifact counts, version checks, and evidence requirements must be manifest-driven.

## Workflow Classification

| Workflow | Class | Alpha action |
|---|---|---|
| `ci.yml` | Fast PR | Keep required for PRs; add manifest validation as a fast structural check. |
| `e2e.yml` | Live validation | Activate through manual dispatch, merge queue, `run-e2e` label, or infrastructure path changes. |
| `release.yml` | Release | Validate manifest and attach release evidence before GitHub Release creation. |
| `pypi-publish.yml` | Release | Build/publish only manifest packages. |
| `helm-release.yaml` | Release | Enforce manifest Helm policy. |
| `helm-ci.yaml` | Merge confidence | Keep chart lint/render/schema validation. |
| `weekly.yml` | Scheduled maintenance | Keep expensive compatibility and dependency drift work scheduled. |
| `security.yml` | Scheduled/security | Keep separate from package publish. |
| `codspeed.yml` | Scheduled/performance | Keep performance signal non-blocking for alpha unless regressions are release-scoped. |

## Required Changes

- Add a fast manifest validation job to `ci.yml`.
- Activate `e2e.yml` only through explicit triggers and path-sensitive changes.
- Upload E2E artifacts on every live-validation run.
- Make release workflows fail before publish when manifest validation fails.
- Keep AWS live provider validation out of default PR CI and inside release or explicit manual lanes.

## Failure Taxonomy

| Class | Meaning | Release behavior |
|---|---|---|
| Product failure | Floe contract/runtime behavior failed | Blocks release. |
| Infrastructure failure | DevPod, Hetzner, Kind, GitHub Actions, or provider capacity failed before product assertion | Rerun allowed after infra evidence is recorded. |
| Credential/setup failure | Required AWS/DevPod/Hetzner setup missing or invalid | Blocks live gate until setup is fixed. |
| Cleanup failure | Product test passed but provider resources remain | Blocks release until cleanup proof is recorded. |
```

- [ ] **Step 5: Add manifest validation to fast PR CI**

Modify `.github/workflows/ci.yml`:

- Add a new job after `lint-typecheck`:

```yaml
  release-manifest:
    name: Release Manifest
    runs-on: ubuntu-latest
    needs: lint-typecheck
    steps:
      - name: Checkout code
        uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2

      - name: Set up Python
        uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0
        with:
          python-version: ${{ env.PYTHON_VERSION_DEFAULT }}

      - name: Install uv
        uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Install dependencies
        run: uv sync --all-extras --dev

      - name: Validate alpha release manifest
        run: uv run python -m testing.release.cli validate --manifest release/floe-release.yaml
```

- Add `release-manifest` to `ci-success.needs`.
- Add `MANIFEST_RESULT: ${{ needs.release-manifest.result }}` to the summary job env.
- Add a failure check:

```bash
          if [[ "$MANIFEST_RESULT" != "success" ]]; then
            echo "release manifest validation failed" >&2
            exit 1
          fi
```

- [ ] **Step 6: Activate E2E with explicit release-aware triggers**

Modify `.github/workflows/e2e.yml`:

- Replace `if: false` with:

```yaml
    if: |
      github.event_name == 'merge_group' ||
      github.event_name == 'workflow_dispatch' ||
      contains(github.event.pull_request.labels.*.name, 'run-e2e') ||
      needs.changed-files.outputs.infra == 'true'
```

- Keep artifact upload as-is.
- Add `release/floe-release.yaml` and `testing/release/**` to the changed-files infra filter.

- [ ] **Step 7: Validate CI workflow structure**

Run:

```bash
uv run pytest testing/tests/unit/test_release_ci_inventory.py testing/tests/unit/test_ci_workflows.py testing/ci/tests/test_github_actions_node24_pins.py -q
uv run python -m testing.release.cli validate --manifest release/floe-release.yaml
```

Expected: all tests pass.

- [ ] **Step 8: Commit CI review and optimization**

Commit:

```bash
git add \
  .github/workflows/ci.yml \
  .github/workflows/e2e.yml \
  .github/CI.md \
  docs/analysis/2026-05-13-ci-release-topology-review.md \
  testing/release/ci_inventory.py \
  testing/tests/unit/test_release_ci_inventory.py
git commit -m "Optimize CI topology for alpha release gates"
```

## Task 4: Release Validation Gate And Evidence Bundle

**Files:**
- Create: `testing/release/evidence.py`
- Create: `testing/tests/unit/test_release_evidence.py`
- Modify: `testing/release/cli.py`
- Modify: `.github/workflows/release.yml`
- Create: `docs/validation/2026-05-13-alpha-release-candidate-validation.md`

- [ ] **Step 1: Add failing evidence helper tests**

Create `testing/tests/unit/test_release_evidence.py`:

```python
from __future__ import annotations

from pathlib import Path

from testing.release.evidence import (
    EvidenceStatus,
    classify_live_validation_failure,
    write_evidence_summary,
)


def test_classifies_live_validation_failures() -> None:
    assert classify_live_validation_failure("pytest failed: assertion error") == "product"
    assert classify_live_validation_failure("resource_unavailable") == "infrastructure"
    assert classify_live_validation_failure("AWS_ACCESS_KEY_ID is required") == "credential-setup"
    assert classify_live_validation_failure("Glue database still exists") == "cleanup"


def test_writes_evidence_summary_without_secrets(tmp_path: Path) -> None:
    output = tmp_path / "summary.md"
    status = EvidenceStatus(
        release_sha="abc123",
        manifest="release/floe-release.yaml",
        package_count=15,
        devpod_artifact="test-artifacts/devpod-run-example",
        aws_live_result="passed",
        cleanup_result="passed",
    )

    write_evidence_summary(output, status)

    text = output.read_text(encoding="utf-8")
    assert "abc123" in text
    assert "15" in text
    assert "AWS_SECRET_ACCESS_KEY" not in text
```

- [ ] **Step 2: Run tests and confirm they fail**

Run:

```bash
uv run pytest testing/tests/unit/test_release_evidence.py -q
```

Expected: fails because `testing.release.evidence` does not exist.

- [ ] **Step 3: Implement evidence helper**

Create `testing/release/evidence.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EvidenceStatus:
    release_sha: str
    manifest: str
    package_count: int
    devpod_artifact: str
    aws_live_result: str
    cleanup_result: str


def classify_live_validation_failure(output: str) -> str:
    lowered = output.lower()
    if "glue database still exists" in lowered or "s3 objects remain" in lowered:
        return "cleanup"
    if "aws_access_key_id" in lowered or "access denied" in lowered or "credential" in lowered:
        return "credential-setup"
    if "resource_unavailable" in lowered or "timed out waiting" in lowered:
        return "infrastructure"
    return "product"


def write_evidence_summary(path: Path, status: EvidenceStatus) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# Alpha Release Candidate Validation",
                "",
                f"- Release SHA: `{status.release_sha}`",
                f"- Manifest: `{status.manifest}`",
                f"- Package count: `{status.package_count}`",
                f"- DevPod artifact: `{status.devpod_artifact}`",
                f"- AWS live validation: `{status.aws_live_result}`",
                f"- Cleanup: `{status.cleanup_result}`",
                "",
            ],
        ),
        encoding="utf-8",
    )
```

- [ ] **Step 4: Add evidence CLI command**

Extend `testing/release/cli.py` with an `evidence-summary` subcommand:

```python
    evidence_parser = subparsers.add_parser("evidence-summary")
    evidence_parser.add_argument("--release-sha", required=True)
    evidence_parser.add_argument("--manifest", default="release/floe-release.yaml")
    evidence_parser.add_argument("--devpod-artifact", required=True)
    evidence_parser.add_argument("--aws-live-result", required=True)
    evidence_parser.add_argument("--cleanup-result", required=True)
    evidence_parser.add_argument("--output", required=True)
```

Add this branch:

```python
    if args.command == "evidence-summary":
        from testing.release.evidence import EvidenceStatus, write_evidence_summary

        result = validate_release_manifest(manifest, repo_root=repo_root, tag=None)
        write_evidence_summary(
            Path(args.output),
            EvidenceStatus(
                release_sha=args.release_sha,
                manifest=args.manifest,
                package_count=result.publish_count,
                devpod_artifact=args.devpod_artifact,
                aws_live_result=args.aws_live_result,
                cleanup_result=args.cleanup_result,
            ),
        )
        return
```

- [ ] **Step 5: Update release workflow**

Modify `.github/workflows/release.yml`:

- In `validate`, add manifest validation after dependency installation:

```yaml
      - name: Validate release manifest
        env:
          REF_NAME: ${{ github.ref_name }}
          REF_TYPE: ${{ github.ref_type }}
        run: |
          set -euo pipefail
          if [[ "${REF_TYPE}" == "tag" ]]; then
            uv run python -m testing.release.cli validate \
              --manifest release/floe-release.yaml \
              --tag "${REF_NAME}"
          else
            uv run python -m testing.release.cli validate \
              --manifest release/floe-release.yaml
          fi
```

- In `release`, add an artifact download or generated summary step before `Create GitHub Release`:

```yaml
      - name: Write release evidence summary
        run: |
          uv sync --all-extras --dev
          uv run python -m testing.release.cli evidence-summary \
            --release-sha "${GITHUB_SHA}" \
            --manifest release/floe-release.yaml \
            --devpod-artifact "pre-tag-required" \
            --aws-live-result "pre-tag-required" \
            --cleanup-result "pre-tag-required" \
            --output release-evidence.md
```

- Update `softprops/action-gh-release` to attach `release-evidence.md`:

```yaml
          files: release-evidence.md
```

Keep the `pre-tag-required` values until Task 7 records real evidence. The release checklist must block tag creation before these marker values can reach a production tag.

- [ ] **Step 6: Validate evidence helper and release workflow tests**

Run:

```bash
uv run pytest testing/tests/unit/test_release_evidence.py -q
uv run python -m testing.release.cli evidence-summary \
  --release-sha "$(git rev-parse HEAD)" \
  --manifest release/floe-release.yaml \
  --devpod-artifact test-artifacts/example \
  --aws-live-result passed \
  --cleanup-result passed \
  --output /tmp/floe-release-evidence.md
test -s /tmp/floe-release-evidence.md
```

Expected: tests pass and evidence summary is written without secrets.

- [ ] **Step 7: Commit release evidence gate**

Commit:

```bash
git add testing/release/evidence.py testing/release/cli.py testing/tests/unit/test_release_evidence.py .github/workflows/release.yml
git commit -m "Add alpha release evidence gate"
```

## Task 5: Helm Alpha Policy

**Files:**
- Modify: `.github/workflows/helm-release.yaml`
- Modify: `testing/release/manifest.py`
- Modify: `testing/tests/unit/test_release_manifest.py`
- Modify: `docs/guides/deployment/kubernetes-helm.md`
- Modify: `.github/CI.md`

- [ ] **Step 1: Add Helm policy assertions**

Add these tests to `testing/tests/unit/test_release_manifest.py`:

```python
def test_manifest_declares_helm_alpha_publish_policy() -> None:
    manifest = load_release_manifest(MANIFEST)

    assert manifest.helm.alpha_policy == "publish"
    assert manifest.helm.charts == ("charts/floe-platform", "charts/floe-jobs")
    assert manifest.release.helm_version == "0.1.0-alpha.1"
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
uv run pytest testing/tests/unit/test_release_manifest.py -q
```

Expected: passes if Task 1 manifest is intact.

- [ ] **Step 3: Gate Helm release workflow on manifest policy**

Modify `.github/workflows/helm-release.yaml`:

- Add Python and uv setup to the `build` job before version extraction:

```yaml
      - name: Set up Python
        uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0
        with:
          python-version: "3.10"

      - name: Install uv
        uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Install dependencies
        run: uv sync --all-extras --dev
```

- Add manifest validation after version extraction:

```yaml
      - name: Validate Helm alpha policy
        run: |
          set -euo pipefail
          uv run python -m testing.release.cli validate --manifest release/floe-release.yaml
```

- Replace manual `version` handling with manifest version for tag-triggered alpha releases where possible:

```bash
if [ -n "${INPUT_VERSION}" ]; then
  VERSION="${INPUT_VERSION}"
else
  VERSION=$(uv run python - <<'PY'
from pathlib import Path
from testing.release.manifest import load_release_manifest
manifest = load_release_manifest(Path("release/floe-release.yaml"))
print(manifest.release.helm_version)
PY
)
fi
```

- [ ] **Step 4: Validate Helm workflow structure**

Run:

```bash
uv run pytest testing/tests/unit/test_release_manifest.py testing/ci/tests/test_github_actions_node24_pins.py -q
```

Expected: tests pass and action pins remain Node 24-compatible.

- [ ] **Step 5: Commit Helm policy alignment**

Commit:

```bash
git add .github/workflows/helm-release.yaml testing/release/manifest.py testing/tests/unit/test_release_manifest.py docs/guides/deployment/kubernetes-helm.md .github/CI.md
git commit -m "Align Helm release policy with alpha manifest"
```

## Task 6: Maintainer And Contributor Documentation

**Files:**
- Modify: `RELEASING.md`
- Modify: `.github/CI.md`
- Modify: `docs/guides/pypi-trusted-publishers.md`
- Modify: `docs/contributing/aws-provider-testing.md`
- Modify: `docs/releases/v0.1.0-alpha.1-checklist.md`
- Modify: `docs/releases/v0.1.0-alpha.1-release-notes.md`

- [ ] **Step 1: Update release process docs**

Modify `RELEASING.md` so the top-level alpha process is:

```markdown
## Alpha Release Flow

1. Sync `main` and verify the release SHA.
2. Validate `release/floe-release.yaml`.
3. Run package build dry-run for the manifest package set.
4. Run current-main CI and verify the required release checks.
5. Run full DevPod+Hetzner E2E from current `main`.
6. Run AWS S3+Glue live validation or cite accepted historical evidence recorded in the manifest.
7. Record AWS and Hetzner cleanup evidence.
8. Push the release tag only after the evidence bundle is complete.
9. Verify PyPI published exactly the manifest package set.
10. Verify Helm behavior matches the manifest policy.
```

Replace every stale reference to `24` PyPI packages with `15 alpha packages`.

- [ ] **Step 2: Update CI docs**

Modify `.github/CI.md` so the quick reference includes:

```markdown
| Trigger | Workflow | Purpose |
|---|---|---|
| Pull request | `ci.yml` | Fast PR confidence plus release manifest structure |
| Pull request label `run-e2e` / infra path / manual | `e2e.yml` | Full E2E validation |
| Tag `v*.*.*` | `release.yml` and `pypi-publish.yml` | Manifest validation, integration, release, package build/publish |
| Tag `helm-v*` / `charts-v*` / manual | `helm-release.yaml` | Helm chart release when manifest policy allows |
| Schedule | `weekly.yml`, `security.yml`, `codspeed.yml` | Drift, security, performance maintenance |
```

- [ ] **Step 3: Update PyPI trusted publisher docs**

Modify `docs/guides/pypi-trusted-publishers.md`:

- Replace the pending publisher list with the 15 manifest-published package names.
- Add a section titled `Excluded from alpha` with the 11 excluded package names.
- State that excluded packages must not be registered as alpha pending publishers until their composition path is proven.

- [ ] **Step 4: Update AWS provider testing docs**

Modify `docs/contributing/aws-provider-testing.md` to include:

```markdown
## Release Evidence Requirements

For alpha release validation, AWS provider testing must record:

- `FLOE_PROVIDER_SPIKE_RUN`
- DevPod workspace name
- S3 test prefix
- Glue database prefix
- pytest result for `tests/integration/test_aws_provider_live.py`
- cleanup output from `scripts/aws-provider-test-cleanup.sh`

Do not archive AWS access keys, secret access keys, session tokens, or remote environment files.
```

- [ ] **Step 5: Validate docs content**

Run:

```bash
uv run python testing/ci/validate-docs-navigation.py
uv run python testing/ci/validate-docs-content.py
rg -n "24 packages|PyPI packages \\(24\\)|pending publishers.*24" RELEASING.md .github/CI.md docs || true
```

Expected: docs validators pass and the `rg` command prints no stale 24-package release claims.

- [ ] **Step 6: Commit documentation**

Commit:

```bash
git add RELEASING.md .github/CI.md docs/guides/pypi-trusted-publishers.md docs/contributing/aws-provider-testing.md docs/releases/v0.1.0-alpha.1-checklist.md docs/releases/v0.1.0-alpha.1-release-notes.md
git commit -m "Document manifest-driven alpha release process"
```

## Task 7: Release Candidate Validation Run

**Files:**
- Create or modify: `docs/validation/2026-05-13-alpha-release-candidate-validation.md`
- Modify: `docs/releases/v0.1.0-alpha.1-checklist.md`

- [ ] **Step 1: Verify local release checks**

Run:

```bash
uv run python -m testing.release.cli validate --manifest release/floe-release.yaml --tag v0.1.0-alpha.1
uv run python -m testing.release.cli build --manifest release/floe-release.yaml --dist-dir /tmp/floe-alpha-dist
uv run pytest testing/tests/unit/test_release_manifest.py testing/tests/unit/test_release_build_packages.py testing/tests/unit/test_release_evidence.py testing/tests/unit/test_release_ci_inventory.py -q
uv run ruff check testing/release testing/tests/unit/test_release_manifest.py testing/tests/unit/test_release_build_packages.py testing/tests/unit/test_release_evidence.py testing/tests/unit/test_release_ci_inventory.py
uv run mypy --strict testing/release
```

Expected: all commands pass.

- [ ] **Step 2: Run full repo tests for the release branch**

Run:

```bash
make test-unit
make test-contract
make lint
make typecheck
```

Expected: all commands pass. Record exact summaries in `docs/validation/2026-05-13-alpha-release-candidate-validation.md`.

- [ ] **Step 3: Run DevPod+Hetzner full E2E**

Run from current `main` or the release-candidate branch after it is pushed:

```bash
DEVPOD_REMOTE_E2E_MAKE_TARGET=test-e2e-full make devpod-test
```

Expected: full remote E2E passes and an artifact directory is created under `test-artifacts/devpod-run-*`. Record:

- release SHA
- DevPod workspace
- Hetzner machine
- artifact path
- final pytest summary
- `devpod list` after cleanup
- direct Hetzner resource inventory after cleanup

- [ ] **Step 4: Run AWS S3+Glue live validation**

Run:

```bash
make devpod-test-aws-provider
```

Expected: `tests/integration/test_aws_provider_live.py` passes through the remote DevPod lane. Record:

- `FLOE_PROVIDER_SPIKE_RUN`
- S3 prefix
- Glue database prefix
- pytest summary
- cleanup command output
- classification as product pass, infrastructure failure, credential/setup failure, or cleanup failure

- [ ] **Step 5: Verify cleanup directly**

Run:

```bash
devpod list
devpod machine list
```

Expected: no release-validation workspaces or machines remain.

If AWS environment variables for the run are present, run:

```bash
scripts/aws-provider-test-cleanup.sh
```

Expected: cleanup prints `Cleanup checks passed`.

- [ ] **Step 6: Write release candidate evidence**

Create or update `docs/validation/2026-05-13-alpha-release-candidate-validation.md`:

```markdown
# Alpha Release Candidate Validation

Date: 2026-05-13
Release candidate SHA: `record the exact output of git rev-parse HEAD from Step 1`
Manifest: `release/floe-release.yaml`

## Summary

| Lane | Command | Result | Evidence |
|---|---|---|---|
| Manifest | `uv run python -m testing.release.cli validate --manifest release/floe-release.yaml --tag v0.1.0-alpha.1` | PASS | package count 15 |
| Package build dry-run | `uv run python -m testing.release.cli build --manifest release/floe-release.yaml --dist-dir /tmp/floe-alpha-dist` | PASS | 15 wheels, 15 sdists |
| Unit/contract/lint/type | see command list | PASS | summaries below |
| DevPod+Hetzner E2E | `DEVPOD_REMOTE_E2E_MAKE_TARGET=test-e2e-full make devpod-test` | PASS | `test-artifacts/...` |
| AWS S3+Glue live | `make devpod-test-aws-provider` | PASS | run id and cleanup proof |
| Cleanup | provider inventory commands | PASS | no residual resources |

## Failure Taxonomy

No release-blocking failures remained after validation.
```

Use exact observed values for the release SHA and `test-artifacts/` path.

- [ ] **Step 7: Update release checklist**

Modify `docs/releases/v0.1.0-alpha.1-checklist.md`:

- Link to the new validation record.
- Record 15 alpha packages.
- Record 11 excluded packages.
- Record Helm policy as publish or skip based on manifest.
- Remove stale historical-only gate language that conflicts with the current validation record.

- [ ] **Step 8: Commit validation evidence**

Commit:

```bash
git add docs/validation/2026-05-13-alpha-release-candidate-validation.md docs/releases/v0.1.0-alpha.1-checklist.md
git commit -m "Record alpha release candidate validation"
```

## Final Verification Before PR

Run:

```bash
git status --short
uv run python -m testing.release.cli validate --manifest release/floe-release.yaml --tag v0.1.0-alpha.1
uv run pytest testing/tests/unit/test_release_manifest.py testing/tests/unit/test_release_build_packages.py testing/tests/unit/test_release_evidence.py testing/tests/unit/test_release_ci_inventory.py -q
uv run ruff check testing/release testing/tests/unit/test_release_manifest.py testing/tests/unit/test_release_build_packages.py testing/tests/unit/test_release_evidence.py testing/tests/unit/test_release_ci_inventory.py
uv run mypy --strict testing/release
make test-unit
make test-contract
```

Expected:

- `git status --short` is clean before PR.
- Manifest validation passes.
- Focused release helper tests pass.
- Ruff and mypy pass.
- Unit and contract suites pass.
- Full DevPod+Hetzner E2E and AWS live validation evidence is recorded in docs before tagging.

## PR Description Template

```markdown
## Summary

- adds manifest-driven alpha release control
- publishes only the evidence-approved alpha package cutline
- aligns PyPI, Helm, CI, and release evidence with `release/floe-release.yaml`

## Validation

- `uv run python -m testing.release.cli validate --manifest release/floe-release.yaml --tag v0.1.0-alpha.1`
- `uv run python -m testing.release.cli build --manifest release/floe-release.yaml --dist-dir /tmp/floe-alpha-dist`
- `uv run pytest testing/tests/unit/test_release_manifest.py testing/tests/unit/test_release_build_packages.py testing/tests/unit/test_release_evidence.py testing/tests/unit/test_release_ci_inventory.py -q`
- `uv run ruff check testing/release testing/tests/unit/test_release_manifest.py testing/tests/unit/test_release_build_packages.py testing/tests/unit/test_release_evidence.py testing/tests/unit/test_release_ci_inventory.py`
- `uv run mypy --strict testing/release`
- `make test-unit`
- `make test-contract`

## Release Evidence

- DevPod+Hetzner full E2E: paste the artifact path recorded in `docs/validation/2026-05-13-alpha-release-candidate-validation.md`
- AWS S3+Glue live validation: paste the run id recorded in `docs/validation/2026-05-13-alpha-release-candidate-validation.md`
- Cleanup proof: paste the cleanup summary recorded in `docs/validation/2026-05-13-alpha-release-candidate-validation.md`
```

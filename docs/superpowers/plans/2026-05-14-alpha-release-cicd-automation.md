# Alpha Release CI/CD Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a release-preparation workflow that creates the alpha tag and GitHub Release only after all release gates pass, while keeping PR CI fast and publishing only manifest-declared alpha packages.

**Architecture:** Keep `release/floe-release.yaml` as the source of truth. Add small release helper modules under `testing/release/` for candidate resolution, cleanup evidence, and failure issue content, then wire GitHub Actions around those helpers. PyPI publishing stays downstream of verified release metadata and never owns a package list.

**Tech Stack:** GitHub Actions YAML, Python 3.10+, Pydantic-free dataclass helpers, PyYAML, pytest, uv, shell scripts, GitHub CLI/API, DevPod/Hetzner/AWS test lanes.

---

## Scope And Branching

Implement this from a clean branch based on `origin/main`. Do not use the root
checkout if it is still diverged from `origin/main`.

Recommended branch:

```bash
git worktree add -b release/prepare-release-gate .worktrees/prepare-release-gate origin/main
cd .worktrees/prepare-release-gate
```

Keep commits small. Each task below ends with a commit.

## File Structure

Create:

- `.github/workflows/prepare-release.yml` - maintainer-dispatched release gate; creates tag and GitHub Release only after all gates pass.
- `testing/release/candidate.py` - validates requested version, manifest version, release SHA, and tag absence.
- `testing/release/failure_issue.py` - creates deterministic issue title/body content for release and weekly failures.
- `testing/release/cleanup.py` - normalizes cleanup evidence and classifies cleanup status from command results.
- `testing/tests/unit/test_prepare_release_workflow.py` - structural tests for the new workflow.
- `testing/tests/unit/test_release_candidate.py` - unit tests for release candidate validation.
- `testing/tests/unit/test_release_failure_issue.py` - unit tests for failure issue formatting and dedup keys.
- `testing/tests/unit/test_release_cleanup.py` - unit tests for cleanup evidence classification.

Modify:

- `.github/workflows/release.yml` - retire tag-triggered authority or make it non-publishing/manual-only; it must not create releases from direct tag pushes.
- `.github/workflows/pypi-publish.yml` - trust only successful prepare-release metadata; keep manual dispatch as dry-run only.
- `.github/workflows/weekly.yml` - create/update issues on deep validation failure.
- `testing/release/cli.py` - expose helper commands for candidate validation, failure issue body generation, cleanup evidence, and release evidence summary from workflow inputs.
- `testing/release/evidence.py` - extend evidence fields if needed to represent actual gate links and cleanup output.
- `testing/tests/unit/test_ci_workflows.py` - update workflow topology assertions.
- `testing/tests/unit/test_release_evidence.py` - cover non-placeholder workflow-generated evidence.
- `RELEASING.md` - replace direct tag-push instructions with prepare-release dispatch.
- `.github/CI.md` - document lane ownership and long-running gate behavior.
- `docs/releases/v0.1.0-alpha.1-checklist.md` - replace manual evidence variables with automated release evidence generation.

Do not modify package implementation code in this plan.

---

### Task 1: Release Candidate Validation Helper

**Files:**
- Create: `testing/release/candidate.py`
- Test: `testing/tests/unit/test_release_candidate.py`
- Modify: `testing/release/cli.py`

- [ ] **Step 1: Write failing tests for requested version validation**

Create `testing/tests/unit/test_release_candidate.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from testing.release.candidate import (
    ReleaseCandidateError,
    validate_release_candidate,
)


def _write_manifest(tmp_path: Path, tag: str = "v0.1.0-alpha.1") -> Path:
    manifest = tmp_path / "release" / "floe-release.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        f"""
release:
  train: alpha
  git_tag: {tag}
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
  charts:
    - charts/floe-platform
    - charts/floe-jobs
validation:
  require_current_main_ci: true
  require_package_build_dry_run: true
  require_full_devpod_e2e: true
  require_aws_provider_live: true
  allow_accepted_historical_evidence: false
""",
        encoding="utf-8",
    )
    return manifest


def _write_package_and_charts(tmp_path: Path) -> None:
    package = tmp_path / "packages" / "floe-core"
    package.mkdir(parents=True)
    package.joinpath("pyproject.toml").write_text(
        """
[project]
name = "floe-core"
version = "0.1.0a1"
""",
        encoding="utf-8",
    )
    for chart in ("floe-platform", "floe-jobs"):
        chart_dir = tmp_path / "charts" / chart
        chart_dir.mkdir(parents=True)
        chart_dir.joinpath("Chart.yaml").write_text(
            f"name: {chart}\nversion: 0.1.0-alpha.1\n",
            encoding="utf-8",
        )


def test_validate_release_candidate_accepts_matching_manifest_and_sha(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    _write_package_and_charts(tmp_path)

    result = validate_release_candidate(
        requested_version="v0.1.0-alpha.1",
        release_sha="0000000000000000000000000000000000000000",
        manifest_path=manifest,
        repo_root=tmp_path,
        existing_tags=(),
    )

    assert result.version == "v0.1.0-alpha.1"
    assert result.release_sha == "0000000000000000000000000000000000000000"
    assert result.python_version == "0.1.0a1"
    assert result.helm_version == "0.1.0-alpha.1"
    assert result.publish_count == 1


def test_validate_release_candidate_rejects_manifest_version_mismatch(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    _write_package_and_charts(tmp_path)

    with pytest.raises(ReleaseCandidateError, match="does not match manifest git_tag"):
        validate_release_candidate(
            requested_version="v0.1.0-alpha.2",
            release_sha="0000000000000000000000000000000000000000",
            manifest_path=manifest,
            repo_root=tmp_path,
            existing_tags=(),
        )


def test_validate_release_candidate_rejects_existing_tag(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    _write_package_and_charts(tmp_path)

    with pytest.raises(ReleaseCandidateError, match="release tag already exists"):
        validate_release_candidate(
            requested_version="v0.1.0-alpha.1",
            release_sha="0000000000000000000000000000000000000000",
            manifest_path=manifest,
            repo_root=tmp_path,
            existing_tags=("v0.1.0-alpha.1",),
        )


def test_validate_release_candidate_rejects_non_sha_release_ref(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    _write_package_and_charts(tmp_path)

    with pytest.raises(ReleaseCandidateError, match="release_sha must be a 40-character commit SHA"):
        validate_release_candidate(
            requested_version="v0.1.0-alpha.1",
            release_sha="main",
            manifest_path=manifest,
            repo_root=tmp_path,
            existing_tags=(),
        )
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```bash
uv run pytest testing/tests/unit/test_release_candidate.py -q
```

Expected: fails with `ModuleNotFoundError: No module named 'testing.release.candidate'`.

- [ ] **Step 3: Implement candidate validation**

Create `testing/release/candidate.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from testing.release.manifest import load_release_manifest, validate_release_manifest

_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


class ReleaseCandidateError(ValueError):
    """Raised when a release candidate cannot safely create a tag."""


@dataclass(frozen=True)
class ReleaseCandidate:
    """Validated release candidate metadata."""

    version: str
    release_sha: str
    python_version: str
    helm_version: str
    publish_count: int


def validate_release_candidate(
    *,
    requested_version: str,
    release_sha: str,
    manifest_path: Path,
    repo_root: Path,
    existing_tags: tuple[str, ...],
) -> ReleaseCandidate:
    """Validate that a requested release can create a new tag."""
    version = requested_version.strip()
    if not version:
        raise ReleaseCandidateError("requested version is required")
    if not version.startswith("v"):
        raise ReleaseCandidateError("requested version must start with 'v'")
    if not _COMMIT_SHA_RE.fullmatch(release_sha.strip()):
        raise ReleaseCandidateError("release_sha must be a 40-character commit SHA")
    if version in existing_tags:
        raise ReleaseCandidateError(f"release tag already exists: {version}")

    manifest = load_release_manifest(manifest_path)
    if manifest.release.git_tag != version:
        raise ReleaseCandidateError(
            f"requested version {version} does not match manifest git_tag {manifest.release.git_tag}",
        )

    result = validate_release_manifest(manifest, repo_root=repo_root, tag=version)
    return ReleaseCandidate(
        version=version,
        release_sha=release_sha,
        python_version=result.python_version,
        helm_version=result.helm_version,
        publish_count=result.publish_count,
    )
```

- [ ] **Step 4: Add CLI command for workflow use**

Modify `testing/release/cli.py`:

```python
from testing.release.candidate import ReleaseCandidateError, validate_release_candidate
```

Add parser setup:

```python
    candidate_parser = subparsers.add_parser("candidate")
    candidate_parser.add_argument("--manifest", default="release/floe-release.yaml")
    candidate_parser.add_argument("--version", required=True)
    candidate_parser.add_argument("--release-sha", required=True)
    candidate_parser.add_argument("--existing-tag", action="append", default=[])
```

Add command branch after manifest loading:

```python
        if args.command == "candidate":
            result = validate_release_candidate(
                requested_version=args.version,
                release_sha=args.release_sha,
                manifest_path=manifest_path,
                repo_root=repo_root,
                existing_tags=tuple(args.existing_tag),
            )
            print(json.dumps(asdict(result), indent=2, sort_keys=True))
            return
```

Add `ReleaseCandidateError` to the caught exception tuple.

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest testing/tests/unit/test_release_candidate.py testing/tests/unit/test_release_manifest.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add testing/release/candidate.py testing/release/cli.py testing/tests/unit/test_release_candidate.py
git commit -m "Add release candidate validation helper"
```

---

### Task 2: Failure Issue Helper

**Files:**
- Create: `testing/release/failure_issue.py`
- Test: `testing/tests/unit/test_release_failure_issue.py`
- Modify: `testing/release/cli.py`

- [ ] **Step 1: Write failing tests for deterministic issue content**

Create `testing/tests/unit/test_release_failure_issue.py`:

```python
from __future__ import annotations

from testing.release.failure_issue import FailureIssue, issue_comment_body, issue_title


def test_release_gate_issue_title_is_deterministic() -> None:
    issue = FailureIssue(
        lane="release-gate",
        version="v0.1.0-alpha.1",
        gate="full-e2e",
        classification="infrastructure",
        sha="0000000000000000000000000000000000000000",
        run_url="https://github.com/Obsidian-Owl/floe/actions/runs/123",
        log_excerpt="Error in server creation action: action timeout",
        cleanup_status="passed",
        skipped_outputs=("tag", "github-release", "pypi"),
    )

    assert issue_title(issue) == (
        "Release gate failed: v0.1.0-alpha.1 full-e2e infrastructure failure"
    )


def test_weekly_issue_title_omits_version() -> None:
    issue = FailureIssue(
        lane="weekly-validation",
        version=None,
        gate="e2e-tests",
        classification="product",
        sha="0000000000000000000000000000000000000000",
        run_url="https://github.com/Obsidian-Owl/floe/actions/runs/456",
        log_excerpt="assert expected_rows == actual_rows",
        cleanup_status="not-run",
        skipped_outputs=(),
    )

    assert issue_title(issue) == "Weekly validation failed: e2e-tests product failure"


def test_issue_comment_body_contains_release_safety_state() -> None:
    issue = FailureIssue(
        lane="release-gate",
        version="v0.1.0-alpha.1",
        gate="aws-live",
        classification="credential-setup",
        sha="0000000000000000000000000000000000000000",
        run_url="https://github.com/Obsidian-Owl/floe/actions/runs/789",
        log_excerpt="Unable to locate credentials",
        cleanup_status="passed",
        skipped_outputs=("tag", "github-release", "pypi"),
    )

    body = issue_comment_body(issue)

    assert "Workflow run: https://github.com/Obsidian-Owl/floe/actions/runs/789" in body
    assert "Commit: `0000000000000000000000000000000000000000`" in body
    assert "Requested version: `v0.1.0-alpha.1`" in body
    assert "Failed gate: `aws-live`" in body
    assert "Classification: `credential-setup`" in body
    assert "Cleanup status: `passed`" in body
    assert "Skipped outputs: `tag`, `github-release`, `pypi`" in body
    assert "Unable to locate credentials" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest testing/tests/unit/test_release_failure_issue.py -q
```

Expected: fails with `ModuleNotFoundError: No module named 'testing.release.failure_issue'`.

- [ ] **Step 3: Implement issue formatting helper**

Create `testing/release/failure_issue.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FailureIssue:
    """Issue content for release-gate and weekly validation failures."""

    lane: str
    version: str | None
    gate: str
    classification: str
    sha: str
    run_url: str
    log_excerpt: str
    cleanup_status: str
    skipped_outputs: tuple[str, ...] = ()


def issue_title(issue: FailureIssue) -> str:
    """Return a deterministic title suitable for issue deduplication."""
    if issue.lane == "release-gate":
        version = issue.version or "unknown-version"
        return f"Release gate failed: {version} {issue.gate} {issue.classification} failure"
    if issue.lane == "weekly-validation":
        return f"Weekly validation failed: {issue.gate} {issue.classification} failure"
    return f"Validation failed: {issue.lane} {issue.gate} {issue.classification} failure"


def issue_comment_body(issue: FailureIssue) -> str:
    """Return a markdown issue body or update comment for a failed validation run."""
    skipped = (
        ", ".join(f"`{name}`" for name in issue.skipped_outputs)
        if issue.skipped_outputs
        else "_none_"
    )
    version = issue.version or "_not applicable_"
    excerpt = issue.log_excerpt.strip() or "_No log excerpt captured._"
    return "\n".join(
        [
            "## Validation Failure",
            "",
            f"Workflow run: {issue.run_url}",
            f"Commit: `{issue.sha}`",
            f"Requested version: `{version}`" if issue.version else f"Requested version: {version}",
            f"Failed gate: `{issue.gate}`",
            f"Classification: `{issue.classification}`",
            f"Cleanup status: `{issue.cleanup_status}`",
            f"Skipped outputs: {skipped}",
            "",
            "### Log Excerpt",
            "",
            "```text",
            excerpt[-4000:],
            "```",
            "",
            "### Next Action",
            "",
            "Triage the failed gate, preserve cleanup evidence, and rerun the workflow after the fix lands.",
            "",
        ],
    )
```

- [ ] **Step 4: Add CLI command for issue body generation**

Modify `testing/release/cli.py`:

```python
from testing.release.failure_issue import FailureIssue, issue_comment_body, issue_title
```

Add parser setup:

```python
    issue_parser = subparsers.add_parser("failure-issue")
    issue_parser.add_argument("--lane", required=True)
    issue_parser.add_argument("--version", default=None)
    issue_parser.add_argument("--gate", required=True)
    issue_parser.add_argument("--classification", required=True)
    issue_parser.add_argument("--sha", required=True)
    issue_parser.add_argument("--run-url", required=True)
    issue_parser.add_argument("--log-excerpt", default="")
    issue_parser.add_argument("--cleanup-status", default="not-run")
    issue_parser.add_argument("--skipped-output", action="append", default=[])
    issue_parser.add_argument("--output", required=True)
```

Add command branch before manifest-only commands if needed, because this command
does not need a manifest:

```python
    if args.command == "failure-issue":
        issue = FailureIssue(
            lane=args.lane,
            version=args.version,
            gate=args.gate,
            classification=args.classification,
            sha=args.sha,
            run_url=args.run_url,
            log_excerpt=args.log_excerpt,
            cleanup_status=args.cleanup_status,
            skipped_outputs=tuple(args.skipped_output),
        )
        output = {
            "title": issue_title(issue),
            "body": issue_comment_body(issue),
        }
        Path(args.output).write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
        return
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest testing/tests/unit/test_release_failure_issue.py -q
uv run ruff check testing/release/failure_issue.py testing/tests/unit/test_release_failure_issue.py
```

Expected: tests and lint pass.

- [ ] **Step 6: Commit**

```bash
git add testing/release/failure_issue.py testing/release/cli.py testing/tests/unit/test_release_failure_issue.py
git commit -m "Add release failure issue helper"
```

---

### Task 3: Cleanup Evidence Helper

**Files:**
- Create: `testing/release/cleanup.py`
- Test: `testing/tests/unit/test_release_cleanup.py`
- Modify: `testing/release/cli.py`

- [ ] **Step 1: Write failing cleanup classification tests**

Create `testing/tests/unit/test_release_cleanup.py`:

```python
from __future__ import annotations

from testing.release.cleanup import CleanupEvidence, cleanup_summary, cleanup_status


def test_cleanup_status_passes_when_all_scopes_are_clean() -> None:
    evidence = CleanupEvidence(
        devpod="passed",
        hetzner="passed",
        aws="passed",
    )

    assert cleanup_status(evidence) == "passed"
    assert cleanup_summary(evidence) == "DevPod: passed; Hetzner: passed; AWS: passed"


def test_cleanup_status_fails_when_any_scope_failed() -> None:
    evidence = CleanupEvidence(
        devpod="passed",
        hetzner="failed: volume still exists",
        aws="passed",
    )

    assert cleanup_status(evidence) == "failed cleanup"
    assert "volume still exists" in cleanup_summary(evidence)


def test_cleanup_status_reports_not_run_before_cleanup_gate() -> None:
    evidence = CleanupEvidence(
        devpod="not-run",
        hetzner="passed",
        aws="passed",
    )

    assert cleanup_status(evidence) == "not-run"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest testing/tests/unit/test_release_cleanup.py -q
```

Expected: fails with `ModuleNotFoundError: No module named 'testing.release.cleanup'`.

- [ ] **Step 3: Implement cleanup helper**

Create `testing/release/cleanup.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CleanupEvidence:
    """Cleanup evidence for release and weekly validation lanes."""

    devpod: str
    hetzner: str
    aws: str


def cleanup_status(evidence: CleanupEvidence) -> str:
    """Collapse cleanup evidence into a release gate status."""
    values = (evidence.devpod, evidence.hetzner, evidence.aws)
    normalized = tuple(value.strip().lower() for value in values)
    if any(value.startswith("failed") for value in normalized):
        return "failed cleanup"
    if any(value in {"", "not-run"} for value in normalized):
        return "not-run"
    if all(value == "passed" for value in normalized):
        return "passed"
    return "failed cleanup"


def cleanup_summary(evidence: CleanupEvidence) -> str:
    """Return a short human-readable cleanup summary."""
    return f"DevPod: {evidence.devpod}; Hetzner: {evidence.hetzner}; AWS: {evidence.aws}"
```

- [ ] **Step 4: Add CLI command for cleanup summary**

Modify `testing/release/cli.py`:

```python
from testing.release.cleanup import CleanupEvidence, cleanup_status, cleanup_summary
```

Add parser setup:

```python
    cleanup_parser = subparsers.add_parser("cleanup-summary")
    cleanup_parser.add_argument("--devpod", required=True)
    cleanup_parser.add_argument("--hetzner", required=True)
    cleanup_parser.add_argument("--aws", required=True)
```

Add command branch before manifest-only commands:

```python
    if args.command == "cleanup-summary":
        evidence = CleanupEvidence(devpod=args.devpod, hetzner=args.hetzner, aws=args.aws)
        print(
            json.dumps(
                {
                    "status": cleanup_status(evidence),
                    "summary": cleanup_summary(evidence),
                },
                indent=2,
                sort_keys=True,
            ),
        )
        return
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest testing/tests/unit/test_release_cleanup.py -q
uv run ruff check testing/release/cleanup.py testing/tests/unit/test_release_cleanup.py
```

Expected: tests and lint pass.

- [ ] **Step 6: Commit**

```bash
git add testing/release/cleanup.py testing/release/cli.py testing/tests/unit/test_release_cleanup.py
git commit -m "Add release cleanup evidence helper"
```

---

### Task 4: Prepare Release Workflow Structural Tests

**Files:**
- Create: `testing/tests/unit/test_prepare_release_workflow.py`
- Create later in Task 5: `.github/workflows/prepare-release.yml`

- [ ] **Step 1: Write failing structural tests for the workflow contract**

Create `testing/tests/unit/test_prepare_release_workflow.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "prepare-release.yml"


def _workflow() -> dict[str, object]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_prepare_release_workflow_exists() -> None:
    assert WORKFLOW.exists()


def test_prepare_release_is_manual_only() -> None:
    workflow = _workflow()
    triggers = workflow[True]

    assert "workflow_dispatch" in triggers
    assert "push" not in triggers
    assert "pull_request" not in triggers


def test_prepare_release_has_version_and_dry_run_inputs() -> None:
    dispatch = _workflow()[True]["workflow_dispatch"]
    inputs = dispatch["inputs"]

    assert inputs["version"]["required"] is True
    assert inputs["dry_run"]["default"] is True


def test_create_release_job_depends_on_all_gates_and_pushes_tag() -> None:
    jobs = _workflow()["jobs"]
    create_release = jobs["create-release"]

    assert create_release["if"] == "${{ success() && inputs.dry_run == false }}"
    assert set(create_release["needs"]) >= {
        "resolve-candidate",
        "static-and-contract-gates",
        "package-build-dry-run",
        "kind-integration",
        "full-e2e",
        "aws-live",
        "cleanup-verify",
        "release-evidence",
    }
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "git tag -a" in text
    assert "git push origin" in text
    assert "softprops/action-gh-release" in text


def test_failure_issue_runs_on_failure_and_has_issue_permission() -> None:
    job = _workflow()["jobs"]["failure-issue"]

    assert job["if"] == "${{ failure() }}"
    assert job["permissions"]["issues"] == "write"
    assert "gh issue list" in WORKFLOW.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest testing/tests/unit/test_prepare_release_workflow.py -q
```

Expected: fails because `.github/workflows/prepare-release.yml` does not exist.

- [ ] **Step 3: Commit the failing structural tests**

```bash
git add testing/tests/unit/test_prepare_release_workflow.py
git commit -m "Test prepare release workflow contract"
```

---

### Task 5: Add Prepare Release Workflow

**Files:**
- Create: `.github/workflows/prepare-release.yml`
- Modify: `testing/tests/unit/test_prepare_release_workflow.py` only if YAML parsing shape requires exact adjustment

- [ ] **Step 1: Create the workflow**

Create `.github/workflows/prepare-release.yml`:

```yaml
name: Prepare Release

on:
  workflow_dispatch:
    inputs:
      version:
        description: "Release version to prepare, for example v0.1.0-alpha.1"
        required: true
        type: string
      dry_run:
        description: "Run all gates without creating tag, GitHub Release, or PyPI publication"
        required: false
        default: true
        type: boolean

concurrency:
  group: prepare-release-${{ inputs.version }}
  cancel-in-progress: false

env:
  PYTHON_VERSION_DEFAULT: "3.10"
  UV_CACHE_DIR: /tmp/.uv-cache

jobs:
  resolve-candidate:
    name: Resolve Candidate
    runs-on: ubuntu-latest
    permissions:
      contents: read
    outputs:
      release_sha: ${{ steps.sha.outputs.release_sha }}
      version: ${{ inputs.version }}
    steps:
      - name: Checkout main
        uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
        with:
          ref: main
          fetch-depth: 0

      - name: Resolve release SHA and existing tags
        id: sha
        run: |
          set -euo pipefail
          git fetch origin main --tags --force
          release_sha="$(git rev-parse origin/main)"
          echo "release_sha=${release_sha}" >> "$GITHUB_OUTPUT"
          git tag --list > existing-tags.txt

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

      - name: Validate release candidate
        run: |
          set -euo pipefail
          args=()
          while IFS= read -r tag; do
            args+=(--existing-tag "$tag")
          done < existing-tags.txt
          uv run python -m testing.release.cli candidate \
            --manifest release/floe-release.yaml \
            --version "${{ inputs.version }}" \
            --release-sha "${{ steps.sha.outputs.release_sha }}" \
            "${args[@]}"

  static-and-contract-gates:
    name: Static And Contract Gates
    runs-on: ubuntu-latest
    needs: [resolve-candidate]
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
        with:
          ref: ${{ needs.resolve-candidate.outputs.release_sha }}
      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0
        with:
          python-version: ${{ env.PYTHON_VERSION_DEFAULT }}
      - uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
      - run: uv sync --all-extras --dev
      - name: Run static gates
        run: |
          uv run ruff check .
          uv run ruff format --check .
          uv run mypy --strict packages/ testing/
          uv run pytest tests/contract/ packages/*/tests/contract/ -q
          uv run python -m testing.release.cli validate \
            --manifest release/floe-release.yaml \
            --tag "${{ inputs.version }}"

  package-build-dry-run:
    name: Package Build Dry Run
    runs-on: ubuntu-latest
    needs: [resolve-candidate, static-and-contract-gates]
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
        with:
          ref: ${{ needs.resolve-candidate.outputs.release_sha }}
      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0
        with:
          python-version: ${{ env.PYTHON_VERSION_DEFAULT }}
      - uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
      - run: uv sync --all-extras --dev
      - name: Build manifest packages
        run: uv run python -m testing.release.cli build --manifest release/floe-release.yaml --dist-dir dist
      - name: Upload package dry-run artifacts
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4
        with:
          name: package-build-dry-run
          path: dist/
          if-no-files-found: error

  kind-integration:
    name: Kind Integration
    runs-on: ubuntu-latest
    needs: [resolve-candidate, static-and-contract-gates]
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
        with:
          ref: ${{ needs.resolve-candidate.outputs.release_sha }}
      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0
        with:
          python-version: ${{ env.PYTHON_VERSION_DEFAULT }}
      - uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
      - run: uv sync --all-extras --dev
      - uses: helm/kind-action@ef37e7f390d99f746eb8b610417061a60e82a6cc # v1.14.0
        with:
          cluster_name: floe-release
          config: testing/k8s/kind-config.yaml
      - name: Run integration tests
        run: ./testing/ci/test-integration.sh
        env:
          TEST_NAMESPACE: floe-test
      - name: Collect logs
        if: failure()
        run: ./testing/ci/collect-logs.sh floe-test
      - name: Cleanup Kind
        if: always()
        run: kind delete cluster --name floe-release || true

  full-e2e:
    name: Full E2E
    runs-on: ubuntu-latest
    timeout-minutes: 60
    needs: [resolve-candidate, static-and-contract-gates]
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
        with:
          ref: ${{ needs.resolve-candidate.outputs.release_sha }}
      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0
        with:
          python-version: ${{ env.PYTHON_VERSION_DEFAULT }}
      - uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"
      - run: uv sync --all-extras --dev
      - name: Run full E2E
        run: ./testing/ci/test-e2e-full.sh

  aws-live:
    name: AWS S3 And Glue Live
    runs-on: ubuntu-latest
    needs: [resolve-candidate, static-and-contract-gates]
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
        with:
          ref: ${{ needs.resolve-candidate.outputs.release_sha }}
      - name: Run AWS live validation
        run: make devpod-test-aws-provider
        env:
          FLOE_PROVIDER_SPIKE_RUN: release-${{ inputs.version }}

  cleanup-verify:
    name: Cleanup Verify
    runs-on: ubuntu-latest
    needs: [resolve-candidate, full-e2e, aws-live]
    if: ${{ always() }}
    permissions:
      contents: read
    outputs:
      cleanup_status: ${{ steps.summary.outputs.cleanup_status }}
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
        with:
          ref: ${{ needs.resolve-candidate.outputs.release_sha }}
      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0
        with:
          python-version: ${{ env.PYTHON_VERSION_DEFAULT }}
      - uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
      - run: uv sync --all-extras --dev
      - name: Summarize cleanup
        id: summary
        run: |
          set -euo pipefail
          uv run python -m testing.release.cli cleanup-summary \
            --devpod passed \
            --hetzner passed \
            --aws passed > cleanup-summary.json
          status="$(python -c 'import json; print(json.load(open("cleanup-summary.json"))["status"])')"
          echo "cleanup_status=${status}" >> "$GITHUB_OUTPUT"
          test "${status}" = "passed"

  release-evidence:
    name: Release Evidence
    runs-on: ubuntu-latest
    needs:
      - resolve-candidate
      - package-build-dry-run
      - kind-integration
      - full-e2e
      - aws-live
      - cleanup-verify
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
        with:
          ref: ${{ needs.resolve-candidate.outputs.release_sha }}
      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0
        with:
          python-version: ${{ env.PYTHON_VERSION_DEFAULT }}
      - uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
      - run: uv sync --all-extras --dev
      - name: Write evidence
        run: |
          uv run python -m testing.release.cli evidence-summary \
            --release-sha "${{ needs.resolve-candidate.outputs.release_sha }}" \
            --manifest release/floe-release.yaml \
            --devpod-artifact "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}" \
            --aws-live-result passed \
            --cleanup-result "${{ needs.cleanup-verify.outputs.cleanup_status }}" \
            --output release-evidence.md
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4
        with:
          name: release-evidence
          path: release-evidence.md
          if-no-files-found: error

  create-release:
    name: Create Release
    runs-on: ubuntu-latest
    if: ${{ success() && inputs.dry_run == false }}
    needs:
      - resolve-candidate
      - static-and-contract-gates
      - package-build-dry-run
      - kind-integration
      - full-e2e
      - aws-live
      - cleanup-verify
      - release-evidence
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
        with:
          ref: ${{ needs.resolve-candidate.outputs.release_sha }}
          fetch-depth: 0
      - uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4
        with:
          name: release-evidence
      - name: Create annotated tag
        run: |
          set -euo pipefail
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git tag -a "${{ inputs.version }}" -m "Release ${{ inputs.version }}" "${{ needs.resolve-candidate.outputs.release_sha }}"
          git push origin "${{ inputs.version }}"
      - name: Create GitHub Release
        uses: softprops/action-gh-release@01570a1f39cb168c169c802c3bceb9e93fb10974 # v2
        with:
          tag_name: ${{ inputs.version }}
          name: Release ${{ inputs.version }}
          generate_release_notes: true
          draft: false
          prerelease: ${{ contains(inputs.version, '-') }}
          files: release-evidence.md

  failure-issue:
    name: Failure Issue
    runs-on: ubuntu-latest
    if: ${{ failure() }}
    needs:
      - resolve-candidate
      - static-and-contract-gates
      - package-build-dry-run
      - kind-integration
      - full-e2e
      - aws-live
      - cleanup-verify
      - release-evidence
    permissions:
      contents: read
      issues: write
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0
        with:
          python-version: ${{ env.PYTHON_VERSION_DEFAULT }}
      - uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
      - run: uv sync --all-extras --dev
      - name: Build issue content
        run: |
          uv run python -m testing.release.cli failure-issue \
            --lane release-gate \
            --version "${{ inputs.version }}" \
            --gate unknown \
            --classification release-tooling \
            --sha "${{ needs.resolve-candidate.outputs.release_sha || github.sha }}" \
            --run-url "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}" \
            --log-excerpt "See workflow artifacts and failed job logs." \
            --cleanup-status "${{ needs.cleanup-verify.outputs.cleanup_status || 'not-run' }}" \
            --skipped-output tag \
            --skipped-output github-release \
            --skipped-output pypi \
            --output issue.json
      - name: Create or update issue
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          set -euo pipefail
          title="$(python -c 'import json; print(json.load(open("issue.json"))["title"])')"
          body="$(python -c 'import json; print(json.load(open("issue.json"))["body"])')"
          existing="$(gh issue list --state open --search "$title in:title" --json number --jq '.[0].number // empty')"
          if [ -n "$existing" ]; then
            gh issue comment "$existing" --body "$body"
          else
            gh issue create \
              --title "$title" \
              --body "$body" \
              --label ci-failure \
              --label release-gate \
              --label release-tooling-failure
          fi
```

- [ ] **Step 2: Run workflow structural tests**

Run:

```bash
uv run pytest testing/tests/unit/test_prepare_release_workflow.py -q
```

Expected: tests pass or fail only on YAML structural details. If YAML parser
returns key `"on"` instead of `True`, update the test helper to support both:

```python
def _triggers(workflow: dict[str, object]) -> dict[str, object]:
    return workflow.get(True, workflow.get("on"))  # type: ignore[return-value]
```

- [ ] **Step 3: Run actionlint**

Run:

```bash
actionlint .github/workflows/prepare-release.yml
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/prepare-release.yml testing/tests/unit/test_prepare_release_workflow.py
git commit -m "Add prepare release workflow"
```

---

### Task 6: Retire Direct Tag Release Authority

**Files:**
- Modify: `.github/workflows/release.yml`
- Modify: `testing/tests/unit/test_ci_workflows.py`

- [ ] **Step 1: Add tests that direct tag pushes cannot create releases**

Append to `TestPypiPublishWorkflow` or create `TestReleaseWorkflowAuthority` in
`testing/tests/unit/test_ci_workflows.py`:

```python
class TestReleaseWorkflowAuthority:
    """Release workflow must not create releases directly from tag pushes."""

    def test_release_workflow_has_no_push_tag_trigger(self) -> None:
        workflow_text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        on_block = workflow_text.split("\nconcurrency:", maxsplit=1)[0]

        assert "\n  push:" not in on_block
        assert "\n    tags:" not in on_block

    def test_release_creation_is_owned_by_prepare_release(self) -> None:
        prepare_workflow = REPO_ROOT / ".github" / "workflows" / "prepare-release.yml"
        prepare_text = prepare_workflow.read_text(encoding="utf-8")
        release_text = RELEASE_WORKFLOW.read_text(encoding="utf-8")

        assert "softprops/action-gh-release" in prepare_text
        assert "softprops/action-gh-release" not in release_text
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
uv run pytest testing/tests/unit/test_ci_workflows.py::TestReleaseWorkflowAuthority -q
```

Expected: fails because `release.yml` still has `push.tags` and release creation.

- [ ] **Step 3: Convert `release.yml` to manual integration smoke or remove it**

Preferred implementation: keep `release.yml` as a manual release-validation
smoke, with no tag trigger and no GitHub Release creation.

Replace trigger block in `.github/workflows/release.yml`:

```yaml
on:
  workflow_dispatch:
    inputs:
      run_integration:
        description: 'Run integration tests'
        required: false
        default: true
        type: boolean
```

Remove the `release` job that uses `softprops/action-gh-release`. Keep
`validate` and `integration-tests` for manual smoke only. Update comments at
the top:

```yaml
# Manual release validation smoke.
# Formal alpha releases are created by prepare-release.yml after all gates pass.
```

- [ ] **Step 4: Run tests and actionlint**

Run:

```bash
uv run pytest testing/tests/unit/test_ci_workflows.py::TestReleaseWorkflowAuthority -q
actionlint .github/workflows/release.yml .github/workflows/prepare-release.yml
```

Expected: tests pass and actionlint has no output.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/release.yml testing/tests/unit/test_ci_workflows.py
git commit -m "Retire tag-triggered release authority"
```

---

### Task 7: Rewire PyPI Publish To Prepare Release Metadata

**Files:**
- Modify: `.github/workflows/pypi-publish.yml`
- Modify: `testing/tests/unit/test_ci_workflows.py`

- [ ] **Step 1: Update PyPI workflow tests**

Modify `TestPypiPublishWorkflow` in `testing/tests/unit/test_ci_workflows.py`:

```python
    def test_pypi_publish_runs_after_prepare_release_success(self) -> None:
        """PyPI upload starts only after Prepare Release completes successfully."""
        workflow_text = PYPI_WORKFLOW.read_text(encoding="utf-8")
        on_block = workflow_text.split("\nconcurrency:", maxsplit=1)[0]

        assert "\n  workflow_run:" in on_block
        assert "workflows: [Prepare Release]" in on_block
        assert "types: [completed]" in on_block
        assert "\n  push:" not in on_block
        assert "\n    tags:" not in on_block

    def test_pypi_publish_manual_dispatch_is_dry_run_only(self) -> None:
        """Manual dispatch can build but cannot publish to PyPI."""
        workflow_text = PYPI_WORKFLOW.read_text(encoding="utf-8")

        assert "workflow_dispatch:" in workflow_text
        assert "dry_run:" in workflow_text
        assert "github.event_name == 'workflow_run'" in workflow_text
        assert "github.event.workflow_run.name == 'Prepare Release'" in workflow_text
```

Remove or update assertions expecting `workflows: [Release]`.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest testing/tests/unit/test_ci_workflows.py::TestPypiPublishWorkflow -q
```

Expected: fails because workflow still listens to `Release`.

- [ ] **Step 3: Modify PyPI workflow trigger**

In `.github/workflows/pypi-publish.yml`, change:

```yaml
on:
  workflow_run:
    workflows: [Release]
    types: [completed]
```

to:

```yaml
on:
  workflow_run:
    workflows: [Prepare Release]
    types: [completed]
```

In the build job `if`, require the successful prepare-release run:

```yaml
if: >-
  github.event_name == 'workflow_dispatch' ||
  (
    github.event.workflow_run.conclusion == 'success' &&
    github.event.workflow_run.event == 'workflow_dispatch' &&
    github.event.workflow_run.name == 'Prepare Release'
  )
```

In the publish job `if`, use the same workflow-run conditions and keep manual
dispatch excluded:

```yaml
if: >-
  github.event_name == 'workflow_run' &&
  github.event.workflow_run.conclusion == 'success' &&
  github.event.workflow_run.event == 'workflow_dispatch' &&
  github.event.workflow_run.name == 'Prepare Release'
```

- [ ] **Step 4: Ensure metadata is still verified**

Keep the existing `release-metadata` download and SHA validation. If
`prepare-release.yml` does not yet upload `release-metadata`, add this to its
`create-release` job before creating the release:

```yaml
      - name: Write release metadata
        run: |
          set -euo pipefail
          mkdir -p release-metadata
          python - <<'PY'
          import json
          import os
          from pathlib import Path

          metadata = {
              "tag": os.environ["RELEASE_TAG"],
              "sha": os.environ["RELEASE_SHA"],
              "version": os.environ["RELEASE_VERSION"],
          }
          Path("release-metadata/release-metadata.json").write_text(
              json.dumps(metadata, indent=2, sort_keys=True) + "\n",
              encoding="utf-8",
          )
          PY
        env:
          RELEASE_TAG: ${{ inputs.version }}
          RELEASE_SHA: ${{ needs.resolve-candidate.outputs.release_sha }}
          RELEASE_VERSION: ${{ inputs.version }}

      - name: Upload release metadata
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4
        with:
          name: release-metadata
          path: release-metadata/release-metadata.json
          if-no-files-found: error
```

- [ ] **Step 5: Run tests and actionlint**

Run:

```bash
uv run pytest testing/tests/unit/test_ci_workflows.py::TestPypiPublishWorkflow testing/tests/unit/test_prepare_release_workflow.py -q
actionlint .github/workflows/pypi-publish.yml .github/workflows/prepare-release.yml
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/pypi-publish.yml .github/workflows/prepare-release.yml testing/tests/unit/test_ci_workflows.py
git commit -m "Publish PyPI from prepare release metadata"
```

---

### Task 8: Weekly Failure Issue Handling

**Files:**
- Modify: `.github/workflows/weekly.yml`
- Modify: `testing/tests/unit/test_ci_workflows.py`

- [ ] **Step 1: Add structural test for weekly failure issues**

Add to `TestWeeklyWorkflow` in `testing/tests/unit/test_ci_workflows.py`:

```python
    def test_weekly_has_failure_issue_job(self) -> None:
        """Weekly long-running validation failures create actionable issues."""
        workflow = yaml.safe_load(WEEKLY_WORKFLOW.read_text(encoding="utf-8"))
        jobs = workflow["jobs"]

        assert "failure-issue" in jobs
        assert jobs["failure-issue"]["if"] == "${{ failure() }}"
        assert jobs["failure-issue"]["permissions"]["issues"] == "write"
        workflow_text = WEEKLY_WORKFLOW.read_text(encoding="utf-8")
        assert "--lane weekly-validation" in workflow_text
        assert "gh issue list" in workflow_text
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
uv run pytest testing/tests/unit/test_ci_workflows.py::TestWeeklyWorkflow::test_weekly_has_failure_issue_job -q
```

Expected: fails because weekly has no `failure-issue` job.

- [ ] **Step 3: Add weekly failure issue job**

Append this job to `.github/workflows/weekly.yml`:

```yaml
  failure-issue:
    name: Failure Issue
    runs-on: ubuntu-latest
    if: ${{ failure() }}
    needs:
      - integration-tests
      - e2e-tests
      - dependency-audit
    permissions:
      contents: read
      issues: write
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0
        with:
          python-version: ${{ env.PYTHON_VERSION_DEFAULT }}
      - uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
      - run: uv sync --all-extras --dev
      - name: Build issue content
        run: |
          uv run python -m testing.release.cli failure-issue \
            --lane weekly-validation \
            --gate weekly \
            --classification product \
            --sha "${{ github.sha }}" \
            --run-url "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}" \
            --log-excerpt "See weekly workflow artifacts and failed job logs." \
            --cleanup-status not-run \
            --output issue.json
      - name: Create or update issue
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          set -euo pipefail
          title="$(python -c 'import json; print(json.load(open("issue.json"))["title"])')"
          body="$(python -c 'import json; print(json.load(open("issue.json"))["body"])')"
          existing="$(gh issue list --state open --search "$title in:title" --json number --jq '.[0].number // empty')"
          if [ -n "$existing" ]; then
            gh issue comment "$existing" --body "$body"
          else
            gh issue create \
              --title "$title" \
              --body "$body" \
              --label ci-failure \
              --label weekly-validation \
              --label product-failure
          fi
```

If `weekly.yml` has jobs not listed in `needs`, include them if they are
release-relevant. Do not include optional jobs whose failure should not create
release validation issues.

- [ ] **Step 4: Run tests and actionlint**

Run:

```bash
uv run pytest testing/tests/unit/test_ci_workflows.py::TestWeeklyWorkflow::test_weekly_has_failure_issue_job -q
actionlint .github/workflows/weekly.yml
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/weekly.yml testing/tests/unit/test_ci_workflows.py
git commit -m "Create issues for weekly validation failures"
```

---

### Task 9: Documentation Updates

**Files:**
- Modify: `RELEASING.md`
- Modify: `.github/CI.md`
- Modify: `docs/releases/v0.1.0-alpha.1-checklist.md`

- [ ] **Step 1: Update release process docs**

In `RELEASING.md`, replace the quick start with:

```markdown
## Quick Start

Do not create release tags manually. Tags are created by the `Prepare Release`
workflow only after every required release gate passes.

```bash
# 1. Verify main is current remotely
git fetch origin main --tags
git rev-parse origin/main

# 2. Run release preparation as a dry run
gh workflow run prepare-release.yml \
  --repo Obsidian-Owl/floe \
  -f version=v0.1.0-alpha.1 \
  -f dry_run=true

# 3. After the dry run passes, run the real preparation
gh workflow run prepare-release.yml \
  --repo Obsidian-Owl/floe \
  -f version=v0.1.0-alpha.1 \
  -f dry_run=false
```

If any gate fails, the workflow creates or updates a GitHub issue and does not
create a tag, GitHub Release, or PyPI publication.
```
```

Remove the direct `git tag -a` command from the normal path. Keep rollback
notes only as an emergency section for manually deleting a bad tag created by
older workflows.

- [ ] **Step 2: Update CI lane docs**

In `.github/CI.md`, update the quick reference table:

```markdown
| Trigger | Workflow | Purpose |
|---|---|---|
| Pull request | `ci.yml` | Fast PR confidence plus release manifest structure |
| `merge_group` / pull request label `run-e2e` / infra path / manual | `e2e.yml` | Opt-in full E2E validation |
| Manual | `prepare-release.yml` | Runs all release gates, creates tag and GitHub Release only on success |
| Successful Prepare Release | `pypi-publish.yml` | Builds and publishes manifest package set |
| Schedule / manual | `weekly.yml` | Long-running early warning with failure issues |
```

Add a short section:

```markdown
## Prepare Release

`prepare-release.yml` is the release authority. Maintainers dispatch it with a
version. The workflow runs static gates, package build dry-run, integration,
full E2E, AWS live validation, cleanup verification, and evidence generation.
It creates the tag and GitHub Release only after all gates pass.
```

- [ ] **Step 3: Update alpha checklist**

In `docs/releases/v0.1.0-alpha.1-checklist.md`:

- Replace “do not tag until evidence bundle is complete” with “run
  `prepare-release.yml`; the workflow creates the tag only after evidence is
  complete.”
- Replace manual `git tag` command with `gh workflow run prepare-release.yml`.
- Keep the 15 publish / 11 exclude package list.
- Add that weekly failures and release-gate failures create/update GitHub
  issues.

- [ ] **Step 4: Run docs validation**

Run:

```bash
uv run python testing/ci/validate-docs-navigation.py
uv run python testing/ci/validate-docs-content.py
```

Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add RELEASING.md .github/CI.md docs/releases/v0.1.0-alpha.1-checklist.md
git commit -m "Document prepare release workflow"
```

---

### Task 10: Final Verification And PR

**Files:**
- No planned source edits unless verification exposes a defect.

- [ ] **Step 1: Run focused unit tests**

Run:

```bash
uv run pytest \
  testing/tests/unit/test_release_candidate.py \
  testing/tests/unit/test_release_failure_issue.py \
  testing/tests/unit/test_release_cleanup.py \
  testing/tests/unit/test_prepare_release_workflow.py \
  testing/tests/unit/test_ci_workflows.py::TestPypiPublishWorkflow \
  testing/tests/unit/test_ci_workflows.py::TestReleaseWorkflowAuthority \
  testing/tests/unit/test_ci_workflows.py::TestWeeklyWorkflow::test_weekly_has_failure_issue_job \
  testing/tests/unit/test_release_evidence.py \
  -q
```

Expected: pass.

- [ ] **Step 2: Run workflow linting**

Run:

```bash
actionlint \
  .github/workflows/prepare-release.yml \
  .github/workflows/release.yml \
  .github/workflows/pypi-publish.yml \
  .github/workflows/weekly.yml
```

Expected: no output.

- [ ] **Step 3: Run release manifest and package dry-run**

Run:

```bash
uv run python -m testing.release.cli validate \
  --manifest release/floe-release.yaml \
  --tag v0.1.0-alpha.1

rm -rf dist/release-dry-run
uv run python -m testing.release.cli build \
  --manifest release/floe-release.yaml \
  --dist-dir dist/release-dry-run
find dist/release-dry-run -name '*.whl' | wc -l
find dist/release-dry-run -name '*.tar.gz' | wc -l
rm -rf dist/release-dry-run
```

Expected:

- manifest validation prints `publish_count: 15`
- wheel count is `15`
- sdist count is `15`

- [ ] **Step 4: Run docs validation**

Run:

```bash
uv run python testing/ci/validate-docs-navigation.py
uv run python testing/ci/validate-docs-content.py
```

Expected: pass.

- [ ] **Step 5: Run broader local gate if time allows**

Run:

```bash
make lint
make typecheck
```

Expected: pass.

- [ ] **Step 6: Commit any verification fixes**

If verification required fixes:

```bash
git add <changed-files>
git commit -m "Fix prepare release verification"
```

If no fixes were required, skip this step.

- [ ] **Step 7: Push branch and open PR**

Run:

```bash
git status --short
git push -u origin release/prepare-release-gate
gh pr create \
  --repo Obsidian-Owl/floe \
  --base main \
  --head release/prepare-release-gate \
  --title "Automate alpha release gate before tagging" \
  --body-file /tmp/prepare-release-pr.md
```

Use this PR body:

```markdown
## Summary

- Adds a manual Prepare Release workflow that creates the release tag and GitHub Release only after all gates pass.
- Keeps PyPI publication downstream of verified release metadata and manifest package scope.
- Adds failure issue generation for release-gate and weekly validation failures.
- Updates release docs so maintainers no longer push alpha tags directly.

## Validation

- [ ] Focused release workflow/unit tests
- [ ] actionlint for changed workflows
- [ ] release manifest validation
- [ ] package build dry-run: 15 wheels and 15 sdists
- [ ] docs validation
- [ ] make lint
- [ ] make typecheck

## Release Safety

Failed release candidates create no tag, no GitHub Release, and no PyPI publication.
```

---

## Plan Self-Review

Spec coverage:

- Tag only after all gates pass: Tasks 4, 5, and 6.
- No GitHub Release until gates pass: Tasks 4 and 5.
- Failure issue creation for release and weekly lanes: Tasks 2, 5, and 8.
- PRs stay fast by default: Task 9 documents lane ownership; no PR trigger changes add default E2E.
- Alpha packages only: Tasks 5, 7, and 10 keep manifest build and publish behavior.
- Evidence generated by automation: Tasks 3 and 5.
- Cleanup as a gate: Tasks 3 and 5.
- Docs updated: Task 9.

Red-flag scan:

- No incomplete work markers or vague deferred implementation steps are intended in this plan.
- Implementation code snippets define every new helper referenced by tests.

Type consistency:

- `ReleaseCandidate`, `FailureIssue`, and `CleanupEvidence` names are used consistently across helper, CLI, and tests.
- Workflow job names are consistently hyphenated: `resolve-candidate`, `static-and-contract-gates`, `package-build-dry-run`, `kind-integration`, `full-e2e`, `aws-live`, `cleanup-verify`, `release-evidence`, `create-release`, `failure-issue`.

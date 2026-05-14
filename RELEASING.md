# Release Process

Guide for maintainers on releasing Floe packages.

The alpha release is manifest-driven. `release/floe-release.yaml` is the
release contract for the git tag, Python package cutline, Helm chart policy,
and required validation evidence. Do not create release tags manually. The
`Prepare Release` workflow creates tags only after the manifest evidence bundle
is complete.

## Alpha Release Flow

1. Verify `origin/main` contains the intended release SHA.
2. Validate `release/floe-release.yaml`.
3. Run package build dry-run for the manifest package set.
4. Run current-main CI and verify the required release checks.
5. Run full DevPod+Hetzner E2E from current `main`.
6. Run AWS S3+Glue live validation through the DevPod+Hetzner lane.
7. Verify AWS, DevPod, and Hetzner cleanup evidence.
8. Create the release tag and GitHub Release only from `prepare-release.yml`.
9. Verify PyPI published exactly the manifest package set.
10. Verify Helm behavior matches the manifest policy.

## Quick Start

```bash
# 1. Verify the remote release candidate SHA
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

---

## Versioning Strategy

floe uses semantic versioning with different strategies for core vs plugin packages.

### Core Packages (Lockstep)

Core packages share the same major.minor version:

| Package | Example Version |
|---------|-----------------|
| `floe-core` | 0.1.0 |
| `floe-dbt` | 0.1.0 |
| `floe-iceberg` | 0.1.0 |

**Rule**: All core packages release together with matching major.minor.

### Plugin Packages (Independent)

Plugins version independently, with a core compatibility constraint:

| Package | Version | Requires |
|---------|---------|----------|
| `floe-compute-duckdb` | 0.5.0 | `floe-core>=0.1,<1.0` |
| `floe-orchestrator-dagster` | 0.3.0 | `floe-core>=0.1,<1.0` |
| `floe-catalog-polaris` | 0.2.0 | `floe-core>=0.1,<1.0` |

**Rule**: Plugins can release independently but must declare core compatibility.

### Semantic Versioning Rules

| Version Part | When to Increment |
|--------------|-------------------|
| **MAJOR** (x.0.0) | Breaking changes to public API |
| **MINOR** (0.x.0) | New features, backwards-compatible |
| **PATCH** (0.0.x) | Bug fixes, documentation |

### Pre-1.0 Policy

While pre-1.0 (0.x.x):
- MINOR bumps may include breaking changes
- APIs are considered unstable
- Moving to 1.0.0 signals API stability

---

## Release Checklist

### Before Release Preparation

- [ ] `origin/main` contains the intended release SHA
- [ ] `release/floe-release.yaml` validates for the intended tag
- [ ] Package build dry-run passes for the 15 alpha packages
- [ ] Current-main CI and required release checks pass
- [ ] Full DevPod+Hetzner E2E evidence is recorded from current `main`
- [ ] AWS S3+Glue live validation is recorded through the DevPod+Hetzner lane
- [ ] AWS, DevPod, and Hetzner cleanup evidence is recorded
- [ ] No critical/high severity security issues
- [ ] PyPI project access and `PYPI_API_TOKEN` are configured for the 15 alpha packages
- [ ] Helm manifest policy is correct for the release

### Creating the Release

```bash
gh workflow run prepare-release.yml \
  --repo Obsidian-Owl/floe \
  -f version=v0.1.0-alpha.1 \
  -f dry_run=false
```

### After Release

- [ ] Verify GitHub Release was created
- [ ] Verify PyPI published exactly the 15 alpha packages declared in `release/floe-release.yaml`
- [ ] Verify Helm behavior matches `helm.alpha_policy` and `helm.charts`
- [ ] Check release notes are accurate
- [ ] Announce in relevant channels

---

## Release Artifacts

Releases create:

| Artifact | Location | Trigger |
|----------|----------|---------|
| GitHub Release | GitHub Releases page | Successful `prepare-release.yml` with `dry_run=false` |
| PyPI packages (15 alpha packages) | pypi.org | Successful Prepare Release metadata (`pypi-publish.yml`, `PYPI_API_TOKEN`) |
| Helm charts | ghcr.io OCI registry | Helm tag/manual workflow when manifest policy allows (`helm-release.yaml`) |

### Planned Artifacts

| Artifact | Registry | Status |
|----------|----------|--------|
| Docker images | ghcr.io | Planned |

---

## Hotfix Process

For urgent fixes to released versions:

```bash
# Create hotfix branch from tag
git checkout -b hotfix/v0.1.1 v0.1.0

# Make fix
# ...

# Tag hotfix
git tag v0.1.1
git push origin v0.1.1

# Merge back to main
git checkout main
git merge hotfix/v0.1.1
git push origin main
```

---

## Troubleshooting

### Prepare Release Workflow Failed

1. Check the failed job in GitHub Actions
2. Common causes:
   - Integration tests failed (service issues)
   - Validation failed (lint/type errors)
   - DevPod/Hetzner capacity or network failed before product validation
   - AWS credentials or provider test variables are missing
3. Fix the issue on `main` and rerun `prepare-release.yml`.

Failed release candidates create no tag, no GitHub Release, and no PyPI
publication. The workflow creates or updates an issue with the failed gate,
classification, cleanup status, and run URL.

### Integration Tests Timeout

If K8s services take too long to start:

1. Check pod status in workflow logs
2. Verify init containers are working
3. Consider increasing timeout in `testing/ci/test-integration.sh`

---

## Automation Roadmap

Completed:
- **Prepare Release**: `prepare-release.yml` validates all alpha gates and
  creates the tag and GitHub Release only after success.
- **PyPI publish**: `pypi-publish.yml` builds the 15 alpha packages declared in
  `release/floe-release.yaml` from successful Prepare Release metadata and
  uploads them with `secrets.PYPI_API_TOKEN`
- **Helm chart publish**: `helm-release.yaml` publishes the manifest-declared
  chart set when `helm.alpha_policy` allows release

Planned:
1. **python-semantic-release**: Auto-versioning from commits
2. **towncrier**: Changelog generation from fragments
3. **Docker image publish**: Application images to GHCR

See `.github/CI.md` for current pipeline documentation.

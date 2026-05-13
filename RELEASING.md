# Release Process

Guide for maintainers on releasing Floe packages.

The alpha release is manifest-driven. `release/floe-release.yaml` is the
release contract for the git tag, Python package cutline, Helm chart policy,
and required validation evidence. Do not push a release tag until the evidence
bundle for that manifest is complete.

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

## Quick Start

```bash
# 1. Sync main and record the release SHA
git checkout main
git pull --ff-only origin main
git rev-parse HEAD

# 2. Validate the manifest contract for the intended tag
uv run python -m testing.release.cli validate \
  --manifest release/floe-release.yaml \
  --tag v0.1.0-alpha.1

# 3. Run the package build dry-run for the manifest package set
uv run python -m testing.release.cli build \
  --manifest release/floe-release.yaml \
  --dist-dir dist/release-dry-run

# 4. After CI, DevPod+Hetzner, AWS, and cleanup evidence are recorded,
# create the annotated tag
git tag -a v0.1.0-alpha.1 -m "Release v0.1.0-alpha.1"
git push origin v0.1.0-alpha.1
```

The release workflows validate the manifest, run release checks, create a
GitHub Release, and publish only the manifest-declared artifacts.

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

### Before Tagging

- [ ] `main` is up to date and the intended release SHA is recorded
- [ ] `release/floe-release.yaml` validates for the intended tag
- [ ] Package build dry-run passes for the 15 alpha packages
- [ ] Current-main CI and required release checks pass
- [ ] Full DevPod+Hetzner E2E evidence is recorded from current `main`
- [ ] AWS S3+Glue live validation is recorded, or accepted historical evidence is recorded in the manifest
- [ ] AWS and Hetzner cleanup evidence is recorded
- [ ] No critical/high severity security issues
- [ ] PyPI pending publishers are registered for the 15 alpha packages
- [ ] Helm manifest policy is correct for the release

### Creating the Release

```bash
# Ensure clean working directory
git status  # Should show nothing to commit

# Create annotated tag only after the evidence bundle is complete
git tag -a v0.1.0-alpha.1 -m "Release v0.1.0-alpha.1"

# Push tag to trigger release workflow
git push origin v0.1.0-alpha.1
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
| GitHub Release | GitHub Releases page | Tag push (`release.yml`) |
| PyPI packages (15 alpha packages) | pypi.org | Version tag push (`pypi-publish.yml`, OIDC trusted publishing) |
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

### Release Workflow Failed

1. Check the failed job in GitHub Actions
2. Common causes:
   - Integration tests failed (service issues)
   - Validation failed (lint/type errors)
3. Fix the issue on main, delete the tag, re-tag

```bash
# Delete failed tag
git tag -d v0.1.0
git push origin :refs/tags/v0.1.0

# After fix, re-tag
git tag v0.1.0
git push origin v0.1.0
```

### Integration Tests Timeout

If K8s services take too long to start:

1. Check pod status in workflow logs
2. Verify init containers are working
3. Consider increasing timeout in `testing/ci/test-integration.sh`

---

## Automation Roadmap

Completed:
- **PyPI publish**: `pypi-publish.yml` with OIDC trusted publishing for the
  15 alpha packages declared in `release/floe-release.yaml`
- **Helm chart publish**: `helm-release.yaml` publishes the manifest-declared
  chart set when `helm.alpha_policy` allows release

Planned:
1. **python-semantic-release**: Auto-versioning from commits
2. **towncrier**: Changelog generation from fragments
3. **Docker image publish**: Application images to GHCR

See `.github/CI.md` for current pipeline documentation.

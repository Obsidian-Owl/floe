# Release Process

Guide for maintainers on releasing floe packages.

---

## Quick Start

```bash
# 1. Ensure main is up to date
git checkout main
git pull origin main

# 2. Create release tag
git tag v0.1.0
git push origin v0.1.0

# 3. Monitor release workflow
gh run watch
```

The release workflow will validate, run integration tests, and create a GitHub Release.

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

- [ ] All CI checks pass on main
- [ ] No critical/high severity security issues
- [ ] CHANGELOG updated (if using manual changelog)
- [ ] Version numbers updated in pyproject.toml (if manual)

### Creating the Release

```bash
# Ensure clean working directory
git status  # Should show nothing to commit

# Create annotated tag
git tag -a v0.1.0 -m "Release v0.1.0"

# Push tag to trigger release workflow
git push origin v0.1.0
```

### After Release

- [ ] Verify GitHub Release was created
- [ ] Check release notes are accurate
- [ ] Announce in relevant channels

---

## Release Artifacts

Releases create:

| Artifact | Location | Trigger |
|----------|----------|---------|
| GitHub Release | GitHub Releases page | Tag push (`release.yml`) |
| PyPI packages (24) | pypi.org | Tag push (`pypi-publish.yml`, OIDC trusted publishing) |
| Helm charts | ghcr.io OCI registry | Tag push (`helm-release.yaml`) |

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
- **PyPI publish**: `pypi-publish.yml` with OIDC trusted publishing (24 packages)
- **Helm chart publish**: `helm-release.yaml` with OCI registry and Cosign signing

Planned:
1. **python-semantic-release**: Auto-versioning from commits
2. **towncrier**: Changelog generation from fragments
3. **Docker image publish**: Application images to GHCR

See `.github/CI.md` for current pipeline documentation.

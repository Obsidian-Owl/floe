# Research Brief: Helm v3 to v4.1.3 Upgrade

**Date**: 2026-03-28 | **Confidence**: HIGH (official docs + release notes + issue trackers)

## Summary

Helm v4.1.3 (released 2026-03-11) is a stable patch release fixing several v4.0.0 regressions. The v3-to-v4 upgrade is less disruptive than v2-to-v3. Key risks are plugin compatibility and flag renames.

## Breaking Changes Relevant to This Project

| Change | Impact | Mitigation |
|--------|--------|------------|
| `--atomic` renamed to `--rollback-on-failure` | Already migrated in commit `56378e4`. Both flags work in v4.1.3 (old emits deprecation warning) | Keep `--rollback-on-failure` |
| `--force` renamed to `--force-replace` | Low — not used in CI or E2E | No action needed |
| `--wait` default changed, new strategies (`watcher`, `hookOnly`, `legacy`) | E2E test may need explicit `--wait` | Add `--wait` to upgrade commands |
| Server-Side Apply (SSA) default for new installs | May surface field manager conflicts in Dagster/OTel charts | Test in staging first |
| Plugin verification enforced | All `helm plugin install` commands need `--verify=false` | Update CI plugin install steps |
| `--validate` deprecated (v4.1.1) | Conflicts with `--dry-run` if both set | Check CI for `--validate` usage |

## Plugin Compatibility

| Plugin | Current | Required for v4 | Notes |
|--------|---------|-----------------|-------|
| helm-unittest | v0.8.2 | v1.0.3 + `--verify=false` | Issue #777 open, `--color` flag conflict possible |
| helm-diff | v3.9.12 | v3.14.0+ (recommend v3.15.3) | Fixes `.Capabilities.APIVersions` bug |

## CI Changes Required

1. **`azure/setup-helm`**: Change `version: v3.14.0` to `version: v4.1.3` (all 6 instances)
2. **helm-unittest install**: Add `--verify=false`, bump to v1.0.3
3. **helm-diff install**: Add `--verify=false`, bump to v3.15.3
4. **`--rollback-on-failure`**: Already correct, no change needed
5. **Add `--wait`**: Where upgrade commands need to block until ready

## Helm v3 End-of-Life

- Bug fixes: until 2026-07-08
- Security fixes: until 2026-11-11
- No feature backports

## Chart Compatibility

- `apiVersion: v2` charts work unchanged in Helm v4
- Dagster (1.12.x) and OTel Collector (0.85.x) should be compatible
- K8s version support: Helm 4.1.x supports K8s 1.32.x-1.35.x

## Open Questions

- helm-unittest `--color` flag conflict: needs testing with v1.0.3 + Helm v4.1.3
- SSA field manager conflicts: needs integration testing with Dagster/OTel charts
- Official v4 migration guide page returned 404 — may not exist yet

## Sources

- helm.sh/docs/overview, helm.sh/docs/changelog
- github.com/helm/helm/releases (v4.0.0, v4.1.3)
- github.com/helm/helm/issues/31900 (--atomic regression)
- github.com/helm-unittest/helm-unittest/issues/777 (v4 support)
- github.com/databus23/helm-diff/releases (v3.14.0+ for v4)
- github.com/Azure/setup-helm/issues/239 (v4 auto-install)

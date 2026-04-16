# Gate: Tests

**Status**: PASS
**Timestamp**: 2026-03-28T09:00:00Z

## Evidence

### Helm Unit Tests
- Suite: `dagster run launcher image config` — 2/2 passing
  - `should render job_image when image is configured` — PASS
  - `should not render job_image when image is not configured` — PASS
- Full suite: 144/144 passing, 0 failures

### Test Coverage
- Positive case: verifies `job_image: "floe-dagster-demo:latest"` rendered in dagster.yaml
- Negative case: verifies no `job_image:` when image block absent
- Both `image.pullPolicy` and sibling `imagePullPolicy` set (schema + template coverage)

## Findings

| # | Severity | Finding |
|---|----------|---------|
| - | - | No findings |

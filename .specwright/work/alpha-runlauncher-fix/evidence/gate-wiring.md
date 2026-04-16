# Gate: Wiring

**Status**: PASS
**Timestamp**: 2026-03-28T09:00:00Z

## Evidence

### Values File Consistency
All 6 values files verified for correct structure:

| File | Key Path | image.repository | image.tag | imagePullPolicy |
|------|----------|------------------|-----------|-----------------|
| values.yaml | dagster.runLauncher.config.k8sRunLauncher | (commented) | (commented) | Always |
| values-test.yaml | dagster.runLauncher.config.k8sRunLauncher | floe-dagster-demo | latest | Never |
| values-dev.yaml | dagster.runLauncher.config.k8sRunLauncher | floe-dagster-demo | latest | Never |
| values-demo.yaml | dagster.runLauncher.config.k8sRunLauncher | floe-dagster-demo | latest | Never |
| values-prod.yaml | dagster.runLauncher.config.k8sRunLauncher | (commented) | (commented) | Always |
| values-staging.yaml | dagster.runLauncher.config.k8sRunLauncher | (commented) | (commented) | Always |

### Key Name Verification
- All files use camelCase `runLauncher` (not snake_case `run_launcher`)
- Prod and staging corrected from `run_launcher` to `runLauncher`

### Schema Compliance
- All active image blocks include both `image.pullPolicy` (schema) and sibling `imagePullPolicy` (template)

## Findings

| # | Severity | Finding |
|---|----------|---------|
| - | - | No findings |

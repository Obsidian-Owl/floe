# Helm CI Failure Classification - 2026-04-25

## Observed Failure

The post-merge Helm CI Kind integration run for commit `3b66f0f` failed during `helm upgrade --install floe-test charts/floe-platform --wait --timeout 10m`.

Helm reported these unready Deployments:

- `Deployment/floe-test/floe-test-dagster-daemon`: `Available: 0/1`
- `Deployment/floe-test/floe-test-dagster-webserver`: `Available: 0/1`

The captured teardown output showed Marquez pods terminating and Marquez probes returning HTTP 500 during cleanup, but the workflow removed the release before Dagster pod logs were captured.

## Classification

Current classification: `unclassified platform readiness failure`.

Evidence is insufficient to choose between Dagster readiness, Marquez dependency readiness, Kind resource pressure, or chart dependency timing. The next run must capture pod logs, events, Helm status, and Helm history before release cleanup.

## Decision

Do not tune timeouts or readiness probes from this evidence alone. First merge diagnosable CI behavior, then classify the next failure from retained logs.

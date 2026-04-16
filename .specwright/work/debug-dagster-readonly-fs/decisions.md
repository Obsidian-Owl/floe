# Decisions: debug-dagster-readonly-fs

## D-1: Fix it now (Type 2 — local scope, reversible)

**Context**: Dagster CrashLoopBackOff blocks all E2E tests. Fix is 1-2 files (values.yaml,
possibly values-test.yaml), local to Helm chart configuration. No architectural changes.

**Decision**: Fix now via `/sw-build`. Handoff to build phase.

## D-2: Individual subdirectory mounts over whole-DAGSTER_HOME emptyDir

**Context**: Mounting emptyDir over `$DAGSTER_HOME` would shadow the `dagster.yaml` ConfigMap
subPath mount. The subchart mounts `dagster.yaml` at `$DAGSTER_HOME/dagster.yaml` with subPath.

**Decision**: Mount individual writable subdirectories using a single emptyDir volume with
subPath mounts. This preserves the ConfigMap mount and is explicit about what directories
are writable.

**Alternative rejected**: Whole-DAGSTER_HOME emptyDir + init container to copy dagster.yaml.
More complex, harder to maintain, and the init container adds startup latency.

## D-3: Keep telemetry enabled

**Context**: User explicitly stated telemetry is a critical proof point. Dagster's built-in
telemetry writes instance UUID and event logs — this is separate from OTel telemetry
(already configured via `OTEL_EXPORTER_OTLP_ENDPOINT`).

**Decision**: Keep `telemetry.enabled: true`. The writable volumes solve the write permission
issue without disabling any functionality.

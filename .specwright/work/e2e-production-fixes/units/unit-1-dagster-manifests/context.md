# Context: Unit 1 — Commit dbt Manifests for Docker Build

## Problem
`@dbt_assets(manifest=MANIFEST_PATH)` reads `target/manifest.json` at module import time. When the Docker image is built from a git-clean working tree, the file is absent (`.gitignore` excludes `target/`), causing `DagsterUserCodeLoadError` for all 3 demo products.

## Key Files
- `.gitignore` line 89: `target/` (global exclude)
- `.gitignore` lines 117-122: comment noting `definitions.py` is tracked for same reason
- `demo/customer-360/target/manifest.json` — 587KB, exists locally
- `demo/iot-telemetry/target/manifest.json` — exists locally
- `demo/financial-risk/target/manifest.json` — exists locally
- `demo/customer-360/definitions.py` line 23: `MANIFEST_PATH = DBT_PROJECT_DIR / "target" / "manifest.json"`
- `docker/dagster-demo/Dockerfile` lines 147-161: `COPY demo/customer-360/ /app/demo/customer_360/`

## Design Decision
Commit manifests with `.gitignore` exception (D1). Same pattern as committed `definitions.py`. Add CI staleness gate.

## Verification
```bash
docker run --rm floe-dagster-demo:latest ls /app/demo/customer_360/target/manifest.json
```

# Storage MinIO Validation

Date: 2026-05-05

## Scope

Validates the strict MinIO storage path:

1. `demo/manifest.yaml` selects `plugins.storage.type: minio`.
2. `floe platform compile` emits `CompiledArtifacts.deployment.storage`.
3. The compiled storage binding contains no raw MinIO credentials.
4. `floe helm generate --artifact` derives MinIO and Polaris values from the binding.
5. The Helm chart creates MinIO buckets and configures Polaris from Secret references.
6. E2E validation reads runtime storage endpoints from compiled artifacts.

## Commands

```bash
uv run pytest tests/contract/test_storage_binding_security.py -v
uv run pytest packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py -v
uv run pytest packages/floe-core/tests/unit/helm/test_generate_cli.py -v
make test-unit
```

Full E2E:

```bash
make test-e2e
```

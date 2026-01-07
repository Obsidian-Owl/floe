# Integration Testing

Integration tests run in Kubernetes pods to ensure infrastructure parity with production.

> **Note:** Integration tests run in Kubernetes pods, not locally with testcontainers.
> See [K8s Testing Infrastructure](k8s-infrastructure.md) for details.

---

## K8s Test Environment

Integration tests execute inside a Kind cluster with minimal floe-platform deployment:

```yaml
# tests/integration/test-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: integration-tests
spec:
  template:
    spec:
      restartPolicy: Never
      serviceAccountName: test-runner
      containers:
        - name: pytest
          image: ghcr.io/floe/test-runner:latest
          command: ["pytest", "tests/integration", "-v", "--junitxml=/results/junit.xml"]
          env:
            # Services discovered via K8s DNS (same as production)
            - name: DAGSTER_HOST
              value: "dagster-webserver.floe-test.svc.cluster.local"
            - name: DAGSTER_PORT
              value: "3000"
            - name: POSTGRES_HOST
              value: "dagster-postgresql.floe-test.svc.cluster.local"
          volumeMounts:
            - name: results
              mountPath: /results
      volumes:
        - name: results
          emptyDir: {}
```

---

## Test Fixtures (K8s-Native)

```python
# tests/integration/conftest.py
import os
import pytest
import httpx

@pytest.fixture(scope="session")
def dagster_client():
    """Connect to Dagster via K8s service discovery."""
    host = os.environ.get("DAGSTER_HOST", "dagster-webserver")
    port = os.environ.get("DAGSTER_PORT", "3000")
    base_url = f"http://{host}:{port}"

    # Wait for Dagster to be ready
    client = httpx.Client(base_url=base_url, timeout=30)
    for _ in range(30):
        try:
            resp = client.get("/health")
            if resp.status_code == 200:
                break
        except httpx.ConnectError:
            import time
            time.sleep(1)

    yield client
    client.close()

@pytest.fixture(scope="session")
def postgres_connection():
    """Connect to PostgreSQL via K8s service discovery."""
    import psycopg2
    host = os.environ.get("POSTGRES_HOST", "dagster-postgresql")
    conn = psycopg2.connect(
        host=host,
        database="dagster",
        user="dagster",
        password=os.environ["POSTGRES_PASSWORD"],
    )
    yield conn
    conn.close()
```

---

## Integration Test Examples

### Dagster Asset Tests

```python
# tests/integration/test_dagster_assets.py
import pytest
from dagster import materialize
from floe_dagster.asset_factory import create_definitions
from floe_core.schemas import CompiledArtifacts

class TestDagsterAssets:
    """Integration tests for Dagster asset creation."""

    def test_dbt_assets_created(self, temp_dbt_project):
        """dbt models should be converted to Dagster assets."""
        artifacts = CompiledArtifacts(
            dbt_project_path=str(temp_dbt_project),
            dbt_manifest_path=str(temp_dbt_project / "target/manifest.json"),
            compute={"target": "duckdb"},
            transforms=[{"type": "dbt", "path": "models/"}],
            observability={},
        )

        defs = create_definitions(artifacts)

        # Should have assets for each dbt model
        asset_keys = [a.key for a in defs.get_all_asset_specs()]
        assert len(asset_keys) > 0

    def test_assets_execute_successfully(self, temp_dbt_project, duckdb_path):
        """Assets should execute without errors."""
        artifacts = create_test_artifacts(temp_dbt_project, duckdb_path)
        defs = create_definitions(artifacts)

        result = materialize(
            defs.get_all_asset_specs(),
            resources=defs.resources,
        )

        assert result.success
```

### Full Pipeline Tests

```python
# tests/integration/test_full_pipeline.py
import pytest
from pathlib import Path
from floe_cli.commands.run import execute_pipeline

class TestFullPipeline:
    """Integration tests for full pipeline execution."""

    @pytest.fixture
    def sample_project(self, tmp_path) -> Path:
        """Create a sample project for testing."""
        # Create floe.yaml
        floe_yaml = tmp_path / "floe.yaml"
        floe_yaml.write_text("""
apiVersion: floe.dev/v1
kind: DataProduct
metadata:
  name: test-pipeline
  version: "1.0"

platform:
  ref: file://./platform-manifest.yaml  # Local platform config for testing

transforms:
  - type: dbt
    path: models/
""")

        # Create dbt project
        (tmp_path / "models").mkdir()
        (tmp_path / "models" / "test_model.sql").write_text("""
SELECT 1 as id, 'test' as name
""")

        # Create dbt_project.yml
        (tmp_path / "dbt_project.yml").write_text("""
name: test_project
version: "1.0"
profile: floe
""")

        return tmp_path

    def test_pipeline_runs_successfully(self, sample_project):
        """Full pipeline should execute without errors."""
        result = execute_pipeline(
            config_path=sample_project / "floe.yaml",
            environment="dev",
        )

        assert result.success
        assert (sample_project / "test.duckdb").exists()
```

---

## Running Integration Tests

```bash
# Create Kind cluster
kind create cluster --name floe-test

# Deploy minimal stack
helm install floe-test ./charts/floe-platform \
  --namespace floe-test --create-namespace \
  --set dagster.enabled=true \
  --set polaris.enabled=false \
  --wait --timeout=5m

# Run integration tests as K8s Job
kubectl apply -f tests/integration/test-job.yaml -n floe-test
kubectl wait --for=condition=complete job/integration-tests -n floe-test --timeout=5m

# View results
kubectl logs job/integration-tests -n floe-test
```

---

## Related

- [Testing Index](index.md)
- [K8s Testing Infrastructure](k8s-infrastructure.md)
- [E2E Testing](e2e-testing.md)

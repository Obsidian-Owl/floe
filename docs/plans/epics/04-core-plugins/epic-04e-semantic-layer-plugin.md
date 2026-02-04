# Epic 4E: Semantic Layer Plugin

## Summary

The SemanticLayerPlugin ABC defines the interface for business intelligence semantic layers. The default implementation uses Cube (ADR-0001), providing a SQL API, REST API, and GraphQL API for querying dbt models with business-friendly semantics.

**Key Insight**: The Semantic Layer is the consumption interface for data products. It abstracts dbt models into measures, dimensions, and time grains that BI tools can query.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [Epic 4E: Semantic Layer Plugin](https://linear.app/obsidianowl/project/epic-4e-semantic-layer-plugin-3c5addd80c14)

---

## Requirements Covered

| Requirement ID | Description | Priority | E2E Test |
|----------------|-------------|----------|----------|
| FR-050 | All 11 plugin types discoverable | CRITICAL | `test_all_plugin_types_discoverable` |
| REQ-080 | SemanticLayerPlugin ABC definition | CRITICAL | - |
| REQ-081 | Cube integration | HIGH | - |
| REQ-082 | dbt model to Cube schema generation | HIGH | - |
| REQ-083 | SQL/REST/GraphQL API exposure | MEDIUM | - |
| REQ-084 | Pre-aggregation configuration | MEDIUM | - |

---

## Architecture Alignment

### Target State (from Architecture Summary)

- **Semantic Layer is PLUGGABLE** - Platform team selects: Cube, dbt Semantic Layer, None
- **Cube is the default** - Provides SQL API, REST API, GraphQL API
- **cube_dbt package** - Bridges dbt models to Cube schemas
- **SemanticLayerPlugin** - Entry point `floe.semantic_layers`

### Plugin Interface (from ADR-0001)

```python
class SemanticLayerPlugin(PluginMetadata):
    """Abstract base class for semantic layer plugins."""

    @abstractmethod
    def generate_schema_from_dbt(self, dbt_manifest: dict) -> dict:
        """Generate semantic layer schema from dbt manifest."""
        ...

    @abstractmethod
    def get_api_endpoints(self) -> dict[str, str]:
        """Return available API endpoints (sql, rest, graphql)."""
        ...

    @abstractmethod
    def get_helm_values_override(self) -> dict[str, Any]:
        """Generate Helm values for deploying semantic layer."""
        ...

    @abstractmethod
    def get_dagster_resource_config(self) -> dict[str, Any]:
        """Generate Dagster resource config for semantic layer queries."""
        ...
```

---

## File Ownership (Exclusive)

```text
# Core ABC
packages/floe-core/src/floe_core/plugins/
└── semantic_layer.py          # SemanticLayerPlugin ABC

# Cube implementation
plugins/floe-semantic-cube/
├── src/floe_semantic_cube/
│   ├── __init__.py
│   ├── plugin.py              # CubeSemanticPlugin
│   ├── schema_generator.py    # dbt → Cube schema
│   └── dagster_resource.py    # Cube query resource
├── tests/
│   ├── unit/
│   └── integration/
└── pyproject.toml             # Entry point: floe.semantic_layers

# Helm chart (subchart)
charts/floe-platform/charts/cube/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── deployment.yaml
    ├── service.yaml
    └── configmap.yaml

# Test fixtures
testing/fixtures/semantic_layer.py
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 1 | Uses plugin registry |
| Blocked By | Epic 5A | dbt manifest required for schema generation |
| Blocked By | Epic 9B | Helm charts for deployment |
| Blocks | None | Terminal plugin |

---

## User Stories (for SpecKit)

### US1: SemanticLayerPlugin ABC (P0)

**As a** plugin developer
**I want** a clear ABC for semantic layer plugins
**So that** I can implement alternative semantic layers (dbt SL)

**Acceptance Criteria**:
- [ ] `SemanticLayerPlugin` ABC defined in floe-core
- [ ] `generate_schema_from_dbt()` method defined
- [ ] `get_api_endpoints()` method defined
- [ ] `get_helm_values_override()` method defined
- [ ] Entry point `floe.semantic_layers` documented

### US2: Cube Plugin Implementation (P0)

**As a** data engineer
**I want** Cube as the default semantic layer
**So that** I can query dbt models via SQL/REST/GraphQL

**Acceptance Criteria**:
- [ ] `CubeSemanticPlugin` implements ABC
- [ ] Registered as entry point `floe.semantic_layers`
- [ ] Schema generation from dbt manifest works
- [ ] Plugin discoverable via PluginRegistry

**Implementation**:
```python
# plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py
from floe_core.plugins.semantic_layer import SemanticLayerPlugin

class CubeSemanticPlugin(SemanticLayerPlugin):
    @property
    def name(self) -> str:
        return "cube"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    def generate_schema_from_dbt(self, dbt_manifest: dict) -> dict:
        """Generate Cube schema from dbt manifest."""
        cubes = []
        for node_id, node in dbt_manifest.get("nodes", {}).items():
            if node["resource_type"] == "model":
                cubes.append(self._model_to_cube(node))
        return {"cubes": cubes}

    def get_api_endpoints(self) -> dict[str, str]:
        return {
            "sql": "/cubejs-api/v1/sql",
            "rest": "/cubejs-api/v1/load",
            "graphql": "/cubejs-api/graphql",
        }

    def get_helm_values_override(self) -> dict[str, Any]:
        return {
            "cube": {
                "enabled": True,
                "image": {"tag": "v0.35.0"},
                "api": {"enabled": True},
            }
        }

    def get_dagster_resource_config(self) -> dict[str, Any]:
        return {
            "cube_api_url": EnvVar("CUBE_API_URL"),
            "cube_api_secret": EnvVar("CUBE_API_SECRET"),
        }
```

### US3: dbt to Cube Schema Generation (P1)

**As a** data engineer
**I want** Cube schemas generated from dbt models
**So that** I don't manually maintain two schemas

**Acceptance Criteria**:
- [ ] Each dbt model becomes a Cube
- [ ] Columns become dimensions or measures (by convention)
- [ ] Relationships inferred from dbt refs
- [ ] Schema written to `cube/schema/` directory

### US4: Helm Deployment (P1)

**As a** platform operator
**I want** Cube deployed via Helm
**So that** the semantic layer runs in K8s

**Acceptance Criteria**:
- [ ] Cube deployed as subchart of floe-platform
- [ ] Connected to dbt models via S3/MinIO
- [ ] API exposed via Ingress (optional)
- [ ] Secrets managed via K8s Secrets

---

## Technical Notes

### Key Decisions

1. **Cube is default but pluggable** - Can be disabled or replaced with dbt Semantic Layer
2. **Schema generation is automatic** - Uses dbt manifest, not manual Cube schema files
3. **Helm subchart pattern** - Cube chart included in floe-platform
4. **API-first consumption** - SQL API enables BI tool connectivity

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Cube version compatibility | MEDIUM | MEDIUM | Pin versions, test upgrades |
| Schema drift | MEDIUM | MEDIUM | Regenerate on each compile |
| Performance for large models | LOW | HIGH | Pre-aggregations, caching |

### Test Strategy

- **Unit**: `plugins/floe-semantic-cube/tests/unit/test_plugin.py`
- **Contract**: `tests/contract/test_semantic_layer_abc.py`
- **Integration**: Cube API querying Iceberg tables

---

## E2E Test Alignment

| Test | Current Status | After Epic |
|------|----------------|------------|
| `test_all_plugin_types_discoverable` | FAIL (SEMANTIC_LAYER missing) | PASS |

---

## SpecKit Context

### Relevant Codebase Paths
- `packages/floe-core/src/floe_core/plugins/`
- `plugins/` (new: floe-semantic-cube)
- `charts/floe-platform/`
- `docs/architecture/plugin-system/`

### Related Existing Code
- `PluginRegistry` from Epic 1
- `PluginMetadata` base class

### External Dependencies
- `cubejs` (Cube.js)
- `cube_dbt` (if available)

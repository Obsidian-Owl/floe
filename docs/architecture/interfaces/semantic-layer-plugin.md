# SemanticLayerPlugin

**Purpose**: Business intelligence API and semantic modeling
**Location**: `floe_core/interfaces/semantic_layer.py`
**Entry Point**: `floe.semantic_layers`
**ADR**: [ADR-0001: Semantic Layer](../adr/0001-semantic-layer.md)

SemanticLayerPlugin abstracts semantic/consumption layers (Cube, dbt Semantic Layer), enabling consistent metrics definitions and business intelligence APIs across different implementations.

## Interface Definition

```python
# floe_core/interfaces/semantic_layer.py
from abc import ABC, abstractmethod
from pathlib import Path

class SemanticLayerPlugin(ABC):
    """Interface for semantic/consumption layers (Cube, dbt Semantic Layer)."""

    name: str
    version: str

    @abstractmethod
    def sync_from_dbt_manifest(
        self,
        manifest_path: Path,
        output_dir: Path
    ) -> list[Path]:
        """Generate semantic models from dbt manifest.

        Args:
            manifest_path: Path to dbt manifest.json
            output_dir: Directory to write semantic model files

        Returns:
            List of generated file paths
        """
        pass

    @abstractmethod
    def get_security_context(
        self,
        namespace: str,
        roles: list[str]
    ) -> dict:
        """Build security context for data isolation.

        Args:
            namespace: Data namespace (e.g., "sales.customer-360")
            roles: User roles

        Returns:
            Security context for query filtering
        """
        pass

    @abstractmethod
    def validate_schema(self, schema_dir: Path) -> list["ValidationError"]:
        """Validate semantic layer schema files.

        Args:
            schema_dir: Directory containing schema files

        Returns:
            List of validation errors (empty if valid)
        """
        pass
```

## Reference Implementations

| Plugin | Description |
|--------|-------------|
| `CubeSemanticLayerPlugin` | Cube.js semantic layer with REST/GraphQL/SQL APIs |
| `DBTSemanticLayerPlugin` | dbt Semantic Layer (dbt Cloud or OSS MetricFlow) |

## Related Documents

- [ADR-0001: Semantic Layer](../adr/0001-semantic-layer.md)
- [Plugin Architecture](../plugin-architecture.md)
- [ComputePlugin](compute-plugin.md) - For database connections

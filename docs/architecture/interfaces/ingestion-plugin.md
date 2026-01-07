# IngestionPlugin

**Purpose**: Data loading from external sources
**Location**: `floe_core/interfaces/ingestion.py`
**Entry Point**: `floe.ingestions`
**ADR**: [ADR-0020: Ingestion Plugins](../adr/0020-ingestion-plugins.md)

IngestionPlugin abstracts data ingestion/EL (Extract-Load) tools, enabling platform teams to choose between embedded (dlt) or external (Airbyte) ingestion patterns while maintaining consistent pipeline definitions.

## Interface Definition

```python
# floe_core/interfaces/ingestion.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class IngestionConfig:
    """Configuration for an ingestion pipeline."""
    name: str                           # Pipeline name
    source: str                         # Source identifier
    destination_table: str              # Target Iceberg table
    write_disposition: str              # append | replace | merge
    incremental: dict | None            # Incremental config
    secret_refs: dict[str, str] | None  # Secret references

@dataclass
class IngestionResult:
    """Result of an ingestion run."""
    success: bool
    rows_loaded: int
    tables_created: list[str]
    duration_seconds: float
    error: str | None

class IngestionPlugin(ABC):
    """Interface for data ingestion/EL plugins (dlt, Airbyte)."""

    name: str
    version: str
    is_external: bool    # True for Airbyte (external), False for dlt (embedded)

    @abstractmethod
    def create_pipeline(self, config: IngestionConfig) -> Any:
        """Create ingestion pipeline from configuration.

        For dlt: Returns dlt.Pipeline object
        For Airbyte: Returns connection configuration dict
        """
        pass

    @abstractmethod
    def run(self, pipeline: Any, **kwargs) -> IngestionResult:
        """Execute the ingestion pipeline.

        For dlt: Runs the pipeline directly
        For Airbyte: Triggers sync via API
        """
        pass

    @abstractmethod
    def get_destination_config(self, catalog_config: dict) -> dict:
        """Generate destination configuration for writing to Iceberg.

        All ingestion plugins MUST write to Iceberg tables via the catalog.
        """
        pass

    @abstractmethod
    def create_dagster_assets(
        self,
        configs: list[IngestionConfig]
    ) -> list:
        """Create Dagster assets from ingestion configurations.

        Returns list of @asset decorated functions for Dagster integration.
        """
        pass
```

## Reference Implementations

| Plugin | Description | External |
|--------|-------------|----------|
| `DLTIngestionPlugin` | Embedded Python ingestion (dlt) | No |
| `AirbyteIngestionPlugin` | External connector platform | Yes |

## Related Documents

- [ADR-0020: Ingestion Plugins](../adr/0020-ingestion-plugins.md)
- [Plugin Architecture](../plugin-architecture.md)
- [CatalogPlugin](catalog-plugin.md) - For destination table registration

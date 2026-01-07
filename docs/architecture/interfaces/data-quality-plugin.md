# DataQualityPlugin

**Purpose**: Data quality validation and monitoring
**Location**: `floe_core/interfaces/data_quality.py`
**Entry Point**: `floe.data_quality`
**ADR**: [ADR-0044: Data Quality Plugin](../adr/0044-data-quality-plugin.md)

DataQualityPlugin abstracts data quality validation frameworks, enabling platform teams to choose between dbt tests, Great Expectations, Soda, or other quality tools while maintaining consistent quality gate enforcement.

> **Note**: This interface is documented in ADR-0044. The interface definition below is a placeholder pending full specification.

## Interface Definition

```python
# floe_core/interfaces/data_quality.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class QualityCheckResult:
    """Result of a data quality check."""
    check_name: str
    passed: bool
    severity: str  # "error" | "warning" | "info"
    details: dict[str, Any]
    rows_checked: int | None = None
    rows_failed: int | None = None

@dataclass
class QualitySummary:
    """Summary of all quality checks for a dataset."""
    dataset: str
    total_checks: int
    passed: int
    failed: int
    warnings: int
    results: list[QualityCheckResult]

class DataQualityPlugin(ABC):
    """Interface for data quality validation frameworks."""

    name: str
    version: str

    @abstractmethod
    def run_checks(
        self,
        dataset: str,
        checks: list[dict[str, Any]],
        connection: dict[str, Any],
    ) -> QualitySummary:
        """Run data quality checks on a dataset.

        Args:
            dataset: Table or dataset identifier
            checks: List of check configurations
            connection: Database connection configuration

        Returns:
            QualitySummary with all check results
        """
        pass

    @abstractmethod
    def validate_freshness(
        self,
        dataset: str,
        timestamp_column: str,
        max_age_hours: float,
        connection: dict[str, Any],
    ) -> QualityCheckResult:
        """Check if data meets freshness requirements.

        Args:
            dataset: Table identifier
            timestamp_column: Column containing timestamps
            max_age_hours: Maximum allowed data age
            connection: Database connection

        Returns:
            QualityCheckResult for freshness check
        """
        pass

    @abstractmethod
    def generate_dbt_tests(
        self,
        checks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate dbt test YAML from quality check definitions.

        Args:
            checks: Quality check configurations

        Returns:
            dbt-compatible test YAML structure
        """
        pass
```

## Reference Implementations

| Plugin | Description |
|--------|-------------|
| `DBTTestsPlugin` | Native dbt tests (default) |
| `GreatExpectationsPlugin` | Great Expectations framework |
| `SodaPlugin` | Soda Core quality checks |

## Related Documents

- [ADR-0044: Data Quality Plugin](../adr/0044-data-quality-plugin.md)
- [Plugin Architecture](../plugin-system/index.md)
- [CatalogPlugin](catalog-plugin.md) - For quality metadata storage

"""Quality Plugin Contract Schemas (Epic 5B Design Artifact).

These schemas represent the target Pydantic models for the Data Quality Plugin.
They serve as design artifacts and will be implemented in:
- packages/floe-core/src/floe_core/schemas/quality_config.py
- packages/floe-core/src/floe_core/schemas/quality_score.py
- packages/floe-core/src/floe_core/schemas/quality_validation.py

Contract Version: 0.4.0 (Epic 5B addition)

NOTE: These files are design artifacts only. Do not import from here in
production code. The actual implementations will be in floe-core.
"""

from __future__ import annotations

# Re-export all schemas from their canonical floe-core locations.
# This allows ``from specs.5b_dataquality_plugin.contracts import …`` to work
# while keeping floe-core as the single source of truth.
from floe_core.plugins.quality import GateResult, ValidationResult
from floe_core.schemas.quality_config import (
    CalculationParameters,
    Dimension,
    DimensionWeights,
    GateTier,
    OverrideConfig,
    QualityConfig,
    QualityGates,
    QualityThresholds,
    SeverityLevel,
)
from floe_core.schemas.quality_score import (
    QualityCheck,
    QualityCheckResult,
    QualityScore,
    QualitySuite,
    QualitySuiteResult,
)

__all__ = [
    # From quality_config.py
    "Dimension",
    "SeverityLevel",
    "DimensionWeights",
    "CalculationParameters",
    "QualityThresholds",
    "GateTier",
    "QualityGates",
    "OverrideConfig",
    "QualityConfig",
    # From quality_score.py
    "QualityCheck",
    "QualityCheckResult",
    "QualitySuiteResult",
    "QualityScore",
    "QualitySuite",
    # From validation_result.py
    "ValidationResult",
    "GateResult",
]

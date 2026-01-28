"""Quality scoring module for calculating unified quality scores.

This module implements the three-layer scoring model:
- Layer 1: Dimension weights (completeness, accuracy, validity, consistency, timeliness)
- Layer 2: Severity weights (critical, warning, info)
- Layer 3: Calculation parameters (baseline, influence caps)

See Also:
    - specs/5b-dataquality-plugin/spec.md: Feature specification
    - FR-015 through FR-016d: Scoring requirements
"""

from __future__ import annotations

from floe_core.scoring.score_calculator import (
    calculate_quality_score,
    calculate_unified_score,
    check_score_thresholds,
)

__all__ = [
    "calculate_quality_score",
    "calculate_unified_score",
    "check_score_thresholds",
]

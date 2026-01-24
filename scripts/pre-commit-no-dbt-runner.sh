#!/usr/bin/env bash
# Pre-commit hook: Prevent dbtRunner imports in orchestrator package (SC-004)
#
# Architecture Constraint:
#   Orchestrator MUST delegate to DBTPlugin, NOT invoke dbtRunner directly.
#   This preserves layer separation and enables Fusion/Core abstraction.
#
# See: docs/architecture/opinionation-boundaries.md

set -e

echo "Checking for forbidden dbtRunner imports in orchestrator..."

# Check for direct dbtRunner imports in floe-orchestrator-dagster
# Forbidden patterns:
#   - from dbt.cli.main import dbtRunner
#   - from dbt.cli import main
#   - import dbt.cli

VIOLATIONS=$(grep -rE "(from dbt\.cli\.main import|from dbt\.cli import|import dbt\.cli)" \
  plugins/floe-orchestrator-dagster/src/ 2>/dev/null || true)

if [[ -n "$VIOLATIONS" ]]; then
  echo "ERROR: Found forbidden dbtRunner imports in orchestrator package:" >&2
  echo "$VIOLATIONS" >&2
  echo "" >&2
  echo "Architecture violation: Orchestrator must use DBTPlugin abstraction." >&2
  echo "Use: from floe_dbt_core import DBTCorePlugin" >&2
  echo "  or: from floe_dbt_fusion import DBTFusionPlugin" >&2
  echo "" >&2
  echo "See: SC-004 (Epic 5A) - dbt owns SQL execution" >&2
  exit 1
fi

echo "No forbidden dbtRunner imports found"

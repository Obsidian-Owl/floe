# ADR-0015: Policy Enforcement as Core Module

## Status

Accepted

## Context

Platform teams need compile-time enforcement of:
- **Naming conventions** (medallion pattern: bronze_*, silver_*, gold_*)
- **Test coverage thresholds** (minimum 80%)
- **Documentation requirements** (descriptions on models, columns)
- **SQL quality** (linting, structure validation)

### Why NOT a Plugin?

Per ADR-0037 (Composability Principle), plugin interfaces are appropriate when:
- Multiple implementations exist OR may exist
- Organizations may swap implementations

Policy enforcement fails these criteria:

1. **Tooling is already pluggable via DBTPlugin** (ADR-0043):
   - `lint_project()` → SQLFluff (dialect-aware SQL linting)
   - `validate_artifacts()` → dbt-checkpoint (manifest validation)

2. **Organizational rules are configuration, not implementations**:
   - Naming conventions differ by organization, not by tool
   - Test coverage is a threshold (80%), not an algorithm
   - Documentation requirements are enumerated fields

3. **No real-world alternatives**:
   - dbt-checkpoint is the only mature dbt artifact validator
   - SQLFluff is the standard SQL linter
   - Both are needed together (they validate different things)

### Boundary: Policy vs Data Quality

| Concern | Timing | Owner | Tool |
|---------|--------|-------|------|
| **PolicyEnforcer** | Compile-time | Core module | dbt-checkpoint, SQLFluff (via DBTPlugin) |
| **DataQualityPlugin** | Runtime | Plugin (ADR-0044) | Great Expectations, Soda |

## Decision

**Policy enforcement is a CORE MODULE in floe-core, not a pluggable interface.**

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: CONFIGURATION (manifest.yaml)                │
│                                                                 │
│  governance:                                                    │
│    naming:                                                      │
│      enforcement: strict          # off | warn | strict         │
│      pattern: medallion           # medallion | kimball | custom│
│    quality_gates:                                               │
│      minimum_test_coverage: 80                                  │
│      require_descriptions: true                                 │
│      block_on_failure: true                                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Consumed by
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: FOUNDATION (floe-core)                                │
│                                                                 │
│  EnforcementEngine (core module)                                │
│  ├── apply_naming_rules(manifest, config)                       │
│  ├── apply_coverage_rules(manifest, config)                     │
│  └── apply_documentation_rules(manifest, config)                │
│                                                                 │
│  DBTPlugin (pluggable via ADR-0043)                             │
│  ├── lint_project()        → SQLFluff                           │
│  └── validate_artifacts()  → dbt-checkpoint                     │
└─────────────────────────────────────────────────────────────────┘
```

### EnforcementEngine Interface

```python
from floe_core.schemas import GovernanceConfig

class EnforcementEngine:
    """Core module for compile-time policy enforcement.

    NOT a plugin - organizational rules are configuration,
    not swappable implementations.
    """

    def enforce(
        self,
        manifest: dict[str, Any],
        config: GovernanceConfig,
    ) -> EnforcementResult:
        """Apply all governance rules to dbt manifest.

        Args:
            manifest: Parsed dbt manifest.json
            config: Governance config from manifest.yaml

        Returns:
            EnforcementResult with violations and severity
        """
        results = []
        results.extend(self._apply_naming_rules(manifest, config.naming))
        results.extend(self._apply_coverage_rules(manifest, config.quality_gates))
        results.extend(self._apply_documentation_rules(manifest, config.quality_gates))
        return EnforcementResult(violations=results)

    def _apply_naming_rules(
        self,
        manifest: dict[str, Any],
        naming_config: NamingConfig,
    ) -> list[Violation]:
        """Validate model names match configured pattern."""
        ...

    def _apply_coverage_rules(
        self,
        manifest: dict[str, Any],
        gates_config: QualityGatesConfig,
    ) -> list[Violation]:
        """Validate test coverage meets threshold."""
        ...

    def _apply_documentation_rules(
        self,
        manifest: dict[str, Any],
        gates_config: QualityGatesConfig,
    ) -> list[Violation]:
        """Validate models have required documentation."""
        ...
```

### Configuration Schema

```yaml
# manifest.yaml
governance:
  naming:
    enforcement: strict  # off | warn | strict
    pattern: medallion   # medallion | kimball | custom
    custom_patterns:     # Only if pattern: custom
      - "^bronze_.*$"
      - "^silver_.*$"
      - "^gold_.*$"

  quality_gates:
    minimum_test_coverage: 80
    require_descriptions: true
    require_column_descriptions: false
    block_on_failure: true
```

### Compile-Time Workflow

```bash
$ floe compile

[1/5] Loading platform manifest...
[2/5] Compiling dbt project...
[3/5] Linting SQL (via DBTPlugin)...        # SQLFluff
[4/5] Validating artifacts (via DBTPlugin)... # dbt-checkpoint
[5/5] Enforcing governance rules...          # EnforcementEngine (core)

Governance violations:
  ✗ ERROR: 'stg_payments' violates medallion naming
           Expected: bronze_*, silver_*, or gold_*
  ✗ ERROR: 'customers' missing model description
           Required by: quality_gates.require_descriptions

Compilation FAILED (block_on_failure: true)
```

## Consequences

### Positive

- **Simpler architecture**: No plugin interface to maintain for rules that don't vary by implementation
- **Clear ownership**: Tooling (SQLFluff, dbt-checkpoint) → DBTPlugin; Rules → Core
- **Reduced complexity**: 12 plugin types (not 13)
- **Configuration-driven**: Platform teams edit YAML, not code

### Negative

- **Less extensible**: Custom enforcement logic requires core changes
- **Mitigation**: Custom rules can extend `EnforcementEngine` or contribute upstream

### Neutral

- **DBTPlugin still handles tooling**: SQLFluff and dbt-checkpoint remain pluggable via ADR-0043
- **DataQualityPlugin unaffected**: Runtime data validation remains a plugin (ADR-0044)

## References

- [ADR-0016: Four-Layer Architecture](0016-platform-enforcement-architecture.md) - Layer 2 configuration model
- [ADR-0037: Composability Principle](0037-composability-principle.md) - When to use plugins vs configuration
- [ADR-0043: DBTPlugin Interface](0043-dbt-runtime-abstraction.md) - Tooling pluggability (SQLFluff, dbt-checkpoint)
- [ADR-0044: Data Quality Plugin](0044-unified-data-quality-plugin.md) - Runtime data validation
- [ADR-0009: dbt Owns SQL](0009-dbt-owns-sql.md) - dbt owns SQL compilation

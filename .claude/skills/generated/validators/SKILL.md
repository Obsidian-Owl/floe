---
name: validators
description: "Skill for the Validators area of floe. 119 symbols across 13 files."
---

# Validators

119 symbols | 13 files | Cohesion: 78%

## When to Use

- Working with code in `packages/`
- Understanding how generate_from_ports, parse_iso8601_duration, parse_percentage work
- Modifying validators-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py` | validate, validate_string, _compute_schema_hash, _compute_schema_hash_string, _create_skipped_result (+25) |
| `packages/floe-core/src/floe_core/enforcement/validators/inheritance.py` | parse_iso8601_duration, parse_percentage, InheritanceValidator, validate_inheritance, _validate_sla_inheritance (+7) |
| `packages/floe-core/src/floe_core/enforcement/validators/semantic.py` | SemanticValidator, validate, validate_refs, validate_sources, detect_circular_deps (+7) |
| `packages/floe-core/src/floe_core/enforcement/validators/custom_rules.py` | CustomRuleValidator, validate, _validate_rule, _filter_models_by_pattern, _validate_tags_for_prefix (+7) |
| `packages/floe-core/src/floe_core/enforcement/validators/versioning.py` | VersioningValidator, parse, is_major_bump, is_minor_bump, validate_version_change (+5) |
| `packages/floe-core/src/floe_core/enforcement/validators/naming.py` | NamingValidator, validate, _matches_pattern, _create_violation, _get_expected_description (+5) |
| `packages/floe-core/src/floe_core/enforcement/validators/documentation.py` | DocumentationValidator, validate, _validate_model_description, _create_model_violation, _create_model_placeholder_violation (+5) |
| `packages/floe-core/src/floe_core/enforcement/validators/coverage.py` | CoverageValidator, validate, _extract_columns, _extract_tests_for_model, _map_tests_to_columns (+4) |
| `packages/floe-core/src/floe_core/enforcement/policy_enforcer.py` | _validate_semantic, _validate_coverage, _validate_custom_rules, _validate_naming, _validate_documentation |
| `packages/floe-core/src/floe_core/contracts/generator.py` | ContractGenerator, generate_from_ports, _generate_contract_for_port, _column_to_property |

## Entry Points

Start here when exploring this area:

- **`generate_from_ports`** (Function) — `packages/floe-core/src/floe_core/contracts/generator.py:79`
- **`parse_iso8601_duration`** (Function) — `packages/floe-core/src/floe_core/enforcement/validators/inheritance.py:83`
- **`parse_percentage`** (Function) — `packages/floe-core/src/floe_core/enforcement/validators/inheritance.py:113`
- **`validate_inheritance`** (Function) — `packages/floe-core/src/floe_core/enforcement/validators/inheritance.py:164`
- **`cycle_to_violation`** (Function) — `packages/floe-core/src/floe_core/enforcement/validators/inheritance.py:640`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `ContractViolation` | Class | `packages/floe-core/src/floe_core/schemas/data_contract.py` | 206 |
| `ContractValidationResult` | Class | `packages/floe-core/src/floe_core/schemas/data_contract.py` | 272 |
| `ContractGenerator` | Class | `packages/floe-core/src/floe_core/contracts/generator.py` | 51 |
| `VersioningValidator` | Class | `packages/floe-core/src/floe_core/enforcement/validators/versioning.py` | 125 |
| `InheritanceValidator` | Class | `packages/floe-core/src/floe_core/enforcement/validators/inheritance.py` | 136 |
| `RegistrationResult` | Class | `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py` | 1226 |
| `CatalogRegistrar` | Class | `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py` | 1267 |
| `SemanticValidator` | Class | `packages/floe-core/src/floe_core/enforcement/validators/semantic.py` | 26 |
| `ContractValidationError` | Class | `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py` | 46 |
| `ContractLintError` | Class | `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py` | 70 |
| `CoverageValidator` | Class | `packages/floe-core/src/floe_core/enforcement/validators/coverage.py` | 33 |
| `CustomRuleValidator` | Class | `packages/floe-core/src/floe_core/enforcement/validators/custom_rules.py` | 32 |
| `NamingValidator` | Class | `packages/floe-core/src/floe_core/enforcement/validators/naming.py` | 56 |
| `DocumentationValidator` | Class | `packages/floe-core/src/floe_core/enforcement/validators/documentation.py` | 84 |
| `DriftDetector` | Class | `packages/floe-iceberg/src/floe_iceberg/drift_detector.py` | 74 |
| `ContractParser` | Class | `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py` | 80 |
| `generate_from_ports` | Function | `packages/floe-core/src/floe_core/contracts/generator.py` | 79 |
| `parse_iso8601_duration` | Function | `packages/floe-core/src/floe_core/enforcement/validators/inheritance.py` | 83 |
| `parse_percentage` | Function | `packages/floe-core/src/floe_core/enforcement/validators/inheritance.py` | 113 |
| `validate_inheritance` | Function | `packages/floe-core/src/floe_core/enforcement/validators/inheritance.py` | 164 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Governance | 15 calls |
| Schemas | 9 calls |
| Floe_core | 5 calls |
| Oci | 3 calls |
| Floe_iceberg | 1 calls |

## How to Explore

1. `gitnexus_context({name: "generate_from_ports"})` — see callers and callees
2. `gitnexus_query({query: "validators"})` — find related execution flows
3. Read key files listed above for implementation details

# Assumptions: E2E Materialization Fix

## A1: DbtProject constructor signature matches our usage
- **Category**: integration
- **Status**: VERIFIED
- **Evidence**: Live debugging — `DbtProject(project_dir=..., profiles_dir=...)` accepted by dagster-dbt in Docker image. The `ParameterCheckError` was specifically about the TYPE being wrong (DbtCliResource vs DbtProject), not about missing parameters.

## A2: `--rollback-on-failure` is available in CI and local Helm
- **Category**: integration
- **Status**: VERIFIED
- **Evidence**: Local `helm version` → v4.0.4. CI uses `azure/setup-helm@v4`. `helm upgrade --help` confirms `--rollback-on-failure` flag exists.

## A3: Code generator output files will not be regenerated before this fix ships
- **Category**: behavioral
- **Status**: ACCEPTED (Type 2 — reversible)
- **Rationale**: The generator template is being updated as part of this fix. Even if regeneration happens, it will use the fixed template.

## A4: No existing tests validate the code generator's template content
- **Category**: reference
- **Status**: VERIFIED
- **Evidence**: `grep -r "generate_definitions\|definitions_content\|DbtProject" --include="test_*.py"` returns no matches. No test exists for the generated file content.

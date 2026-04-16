# Decisions: E2E Materialization Fix

## D1: Include code generator fix in scope
- **Type**: Type 2 (reversible, bounded scope)
- **Decision**: Fix the code generator template at `plugin.py:1179-1189` alongside the demo definitions
- **Rationale**: The architect BLOCK is correct — the demo files say "AUTO-GENERATED" and the generator template still emits the broken pattern. Fixing only the output files without fixing the generator is treating symptoms.
- **Rule**: DISAMBIGUATION — "fix includes root cause" over "minimal change"

## D2: Do NOT add a test for the code generator
- **Type**: Type 2 (reversible)
- **Decision**: Out of scope for this fix. Track as backlog item.
- **Rationale**: Adding a test for the generator output is a good idea but expands scope beyond the immediate fix. The fix is verified by live debugging evidence.

## D3: Add review-by date to CVE ignore
- **Type**: Type 2 (reversible)
- **Decision**: Add "Review by 2026-04-28" to the `.vuln-ignore` entry for consistency with existing entries
- **Rationale**: Architect WARN accepted — matches pattern of other entries (e.g., Pygments at line 26)

## D5: Single work unit (flat layout)
- **Type**: Type 2 (reversible)
- **Decision**: No decomposition needed — single work unit with flat layout
- **Rationale**: All remaining changes are <=2 files, local blast radius, no architectural boundaries crossed. Decomposing would add overhead with no benefit.
- **Rule**: DISAMBIGUATION — "minimal ceremony" over "maximum structure" for trivial scope

## D4: Dismiss Helm version WARN
- **Type**: Type 2 (clarification)
- **Decision**: No action needed — CI uses `azure/setup-helm@v4` (Helm v4), matching local environment
- **Evidence**: `.github/workflows/helm-ci.yaml:46` uses the v4 action. Local `helm version` → v4.0.4.

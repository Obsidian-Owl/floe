# Epic 3E: Governance Integration

## Summary

Integrates the governance subsystems (policy enforcement, RBAC, network security, secret scanning) into the compilation pipeline as compile-time enforcement. This epic wires together the foundational work from Epics 3A, 3B, 7B, and 7C to provide a unified governance experience validated by E2E tests.

**Key Insight**: Governance features exist as separate subsystems but are not integrated into the compile-time workflow. This epic creates the "glue" that runs governance checks during `floe compile`.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [Epic 3E: Governance Integration](https://linear.app/obsidianowl/project/epic-3e-governance-integration-2ba5462f1c22)

---

## Requirements Covered

| Requirement ID | Description | Priority | E2E Test |
|----------------|-------------|----------|----------|
| FR-060 | RBAC enforcement during compilation | CRITICAL | `test_rbac_enforcement` |
| FR-062 | Network policies generated in Helm | HIGH | `test_network_policies` |
| FR-066 | Hardcoded secrets detection | HIGH | `test_hardcoded_secrets_detection` |
| FR-067 | Policy-as-code framework | HIGH | `test_policy_as_code` |
| REQ-205 | Enforcement hooks | HIGH | (from 3A) |
| REQ-208 | Audit logging | HIGH | (from 3A) |

---

## Architecture Alignment

### Target State (from Architecture Summary)

- **Compile-time enforcement** - Governance checks run during `floe compile`, not at runtime
- **PolicyEnforcer is core module** (not plugin) - Lives in floe-core
- **GovernanceConfig in manifest** - Platform team defines governance rules
- **EnforcementResultSummary in CompiledArtifacts** - Results persisted for audit

### Governance Integration Model

```
┌─────────────────────────────────────────────────────────────┐
│                    floe compile                              │
├─────────────────────────────────────────────────────────────┤
│  Stage 1: Load FloeSpec                                     │
│  Stage 2: Load PlatformManifest                             │
│  Stage 3: Resolve Plugins                                   │
│  Stage 4: Resolve Transforms                                │
│  Stage 5: Generate dbt Profiles                             │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Stage 6: GOVERNANCE ENFORCEMENT (NEW)                  │ │
│  │                                                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │ │
│  │  │ RBAC Check  │  │ Secret Scan │  │ Policy Evaluate │ │ │
│  │  │ (Epic 7B)   │  │ (Epic 7A)   │  │ (Epic 3A/3B)    │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘ │ │
│  │                          │                              │ │
│  │                          ▼                              │ │
│  │            EnforcementResultSummary                     │ │
│  │            - violations: []                             │ │
│  │            - passed: bool                               │ │
│  │            - policy_count: int                          │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Stage 7: Build CompiledArtifacts                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Helm Template Generation                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ NetworkPolicy (if governance.networkPolicies.enabled)│    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## File Ownership (Exclusive)

```text
# Core governance integration
packages/floe-core/src/floe_core/
├── governance/
│   ├── __init__.py
│   ├── integration.py         # run_governance_checks() - main entry
│   ├── rbac.py                # RBAC enforcement (compile-time)
│   ├── secrets.py             # Secret scanning (pre-commit style)
│   └── policies.py            # Policy-as-code framework
├── compilation/
│   └── stages.py              # Add Stage 6: Governance Enforcement

# Schema updates
packages/floe-core/src/floe_core/schemas/
├── governance_config.py       # GovernanceConfig (manifest.yaml)
└── compiled_artifacts.py      # EnforcementResultSummary (already exists)

# Helm templates
charts/floe-platform/templates/
└── networkpolicy.yaml         # Generate from governance config

# Test fixtures
testing/fixtures/governance.py     # Governance test utilities
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 2B | Compilation pipeline foundation |
| Blocked By | Epic 3A | PolicyEnforcer core |
| Blocked By | Epic 3B | Policy validation rules |
| Requires | Epic 7B | K8s RBAC definitions |
| Requires | Epic 7C | NetworkPolicy templates |
| Blocks | None | Terminal epic (integration) |

---

## User Stories (for SpecKit)

### US1: RBAC Enforcement at Compile-Time (P0)

**As a** platform operator
**I want** RBAC checked during compilation
**So that** unauthorized users can't compile pipelines

**Acceptance Criteria**:
- [ ] `GovernanceConfig.rbac.enabled` controls RBAC enforcement
- [ ] If `rbac.required_role` set, compilation fails without proper role
- [ ] RBAC violations appear in `EnforcementResultSummary.violations`
- [ ] `--dry-run` mode shows what would be enforced

**Implementation**:
```python
# packages/floe-core/src/floe_core/governance/rbac.py
from floe_core.schemas.manifest import GovernanceConfig

def check_rbac(
    principal: str | None,
    governance: GovernanceConfig,
) -> list[PolicyViolation]:
    """Check if principal has required role."""
    violations: list[PolicyViolation] = []

    if not governance.rbac or not governance.rbac.enabled:
        return violations

    required_role = governance.rbac.required_role
    if required_role and principal:
        # In real implementation, query identity provider
        principal_roles = get_principal_roles(principal)
        if required_role not in principal_roles:
            violations.append(PolicyViolation(
                policy="rbac.required_role",
                message=f"Principal '{principal}' lacks required role: {required_role}",
                severity="error",
            ))
    elif required_role and not principal:
        violations.append(PolicyViolation(
            policy="rbac.required_role",
            message="RBAC required but no principal provided (run with --principal)",
            severity="error",
        ))

    return violations
```

### US2: Secret Scanning (P0)

**As a** security engineer
**I want** hardcoded secrets detected during compilation
**So that** credentials don't leak into artifacts

**Acceptance Criteria**:
- [ ] Scans FloeSpec, manifest, and referenced SQL files
- [ ] Detects patterns: AWS keys, API tokens, passwords
- [ ] Excludes `tests/` directory by default (configurable)
- [ ] Violations block compilation unless `--allow-secrets` flag

**Implementation**:
```python
# packages/floe-core/src/floe_core/governance/secrets.py
import re
from pathlib import Path

SECRET_PATTERNS = [
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"][^'\"]+['\"]", "Hardcoded password"),
    (r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"][^'\"]+['\"]", "API key"),
]

def scan_for_secrets(
    paths: list[Path],
    exclude_patterns: list[str] | None = None,
) -> list[PolicyViolation]:
    """Scan files for hardcoded secrets."""
    violations: list[PolicyViolation] = []
    exclude = exclude_patterns or ["**/test*/**", "**/tests/**"]

    for path in paths:
        if any(path.match(p) for p in exclude):
            continue

        content = path.read_text()
        for pattern, description in SECRET_PATTERNS:
            if re.search(pattern, content):
                violations.append(PolicyViolation(
                    policy="secrets.hardcoded",
                    message=f"{description} detected in {path}",
                    severity="error",
                    file_path=str(path),
                ))

    return violations
```

### US3: Policy-as-Code Framework (P1)

**As a** platform operator
**I want** to define custom policies
**So that** I can enforce organization-specific rules

**Acceptance Criteria**:
- [ ] Policies defined in `manifest.yaml` under `governance.policies`
- [ ] Each policy has: name, condition, action (warn/error/block)
- [ ] OPA/Rego integration prepared (future)
- [ ] Built-in policies: `required_tags`, `naming_convention`, `max_transforms`

### US4: Network Policy Generation (P1)

**As a** platform operator
**I want** network policies generated in Helm
**So that** pod communication is restricted by default

**Acceptance Criteria**:
- [ ] `governance.networkPolicies.enabled` controls generation
- [ ] Default deny-all policy with explicit allow rules
- [ ] Allow rules for: Polaris, PostgreSQL, MinIO, OTel Collector
- [ ] Network policies validate in CI

**Implementation**:
```yaml
# charts/floe-platform/templates/networkpolicy.yaml
{{- if .Values.governance.networkPolicies.enabled }}
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "floe-platform.fullname" . }}-default-deny
  namespace: {{ .Release.Namespace }}
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "floe-platform.fullname" . }}-allow-platform
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/instance: {{ .Release.Name }}
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app.kubernetes.io/instance: {{ .Release.Name }}
  egress:
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

---

## Technical Notes

### Key Decisions

1. **Governance runs as compilation Stage 6** - After transforms resolved, before artifact build
2. **Violations collected, not thrown** - All checks run; summary returned with all violations
3. **Secret scanning excludes tests by default** - Test fixtures contain fake credentials
4. **RBAC uses principal from CLI/env** - `--principal` flag or `FLOE_PRINCIPAL` env var

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| False positive secrets | MEDIUM | MEDIUM | Configurable exclusion patterns |
| RBAC integration complexity | HIGH | HIGH | Start with simple role check, evolve to OIDC |
| Policy-as-code adoption | LOW | LOW | Provide useful built-in policies |

### Test Strategy

- **Unit**: `packages/floe-core/tests/unit/test_governance_integration.py`
- **Contract**: `tests/contract/test_enforcement_result_schema.py`
- **E2E**: `tests/e2e/test_governance.py`

---

## E2E Test Alignment

| Test | Current Status | After Epic |
|------|----------------|------------|
| `test_rbac_enforcement` | FAIL (not implemented) | PASS |
| `test_network_policies` | FAIL (not generated) | PASS |
| `test_hardcoded_secrets_detection` | FAIL (scans tests) | PASS |
| `test_policy_as_code` | FAIL (no framework) | PASS |

---

## GovernanceConfig Schema

```yaml
# manifest.yaml
governance:
  rbac:
    enabled: true
    required_role: "data-engineer"  # Role required to compile

  secretScanning:
    enabled: true
    excludePatterns:
      - "**/test*/**"
      - "**/fixtures/**"

  networkPolicies:
    enabled: true
    defaultDeny: true

  policies:
    - name: required_tags
      condition: "spec.metadata.tags contains 'domain'"
      action: error
      message: "All specs must have a 'domain' tag"

    - name: naming_convention
      condition: "spec.metadata.name matches '^[a-z][a-z0-9-]*$'"
      action: warn
      message: "Spec name should be lowercase with hyphens"
```

---

## SpecKit Context

### Relevant Codebase Paths
- `packages/floe-core/src/floe_core/compilation/`
- `packages/floe-core/src/floe_core/governance/` (new)
- `packages/floe-core/src/floe_core/schemas/`
- `charts/floe-platform/templates/`
- `tests/e2e/test_governance.py`

### Related Existing Code
- `floe_core/schemas/compiled_artifacts.py` - EnforcementResultSummary
- `floe_core/schemas/manifest.py` - GovernanceConfig (may need extension)

### External Dependencies
- `pydantic>=2.0` (schema validation)
- Future: `opa` (policy evaluation)

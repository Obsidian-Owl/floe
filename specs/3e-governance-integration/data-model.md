# Data Model: Epic 3E — Governance Integration

**Date**: 2026-02-09
**Spec**: `specs/3e-governance-integration/spec.md`
**Plan**: `specs/3e-governance-integration/plan.md`

## Entity Relationship Overview

```
PlatformManifest
└── GovernanceConfig (EXTENDED)
    ├── pii_encryption, audit_logging, ... (existing)
    ├── naming: NamingConfig (3A)
    ├── quality_gates: QualityGatesConfig (3A)
    ├── custom_rules: list[CustomRule] (3B)
    ├── policy_overrides: list[PolicyOverride] (3B)
    ├── data_contracts: DataContractsConfig (3C)
    ├── rbac: RBACConfig (NEW 3E)
    ├── secret_scanning: SecretScanningConfig (NEW 3E)
    └── network_policies: NetworkPoliciesConfig (NEW 3E)

GovernanceIntegrator
├── PolicyEnforcer (sealed, delegates to)
│   └── returns EnforcementResult with Violation[]
├── RBACChecker (new)
│   ├── uses IdentityPlugin.validate_token()
│   └── returns list[Violation] (policy_type="rbac")
└── SecretScanner (new)
    ├── uses SecretScannerPlugin[] (entry point discovery)
    └── returns list[Violation] (policy_type="secret_scanning")

EnforcementResult
├── passed: bool
├── violations: list[Violation]  # All types merged
├── summary: EnforcementSummary  # Per-type counters
└── enforcement_level: Literal["off", "warn", "strict"]
        │
        ▼
EnforcementResultSummary (stored in CompiledArtifacts)
```

## New Models

### RBACConfig

**Location**: `packages/floe-core/src/floe_core/schemas/manifest.py`
**Parent**: `GovernanceConfig.rbac`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `False` | Enable compile-time RBAC checking |
| `required_role` | `str \| None` | `None` | Role the caller must have (e.g., "platform-engineer") |
| `allow_principal_fallback` | `bool` | `True` | Allow `--principal` / `FLOE_PRINCIPAL` when no OIDC |

**Validation**: `model_config = ConfigDict(frozen=True, extra="forbid")`

**YAML example**:
```yaml
governance:
  rbac:
    enabled: true
    required_role: "platform-engineer"
    allow_principal_fallback: true
```

### SecretScanningConfig

**Location**: `packages/floe-core/src/floe_core/schemas/manifest.py`
**Parent**: `GovernanceConfig.secret_scanning`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `False` | Enable secret scanning during compilation |
| `exclude_patterns` | `list[str]` | `[]` | Glob patterns to exclude (e.g., `**/tests/**`) |
| `custom_patterns` | `list[SecretPattern] \| None` | `None` | Additional regex patterns beyond built-in |
| `severity` | `Literal["error", "warning"]` | `"error"` | Default severity for detected secrets |

**SecretPattern model**:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Pattern name (e.g., "Custom API Token") |
| `pattern` | `str` | Regex pattern |
| `severity` | `Literal["error", "warning"]` | Severity override |

**YAML example**:
```yaml
governance:
  secret_scanning:
    enabled: true
    exclude_patterns:
      - "**/tests/**"
      - "**/fixtures/**"
    custom_patterns:
      - name: "Internal API Token"
        pattern: "MYCO-[A-Za-z0-9]{32}"
        severity: error
```

### NetworkPoliciesConfig

**Location**: `packages/floe-core/src/floe_core/schemas/manifest.py`
**Parent**: `GovernanceConfig.network_policies`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `False` | Enable network policy generation |
| `default_deny` | `bool` | `True` | Generate default-deny policy |
| `custom_egress_rules` | `list[dict[str, Any]]` | `[]` | Additional egress rules to merge |

**YAML example**:
```yaml
governance:
  network_policies:
    enabled: true
    default_deny: true
    custom_egress_rules:
      - to:
          - ipBlock:
              cidr: 10.0.0.0/8
        ports:
          - protocol: TCP
            port: 443
```

### SecretFinding

**Location**: `packages/floe-core/src/floe_core/governance/types.py`

| Field | Type | Description |
|-------|------|-------------|
| `file_path` | `str` | Relative path to file |
| `line_number` | `int` | Line where secret detected |
| `pattern_name` | `str` | Name of the matched pattern |
| `severity` | `Literal["error", "warning"]` | Finding severity |
| `match_context` | `str` | Redacted context around match |
| `confidence` | `Literal["high", "medium", "low"]` | Detection confidence |

### GovernanceCheckResult

**Location**: `packages/floe-core/src/floe_core/governance/types.py`

| Field | Type | Description |
|-------|------|-------------|
| `check_type` | `str` | "rbac", "secrets", "policies", "network" |
| `violations` | `list[Violation]` | Violations from this check |
| `duration_ms` | `float` | Check execution time |
| `metadata` | `dict[str, Any]` | Check-specific metadata |

## Modified Models

### Violation.policy_type (EXTENDED)

**Location**: `packages/floe-core/src/floe_core/enforcement/result.py:84`

```python
# Before:
policy_type: Literal["naming", "coverage", "documentation", "semantic", "custom", "data_contract"]

# After:
policy_type: Literal[
    "naming", "coverage", "documentation", "semantic", "custom", "data_contract",
    "rbac", "secret_scanning", "network_policy",
]
```

**Impact**: Additive change. Existing validators produce only existing types. New validators produce new types. No existing code breaks.

### VALID_POLICY_TYPES (EXTENDED)

**Location**: `packages/floe-core/src/floe_core/schemas/governance.py:596`

```python
VALID_POLICY_TYPES = frozenset({
    "naming", "coverage", "documentation", "semantic", "custom", "data_contract",
    "rbac", "secret_scanning", "network_policy",
})
```

### EnforcementSummary (EXTENDED)

**Location**: `packages/floe-core/src/floe_core/enforcement/result.py`

New fields (all default=0 for backward compatibility):
| Field | Type | Default |
|-------|------|---------|
| `rbac_violations` | `int` (ge=0) | `0` |
| `secret_violations` | `int` (ge=0) | `0` |
| `network_policy_violations` | `int` (ge=0) | `0` |

### EnforcementResultSummary (EXTENDED)

**Location**: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`

New fields (all optional/defaulted for backward compatibility):
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `rbac_principal` | `str \| None` | `None` | Authenticated principal name |
| `secrets_scanned` | `int` | `0` | Number of files scanned |

### GovernanceConfig (EXTENDED)

**Location**: `packages/floe-core/src/floe_core/schemas/manifest.py`

New fields (all optional for backward compatibility):
| Field | Type | Default |
|-------|------|---------|
| `rbac` | `RBACConfig \| None` | `None` |
| `secret_scanning` | `SecretScanningConfig \| None` | `None` |
| `network_policies` | `NetworkPoliciesConfig \| None` | `None` |

## Plugin Interface

### SecretScannerPlugin ABC

**Location**: `packages/floe-core/src/floe_core/plugins/secret_scanner.py`
**Entry Point**: `floe.secret_scanners`

```python
class SecretScannerPlugin(PluginMetadata):
    """Abstract base class for secret scanning plugins."""

    @abstractmethod
    def scan_file(self, file_path: Path, content: str) -> list[SecretFinding]:
        """Scan file content for secrets. Return findings."""
        ...

    @abstractmethod
    def scan_directory(
        self,
        directory: Path,
        exclude_patterns: list[str] | None = None,
    ) -> list[SecretFinding]:
        """Scan directory for secrets. Respects exclude patterns."""
        ...

    @abstractmethod
    def get_supported_patterns(self) -> list[str]:
        """Return list of pattern names this scanner detects."""
        ...
```

## Inheritance Rules (3-Tier Mode)

GovernanceConfig follows existing inheritance: enterprise sets floor, domain can escalate.

| Field | Inheritance | Strengthening Direction |
|-------|-------------|------------------------|
| `policy_enforcement_level` | Enterprise floor | off < warn < strict |
| `rbac.enabled` | Enterprise floor | False < True |
| `rbac.required_role` | Enterprise floor | None < any value |
| `secret_scanning.enabled` | Enterprise floor | False < True |
| `secret_scanning.severity` | Enterprise floor | warning < error |
| `network_policies.enabled` | Enterprise floor | False < True |
| `network_policies.default_deny` | Enterprise floor | False < True |

## Error Code Registry

### Existing Ranges
- E2xx: Naming violations
- E210-E211: Coverage violations
- E220-E222: Documentation violations
- E3xx: Semantic violations
- E4xx: Custom rule violations

### New Ranges (Epic 3E)
- **E501**: Missing identity token (no FLOE_TOKEN and no --principal)
- **E502**: Expired identity token
- **E503**: Invalid identity token (signature, issuer)
- **E504**: Insufficient role (principal lacks required_role)
- **E505**: Identity provider unreachable
- **E601**: AWS Access Key ID detected
- **E602**: Hardcoded password detected
- **E603**: API key/token detected
- **E604**: Private key (RSA/EC) detected
- **E605**: High-entropy string detected
- **E606**: Custom secret pattern matched
- **E701**: Network policy generation failed
- **E702**: Default-deny policy conflict

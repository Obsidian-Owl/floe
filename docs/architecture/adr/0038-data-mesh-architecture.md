# ADR-0038: Data Mesh Architecture

## Status

Accepted

## Context

floe must support organizations at vastly different scales and structures:

1. **Single-team startup** - 5 data engineers, one platform, direct collaboration
2. **Multi-team enterprise** - Shared platform team, multiple data teams, standardized tooling
3. **Data Mesh organization** - Federated domains, autonomous product teams, domain-specific governance

Traditional data platforms fail at this range:
- **Centralized platforms** work for single/multi-team but don't scale to Data Mesh (100+ domains)
- **Domain-specific platforms** work for Data Mesh but create massive overhead for small teams
- **Separate codebases** for each model require rewrites when scaling

**The tension:** We need ONE architecture that supports both extremes without rewriting.

### What is Data Mesh?

Data Mesh is an organizational pattern with four principles (Zhamak Dehghani):

1. **Domain Ownership** - Domains own their data products (not central data team)
2. **Data as a Product** - Treat data like software products (SLOs, versioning, documentation)
3. **Self-Service Platform** - Platform team enables domains (not controls them)
4. **Federated Computational Governance** - Policies set centrally, enforced automatically

**Key insight:** Data Mesh requires **federated autonomy** while maintaining **enterprise governance**.

### Current Problem: Two-Tier Configuration Only

floe currently supports two-tier configuration:

```yaml
# manifest.yaml (Platform Team)
plugins:
  compute: snowflake
  catalog: polaris

# floe.yaml (Data Team)
transforms:
  - type: dbt
    path: models/
```

**This works for:**
- Single-team startup (one platform, one team)
- Multi-team enterprise (one platform, many teams with same governance)

**This FAILS for Data Mesh:**
- No domain-level governance (sales domain vs marketing domain policies differ)
- No enterprise-wide defaults (approved plugins must be defined per-platform)
- No inheritance model (domain can't override enterprise defaults)

### Data Mesh Organizational Structure

```
┌─────────────────────────────────────────────────────────────────┐
│  ENTERPRISE                                                      │
│                                                                  │
│  CTO Office                                                      │
│  - Sets enterprise-wide governance                               │
│  - Approves plugins (DuckDB, Snowflake allowed)                 │
│  - Enforces security policies (PII encryption)                   │
│  - Defines observability backend (Datadog)                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  DOMAIN: Sales  │ │ DOMAIN: Marketing│ │ DOMAIN: Finance │
│                 │ │                  │ │                 │
│  Domain Owner   │ │  Domain Owner    │ │ Domain Owner    │
│  - Approves     │ │  - Approves      │ │ - Approves      │
│    products     │ │    products      │ │    products     │
│  - Domain SLOs  │ │  - Domain SLOs   │ │  - Domain SLOs  │
│  - Custom       │ │  - Custom        │ │  - Custom       │
│    policies     │ │    policies      │ │    policies     │
└────────┬────────┘ └────────┬─────────┘ └────────┬────────┘
         │                   │                    │
    ┌────┼────┐         ┌────┼────┐         ┌────┼────┐
    ▼    ▼    ▼         ▼    ▼    ▼         ▼    ▼    ▼
  P1   P2   P3        P4   P5   P6        P7   P8   P9
  (Data Products)     (Data Products)     (Data Products)
```

**Hierarchy:**
- **Enterprise**: 1 (CTO office, platform team)
- **Domains**: 3-50 (sales, marketing, finance, operations, etc.)
- **Products**: 10-500+ per domain (customer-360, sales-forecast, etc.)

**Requirements:**
- Enterprise sets baseline governance (ALL domains inherit)
- Domains add domain-specific policies (only their products inherit)
- Products focus on data transformation (inherit everything)

## Decision

Implement **Data Mesh support via unified Manifest schema with scope field**.

### Unified Manifest Schema

**One Pydantic model, not separate types:**

```python
from pydantic import BaseModel
from typing import Literal

class Manifest(BaseModel):
    """Unified manifest schema for 2-tier AND 3-tier configuration.

    scope field determines usage:
    - scope: None → 2-tier (single platform, no Data Mesh)
    - scope: "enterprise" → 3-tier (enterprise-level defaults)
    - scope: "domain" → 3-tier (domain-level overrides)
    """

    scope: Literal["enterprise", "domain"] | None = None  # Key field

    # Platform configuration (same fields for all scopes)
    plugins: dict[str, str]
    approved_plugins: dict[str, str] | None = None
    observability: ObservabilityConfig
    governance: GovernanceConfig

    # Domain-specific (only when scope="domain")
    approved_products: list[str] | None = None
    parent_domain: str | None = None
```

**Key insight:** Same schema, different `scope` value. No breaking changes when scaling.

### Three-Tier Inheritance Model

```
┌─────────────────────────────────────────────────────────────────┐
│  enterprise-manifest.yaml (scope: enterprise)                    │
│                                                                  │
│  approved_plugins:                                               │
│    compute: ["duckdb", "snowflake"]  # Enterprise whitelist     │
│  plugins:                                                        │
│    observability: datadog            # ALL domains use Datadog   │
│  governance:                                                     │
│    pii_encryption: required          # CANNOT override          │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Inherits ↓
┌─────────────────────────────────────────────────────────────────┐
│  domain-manifest.yaml (scope: domain)                            │
│                                                                  │
│  parent_manifest: oci://registry/enterprise-manifest:v1.0.0     │
│  plugins:                                                        │
│    compute: snowflake                # Domain choice from        │
│                                      # enterprise whitelist      │
│  approved_products:                                              │
│    - customer-360                    # Domain approves products  │
│    - sales-forecast                                              │
│  governance:                                                     │
│    data_retention_days: 90           # Domain-specific policy    │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Inherits ↓
┌─────────────────────────────────────────────────────────────────┐
│  floe.yaml (NO scope field)                              │
│                                                                  │
│  platform:                                                       │
│    ref: oci://registry/sales-domain-manifest:v2.1.0             │
│  transforms:                                                     │
│    - type: dbt                       # Inherits Snowflake        │
│      path: models/                   # Inherits Datadog          │
│                                      # Inherits PII encryption   │
└─────────────────────────────────────────────────────────────────┘
```

**Inheritance Rules:**

| Field | Enterprise | Domain | Product | Mergeable? |
|-------|------------|--------|---------|------------|
| `approved_plugins` | Define | Inherit | Inherit | No (immutable) |
| `plugins.observability` | Define | Inherit | Inherit | No (immutable) |
| `governance.pii_encryption` | Define | Inherit | Inherit | No (security) |
| `plugins.compute` | Whitelist | Select | Inherit | No (platform choice) |
| `governance.data_retention_days` | Default | Override | Inherit | Yes (domain-specific) |
| `approved_products` | N/A | Define | Inherit | No (domain controls) |

**Key principles:**
- **Security policies**: Enterprise-defined, CANNOT be overridden
- **Plugin selection**: Domain selects from enterprise whitelist
- **Domain policies**: Domain-specific governance (retention, SLOs)
- **Product focus**: Products only define transforms, inherit everything

### Two-Tier vs Three-Tier

**Two-Tier (No Data Mesh):**

```yaml
# manifest.yaml (scope: None - default)
plugins:
  compute: duckdb
  observability: jaeger

# floe.yaml
platform:
  ref: oci://registry/platform-manifest:v1.0.0
transforms:
  - type: dbt
    path: models/
```

**Three-Tier (Data Mesh):**

```yaml
# enterprise-manifest.yaml (scope: enterprise)
scope: enterprise
approved_plugins:
  compute: ["duckdb", "snowflake"]
plugins:
  observability: datadog

# sales-domain-manifest.yaml (scope: domain)
scope: domain
parent_manifest: oci://registry/enterprise-manifest:v1.0.0
plugins:
  compute: snowflake  # From enterprise whitelist
approved_products: ["customer-360"]

# floe.yaml (same as 2-tier!)
platform:
  ref: oci://registry/sales-domain-manifest:v2.0.0
transforms:
  - type: dbt
    path: models/
```

**Key insight:** floe.yaml is IDENTICAL in 2-tier and 3-tier. Scaling is transparent.

## Consequences

### Positive

- **No rewrite when scaling** - 2-tier → 3-tier is adding manifests, not changing code
- **Federated autonomy** - Domains control product approval, policies
- **Enterprise governance** - Security/compliance enforced across all domains
- **Composability** - Unified Manifest schema (ADR-0037 principle)
- **Progressive disclosure** - Start simple (2-tier), add complexity (3-tier) only when needed

### Negative

- **Increased complexity** - Three manifest layers vs one (for Data Mesh orgs)
- **Governance overhead** - Enterprise and domain teams must coordinate
- **Testing complexity** - Must test inheritance resolution logic
- **Documentation burden** - Explain 2-tier vs 3-tier to users

### Neutral

- **Not required** - Data Mesh is opt-in (scope field enables, but not required)
- **Gradual adoption** - Organizations can start 2-tier, migrate to 3-tier later
- **Industry alignment** - Follows Zhamak Dehghani's Data Mesh principles

## Implementation Details

### Manifest Resolution Algorithm

```python
def resolve_manifest(product_manifest: DataProduct) -> ResolvedManifest:
    """Resolve data product manifest with 2-tier or 3-tier inheritance.

    Algorithm:
    1. Load platform manifest (from product_manifest.platform.ref)
    2. If platform has scope="domain":
       - Load parent_manifest (enterprise)
       - Merge: enterprise ← domain ← product
    3. Else (scope=None):
       - Merge: platform ← product
    4. Validate: Domain plugins in enterprise whitelist
    5. Return: ResolvedManifest with all inherited config
    """
    platform = load_manifest(product_manifest.platform.ref)

    if platform.scope == "domain":
        # Three-tier: Enterprise → Domain → Product
        enterprise = load_manifest(platform.parent_manifest)
        return merge_manifests(
            base=enterprise,
            domain=platform,
            product=product_manifest
        )
    else:
        # Two-tier: Platform → Product
        return merge_manifests(
            base=platform,
            product=product_manifest
        )
```

### Merge Strategy

```python
def merge_manifests(
    base: Manifest,
    domain: Manifest | None = None,
    product: DataProduct
) -> ResolvedManifest:
    """Merge manifests with inheritance rules.

    Rules:
    - approved_plugins: base only (immutable)
    - plugins: domain selects from base whitelist
    - governance: merge with domain overrides
    - Security policies: base only (cannot override)
    """
    resolved = ResolvedManifest()

    # Immutable fields (enterprise only)
    resolved.approved_plugins = base.approved_plugins
    resolved.pii_encryption = base.governance.pii_encryption

    # Domain selections (from whitelist)
    if domain:
        validate_plugin_approved(domain.plugins, base.approved_plugins)
        resolved.plugins = domain.plugins
    else:
        resolved.plugins = base.plugins

    # Mergeable governance
    resolved.governance = merge_governance(
        base.governance,
        domain.governance if domain else None
    )

    return resolved
```

### Validation Rules

**At compile-time:**
1. Domain `plugins.compute` MUST be in enterprise `approved_plugins.compute`
2. Enterprise `governance.pii_encryption` CANNOT be overridden by domain
3. Domain `approved_products` MUST include the product being compiled
4. Product `platform.ref` MUST resolve to valid manifest (OCI artifact)

## Data Mesh Principles Alignment

### 1. Domain Ownership

**Enabled by:**
- Domain manifests define `approved_products` (domain controls product lifecycle)
- Domain-specific governance (`data_retention_days`, SLOs)
- Domain selects compute from enterprise whitelist (autonomy within guardrails)

### 2. Data as a Product

**Enabled by:**
- floe.yaml defines transforms, schedules, dependencies
- Platform enforces product contracts (ODCS v3 via DataContractPlugin)
- Product metadata (name, version, description) required

### 3. Self-Service Platform

**Enabled by:**
- Platform team provides enterprise manifest (approved plugins, observability)
- Domains self-service: select compute, approve products, set policies
- Products self-service: define transforms, no platform approval needed

### 4. Federated Computational Governance

**Enabled by:**
- Enterprise sets policies (PII encryption, approved plugins)
- Compiler enforces at build-time (domain cannot bypass)
- PolicyEnforcer plugins validate governance rules
- Automated enforcement (not manual reviews)

## Migration Path

### Phase 1: Two-Tier (Current State)

```yaml
# manifest.yaml
plugins:
  compute: duckdb

# floe.yaml
platform:
  ref: oci://registry/platform-manifest:v1.0.0
```

### Phase 2: Add Enterprise Manifest (No Breaking Changes)

```yaml
# enterprise-manifest.yaml (NEW)
scope: enterprise
approved_plugins:
  compute: ["duckdb", "snowflake"]
plugins:
  observability: datadog

# manifest.yaml (UPDATED to reference enterprise)
scope: domain  # Added scope field
parent_manifest: oci://registry/enterprise-manifest:v1.0.0
plugins:
  compute: duckdb  # Must be in enterprise whitelist

# floe.yaml (UNCHANGED)
platform:
  ref: oci://registry/platform-manifest:v1.0.0
```

**Key:** floe.yaml does NOT change. Backward compatible.

### Phase 3: Add Domain Manifests (Data Mesh)

```yaml
# enterprise-manifest.yaml (SAME)
scope: enterprise
approved_plugins:
  compute: ["duckdb", "snowflake"]

# sales-domain-manifest.yaml (NEW)
scope: domain
parent_manifest: oci://registry/enterprise-manifest:v1.0.0
plugins:
  compute: snowflake
approved_products: ["customer-360"]

# marketing-domain-manifest.yaml (NEW)
scope: domain
parent_manifest: oci://registry/enterprise-manifest:v1.0.0
plugins:
  compute: duckdb
approved_products: ["campaign-analytics"]

# floe.yaml (UPDATED ref only)
platform:
  ref: oci://registry/sales-domain-manifest:v2.0.0  # Changed ref
transforms:
  - type: dbt
    path: models/
```

**Key:** Only `platform.ref` changes. No structural changes to floe.yaml.

## Anti-Patterns

### DON'T: Create separate Manifest types per tier

```python
# ❌ BAD: Separate types cause breaking changes
class EnterpriseManifest(BaseModel):
    approved_plugins: dict[str, list[str]]

class DomainManifest(BaseModel):
    parent_manifest: str
    plugins: dict[str, str]

# Scaling from 2-tier to 3-tier = rewrite
```

### DON'T: Allow domain to override security policies

```yaml
# ❌ BAD: Domain overrides enterprise security
# enterprise-manifest.yaml
governance:
  pii_encryption: required

# domain-manifest.yaml
governance:
  pii_encryption: optional  # FORBIDDEN!
```

### DO: Use unified Manifest with scope field

```python
# ✅ GOOD: One type, scope field differentiates
class Manifest(BaseModel):
    scope: Literal["enterprise", "domain"] | None = None
    # Same fields for all scopes

# Scaling from 2-tier to 3-tier = add manifests, change refs
```

## Testing Strategy

### Unit Tests

```python
def test_two_tier_resolution():
    """Test 2-tier manifest resolution."""
    platform = Manifest(plugins={"compute": "duckdb"})
    product = DataProduct(platform={"ref": "platform-manifest"})

    resolved = resolve_manifest(product)
    assert resolved.plugins["compute"] == "duckdb"


def test_three_tier_resolution():
    """Test 3-tier manifest resolution with inheritance."""
    enterprise = Manifest(
        scope="enterprise",
        approved_plugins={"compute": ["duckdb", "snowflake"]},
    )
    domain = Manifest(
        scope="domain",
        parent_manifest="enterprise-manifest",
        plugins={"compute": "snowflake"},
    )
    product = DataProduct(platform={"ref": "domain-manifest"})

    resolved = resolve_manifest(product)
    assert resolved.plugins["compute"] == "snowflake"
    assert "duckdb" in resolved.approved_plugins["compute"]
```

### Integration Tests

```python
def test_data_mesh_validation():
    """Test domain cannot override enterprise security."""
    enterprise = Manifest(
        scope="enterprise",
        governance={"pii_encryption": "required"},
    )
    domain = Manifest(
        scope="domain",
        governance={"pii_encryption": "optional"},  # Attempt override
    )

    with pytest.raises(ValidationError, match="Cannot override security policy"):
        merge_manifests(base=enterprise, domain=domain)
```

## Security Considerations

### Enterprise Policies are Immutable

- **PII encryption**: Enterprise requires, domain CANNOT disable
- **Approved plugins**: Enterprise whitelists, domain CANNOT add
- **Audit logging**: Enterprise enables, domain CANNOT disable
- **Network policies**: Enterprise defines, domain CANNOT bypass

### Domain Autonomy Within Guardrails

- **Plugin selection**: Domain selects from enterprise whitelist
- **Data retention**: Domain sets retention (within enterprise min/max)
- **Product approval**: Domain controls product lifecycle
- **Custom policies**: Domain adds (cannot remove enterprise policies)

## Open Questions

### Q: Can a product belong to multiple domains?

**A:** No. Each product has ONE domain. Cross-domain products require data contracts and catalog sharing.

### Q: Can domains share plugins (e.g., Snowflake warehouse)?

**A:** Yes. Multiple domains can select same plugin. Catalog namespacing ensures isolation.

### Q: What if domain wants plugin NOT in enterprise whitelist?

**A:** Domain requests enterprise to add to whitelist. Enterprise evaluates security, cost, support.

## References

- [ADR-0037: Composability Principle](0037-composability-principle.md) - Unified schema rationale
- [ADR-0016: Platform Enforcement Architecture](0016-platform-enforcement-architecture.md) - Compile-time enforcement
- [platform-enforcement.md](../platform-enforcement.md) - Three-tier inheritance details
- **Industry References:**
  - [Data Mesh Principles (Zhamak Dehghani)](https://martinfowler.com/articles/data-mesh-principles.html)
  - [Data Mesh: Delivering Data-Driven Value at Scale (O'Reilly)](https://www.oreilly.com/library/view/data-mesh/9781492092384/)
  - [Thoughtworks Technology Radar: Data Mesh](https://www.thoughtworks.com/radar/techniques/data-mesh)

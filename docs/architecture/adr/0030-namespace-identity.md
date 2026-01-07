# ADR-0030: Namespace-Based Identity Model

## Status

Accepted

## Context

Data products in floe currently lack a mechanism to prevent naming collisions in distributed Data Mesh environments. When multiple teams independently deploy data products, there is no registry or validation to ensure unique identification.

### The Problem

**Scenario**: Two teams independently create data products:
- Team A: `data-product.yaml` with `name: sales-customers`
- Team B: `data-product.yaml` with `name: sales-customers`

Both compile and deploy successfully, but:
- Tables overwrite each other
- Contracts conflict
- Lineage becomes corrupted
- No error is raised

### Root Cause Analysis

The identity problem exists at ALL levels of the architecture:

```
Level           | Identity           | Collision Prevention
----------------|--------------------|-----------------------
Data Product    | name (loose)       | NONE
Data Contract   | name + version     | NONE
Domain          | name               | NONE
Table           | namespace.table    | Catalog (partial)
```

Currently:
- Data products have loose identity (just `name` + `version`)
- No product registry exists
- No contract registry exists
- Multiple repositories can claim the same product name
- The only collision detection is at the Iceberg table level (too late)

### Requirements

1. Data products must have globally unique identifiers
2. Identity must be verifiable at compile-time (fail fast)
3. First-to-register wins (deterministic ownership)
4. Solution must work with ANY Iceberg-compatible catalog (Polaris, Unity, Glue, Hive, Nessie)
5. No central registration service required (use existing infrastructure)
6. Contracts must inherit identity from their parent product

## Decision

Implement a **namespace-based identity model** using Iceberg catalog namespace properties as the registry:

1. **Product Identity**: `{domain}.{product}` (e.g., `sales.customer_360`)
2. **Contract Identity**: `{domain}.{product}/{contract}:{version}` (e.g., `sales.customer_360/customers:1.0.0`)
3. **Registry**: Iceberg catalog namespace properties (no new infrastructure)
4. **Enforcement**: Compile-time via PolicyEnforcer + CatalogPlugin

### Identity Resolution

```
Product ID:   {domain}.{product}
              └──────┬──────────┘
              "sales.customer_360"

Contract ID:  {domain}.{product}/{contract}:{version}
              └──────────────────┬─────────────────────┘
              "sales.customer_360/customers:1.0.0"

Table Path:   {domain}/{layer}/{product}/{table}
              └──────────────┬───────────────────┘
              "sales/gold/customer_360/customers"
```

### Namespace Structure in Catalog

The Iceberg catalog namespace becomes the product registry:

```
Catalog: floe-data
├── sales (domain namespace)
│   ├── Properties:
│   │   ├── floe.domain.name = "sales"
│   │   └── floe.domain.owner = "sales-platform@acme.com"
│   │
│   ├── sales.customer_360 (product namespace)
│   │   ├── Properties:
│   │   │   ├── floe.product.name = "customer_360"
│   │   │   ├── floe.product.domain = "sales"
│   │   │   ├── floe.product.owner = "sales-analytics@acme.com"
│   │   │   ├── floe.product.repo = "github.com/acme/sales-customer-360"
│   │   │   ├── floe.product.version = "1.2.3"
│   │   │   └── floe.product.registered_at = "2026-01-03T10:00:00Z"
│   │   │
│   │   ├── floe.contracts = '["customers:1.0.0", "orders:2.1.0"]'
│   │   │
│   │   └── Tables:
│   │       ├── bronze.raw_customers
│   │       ├── silver.customers
│   │       └── gold.customers
│   │
│   └── sales.order_analytics (another product)
│       └── Properties: ...
```

### Property Prefix Convention

All floe-managed properties use the `floe.` prefix:

| Property | Description |
|----------|-------------|
| `floe.domain.name` | Domain identifier |
| `floe.domain.owner` | Domain owner email |
| `floe.product.name` | Product name |
| `floe.product.domain` | Parent domain |
| `floe.product.owner` | Product owner email |
| `floe.product.repo` | Source repository (ownership proof) |
| `floe.product.version` | Current deployed version |
| `floe.product.registered_at` | Initial registration timestamp |
| `floe.contracts` | JSON array of registered contracts |

### CatalogPlugin Extension

Add identity management methods to `CatalogPlugin`:

```python
class CatalogPlugin(ABC):
    """Extended interface for catalog operations with identity management."""

    # === Existing methods... ===

    # === NEW: Product Registration ===

    @abstractmethod
    def register_product_namespace(
        self,
        namespace: str,              # "sales.customer_360"
        product_metadata: ProductMetadata,
    ) -> RegistrationResult:
        """
        Register a data product by creating/claiming a namespace.

        First-to-register wins. Returns conflict if namespace exists
        with different owner (repository).

        Args:
            namespace: Product namespace (domain.product_name)
            product_metadata: Product metadata including repository

        Returns:
            RegistrationResult with status (created, updated, conflict)
        """
        pass

    @abstractmethod
    def get_namespace_owner(self, namespace: str) -> str | None:
        """Get the repository owner of a namespace, or None if unregistered."""
        pass

    @abstractmethod
    def validate_product_identity(
        self,
        namespace: str,
        expected_repo: str,
    ) -> IdentityValidationResult:
        """
        Validate that the caller is the legitimate owner of a namespace.

        Args:
            namespace: Product namespace to validate
            expected_repo: Repository claiming ownership

        Returns:
            IdentityValidationResult with status:
              - VALID: Namespace owned by this repo
              - CONFLICT: Namespace owned by different repo
              - AVAILABLE: Namespace not yet registered
        """
        pass

    # === NEW: Contract Registration ===

    @abstractmethod
    def register_contract(
        self,
        namespace: str,
        contract_name: str,
        contract_version: str,
        schema_hash: str,
        metadata: ContractMetadata,
    ) -> RegistrationResult:
        """
        Register a contract version under a product namespace.

        Prerequisites:
          - Product namespace must exist
          - Caller must be namespace owner
          - Contract version must not already exist

        Args:
            namespace: Product namespace
            contract_name: Contract name
            contract_version: Semantic version
            schema_hash: SHA256 of contract schema (for drift detection)
            metadata: Contract metadata

        Returns:
            RegistrationResult with status
        """
        pass

    @abstractmethod
    def list_registered_contracts(
        self,
        namespace: str,
    ) -> list[RegisteredContract]:
        """List all contracts registered under a product namespace."""
        pass


@dataclass
class ProductMetadata:
    """Metadata stored in namespace properties."""
    name: str                    # "customer_360"
    domain: str                  # "sales"
    owner: str                   # "sales-analytics@acme.com"
    repository: str              # "github.com/acme/sales-customer-360"
    version: str                 # "1.2.3"
    registered_at: datetime


@dataclass
class RegistrationResult:
    """Result of a registration operation."""
    status: Literal["created", "updated", "conflict", "error"]
    message: str
    existing_owner: str | None = None  # If conflict


@dataclass
class IdentityValidationResult:
    """Result of identity validation."""
    status: Literal["valid", "conflict", "available"]
    owner: str | None
    repository: str | None


@dataclass
class ContractMetadata:
    """Contract metadata stored in catalog."""
    owner: str
    description: str | None
    registered_at: datetime


@dataclass
class RegisteredContract:
    """Contract registration info."""
    name: str
    version: str
    schema_hash: str
    registered_at: datetime
```

### Compile-Time Enforcement

Identity validation occurs during `floe compile`:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         floe compile                                         │
│                                                                              │
│  1. Parse data-product.yaml                                                  │
│     └── Extract: name, domain, version, repository                          │
│                                                                              │
│  2. Generate Product ID                                                      │
│     └── product_id = f"{domain}.{name}"                                      │
│                                                                              │
│  3. Check Catalog (via CatalogPlugin)                                        │
│     ├── catalog.validate_product_identity(product_id, repository)            │
│     │                                                                        │
│     ├── AVAILABLE → catalog.register_product_namespace(...)                  │
│     │              └── First registration, claim namespace                   │
│     │                                                                        │
│     ├── VALID → catalog.update_product_metadata(...)                         │
│     │          └── Owner match, update version/metadata                      │
│     │                                                                        │
│     └── CONFLICT → FAIL COMPILATION                                          │
│                   └── "Namespace 'sales.customer_360' owned by               │
│                        'github.com/acme/other-repo', not                     │
│                        'github.com/acme/sales-customer-360'"                 │
│                                                                              │
│  4. Register Contracts                                                       │
│     └── For each contract in data_contracts:                                 │
│         catalog.register_contract(product_id, name, version, hash)           │
│                                                                              │
│  5. Continue with normal compilation...                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### PolicyEnforcer Integration

Add identity validation to `PolicyEnforcer`:

```python
class PolicyEnforcer:
    """Extended with identity validation."""

    def validate_product_identity(
        self,
        product: DataProduct,
        catalog: CatalogPlugin,
    ) -> list[EnforcementViolation]:
        """
        Validate product can claim its namespace.
        Called during compile phase.
        """
        product_id = f"{product.domain}.{product.name}"

        result = catalog.validate_product_identity(
            namespace=product_id,
            expected_repo=product.repository,
        )

        if result.status == "conflict":
            return [
                EnforcementViolation(
                    severity=Severity.ERROR,
                    code="IDENTITY_CONFLICT",
                    message=f"Namespace '{product_id}' is owned by "
                            f"'{result.repository}', not '{product.repository}'",
                    resolution="Choose a different product name or contact "
                              f"the namespace owner: {result.owner}",
                )
            ]

        return []
```

### Universal Catalog Support

The Iceberg specification defines namespace properties as extensible key-value metadata. All Iceberg-compatible catalogs support this:

| Catalog | Implementation | Notes |
|---------|---------------|-------|
| Polaris | REST API `createNamespace()` with properties | Native support |
| Unity Catalog | `CREATE NAMESPACE ... WITH DBPROPERTIES` | DBPROPERTIES |
| AWS Glue | `create_database(Parameters={...})` | Database Parameters |
| Hive Metastore | `ALTER DATABASE ... SET DBPROPERTIES` | DBPROPERTIES |
| Nessie | Native namespace properties | Version-aware |

**Example implementations:**

```python
# Polaris (REST Catalog)
client.create_namespace("sales.customer_360", {
    "floe.product.owner": "sales-analytics@acme.com",
    "floe.product.repo": "github.com/acme/sales-customer-360",
})

# Unity Catalog
spark.sql("""
    CREATE NAMESPACE sales.customer_360
    WITH DBPROPERTIES (
        'floe.product.owner' = 'sales-analytics@acme.com',
        'floe.product.repo' = 'github.com/acme/sales-customer-360'
    )
""")

# AWS Glue
glue.create_database(
    DatabaseInput={
        "Name": "sales_customer_360",
        "Parameters": {
            "floe.product.owner": "sales-analytics@acme.com",
            "floe.product.repo": "github.com/acme/sales-customer-360",
        }
    }
)
```

### Domain Governance (Optional Enhancement)

For Data Mesh deployments, the domain manifest can serve as a secondary registry:

```yaml
# domain-manifest.yaml
apiVersion: floe.dev/v1
kind: DomainManifest
metadata:
  name: sales

governance:
  product_registration:
    mode: open                    # open | approval_required
    allowed_repositories:
      - "github.com/acme/sales-*" # Glob pattern

registered_products:              # Auto-updated by compile
  - name: customer_360
    repository: github.com/acme/sales-customer-360
    registered_at: "2026-01-03T10:00:00Z"
  - name: order_analytics
    repository: github.com/acme/sales-order-analytics
    registered_at: "2026-01-02T09:00:00Z"
```

**Two registration models:**

| Model | Registry | Enforcement | Use Case |
|-------|----------|-------------|----------|
| Catalog-Only | Iceberg namespace properties | Compile-time check | Simple deployments |
| Domain + Catalog | Domain manifest + catalog | Two-phase validation | Data Mesh governance |

### data-product.yaml Extension

Add `repository` field for ownership verification:

```yaml
# data-product.yaml
apiVersion: floe.dev/v1
kind: DataProduct
metadata:
  name: customer-360
  version: "1.2.3"
  owner: sales-analytics@acme.com
  domain: sales
  repository: github.com/acme/sales-customer-360  # NEW: Ownership proof
```

The `repository` field:
- Must match the source control origin
- Used to verify namespace ownership
- Prevents accidental collisions from copy-paste

### CompiledArtifacts Extension

Add product identity to compiled artifacts:

```json
{
  "version": "0.1.0",
  "metadata": {
    "compiled_at": "2026-01-03T10:00:00Z",
    "product_name": "customer-360",
    "product_version": "1.2.3"
  },
  "identity": {
    "product_id": "sales.customer_360",
    "repository": "github.com/acme/sales-customer-360",
    "namespace_registered": true,
    "registration_timestamp": "2026-01-01T00:00:00Z"
  }
}
```

## Consequences

### Positive

1. **Collision prevention**: Deterministic first-to-register ownership
2. **Compile-time safety**: Conflicts detected before deployment
3. **No new infrastructure**: Uses existing Iceberg catalog capabilities
4. **Universal support**: Works with all Iceberg-compatible catalogs
5. **Auditable**: Registration timestamps provide audit trail
6. **Decentralized**: No central registration service required

### Negative

1. **Repository coupling**: Products must declare their source repository
2. **Catalog dependency**: Requires catalog access during compile
3. **Property pollution**: Adds floe.* properties to namespaces
4. **Migration effort**: Existing products need namespace registration

### Neutral

1. **First-to-register wins**: Deterministic but no appeals process
2. **Domain namespace required**: Products must belong to a domain
3. **Case sensitivity**: Namespace matching is catalog-dependent

## Migration

For existing deployments without namespace registration:

1. **Phase 1 (Warn)**: Log warnings for unregistered products
2. **Phase 2 (Register)**: Auto-register existing products on first compile
3. **Phase 3 (Enforce)**: Require registration, fail on conflicts

```yaml
# platform-manifest.yaml
identity:
  enforcement: warn    # off | warn | register | enforce
  auto_register: true  # Auto-register unregistered products
```

## References

- [Iceberg REST Catalog Specification](https://iceberg.apache.org/docs/latest/rest-catalog/)
- [ADR-0021: Data Architecture Patterns](./0021-data-architecture-patterns.md) - Namespace structure
- [ADR-0026: Data Contract Architecture](./0026-data-contract-architecture.md) - Contract identity
- [ADR-0016: Platform Enforcement Architecture](./0016-platform-enforcement-architecture.md) - PolicyEnforcer

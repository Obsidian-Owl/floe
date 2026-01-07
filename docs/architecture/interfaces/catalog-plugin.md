# CatalogPlugin

**Purpose**: Iceberg table catalog management and product identity
**Location**: `floe_core/interfaces/catalog.py`
**Entry Point**: `floe.catalogs`
**ADR**: [ADR-0008: Repository Split](../adr/0008-repository-split.md), [ADR-0030: Namespace-Based Identity](../adr/0030-namespace-identity.md)

CatalogPlugin abstracts Iceberg catalog implementations (Polaris, Glue, Hive, Unity, Nessie), providing consistent namespace management, table operations, and credential vending. It also implements the namespace-based product identity model from ADR-0030.

## Interface Definition

```python
# floe_core/interfaces/catalog.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from pyiceberg.catalog import Catalog
from pyiceberg.table import Table

# ─────────────────────────────────────────────────────────────────
# Identity Management Types (ADR-0030)
# ─────────────────────────────────────────────────────────────────

@dataclass
class ProductMetadata:
    """Metadata stored in namespace properties for product registration.

    See ADR-0030 for the namespace-based identity model.
    """
    name: str                    # "customer_360"
    domain: str                  # "sales"
    owner: str                   # "sales-analytics@acme.com"
    repository: str              # "github.com/acme/sales-customer-360"
    version: str                 # "1.2.3"
    registered_at: datetime


@dataclass
class RegistrationResult:
    """Result of a product or contract registration operation."""
    status: Literal["created", "updated", "conflict", "error"]
    message: str
    existing_owner: str | None = None  # If conflict, who owns it


@dataclass
class IdentityValidationResult:
    """Result of validating product identity against catalog."""
    status: Literal["valid", "conflict", "available"]
    owner: str | None            # Email of owner (if registered)
    repository: str | None       # Repository (if registered)


@dataclass
class ContractMetadata:
    """Metadata for contract registration in catalog."""
    owner: str
    description: str | None
    registered_at: datetime


@dataclass
class RegisteredContract:
    """Contract registration information from catalog."""
    name: str
    version: str
    schema_hash: str
    registered_at: datetime


class CatalogPlugin(ABC):
    """Interface for Iceberg catalogs (Polaris, Glue, Hive, Unity, Nessie).

    Provides:
    - Standard Iceberg operations (namespace, tables, credentials)
    - Product identity management (ADR-0030)
    - Contract registration

    All catalog plugins use the `floe.*` property prefix for managed metadata.
    """

    name: str
    version: str

    # ─────────────────────────────────────────────────────────────────
    # Standard Catalog Operations
    # ─────────────────────────────────────────────────────────────────

    @abstractmethod
    def connect(self, config: dict) -> Catalog:
        """Connect to catalog and return PyIceberg Catalog instance.

        Args:
            config: Catalog configuration (URI, credentials, etc.)

        Returns:
            PyIceberg Catalog instance
        """
        pass

    @abstractmethod
    def create_namespace(self, namespace: str, properties: dict | None = None) -> None:
        """Create a namespace in the catalog.

        Args:
            namespace: Namespace name (e.g., "bronze", "silver", "gold")
            properties: Optional namespace properties
        """
        pass

    @abstractmethod
    def list_namespaces(self) -> list[str]:
        """List all namespaces in the catalog."""
        pass

    @abstractmethod
    def get_namespace_properties(self, namespace: str) -> dict[str, str]:
        """Get properties for a namespace.

        Args:
            namespace: Namespace identifier

        Returns:
            Dict of namespace properties (empty if namespace doesn't exist)
        """
        pass

    @abstractmethod
    def update_namespace_properties(
        self,
        namespace: str,
        updates: dict[str, str],
        removals: list[str] | None = None
    ) -> None:
        """Update properties for a namespace.

        Args:
            namespace: Namespace identifier
            updates: Properties to add/update
            removals: Property keys to remove
        """
        pass

    @abstractmethod
    def get_table(self, identifier: str) -> Table:
        """Get an Iceberg table by identifier.

        Args:
            identifier: Table identifier (e.g., "bronze.customers")
        """
        pass

    @abstractmethod
    def vend_credentials(
        self,
        table_path: str,
        operations: list[str]
    ) -> dict:
        """Vend short-lived credentials for table access.

        Args:
            table_path: Path to the table
            operations: List of operations (READ, WRITE)

        Returns:
            Dict with temporary credentials
        """
        pass

    # ─────────────────────────────────────────────────────────────────
    # Product Identity Management (ADR-0030)
    # ─────────────────────────────────────────────────────────────────

    @abstractmethod
    def register_product_namespace(
        self,
        namespace: str,
        product_metadata: ProductMetadata,
    ) -> RegistrationResult:
        """Register a data product by creating/claiming a namespace.

        First-to-register wins. If the namespace exists with a different
        repository owner, returns a conflict status.

        This method:
        1. Checks if namespace exists
        2. If not, creates namespace with floe.product.* properties
        3. If yes, validates repository ownership
        4. Returns appropriate status

        Args:
            namespace: Product namespace (e.g., "sales.customer_360")
            product_metadata: Product metadata to store in properties

        Returns:
            RegistrationResult with status:
              - created: New namespace created
              - updated: Existing namespace updated (same owner)
              - conflict: Namespace owned by different repository
              - error: Registration failed

        Example:
            result = catalog.register_product_namespace(
                namespace="sales.customer_360",
                product_metadata=ProductMetadata(
                    name="customer_360",
                    domain="sales",
                    owner="sales-analytics@acme.com",
                    repository="github.com/acme/sales-customer-360",
                    version="1.2.3",
                    registered_at=datetime.utcnow(),
                )
            )
            if result.status == "conflict":
                raise IdentityConflictError(result.message)
        """
        pass

    @abstractmethod
    def get_namespace_owner(self, namespace: str) -> str | None:
        """Get the repository owner of a namespace.

        Args:
            namespace: Namespace to check

        Returns:
            Repository URL if registered, None if not registered
        """
        pass

    @abstractmethod
    def validate_product_identity(
        self,
        namespace: str,
        expected_repo: str,
    ) -> IdentityValidationResult:
        """Validate that the caller is the legitimate owner of a namespace.

        This is the primary method for identity verification during compile.

        Args:
            namespace: Product namespace to validate
            expected_repo: Repository claiming ownership

        Returns:
            IdentityValidationResult with status:
              - valid: Namespace owned by expected_repo
              - conflict: Namespace owned by different repository
              - available: Namespace not yet registered

        Example:
            result = catalog.validate_product_identity(
                namespace="sales.customer_360",
                expected_repo="github.com/acme/sales-customer-360",
            )
            match result.status:
                case "valid":
                    pass  # Continue compilation
                case "conflict":
                    raise IdentityConflictError(
                        f"Namespace owned by {result.repository}"
                    )
                case "available":
                    catalog.register_product_namespace(...)
        """
        pass

    # ─────────────────────────────────────────────────────────────────
    # Contract Registration (ADR-0030)
    # ─────────────────────────────────────────────────────────────────

    @abstractmethod
    def register_contract(
        self,
        namespace: str,
        contract_name: str,
        contract_version: str,
        schema_hash: str,
        metadata: ContractMetadata,
    ) -> RegistrationResult:
        """Register a contract version under a product namespace.

        Prerequisites:
          - Product namespace must exist
          - Caller must be namespace owner (verified separately)
          - Contract version must not already exist (immutable versions)

        The contract is stored as a JSON array in the namespace property
        `floe.contracts` for discoverability.

        Args:
            namespace: Product namespace (e.g., "sales.customer_360")
            contract_name: Contract name (e.g., "customers")
            contract_version: Semantic version (e.g., "1.0.0")
            schema_hash: SHA256 hash of contract schema (for drift detection)
            metadata: Contract metadata

        Returns:
            RegistrationResult with status:
              - created: New contract version registered
              - conflict: Contract version already exists
              - error: Registration failed

        Example:
            result = catalog.register_contract(
                namespace="sales.customer_360",
                contract_name="customers",
                contract_version="1.0.0",
                schema_hash="abc123...",
                metadata=ContractMetadata(
                    owner="sales-analytics@acme.com",
                    description="Customer master data contract",
                    registered_at=datetime.utcnow(),
                ),
            )
        """
        pass

    @abstractmethod
    def list_registered_contracts(
        self,
        namespace: str,
    ) -> list[RegisteredContract]:
        """List all contracts registered under a product namespace.

        Args:
            namespace: Product namespace

        Returns:
            List of registered contracts with versions
        """
        pass

    # ─────────────────────────────────────────────────────────────────
    # Orphan Detection and Reconciliation
    # ─────────────────────────────────────────────────────────────────

    @abstractmethod
    def list_orphaned_tables(
        self,
        namespace: str,
        orphan_types: list[str] | None = None,
    ) -> list["OrphanedTable"]:
        """Find tables that are orphaned in the given namespace.

        Orphan types:
          - storage: Files in storage without catalog entry
          - catalog: Catalog entry with missing storage
          - metadata: Table with corrupted metadata
          - unregistered: Table not owned by any data product

        Args:
            namespace: Namespace to scan
            orphan_types: Types to check (default: all)

        Returns:
            List of orphaned tables

        Example:
            orphans = catalog.list_orphaned_tables("sales.gold")
            for orphan in orphans:
                print(f"{orphan.table_name}: {orphan.orphan_type}")
        """
        pass

    @abstractmethod
    def reconcile_catalog(
        self,
        namespace: str,
        dry_run: bool = True,
        actions: list[str] | None = None,
    ) -> "ReconciliationResult":
        """Reconcile catalog with storage state.

        Actions:
          - delete-storage: Remove orphaned storage files
          - drop-catalog: Drop orphaned catalog entries
          - fix-metadata: Repair corrupted metadata

        Always runs in dry_run mode by default to prevent accidental data loss.

        Args:
            namespace: Namespace to reconcile
            dry_run: If True, report only without making changes
            actions: Actions to take (default: report only)

        Returns:
            ReconciliationResult with summary and details

        Example:
            # First, dry run
            result = catalog.reconcile_catalog("sales.gold", dry_run=True)
            print(f"Would remediate {len(result.orphans_found)} orphans")

            # Then execute with confirmation
            if confirm():
                result = catalog.reconcile_catalog(
                    "sales.gold",
                    dry_run=False,
                    actions=["delete-storage", "drop-catalog"]
                )
        """
        pass

    @abstractmethod
    def validate_table_health(
        self,
        table_identifier: str,
    ) -> tuple[bool, str]:
        """Validate that a table is healthy and accessible.

        Checks:
          - Catalog entry exists
          - Storage location accessible
          - Metadata is valid and readable
          - At least one snapshot exists

        Args:
            table_identifier: Full table identifier (e.g., "sales.gold.customers")

        Returns:
            Tuple of (is_healthy, message)

        Example:
            healthy, message = catalog.validate_table_health("sales.gold.customers")
            if not healthy:
                logger.warning(f"Table unhealthy: {message}")
        """
        pass
```

## Supporting Types

```python
@dataclass
class OrphanedTable:
    """An orphaned table detected during reconciliation."""
    namespace: str
    table_name: str
    orphan_type: Literal["storage", "catalog", "metadata", "unregistered"]
    location: str | None
    size_bytes: int | None
    last_modified: datetime | None
    error_message: str | None

@dataclass
class ReconciliationResult:
    """Result of a catalog reconciliation operation."""
    namespace: str
    tables_scanned: int
    orphans_found: list[OrphanedTable]
    orphans_remediated: list[str]
    storage_reclaimed_bytes: int
    errors: list[str]
    dry_run: bool
```

## Namespace Property Convention

All floe-managed properties use the `floe.` prefix to avoid conflicts:

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

## Catalog-Specific Implementations

Each catalog plugin implements the interface using the catalog's native property support:

| Catalog | Property Storage | Implementation Notes |
|---------|-----------------|---------------------|
| Polaris | `createNamespace(properties)` | REST API native |
| Unity Catalog | `DBPROPERTIES` | Spark SQL or REST |
| AWS Glue | `Database.Parameters` | Boto3 API |
| Hive Metastore | `DBPROPERTIES` | Spark SQL |
| Nessie | Namespace properties | Version-aware |

## Reference Implementations

| Plugin | Description |
|--------|-------------|
| `PolarisCatalogPlugin` | Apache Polaris REST catalog |
| `GlueCatalogPlugin` | AWS Glue Data Catalog |
| `HiveCatalogPlugin` | Hive Metastore |
| `UnityCatalogPlugin` | Databricks Unity Catalog |
| `NessieCatalogPlugin` | Project Nessie (git-like versioning) |

## Related Documents

- [ADR-0008: Repository Split](../adr/0008-repository-split.md)
- [ADR-0030: Namespace-Based Identity](../adr/0030-namespace-identity.md)
- [Plugin Architecture](../plugin-architecture.md)
- [StoragePlugin](storage-plugin.md) - For storage layer integration

# Catalog Reconciliation Guide

This guide covers procedures for detecting and managing orphaned tables in Iceberg catalogs.

---

## Overview

Orphaned tables occur when the catalog and storage state diverge:

| Scenario | Result |
|----------|--------|
| Table dropped from catalog but files remain in storage | Storage orphan |
| Compile/deploy fails after table creation | Catalog orphan |
| Metadata corruption or incomplete transactions | Drift |
| Manual interventions outside floe | Unknown state |

### Impact

- **Storage costs**: Orphaned files consume storage indefinitely
- **Governance risk**: Untracked data may contain PII
- **Query confusion**: Stale tables appear in discovery
- **Quota pressure**: Namespace quotas count orphaned tables

---

## Orphan Detection

### Types of Orphans

| Type | Definition | Detection Method |
|------|------------|------------------|
| **Storage Orphan** | Files in storage without catalog entry | Compare storage paths to catalog |
| **Catalog Orphan** | Catalog entry pointing to missing files | Validate storage location exists |
| **Metadata Orphan** | Table with corrupted/incomplete metadata | Metadata validation scan |
| **Namespace Orphan** | Empty namespace with no tables | List namespaces without tables |

### Manual Detection (CLI)

```bash
# List all tables in a namespace
floe catalog tables --namespace sales.gold

# Validate table accessibility (checks storage + metadata)
floe catalog validate --namespace sales.gold

# Output:
TABLE                    STATUS      ISSUE
sales.gold.customers     valid       -
sales.gold.orders        orphan      Storage path not found: s3://bucket/orders/
sales.gold.legacy_dim    orphan      Not in registered products

# List orphaned tables
floe catalog orphans --namespace sales.gold

# Output:
NAMESPACE      TABLE           TYPE             LAST_ACCESS
sales.gold     orders          storage_missing  2024-06-15
sales.gold     legacy_dim      unregistered     2024-01-03
```

### Automated Detection (Scheduled Job)

Configure a reconciliation job in `platform-manifest.yaml`:

```yaml
# platform-manifest.yaml
reconciliation:
  enabled: true
  schedule: "0 2 * * 0"  # Weekly at 2 AM Sunday
  namespaces:
    - "*"  # All namespaces, or list specific ones
  actions:
    - detect  # Required: always detect first
    # - remediate  # Optional: auto-cleanup (use with caution)
  notifications:
    slack: "#data-platform-alerts"
    email: platform-team@acme.com
  thresholds:
    orphan_count_warn: 10
    orphan_count_fail: 50
    orphan_size_gb_warn: 100
```

---

## Reconciliation Procedures

### Procedure 1: Storage Orphan Cleanup

**Scenario**: Files exist in object storage without corresponding catalog entry.

**Steps:**

1. **Identify orphaned paths**
   ```bash
   # List storage paths not in catalog
   floe catalog orphans --type storage --namespace sales.gold

   # Output:
   PATH                                    SIZE_GB   LAST_MODIFIED
   s3://bucket/sales/gold/old_table/       12.5      2024-01-15
   s3://bucket/sales/gold/test_data/       0.3       2024-05-20
   ```

2. **Review and backup (optional)**
   ```bash
   # Backup to quarantine location
   aws s3 cp --recursive s3://bucket/sales/gold/old_table/ \
       s3://bucket-quarantine/sales/gold/old_table/
   ```

3. **Delete orphaned files**
   ```bash
   # Dry run first
   floe catalog cleanup --type storage --namespace sales.gold --dry-run

   # Execute cleanup
   floe catalog cleanup --type storage --namespace sales.gold --confirm
   ```

4. **Verify**
   ```bash
   floe catalog orphans --type storage --namespace sales.gold
   # Expected: No orphans found
   ```

### Procedure 2: Catalog Orphan Cleanup

**Scenario**: Catalog entry points to non-existent storage location.

**Steps:**

1. **Identify orphaned entries**
   ```bash
   floe catalog orphans --type catalog --namespace sales.gold

   # Output:
   TABLE                    LOCATION                           ERROR
   sales.gold.orders        s3://bucket/sales/gold/orders/     StorageNotFound
   ```

2. **Attempt recovery (if data exists elsewhere)**
   ```bash
   # Check if data was moved
   aws s3 ls s3://bucket/sales/gold/ | grep orders

   # If found at different path, update catalog
   floe catalog repair --table sales.gold.orders \
       --new-location s3://bucket/sales/gold/orders_v2/
   ```

3. **Drop orphaned entry (if data is truly lost)**
   ```bash
   # Dry run
   floe catalog drop --table sales.gold.orders --dry-run

   # Execute
   floe catalog drop --table sales.gold.orders --confirm
   ```

### Procedure 3: Full Namespace Reconciliation

**Scenario**: Complete reconciliation of a namespace after incident.

```bash
# 1. Generate reconciliation report
floe catalog reconcile --namespace sales --report-only

# Output:
RECONCILIATION REPORT: sales
============================
Namespaces scanned: 3 (sales.bronze, sales.silver, sales.gold)
Tables validated: 47
Valid tables: 42
Orphaned tables: 5
  - Storage orphans: 2
  - Catalog orphans: 2
  - Metadata orphans: 1

Recommended actions:
  floe catalog cleanup --namespace sales --action delete-storage --count 2
  floe catalog cleanup --namespace sales --action drop-catalog --count 2
  floe catalog repair --namespace sales --action fix-metadata --count 1

Total storage to reclaim: 45.2 GB

# 2. Execute reconciliation (with dry-run)
floe catalog reconcile --namespace sales --dry-run

# 3. Execute reconciliation
floe catalog reconcile --namespace sales --confirm
```

---

## Prevention Strategies

### 1. Transactional Table Creation

Always create tables within floe's compile/deploy flow:

```yaml
# data-product.yaml - Tables created through proper flow
output_ports:
  - name: customers
    table: sales.gold.customers
    # Table creation is atomic with namespace registration
```

### 2. Soft Deletes Before Hard Deletes

Mark tables for deletion before removing:

```yaml
# data-product.yaml
deprecation:
  tables:
    - name: sales.gold.old_customers
      sunset_date: 2025-03-01
      replacement: sales.gold.customers_v2
```

### 3. Compile-Time Validation

Enable orphan detection during compile:

```yaml
# platform-manifest.yaml
compile:
  validations:
    check_orphaned_tables: true  # Fail if orphans found
    orphan_threshold: 0          # Zero tolerance
```

### 4. Ownership Tracking

All tables must belong to a registered data product:

```bash
# Check table ownership
floe catalog ownership --table sales.gold.customers

# Output:
TABLE                    PRODUCT           DOMAIN    OWNER
sales.gold.customers     customer-360      sales     sales-analytics@acme.com

# Tables without ownership are flagged as potential orphans
```

---

## CatalogPlugin Interface

The `CatalogPlugin` interface provides methods for orphan detection and reconciliation:

```python
# floe_core/interfaces/catalog.py

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

class CatalogPlugin(ABC):
    # ... existing methods ...

    @abstractmethod
    def list_orphaned_tables(
        self,
        namespace: str,
        orphan_types: list[str] | None = None,
    ) -> list[OrphanedTable]:
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
        """
        pass

    @abstractmethod
    def reconcile_catalog(
        self,
        namespace: str,
        dry_run: bool = True,
        actions: list[str] | None = None,
    ) -> ReconciliationResult:
        """Reconcile catalog with storage state.

        Actions:
          - delete-storage: Remove orphaned storage files
          - drop-catalog: Drop orphaned catalog entries
          - fix-metadata: Repair corrupted metadata

        Args:
            namespace: Namespace to reconcile
            dry_run: If True, report only without making changes
            actions: Actions to take (default: report only)

        Returns:
            ReconciliationResult with summary and details
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
            table_identifier: Full table identifier

        Returns:
            Tuple of (is_healthy, message)
        """
        pass
```

---

## Monitoring

### Prometheus Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `floe_catalog_orphaned_tables` | Gauge | namespace, type | Count of orphaned tables |
| `floe_catalog_orphaned_bytes` | Gauge | namespace | Storage bytes in orphans |
| `floe_catalog_reconciliation_duration_seconds` | Histogram | namespace | Reconciliation job duration |
| `floe_catalog_reconciliation_errors_total` | Counter | namespace, error_type | Reconciliation errors |

### Alert Rules

```yaml
groups:
  - name: catalog-health
    rules:
      - alert: CatalogOrphansDetected
        expr: floe_catalog_orphaned_tables > 10
        for: 24h
        labels:
          severity: warning
        annotations:
          summary: "{{ $value }} orphaned tables in {{ $labels.namespace }}"

      - alert: CatalogOrphanStorageHigh
        expr: floe_catalog_orphaned_bytes > 100 * 1024 * 1024 * 1024  # 100GB
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "{{ $value | humanize }} orphaned storage"

      - alert: CatalogReconciliationFailed
        expr: increase(floe_catalog_reconciliation_errors_total[1h]) > 0
        labels:
          severity: critical
        annotations:
          summary: "Catalog reconciliation failed in {{ $labels.namespace }}"
```

### OpenLineage Events

Reconciliation jobs emit lineage events:

```json
{
  "eventType": "COMPLETE",
  "job": { "name": "catalog.reconciliation.sales" },
  "run": {
    "facets": {
      "catalogReconciliation": {
        "namespace": "sales",
        "tablesScanned": 47,
        "orphansFound": 5,
        "orphansRemediated": 3,
        "storageReclaimedBytes": 48576000000
      }
    }
  }
}
```

---

## Governance Policies

### Data Retention

Orphaned data is subject to governance:

```yaml
# platform-manifest.yaml
governance:
  orphan_handling:
    quarantine_days: 30        # Days to keep in quarantine before deletion
    require_approval: true     # Require manual approval for deletion
    audit_deletions: true      # Log all deletions to audit trail
    pii_scan_before_delete: true  # Scan for PII before deletion
```

### Access Control

Reconciliation operations require elevated permissions:

| Operation | Required Role |
|-----------|---------------|
| `list_orphaned_tables` | `data_engineer` |
| `reconcile_catalog` (dry_run) | `data_engineer` |
| `reconcile_catalog` (execute) | `platform_admin` |
| `delete storage` | `platform_admin` |

---

## References

- [CatalogPlugin Interface](../architecture/interfaces/catalog-plugin.md)
- [ADR-0030: Namespace-Based Identity](../architecture/adr/0030-namespace-identity.md)
- [Apache Iceberg Maintenance](https://iceberg.apache.org/docs/latest/maintenance/)
- [Data Contract Lifecycle](../architecture/adr/0029-contract-lifecycle-management.md)

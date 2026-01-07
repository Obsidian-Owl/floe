# Storage Integration Architecture

This document describes how floe integrates with object storage for Apache Iceberg tables.

## Overview

floe enforces Apache Iceberg as the table format. Iceberg tables are stored on object storage, with metadata managed by the catalog (Polaris).

```
┌─────────────────────────────────────────────────────────────┐
│                     Object Storage                           │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ s3://floe-warehouse/iceberg/                            ││
│  │ ├── bronze.db/                                          ││
│  │ │   └── customers/                                       ││
│  │ │       ├── metadata/                                    ││
│  │ │       │   ├── v1.metadata.json                        ││
│  │ │       │   └── snap-xxx.avro                           ││
│  │ │       └── data/                                        ││
│  │ │           └── part-00000.parquet                      ││
│  │ ├── silver.db/                                          ││
│  │ └── gold.db/                                            ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
           ▲                              ▲
           │ Metadata                     │ Data
           │                              │
┌──────────┴──────────┐      ┌───────────┴───────────┐
│   Polaris Catalog   │      │   Compute (dbt/dlt)   │
│   (REST Catalog)    │      │   (via Iceberg SDK)   │
└─────────────────────┘      └───────────────────────┘
```

## Object Storage Options

| Storage | Use Case | Authentication |
|---------|----------|----------------|
| **MinIO** (default) | Local development, self-hosted | Access Key / Secret Key |
| **AWS S3** | Production on AWS | IRSA (recommended) or IAM User |
| **Google Cloud Storage** | Production on GCP | Workload Identity (recommended) or SA Key |
| **Azure Blob / ADLS Gen2** | Production on Azure | Managed Identity (recommended) or SP |

### MinIO (Default for Development)

MinIO is the recommended object storage for local development and self-hosted deployments:

- S3-compatible API (works with Iceberg's S3 file IO)
- Included in the `floe-platform` Helm chart
- Easy local setup via Docker or Kubernetes
- Supports versioning for backup/recovery

```yaml
# manifest.yaml
storage:
  type: minio
  warehouse_path: s3://floe-warehouse/iceberg
  config:
    endpoint: http://minio.floe-platform:9000
    access_key_ref: minio-credentials
    secret_key_ref: minio-credentials
```

### AWS S3

For production on AWS, use IAM Roles for Service Accounts (IRSA):

```yaml
# manifest.yaml
storage:
  type: s3
  warehouse_path: s3://my-company-data-lake/floe/iceberg
  config:
    region: us-east-1
    auth: irsa  # Uses pod's service account
```

**IAM Policy Required:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::my-company-data-lake/floe/*",
        "arn:aws:s3:::my-company-data-lake"
      ]
    }
  ]
}
```

### Google Cloud Storage

For production on GCP, use Workload Identity:

```yaml
# manifest.yaml
storage:
  type: gcs
  warehouse_path: gs://my-company-data-lake/floe/iceberg
  config:
    project: my-gcp-project
    auth: workload_identity
```

### Azure Blob Storage / ADLS Gen2

For production on Azure, use Managed Identity:

```yaml
# manifest.yaml
storage:
  type: azure
  warehouse_path: abfss://data@mystorageaccount.dfs.core.windows.net/floe/iceberg
  config:
    auth: managed_identity
```

## Storage Layout

Iceberg tables follow a consistent directory structure:

```
{warehouse_path}/
├── {database}.db/
│   └── {table}/
│       ├── metadata/
│       │   ├── v1.metadata.json      # Table metadata (schema, partitions, snapshots)
│       │   ├── v2.metadata.json      # Updated metadata after writes
│       │   ├── snap-{id}.avro        # Snapshot manifests
│       │   └── {manifest-id}.avro    # Manifest files
│       └── data/
│           ├── {partition}/          # Partition directories (if partitioned)
│           │   └── {file-id}.parquet # Data files (Parquet format)
│           └── {file-id}.parquet     # Data files (if unpartitioned)
```

### Naming Convention Integration

The storage layout follows the data architecture pattern specified in the Manifest:

| Pattern | Database Names | Example Path |
|---------|---------------|--------------|
| **Medallion** | bronze, silver, gold | `s3://warehouse/iceberg/bronze.db/customers/` |
| **Kimball** | staging, dimensions, facts | `s3://warehouse/iceberg/dimensions.db/dim_customer/` |
| **Data Vault** | raw_vault, business_vault | `s3://warehouse/iceberg/raw_vault.db/hub_customer/` |

## Credential Vending

For enhanced security, Polaris can vend short-lived credentials for table access:

```
┌─────────────────┐     1. Request credentials     ┌─────────────────┐
│   Job Pod       │ ─────────────────────────────► │   Polaris       │
│   (dbt/dlt)     │                                │   Catalog       │
└─────────────────┘                                └────────┬────────┘
        │                                                   │
        │ 2. Short-lived STS credentials                    │
        │◄──────────────────────────────────────────────────┘
        │
        │ 3. Access storage with temporary credentials
        ▼
┌─────────────────┐
│  Object Storage │
│  (S3/GCS/Azure) │
└─────────────────┘
```

**Benefits:**
- No long-lived credentials in job pods
- Credentials scoped to specific tables
- Automatic expiration (typically 1 hour)
- Audit trail via Polaris

**Polaris Configuration:**
```yaml
# In CatalogPlugin configuration
catalog:
  type: polaris
  config:
    credential_vending: true
    credential_ttl: 3600  # 1 hour
```

## Compute Engine Catalog Integration

Each compute engine connects to the Iceberg catalog differently. All table operations go through the catalog to ensure consistent metadata management.

| Compute | Catalog Connection Method |
|---------|--------------------------|
| DuckDB | ATTACH statement with Iceberg REST endpoint |
| Spark | SparkCatalog configuration in spark-defaults.conf |
| Snowflake | External volume + catalog integration (managed by Snowflake) |

### DuckDB + Polaris Data Flow

When using DuckDB as the compute engine with Polaris as the catalog:

```
1. dbt pre-hook executes ATTACH to Polaris
   ↓
2. DuckDB establishes REST connection to Polaris
   ↓
3. Polaris vends short-lived credentials for object storage
   ↓
4. dbt model SQL executes (CREATE TABLE AS SELECT)
   ↓
5. DuckDB writes Parquet files to object storage
   ↓
6. DuckDB updates table metadata via Polaris REST API
   ↓
7. Polaris persists metadata to PostgreSQL
```

The floe-dbt package generates appropriate pre-hooks based on the compute plugin's `get_catalog_attachment_sql()` method:

```yaml
# Generated dbt_project.yml
on-run-start:
  - "LOAD iceberg;"
  - "CREATE SECRET IF NOT EXISTS polaris_secret (...)"
  - "ATTACH IF NOT EXISTS 'warehouse' AS ice (TYPE iceberg, ...)"
```

## Compute-Storage Compatibility Matrix

Not all compute engines support all storage backends. The PolicyEnforcer validates compatibility at compile time.

| Compute | S3/MinIO | GCS | Azure ADLS |
|---------|----------|-----|------------|
| DuckDB | ✅ | ❌ | ❌ |
| Spark | ✅ | ✅ | ✅ |
| Snowflake | N/A (uses Snowflake storage) | N/A | N/A |

**MVP Scope**: S3-compatible storage only (AWS S3, MinIO).

For GCP/Azure deployments, use MinIO as the storage layer, which provides S3-compatible access for DuckDB while running on cloud-native infrastructure:

```yaml
# manifest.yaml (GCP deployment with MinIO)
storage:
  type: minio
  warehouse_path: s3://floe-warehouse/iceberg
  config:
    endpoint: http://minio.floe-platform:9000
    # MinIO deployed on GKE/AKS provides S3-compatible API
```

Native GCS and Azure ADLS support for DuckDB is pending upstream DuckDB Iceberg extension updates and will be added in a future release.

## Backup Strategies

### Object Storage Versioning

Enable versioning on the warehouse bucket for point-in-time recovery:

```bash
# AWS S3
aws s3api put-bucket-versioning \
  --bucket my-company-data-lake \
  --versioning-configuration Status=Enabled

# MinIO
mc version enable minio/floe-warehouse
```

### Iceberg Time Travel

Iceberg maintains table history via snapshots. Configure retention in the Manifest:

```yaml
# manifest.yaml
data_architecture:
  iceberg:
    snapshot_retention_days: 7
    min_snapshots_to_keep: 5
```

**Recovery commands:**
```sql
-- List available snapshots
SELECT * FROM iceberg.bronze.customers.snapshots;

-- Query historical data
SELECT * FROM iceberg.bronze.customers FOR TIMESTAMP AS OF '2024-01-15 10:00:00';

-- Rollback to previous snapshot
ALTER TABLE iceberg.bronze.customers EXECUTE rollback_to_timestamp('2024-01-15 10:00:00');
```

### Metadata Backup

Polaris stores catalog metadata in PostgreSQL. Include in backup strategy:

```yaml
# Platform services backup
backups:
  polaris_postgres:
    schedule: "0 */6 * * *"  # Every 6 hours
    retention: 30d
```

## Performance Tuning

### Object Size Optimization

Iceberg target file size affects query performance:

```yaml
# manifest.yaml
data_architecture:
  iceberg:
    target_file_size_mb: 512  # 512 MB files (default)
    # Smaller for frequently updated tables
    # Larger for append-only tables
```

### Compaction

Configure automatic compaction to merge small files:

```yaml
# manifest.yaml
data_architecture:
  iceberg:
    compaction:
      enabled: true
      min_input_files: 5
      target_file_size_mb: 512
```

## Configuration Schema

```yaml
# Full storage configuration schema
storage:
  type: minio | s3 | gcs | azure
  warehouse_path: string  # URI to Iceberg warehouse root
  config:
    # MinIO / S3
    endpoint: string      # S3-compatible endpoint (MinIO only)
    region: string        # AWS region
    access_key_ref: string  # K8s Secret reference
    secret_key_ref: string  # K8s Secret reference
    auth: irsa | access_key  # Authentication method

    # GCS
    project: string       # GCP project ID
    auth: workload_identity | service_account_key

    # Azure
    auth: managed_identity | service_principal
```

## References

- [Apache Iceberg Documentation](https://iceberg.apache.org/docs/latest/)
- [Iceberg Table Spec](https://iceberg.apache.org/spec/)
- [Polaris Catalog](https://github.com/apache/polaris)
- [MinIO Documentation](https://min.io/docs/minio/kubernetes/upstream/)
- [ADR-0018: Opinionation Boundaries](adr/0018-opinionation-boundaries.md) - Iceberg enforcement
- [Platform Services](platform-services.md) - MinIO deployment

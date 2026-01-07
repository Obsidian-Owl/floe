# Apache Polaris REST API Reference

This document provides a comprehensive reference for the Apache Polaris REST API, covering authentication, management operations, catalog operations, and access control.

## Table of Contents

1. [Authentication](#authentication)
2. [Management API](#management-api)
3. [Catalog API](#catalog-api)
4. [Storage Configuration](#storage-configuration)
5. [Access Control (RBAC)](#access-control-rbac)
6. [Error Handling](#error-handling)

---

## Authentication

### OAuth2 Client Credentials Flow

Polaris uses OAuth2 client credentials flow for API authentication.

#### Obtain Access Token

**Request:**

```bash
curl -X POST http://localhost:8181/api/catalog/v1/oauth/tokens \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=demo_client" \
  -d "client_secret=demo_secret" \
  -d "scope=PRINCIPAL_ROLE:ALL"
```

**Response:**

```json
{
  "access_token": "<jwt-token-will-appear-here>",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "PRINCIPAL_ROLE:ALL"
}
```

#### Use Access Token

All subsequent API calls must include the token in the `Authorization` header:

```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8181/api/management/v1/catalogs
```

#### Token Refresh

Polaris tokens expire (default: 1 hour). PyIceberg handles refresh automatically when `token-refresh-enabled: true` is configured.

**Manual refresh** (if needed):

```python
import time

def get_token():
    # ... OAuth2 token request
    return token, expiry_timestamp

token, expiry = get_token()

# Refresh before expiry (5 minutes buffer)
if time.time() > (expiry - 300):
    token, expiry = get_token()
```

---

## Management API

Base URL: `http://localhost:8181/api/management/v1`

### Catalogs

#### Create Catalog

**Request:**

```bash
POST /api/management/v1/catalogs
Content-Type: application/json
Authorization: Bearer $TOKEN

{
  "catalog": {
    "name": "my_catalog",
    "type": "INTERNAL",
    "properties": {
      "default-base-location": "s3://bucket/warehouse"
    },
    "storageConfigInfo": {
      "storageType": "S3",
      "allowedLocations": ["s3://bucket/"],
      "endpoint": "http://localstack:4566",
      "pathStyleAccess": true,
      "region": "us-east-1",
      "roleArn": "arn:aws:iam::000000000000:role/polaris-role"
    }
  }
}
```

**Response:** `201 Created`

```json
{
  "name": "my_catalog",
  "type": "INTERNAL",
  "properties": {"default-base-location": "s3://bucket/warehouse"},
  "createTimestamp": 1234567890000,
  "lastUpdateTimestamp": 1234567890000,
  "entityVersion": 1
}
```

#### Get Catalog

```bash
GET /api/management/v1/catalogs/{catalog_name}
Authorization: Bearer $TOKEN
```

**Response:** `200 OK`

```json
{
  "name": "my_catalog",
  "type": "INTERNAL",
  "properties": {"default-base-location": "s3://bucket/warehouse"},
  "storageConfigInfo": {
    "storageType": "S3",
    "endpoint": "http://localstack:4566",
    "pathStyleAccess": true
  },
  "entityVersion": 1
}
```

#### List Catalogs

```bash
GET /api/management/v1/catalogs
Authorization: Bearer $TOKEN
```

**Response:** `200 OK`

```json
{
  "catalogs": [
    {"name": "catalog1", "type": "INTERNAL"},
    {"name": "catalog2", "type": "INTERNAL"}
  ]
}
```

#### Update Catalog

**⚠️ WARNING**: Storage configuration **CANNOT** be updated after creation. Only properties can be changed.

```bash
PUT /api/management/v1/catalogs/{catalog_name}
Authorization: Bearer $TOKEN

{
  "currentEntityVersion": 1,
  "properties": {
    "new-property": "value"
  }
}
```

#### Delete Catalog

```bash
DELETE /api/management/v1/catalogs/{catalog_name}
Authorization: Bearer $TOKEN
```

### Principals

#### Create Principal

```bash
POST /api/management/v1/principals
Authorization: Bearer $TOKEN

{
  "principal": {
    "name": "data_engineer_service",
    "clientId": "data_engineer_service"
  }
}
```

**Response:** `201 Created`

#### List Principals

```bash
GET /api/management/v1/principals
Authorization: Bearer $TOKEN
```

### Principal Roles

#### Create Principal Role

```bash
POST /api/management/v1/principal-roles
Authorization: Bearer $TOKEN

{
  "principalRole": {
    "name": "data_engineer"
  }
}
```

#### Assign Principal Role to Principal

```bash
PUT /api/management/v1/principals/{principal_name}/principal-roles
Authorization: Bearer $TOKEN

{
  "principalRole": {
    "name": "data_engineer"
  }
}
```

### Catalog Roles

#### Create Catalog Role

```bash
POST /api/management/v1/catalogs/{catalog_name}/catalog-roles
Authorization: Bearer $TOKEN

{
  "catalogRole": {
    "name": "analytics_writer"
  }
}
```

#### Grant Privilege to Catalog Role

```bash
PUT /api/management/v1/catalogs/{catalog_name}/catalog-roles/{role_name}/grants
Authorization: Bearer $TOKEN

{
  "grant": {
    "type": "catalog",
    "privilege": "TABLE_WRITE_DATA"
  }
}
```

**Available privileges**:
- `CATALOG_MANAGE_CONTENT` - Create/drop tables and namespaces
- `TABLE_CREATE` - Create tables
- `TABLE_DROP` - Drop tables
- `TABLE_READ_DATA` - Read table data
- `TABLE_WRITE_DATA` - Write table data
- `TABLE_LIST` - List tables
- `NAMESPACE_CREATE` - Create namespaces
- `NAMESPACE_DROP` - Drop namespaces
- `NAMESPACE_LIST` - List namespaces
- `VIEW_CREATE` - Create views
- `VIEW_DROP` - Drop views
- `VIEW_LIST` - List views

#### Assign Catalog Role to Principal Role

```bash
PUT /api/management/v1/principal-roles/{principal_role}/catalog-roles/{catalog_name}
Authorization: Bearer $TOKEN

{
  "catalogRole": {
    "name": "analytics_writer"
  }
}
```

---

## Catalog API

Base URL: `http://localhost:8181/api/catalog/v1/{catalog_name}`

### Namespaces

#### Create Namespace

**Flat namespace**:

```bash
POST /api/catalog/v1/{catalog_name}/namespaces
Authorization: Bearer $TOKEN

{
  "namespace": ["bronze"],
  "properties": {"owner": "data_team"}
}
```

**Nested namespace** (parent must exist first):

```bash
# Create parent first
POST /api/catalog/v1/{catalog_name}/namespaces
{
  "namespace": ["demo"],
  "properties": {}
}

# Then create child
POST /api/catalog/v1/{catalog_name}/namespaces
{
  "namespace": ["demo", "bronze"],
  "properties": {}
}
```

**Response:** `200 OK`

```json
{
  "namespace": ["demo", "bronze"],
  "properties": {}
}
```

#### List Namespaces

```bash
GET /api/catalog/v1/{catalog_name}/namespaces
Authorization: Bearer $TOKEN
```

**Response:**

```json
{
  "namespaces": [
    ["bronze"],
    ["silver"],
    ["gold"]
  ]
}
```

#### Get Namespace Properties

```bash
GET /api/catalog/v1/{catalog_name}/namespaces/{namespace}
Authorization: Bearer $TOKEN
```

**Response:**

```json
{
  "namespace": ["bronze"],
  "properties": {"owner": "data_team"}
}
```

#### Update Namespace Properties

```bash
POST /api/catalog/v1/{catalog_name}/namespaces/{namespace}/properties
Authorization: Bearer $TOKEN

{
  "updates": {"owner": "new_team"},
  "removals": ["old_property"]
}
```

#### Drop Namespace

**⚠️ WARNING**: Namespace must be empty (no tables).

```bash
DELETE /api/catalog/v1/{catalog_name}/namespaces/{namespace}
Authorization: Bearer $TOKEN
```

### Tables

#### List Tables

```bash
GET /api/catalog/v1/{catalog_name}/namespaces/{namespace}/tables
Authorization: Bearer $TOKEN
```

**Response:**

```json
{
  "identifiers": [
    {"namespace": ["bronze"], "name": "raw_events"},
    {"namespace": ["bronze"], "name": "raw_users"}
  ]
}
```

#### Load Table Metadata

```bash
GET /api/catalog/v1/{catalog_name}/namespaces/{namespace}/tables/{table_name}
Authorization: Bearer $TOKEN
```

**Response:**

```json
{
  "metadata-location": "s3://bucket/warehouse/bronze/raw_events/metadata/v1.metadata.json",
  "metadata": {
    "format-version": 2,
    "table-uuid": "abc-123",
    "location": "s3://bucket/warehouse/bronze/raw_events",
    "current-snapshot-id": 1234567890,
    "schemas": [...],
    "partition-specs": [...],
    "sort-orders": [...]
  }
}
```

---

## Storage Configuration

### OpenAPI Spec: AwsStorageConfigInfo

**CRITICAL**: Polaris uses **flat keys**, NOT nested objects.

#### Correct Schema (Flat Keys)

```python
storage_config = {
    "storageType": "S3",
    "allowedLocations": ["s3://bucket-name/"],
    # Flat keys per OpenAPI spec
    "endpoint": "http://localstack:4566",      # NOT s3.endpoint
    "pathStyleAccess": True,                    # NOT s3.pathStyleAccess
    "roleArn": "arn:aws:iam::000000000000:role/my-role",
    "region": "us-east-1",
    "externalId": "optional-external-id"
}
```

#### Incorrect Schema (Nested - NOT ACCEPTED)

```python
# ❌ WRONG - This will be rejected
storage_config = {
    "storageType": "S3",
    "s3": {
        "endpoint": "...",
        "pathStyleAccess": True
    }
}
```

### Path-Style Access

**Why it matters**:

Without `pathStyleAccess: true`, Polaris uses **virtual-hosted style** URLs:
- Virtual-hosted: `http://bucket.localstack:4566/key` ❌ (DNS fails for LocalStack)
- Path-style: `http://localstack:4566/bucket/key` ✅ (works for LocalStack/MinIO)

**Error without `pathStyleAccess: true`**:

```
UnknownHostException: iceberg-data.floe-infra-localstack: Name or service not known
```

### IAM Role for Credential Vending

For Polaris to vend temporary credentials via STS `AssumeRole`:

1. **Create IAM role** (in LocalStack or AWS):

```bash
aws --endpoint-url=http://localstack:4566 iam create-role \
  --role-name polaris-storage-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "sts.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'
```

2. **Attach S3 permissions**:

```bash
aws --endpoint-url=http://localstack:4566 iam attach-role-policy \
  --role-name polaris-storage-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
```

3. **Configure catalog with `roleArn`**:

```python
storage_config = {
    "storageType": "S3",
    "roleArn": "arn:aws:iam::000000000000:role/polaris-storage-role",
    "pathStyleAccess": True,
    "endpoint": "http://localstack:4566",
    "region": "us-east-1",
    "allowedLocations": ["s3://iceberg-data/"]
}
```

4. **Disable vended credentials in PyIceberg** (if not using STS):

```python
catalog_config = {
    "header.X-Iceberg-Access-Delegation": ""  # Empty string disables vending
}
```

### Storage Config Immutability

**Known limitation**: Storage configuration **CANNOT** be updated after catalog creation.

Attempting to update storage config returns `400 Bad Request`:

```bash
PUT /api/management/v1/catalogs/my_catalog
{
  "storageConfigInfo": {...}  # This will fail
}
```

**Workaround**:
1. Delete catalog (requires dropping all namespaces/tables first)
2. Recreate catalog with correct storage config

**Helm init job pattern** (idempotent):

```python
status, resp = api_request("GET", f"/api/management/v1/catalogs/{CATALOG_NAME}")
if status == 200:
    # Catalog exists - cannot update storage config
    print("Catalog exists, continuing with existing config")
elif status == 404:
    # Create new catalog with correct storage config
    api_request("POST", "/api/management/v1/catalogs", {...})
```

---

## Access Control (RBAC)

### Three-Tier RBAC Model

```
Principal (e.g., demo_client)
  ↓ has
Principal Role (e.g., service_admin)
  ↓ assigned to
Catalog Role (e.g., demo_data_admin)
  ↓ has
Privileges (e.g., TABLE_WRITE_DATA)
  ↓ on
Resources (catalog, namespace, table)
```

### Example: Creating Full Role Hierarchy

```bash
# 1. Create Principal
POST /api/management/v1/principals
{
  "principal": {
    "name": "data_engineer_service",
    "clientId": "data_engineer_service"
  }
}

# 2. Create Principal Role
POST /api/management/v1/principal-roles
{
  "principalRole": {"name": "data_engineer"}
}

# 3. Assign Principal Role to Principal
PUT /api/management/v1/principals/data_engineer_service/principal-roles
{
  "principalRole": {"name": "data_engineer"}
}

# 4. Create Catalog Role
POST /api/management/v1/catalogs/my_catalog/catalog-roles
{
  "catalogRole": {"name": "analytics_writer"}
}

# 5. Grant Privileges to Catalog Role (repeat for each privilege)
PUT /api/management/v1/catalogs/my_catalog/catalog-roles/analytics_writer/grants
{
  "grant": {
    "type": "catalog",
    "privilege": "NAMESPACE_CREATE"
  }
}

PUT /api/management/v1/catalogs/my_catalog/catalog-roles/analytics_writer/grants
{
  "grant": {
    "type": "namespace",
    "privilege": "TABLE_READ_DATA",
    "namespace": ["bronze"]
  }
}

PUT /api/management/v1/catalogs/my_catalog/catalog-roles/analytics_writer/grants
{
  "grant": {
    "type": "namespace",
    "privilege": "TABLE_WRITE_DATA",
    "namespace": ["silver"]
  }
}

# 6. Assign Catalog Role to Principal Role
PUT /api/management/v1/principal-roles/data_engineer/catalog-roles/my_catalog
{
  "catalogRole": {"name": "analytics_writer"}
}
```

### Grant Types

| Type | Scope | Example |
|------|-------|---------|
| `catalog` | Entire catalog | `{"type": "catalog", "privilege": "CATALOG_MANAGE_CONTENT"}` |
| `namespace` | Specific namespace | `{"type": "namespace", "privilege": "TABLE_READ_DATA", "namespace": ["bronze"]}` |
| `table` | Specific table | `{"type": "table", "privilege": "TABLE_WRITE_DATA", "namespace": ["bronze"], "name": "events"}` |

### Privilege Hierarchy

**Catalog-level privileges** (highest scope):
- `CATALOG_MANAGE_CONTENT` - Implies all table/namespace operations

**Namespace-level privileges**:
- `NAMESPACE_CREATE`, `NAMESPACE_DROP`, `NAMESPACE_LIST`
- `TABLE_CREATE`, `TABLE_DROP`, `TABLE_LIST` (within namespace)

**Table-level privileges** (lowest scope):
- `TABLE_READ_DATA` - Read table data
- `TABLE_WRITE_DATA` - Write table data

### floe-runtime Default Roles

From `polaris-init-job.yaml`:

| Entity | Type | Name | Privileges |
|--------|------|------|------------|
| Principal | `principal` | `demo_client` | (via role) |
| Principal Role | `principal_role` | `service_admin` | (bootstrap role) |
| Catalog Role | `catalog_role` | `demo_data_admin` | ALL (CATALOG_MANAGE_CONTENT, TABLE_*, NAMESPACE_*, VIEW_*) |

**Security best practices**:
- Use `PRINCIPAL_ROLE:<role_name>` with least-privilege scope
- NEVER use `PRINCIPAL_ROLE:ALL` in production (overly permissive)
- Create separate roles for read-only, read-write, admin access
- Rotate credentials regularly via K8s secrets

---

## Error Handling

### Common HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| `200` | OK | Successful operation |
| `201` | Created | Resource created successfully |
| `204` | No Content | Successful delete or void operation |
| `400` | Bad Request | Invalid request body, attempting to update immutable fields |
| `401` | Unauthorized | Missing or expired token |
| `403` | Forbidden | Insufficient privileges |
| `404` | Not Found | Catalog, namespace, or table doesn't exist |
| `409` | Conflict | Resource already exists |
| `500` | Internal Server Error | Polaris internal error |

### Python Exception Handling

```python
from pyiceberg.exceptions import (
    CommitFailedException,
    NamespaceAlreadyExistsError,
    NamespaceNotEmptyError,
    NoSuchNamespaceError,
    NoSuchTableError,
)
from floe_polaris.errors import (
    CatalogAuthenticationError,
    CatalogConnectionError,
    NamespaceExistsError,
    NamespaceNotFoundError,
    TableNotFoundError,
)

# Authentication errors
try:
    catalog = create_catalog(config)
except CatalogAuthenticationError as e:
    print(f"Authentication failed: {e}")
    # Verify credentials and scope

# Namespace errors
try:
    catalog.create_namespace("demo.bronze")
except NamespaceExistsError:
    print("Namespace already exists, continuing")

try:
    catalog.drop_namespace("demo.bronze")
except NamespaceNotEmptyError:
    print("Namespace contains tables, cannot drop")

# Table errors
try:
    table = catalog.load_table("demo.bronze.events")
except TableNotFoundError:
    print("Table doesn't exist")

# Commit conflicts (concurrent writes)
try:
    table.append(data)
except CommitFailedException:
    # Refresh metadata and retry
    table.refresh()
    table.append(data)
```

### Debugging Tips

**Enable HTTP logging in DuckDB**:

```sql
CALL enable_logging('HTTP');
SELECT * FROM polaris_catalog.demo.bronze.events;
SELECT * FROM duckdb_logs_parsed('HTTP');
```

**Test OAuth2 token manually**:

```bash
TOKEN=$(curl -s -X POST http://localhost:8181/api/catalog/v1/oauth/tokens \
  -d "grant_type=client_credentials" \
  -d "client_id=demo_client" \
  -d "client_secret=demo_secret" \
  -d "scope=PRINCIPAL_ROLE:ALL" \
  | jq -r '.access_token')

echo $TOKEN

# Test with token
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8181/api/management/v1/catalogs
```

**Check Polaris health**:

```bash
# Liveness (Polaris is running)
curl http://localhost:8181/q/health/live

# Readiness (Polaris is ready to accept requests)
curl http://localhost:8181/q/health/ready
```

---

## References

- **Official Docs**: https://polaris.apache.org
- **OpenAPI Spec**: https://github.com/apache/polaris/blob/main/spec/polaris-management-service.yml
- **Entities Guide**: https://polaris.apache.org/releases/1.0.1/entities/
- **Getting Started**: https://polaris.apache.org/releases/1.0.0/getting-started/using-polaris/
- **floe-polaris Package**: `packages/floe-polaris/README.md`
- **Platform Config Guide**: `docs/platform-config.md`

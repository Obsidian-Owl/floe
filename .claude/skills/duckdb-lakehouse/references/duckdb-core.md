# DuckDB Core Reference

## Installation
```bash
pip install duckdb==1.4.3  # floe-platform version
```

## Connection Management

### In-Memory vs Persistent
```python
import duckdb

# In-memory (ephemeral, recommended for one-off scripts)
conn = duckdb.connect()  # or duckdb.connect(":memory:")

# Named in-memory (shareable across connections in same process)
conn1 = duckdb.connect(":memory:mydb")
conn2 = duckdb.connect(":memory:mydb")  # Same database

# Persistent file (REQUIRED for floe-platform - extensions persist)
conn = duckdb.connect("/tmp/floe.duckdb")

# Read-only (allows multiple processes)
conn = duckdb.connect("/tmp/floe.duckdb", read_only=True)
```

**floe-platform Pattern**: Use file-based database (`/tmp/floe.duckdb`) because:
- Extensions (iceberg, httpfs) persist across sessions
- Pre-installation in entrypoint avoids timing issues
- `:memory:` requires re-installation every connection

### Configuration Options
```python
conn = duckdb.connect(config={
    'memory_limit': '8GB',      # Default: 80% of RAM
    'threads': 4,                # Default: CPU cores
    'temp_directory': '/tmp/duckdb',    # Spill location
    'preserve_insertion_order': 'false'  # Faster bulk imports
})

# Runtime adjustment
conn.execute("SET memory_limit = '4GB'")
conn.execute("SET threads = 2")
```

**floe-platform K8s Environment**:
```yaml
# Set via environment variables in platform.yaml
env:
  DUCKDB_MEMORY_LIMIT: "8GB"  # 67% of 12Gi container limit
  DUCKDB_THREADS: "4"
  DUCKDB_TEMP_DIRECTORY: "/tmp/duckdb"
```

### Thread Safety
```python
# ❌ WRONG: Global connection across threads
def bad():
    return duckdb.sql("SELECT 1").fetchall()  # NOT thread-safe

# ✅ CORRECT: Connection per thread
def good():
    conn = duckdb.connect("/tmp/floe.duckdb")  # New connection
    return conn.sql("SELECT 1").fetchall()
    # Note: DuckDB files support only ONE writer at a time
```

## Query Execution

### Basic Patterns
```python
# sql() returns Relation (lazy, chainable)
rel = conn.sql("SELECT * FROM table")
rel.filter("col > 10").limit(100).show()

# execute() for DDL/DML
conn.execute("CREATE TABLE t (id INT)")
conn.execute("INSERT INTO t VALUES (1), (2)")
```

### Fetching Results
```python
conn.execute("SELECT * FROM t")
conn.fetchall()      # List of tuples
conn.fetchone()      # Single tuple
conn.fetchdf()       # Pandas DataFrame
conn.fetchnumpy()    # Dict of NumPy arrays

# Via Relation
rel = conn.sql("SELECT * FROM t")
rel.df()             # Pandas
rel.pl()             # Polars
rel.arrow()          # PyArrow Table (zero-copy)
```

### Parameterized Queries (Security)
```python
# Positional (?)
conn.execute("SELECT * FROM t WHERE id = ?", [42])

# Named ($param)
conn.execute("SELECT $name, $value", {"name": "test", "value": 123})

# Multiple rows
conn.executemany("INSERT INTO t VALUES (?)", [[1], [2], [3]])
```

### Transactions
```python
conn.execute("BEGIN TRANSACTION")
try:
    conn.execute("INSERT INTO t VALUES (1)")
    conn.execute("INSERT INTO t VALUES (2)")
    conn.execute("COMMIT")
except:
    conn.execute("ROLLBACK")
```

## Extensions

### Loading Extensions
```python
# Auto-loads on first use for most extensions
conn.sql("SELECT * FROM 's3://bucket/file.parquet'")  # Loads httpfs

# Manual installation (floe-platform pattern - in entrypoint.sh)
conn.execute("INSTALL iceberg")
conn.execute("LOAD iceberg")

# Or via Python API
conn.install_extension("iceberg")
conn.load_extension("iceberg")
```

**floe-platform Pre-Installation** (docker/entrypoint.sh):
```python
import duckdb

db_path = '/tmp/floe.duckdb'
conn = duckdb.connect(db_path)

conn.execute("INSTALL iceberg")
conn.execute("INSTALL httpfs")

print(f"✓ Installed DuckDB extensions (iceberg, httpfs)")
conn.close()
```

### httpfs (S3/HTTP Access)
```python
# S3 via secrets (traditional approach)
conn.execute("""
CREATE SECRET s3_creds (
    TYPE s3,
    KEY_ID '${AWS_ACCESS_KEY_ID}',
    SECRET '${AWS_SECRET_ACCESS_KEY}',
    REGION 'us-east-1'
)
""")

# AWS credential chain
conn.execute("""
CREATE SECRET aws_auto (
    TYPE s3,
    PROVIDER credential_chain
)
""")

# Query S3
conn.sql("SELECT * FROM 's3://bucket/data/*.parquet'")

# Write to S3
conn.execute("COPY table TO 's3://bucket/output.parquet'")
```

**floe-platform Note**: For Iceberg tables, use ATTACH with inline credentials (see references/floe-platform-integration.md).

### Iceberg Extension
```python
conn.execute("INSTALL iceberg; LOAD iceberg;")

# Direct scan (without catalog)
conn.sql("""
SELECT * FROM iceberg_scan(
    's3://bucket/table/metadata/v1.metadata.json',
    allow_moved_paths = true
)
""")

# View snapshots
conn.sql("SELECT * FROM iceberg_snapshots('path/to/table')")

# Time travel
conn.sql("""
SELECT * FROM iceberg_scan('path/to/table',
    snapshot_from_timestamp = TIMESTAMP '2024-01-01 12:00:00')
""")
```

**floe-platform Pattern**: Use ATTACH for catalog-coordinated access:
```python
# Inline credentials bypass secret manager timing issue
attach_sql = f"""
ATTACH IF NOT EXISTS '{warehouse}' AS polaris_catalog (
    TYPE ICEBERG,
    CLIENT_ID '{client_id}',
    CLIENT_SECRET '{client_secret}',
    OAUTH2_SERVER_URI '{oauth2_server_uri}',
    ENDPOINT '{catalog_uri}'
)
"""
conn.execute(attach_sql)

# Query via attached catalog
conn.sql("SELECT * FROM polaris_catalog.namespace.table_name")
```

## PyArrow Integration (Zero-Copy)

```python
import pyarrow as pa

# Query Arrow tables directly
arrow_table = pa.Table.from_pydict({"id": [1, 2, 3], "name": ["a", "b", "c"]})
duckdb.sql("SELECT * FROM arrow_table WHERE id > 1")

# Register for reuse
conn.register('my_arrow', arrow_table)
conn.sql("SELECT * FROM my_arrow")

# Export to Arrow (zero-copy to Iceberg)
result = conn.sql("SELECT * FROM t").arrow()

# Stream large results
for batch in conn.sql("SELECT * FROM big_table").fetch_arrow_reader(batch_size=100000):
    process(batch)
```

## Performance Tuning

### Memory Rules
- Minimum: 125 MB per thread
- Aggregation: 1-2 GB per thread
- Joins: 3-4 GB per thread
- Optimal: 5 GB per thread

**floe-platform K8s**:
- Transform jobs: 12Gi limit, 4Gi request
- DUCKDB_MEMORY_LIMIT: 8GB (67% of 12Gi)
- DUCKDB_THREADS: 4

### Query Profiling
```python
conn.sql("EXPLAIN SELECT * FROM t WHERE id > 100").show()
conn.sql("EXPLAIN ANALYZE SELECT * FROM t WHERE id > 100").show()

conn.execute("PRAGMA enable_profiling = 'json'")
conn.execute("PRAGMA profiling_output = 'profile.json'")
```

### Best Practices
```python
# Use COPY for bulk inserts (NOT executemany)
conn.execute("COPY t FROM 'data.csv'")

# Or from DataFrame
conn.execute("INSERT INTO t SELECT * FROM df")

# Reuse connections
conn = duckdb.connect("/tmp/floe.duckdb")
for query in queries:
    conn.execute(query)  # Don't reconnect each time

# For remote data, increase threads
conn.execute("SET threads = 16")  # Network-bound workloads
```

## Common Errors in floe-platform

### Error: "Secret Manager settings cannot be changed"
**Cause**: Attempting CREATE SECRET after secret manager initialization.
**Solution**: Use inline credentials in ATTACH (see references/floe-platform-integration.md).

### Error: "ICEBERG extension not found"
**Cause**: Extensions not pre-installed or using `:memory:` database.
**Solution**: Pre-install in entrypoint with file-based database (`/tmp/floe.duckdb`).

### Error: "Database locked"
**Cause**: Multiple writers to same DuckDB file (single-writer limitation).
**Solution**: Use DuckDB for ephemeral compute, Iceberg for shared persistent storage.

## References

- DuckDB Documentation: https://duckdb.org/docs/
- DuckDB Iceberg Extension: https://duckdb.org/docs/extensions/iceberg
- DuckDB Issue #18021: Lazy loading of persistent secrets
- floe-platform Polaris Plugin: packages/floe-dbt/src/floe_dbt/plugins/polaris.py

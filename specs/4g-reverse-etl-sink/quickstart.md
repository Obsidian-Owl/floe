# Quickstart: Epic 4G — Reverse ETL (SinkConnector)

## For Plugin Developers

### Implementing SinkConnector

```python
from floe_core.plugins.sink import SinkConnector, SinkConfig, EgressResult

class MySinkPlugin(SinkConnector):
    """Custom reverse ETL plugin."""

    def list_available_sinks(self) -> list[str]:
        return ["my_api", "my_database"]

    def create_sink(self, config: SinkConfig) -> Any:
        # Create and return a configured destination object
        return MyDestination(config.sink_type, config.connection_config)

    def write(self, sink: Any, data: Any, **kwargs: Any) -> EgressResult:
        # data is a pyarrow.Table at runtime
        rows = data.num_rows
        sink.push(data)
        return EgressResult(
            success=True,
            rows_delivered=rows,
            bytes_transmitted=data.nbytes,
            duration_seconds=1.5,
            checksum=hashlib.sha256(data.to_pandas().to_csv().encode()).hexdigest(),
            delivery_timestamp=datetime.utcnow().isoformat(),
            idempotency_key=str(uuid.uuid4()),
        )

    def get_source_config(self, catalog_config: dict[str, Any]) -> dict[str, Any]:
        return {"catalog_uri": catalog_config["uri"], "warehouse": catalog_config["warehouse"]}
```

### Bidirectional Plugin (Ingestion + Egress)

```python
from floe_core.plugins.ingestion import IngestionPlugin
from floe_core.plugins.sink import SinkConnector

class BidirectionalPlugin(IngestionPlugin, SinkConnector):
    """Plugin supporting both data ingestion and reverse ETL."""

    # IngestionPlugin methods
    @property
    def name(self) -> str:
        return "bidirectional"

    # ... other IngestionPlugin methods ...

    # SinkConnector methods
    def list_available_sinks(self) -> list[str]:
        return ["rest_api"]

    # ... other SinkConnector methods ...
```

### Runtime Detection

```python
# Check if a plugin supports egress
if isinstance(plugin, SinkConnector):
    sinks = plugin.list_available_sinks()
    print(f"Plugin supports egress to: {sinks}")
else:
    print("Plugin does not support reverse ETL")
```

## For Data Engineers

### Configuring Destinations in floe.yaml

```yaml
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: customer-analytics
  version: "1.0.0"

transforms:
  - name: stg_customers
  - name: fct_orders
    dependsOn: [stg_customers]

# Reverse ETL destinations (optional)
destinations:
  - name: salesforce-sync
    sink_type: rest_api
    connection_secret_ref: salesforce-api-creds
    source_table: gold.dim_customers
    field_mapping:
      customer_id: "Id"
      email: "Email"
      lifetime_value: "Custom_LTV__c"
    batch_size: 500

  - name: warehouse-export
    sink_type: sql_database
    connection_secret_ref: postgres-export-creds
    source_table: gold.fct_orders
```

## For Platform Engineers

### Governing Egress Destinations

```yaml
# manifest.yaml
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: acme-platform
  version: "1.0.0"
  owner: platform-team@acme.com
scope: enterprise

plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster

# Restrict which sink types data engineers can use
approved_sinks:
  - salesforce
  - postgres
  - rest_api
```

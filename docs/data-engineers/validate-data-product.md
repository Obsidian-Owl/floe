# Validate Your Data Product

Use this guide after your product runtime artifact has been deployed through the organization-approved path.

## Business Output Evidence

For `hello-orders`, pass criteria are:

- The `mart_daily_orders` output exists.
- `order_count` is greater than zero for at least one day.
- `total_order_value` is positive for at least one day.

## Runtime Evidence

- Dagster shows the latest product run succeeded.
- The run used the expected product image or code location.
- The run read the compiled artifacts generated for the product version.

## Lineage And Telemetry Evidence

- Marquez shows the product job and output dataset.
- Jaeger or your configured trace backend shows traces for the product run.
- OpenLineage and OpenTelemetry evidence use the platform namespace and product name from compiled artifacts.

## Escalation Boundary

Escalate to the Platform Engineer when multiple products fail the same platform service, when a service URL in the Platform Environment Contract is unreachable, or when the runtime cannot access approved secrets. Keep product model failures, dbt test failures, and invalid `floe.yaml` changes within the data product team first.

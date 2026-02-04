# Data Model: Epic 13 - E2E Platform Testing & Live Demo

## Demo Data Products

### customer-360 (Retail)

**Seeds** (configurable via `FLOE_DEMO_SEED_SCALE`):

| Table | Columns | Default Rows |
|-------|---------|-------------|
| raw_customers | customer_id, name, email, signup_date, segment | 500 |
| raw_transactions | txn_id, customer_id, amount, product_id, txn_date, status | 1000 |
| raw_support_tickets | ticket_id, customer_id, category, priority, created_at, resolved_at | 300 |

**Models**:

| Layer | Model | Description |
|-------|-------|-------------|
| Staging | stg_crm_customers | Clean customer records, normalize email, validate segment |
| Staging | stg_transactions | Clean transactions, cast types, filter invalid |
| Staging | stg_support_tickets | Clean tickets, compute resolution_hours |
| Intermediate | int_customer_orders | Aggregate per-customer: total_orders, total_spend, avg_order_value |
| Intermediate | int_customer_support | Aggregate per-customer: ticket_count, avg_resolution_hours |
| Mart | mart_customer_360 | Join all dimensions: customer + orders + support + segment |

### iot-telemetry (Manufacturing)

**Seeds**:

| Table | Columns | Default Rows |
|-------|---------|-------------|
| raw_sensors | sensor_id, equipment_id, sensor_type, location, installed_at | 200 |
| raw_readings | reading_id, sensor_id, timestamp, value, unit | 1000 |
| raw_maintenance_log | log_id, equipment_id, maintenance_type, performed_at, technician | 100 |

**Models**:

| Layer | Model | Description |
|-------|-------|-------------|
| Staging | stg_sensors | Clean sensor metadata, validate types |
| Staging | stg_readings | Clean readings, cast types, filter outliers |
| Staging | stg_maintenance | Clean maintenance records |
| Intermediate | int_sensor_metrics | Per-sensor aggregates: avg, min, max, stddev over windows |
| Intermediate | int_anomaly_detection | Flag readings outside 3-sigma threshold |
| Mart | mart_equipment_health | Per-equipment: health_score, anomaly_count, last_maintenance |

### financial-risk (Finance)

**Seeds**:

| Table | Columns | Default Rows |
|-------|---------|-------------|
| raw_positions | position_id, portfolio_id, instrument_id, quantity, entry_price, entry_date | 500 |
| raw_market_data | instrument_id, date, close_price, volume, volatility | 1000 |
| raw_counterparties | counterparty_id, name, rating, country, exposure_limit | 100 |

**Models**:

| Layer | Model | Description |
|-------|-------|-------------|
| Staging | stg_positions | Clean positions, validate quantities |
| Staging | stg_market_data | Clean market data, compute daily returns |
| Staging | stg_counterparties | Clean counterparty records, validate ratings |
| Intermediate | int_portfolio_risk | Per-portfolio: VaR, expected shortfall, max drawdown |
| Intermediate | int_counterparty_exposure | Per-counterparty: total exposure, utilization vs limit |
| Mart | mart_risk_dashboard | Cross-portfolio risk summary with counterparty overlay |

## Retention Model

All demo tables include a `_loaded_at TIMESTAMP` column populated by dbt. Cleanup model runs as a post-hook:

```sql
-- Retention: delete records older than 1 hour
DELETE FROM {{ this }} WHERE _loaded_at < CURRENT_TIMESTAMP - INTERVAL '1 hour'
```

Iceberg snapshot expiry configured to keep last 6 snapshots (1 hour at 10-min intervals).

## Environment Namespaces

| Environment | K8s Namespace | Purpose |
|-------------|---------------|---------|
| dev | floe-dev | Development testing |
| staging | floe-staging | Promotion gate validation |
| prod | floe-prod | Production simulation |
| test | floe-test-{uuid} | E2E test isolation |

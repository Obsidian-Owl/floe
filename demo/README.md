# Demo: Customer 360 Data Product

This directory contains an example data product configuration demonstrating floe's data contract integration.

## Files

| File | Description |
|------|-------------|
| `floe.yaml` | Data product configuration (pipelines, schedules, ports) |
| `datacontract.yaml` | ODCS v3.1 data contract (schema, SLAs, quality rules) |

## Usage

```bash
# Validate the data product configuration
floe validate demo/

# Compile with contract validation
floe compile demo/

# Check for schema drift (requires database connection)
floe compile demo/ --drift-detection
```

## Data Contract Features Demonstrated

1. **Schema Definition** - Column types, constraints, PII classification
2. **SLA Properties** - Freshness (6h), availability (99.9%), latency (30s)
3. **Quality Rules** - Email format, UUID format, non-negative values
4. **Terms & Conditions** - Usage restrictions, retention policy
5. **Contacts** - Owner and technical contacts
6. **Links** - Catalog, documentation, monitoring dashboards

## Contract Validation

The `datacontract.yaml` is validated during `floe compile`:

- **FLOE-E500**: Contract not found (if neither file nor output_ports exist)
- **FLOE-E501**: Invalid ODCS syntax
- **FLOE-E510**: SLA weakening (if inheriting from parent contract)
- **FLOE-E511**: Classification weakening
- **FLOE-E530**: Type mismatch (during drift detection)

## Related Documentation

- [Data Contracts Architecture](../docs/architecture/data-contracts.md)
- [ODCS Standard](https://github.com/bitol-io/open-data-contract-standard)

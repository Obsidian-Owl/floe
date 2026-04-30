# Validate Your Data Product

Use this guide to prove that a data product produced useful outputs on a Floe platform.

## Validate Business Outputs

This is the current alpha repo-checkout evidence validator; a packaged product command is not available yet. In a product workspace, use the equivalent evidence requirements and run trigger your Platform Engineer provides.

```bash
make demo-customer-360-validate
```

Expected outcome:

- `evidence.business.customer_count` is a non-negative integer.
- `evidence.business.total_lifetime_value` is a non-negative decimal.

## Inspect Orchestration

Open Dagster using the service URL provided by your Platform Engineer.

Pass criteria:

- The latest Customer 360 run succeeded.
- The run uses the expected job or asset definitions.

## Inspect Storage

Open the object storage or Iceberg catalog view provided by your Platform Engineer.

Pass criteria:

- Customer 360 output objects or tables exist.
- The final customer mart is available for query.

## Inspect Lineage And Traces

Open Marquez and Jaeger using the service URLs provided by your Platform Engineer.

Pass criteria:

- Marquez shows Customer 360 jobs and datasets.
- Jaeger shows traces for the Customer 360 execution path.

## Troubleshooting

If validation fails:

- Check the product run status in Dagster.
- Check whether compiled artifacts match the platform manifest.
- Check storage outputs before lineage and trace checks.
- Ask the Platform Engineer to confirm platform service health if multiple products fail the same way.

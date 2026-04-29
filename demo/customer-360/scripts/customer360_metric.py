"""Query Customer 360 demo business metrics from DuckDB."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from contextlib import redirect_stdout
from pathlib import Path

import duckdb
import pyarrow.compute as pc
from floe_core.schemas.compiled_artifacts import CompiledArtifacts
from floe_orchestrator_dagster.validation.iceberg_outputs import (
    connect_catalog_from_artifacts,
    expected_iceberg_tables,
)

DEFAULT_DATABASE = "/tmp/floe/customer_360.duckdb"
DEFAULT_TABLE = "mart_customer_360"
DEFAULT_LIFETIME_VALUE_COLUMN = "total_spend"
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _identifier(value: str, field_name: str) -> str:
    """Validate a DuckDB identifier supplied by demo configuration."""
    if not IDENTIFIER_RE.fullmatch(value):
        raise argparse.ArgumentTypeError(f"{field_name} must be a simple SQL identifier")
    return value


def build_parser() -> argparse.ArgumentParser:
    """Build the Customer 360 metric query parser."""
    parser = argparse.ArgumentParser(description="Query Customer 360 demo metrics")
    parser.add_argument("metric", choices=("customer-count", "total-lifetime-value"))
    parser.add_argument("--source", choices=("duckdb", "iceberg"), default="duckdb")
    parser.add_argument("--artifacts-path", type=Path)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument(
        "--table",
        default=DEFAULT_TABLE,
        type=lambda value: _identifier(value, "--table"),
    )
    parser.add_argument(
        "--lifetime-value-column",
        default=DEFAULT_LIFETIME_VALUE_COLUMN,
        type=lambda value: _identifier(value, "--lifetime-value-column"),
    )
    return parser


def query_metric(
    *,
    source: str,
    artifacts_path: Path | None,
    database: str,
    table: str,
    metric: str,
    lifetime_value_column: str,
) -> object:
    """Return a Customer 360 business metric from the configured source."""
    if source == "iceberg":
        if artifacts_path is None:
            raise ValueError("--artifacts-path is required when --source=iceberg")
        artifacts = CompiledArtifacts.model_validate_json(artifacts_path.read_text())
        table_identifier = expected_iceberg_tables(artifacts, [table])[0]
        iceberg_table = connect_catalog_from_artifacts(artifacts).load_table(table_identifier)
        if metric == "customer-count":
            arrow_table = iceberg_table.scan(selected_fields=("customer_id",)).to_arrow()
            return arrow_table.num_rows
        if metric == "total-lifetime-value":
            arrow_table = iceberg_table.scan(selected_fields=(lifetime_value_column,)).to_arrow()
            result = pc.sum(arrow_table[lifetime_value_column]).as_py()
            return result or 0
        raise ValueError(f"Unsupported metric: {metric}")

    with duckdb.connect(database, read_only=True) as conn:
        if metric == "customer-count":
            count_row = conn.execute(f"select count(*) from {table}").fetchone()
            if count_row is None:
                raise RuntimeError("Customer count query returned no rows")
            return count_row[0]
        if metric == "total-lifetime-value":
            lifetime_value_row = conn.execute(
                f"select coalesce(sum({lifetime_value_column}), 0) from {table}"
            ).fetchone()
            if lifetime_value_row is None:
                raise RuntimeError("Lifetime value query returned no rows")
            return lifetime_value_row[0]
    raise ValueError(f"Unsupported metric: {metric}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Customer 360 metric query CLI."""
    args = build_parser().parse_args(argv)
    with redirect_stdout(sys.stderr):
        value = query_metric(
            database=args.database,
            table=args.table,
            metric=args.metric,
            source=args.source,
            artifacts_path=args.artifacts_path,
            lifetime_value_column=args.lifetime_value_column,
        )
    print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

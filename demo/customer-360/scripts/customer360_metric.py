"""Query Customer 360 demo business metrics from DuckDB."""

from __future__ import annotations

import argparse
import re
from collections.abc import Sequence

import duckdb

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
    database: str,
    table: str,
    metric: str,
    lifetime_value_column: str,
) -> object:
    """Return a Customer 360 business metric from the configured DuckDB table."""
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
    print(
        query_metric(
            database=args.database,
            table=args.table,
            metric=args.metric,
            lifetime_value_column=args.lifetime_value_column,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

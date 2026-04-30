#!/usr/bin/env python3
"""Run the Customer 360 golden demo Dagster job."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from testing.demo.customer360_runner import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_VALIDATION_MANIFEST,
    Customer360DagsterRunner,
    RunnerError,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the Customer 360 run CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validation-manifest",
        default=os.environ.get("FLOE_DEMO_VALIDATION_MANIFEST", str(DEFAULT_VALIDATION_MANIFEST)),
        help="YAML manifest containing Customer 360 Dagster launch metadata.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=os.environ.get("FLOE_DEMO_RUN_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)),
        help="Maximum time to wait for the Dagster run to finish.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=os.environ.get(
            "FLOE_DEMO_RUN_POLL_INTERVAL_SECONDS",
            str(DEFAULT_POLL_INTERVAL_SECONDS),
        ),
        help="Seconds between Dagster run status polls.",
    )
    return parser


def main() -> int:
    """Run the configured Customer 360 Dagster job."""
    parser = build_parser()
    args = parser.parse_args()
    runner = Customer360DagsterRunner(
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
    )
    try:
        runner.run(Path(args.validation_manifest))
    except (OSError, ValueError, RunnerError) as exc:
        if not isinstance(exc, RunnerError):
            print("status=FAIL")
            print(f"error={exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

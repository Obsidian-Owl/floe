#!/usr/bin/env python3
"""Validate the Customer 360 golden demo."""

from __future__ import annotations

import argparse
import os
import shlex

from testing.demo.customer360_validator import (
    Customer360Config,
    Customer360Validator,
    ValidationResult,
)


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _command_arg(value: str | None) -> list[str] | None:
    if value is None or not value.strip():
        return None
    return shlex.split(value)


def _parse_command_arg(
    parser: argparse.ArgumentParser,
    option_name: str,
    value: str | None,
) -> list[str] | None:
    try:
        return _command_arg(value)
    except ValueError as exc:
        parser.error(f"invalid {option_name}: {exc}")


def _comma_separated(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def print_result(result: ValidationResult) -> int:
    """Print deterministic validation output and return a process exit code."""
    print(f"status={result.status}")
    for key, value in sorted(result.evidence.items()):
        print(f"evidence.{key}={value}")
    for failure in result.failures:
        print(f"failure={failure}")
    return 1 if result.failures else 0


def build_parser() -> argparse.ArgumentParser:
    """Build the Customer 360 validation CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--namespace",
        default=_env("FLOE_DEMO_NAMESPACE", "floe-dev"),
        help="Kubernetes namespace containing the demo platform.",
    )
    parser.add_argument(
        "--dagster-url",
        default=_env("FLOE_DEMO_DAGSTER_URL", "http://localhost:3100"),
        help="Base URL for Dagster webserver.",
    )
    parser.add_argument(
        "--marquez-url",
        default=_env("FLOE_DEMO_MARQUEZ_URL", "http://localhost:5100"),
        help="Base URL for Marquez API.",
    )
    parser.add_argument(
        "--jaeger-url",
        default=_env("FLOE_DEMO_JAEGER_URL", "http://localhost:16686"),
        help="Base URL for Jaeger query API.",
    )
    parser.add_argument(
        "--platform-expected-services",
        default=_env(
            "FLOE_DEMO_PLATFORM_EXPECTED_SERVICES",
            "dagster,polaris,minio,jaeger,marquez",
        ),
        help="Comma-separated pod name fragments required for platform readiness.",
    )
    parser.add_argument(
        "--command-timeout-seconds",
        type=float,
        default=float(_env("FLOE_DEMO_COMMAND_TIMEOUT_SECONDS", "30")),
        help="Timeout for default validation commands.",
    )
    parser.add_argument(
        "--dagster-run-check-command",
        default=os.environ.get("FLOE_DEMO_DAGSTER_RUN_CHECK_COMMAND"),
        help="Command proving a Customer 360 Dagster run completed.",
    )
    parser.add_argument(
        "--dagster-expected-text",
        default=_env("FLOE_DEMO_DAGSTER_EXPECTED_TEXT", "customer_360"),
        help="Text expected in Dagster run check command output.",
    )
    parser.add_argument(
        "--lineage-check-command",
        default=os.environ.get("FLOE_DEMO_LINEAGE_CHECK_COMMAND"),
        help="Command proving Customer 360 lineage/job/dataset evidence exists.",
    )
    parser.add_argument(
        "--lineage-expected-text",
        default=_env("FLOE_DEMO_LINEAGE_EXPECTED_TEXT", "customer_360"),
        help="Text expected in lineage check command output.",
    )
    parser.add_argument(
        "--tracing-check-command",
        default=os.environ.get("FLOE_DEMO_TRACING_CHECK_COMMAND"),
        help="Command proving Customer 360 trace evidence exists.",
    )
    parser.add_argument(
        "--tracing-expected-text",
        default=_env("FLOE_DEMO_TRACING_EXPECTED_TEXT", "customer_360"),
        help="Text expected in tracing check command output.",
    )
    parser.add_argument(
        "--storage-check-command",
        default=os.environ.get("FLOE_DEMO_STORAGE_CHECK_COMMAND"),
        help="Command proving Customer 360 storage outputs exist.",
    )
    parser.add_argument(
        "--storage-expected-text",
        default=_env("FLOE_DEMO_STORAGE_EXPECTED_TEXT", "customer_360"),
        help="Text expected in storage check command output.",
    )
    parser.add_argument(
        "--customer-count-command",
        default=os.environ.get("FLOE_DEMO_CUSTOMER_COUNT_COMMAND"),
        help="Command returning the Customer 360 customer count.",
    )
    parser.add_argument(
        "--lifetime-value-command",
        default=os.environ.get("FLOE_DEMO_LIFETIME_VALUE_COMMAND"),
        help="Command returning the Customer 360 total lifetime value.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = Customer360Config(
        namespace=args.namespace,
        dagster_url=args.dagster_url,
        marquez_url=args.marquez_url,
        jaeger_url=args.jaeger_url,
        platform_expected_services=_comma_separated(args.platform_expected_services),
        command_timeout_seconds=args.command_timeout_seconds,
        dagster_run_check_command=_parse_command_arg(
            parser,
            "--dagster-run-check-command",
            args.dagster_run_check_command,
        ),
        dagster_expected_text=args.dagster_expected_text,
        lineage_check_command=_parse_command_arg(
            parser,
            "--lineage-check-command",
            args.lineage_check_command,
        ),
        lineage_expected_text=args.lineage_expected_text,
        tracing_check_command=_parse_command_arg(
            parser,
            "--tracing-check-command",
            args.tracing_check_command,
        ),
        tracing_expected_text=args.tracing_expected_text,
        storage_check_command=_parse_command_arg(
            parser,
            "--storage-check-command",
            args.storage_check_command,
        ),
        storage_expected_text=args.storage_expected_text,
        customer_count_command=_parse_command_arg(
            parser,
            "--customer-count-command",
            args.customer_count_command,
        ),
        lifetime_value_command=_parse_command_arg(
            parser,
            "--lifetime-value-command",
            args.lifetime_value_command,
        ),
    )
    result = Customer360Validator(config=config).validate()
    return print_result(result)


if __name__ == "__main__":
    raise SystemExit(main())

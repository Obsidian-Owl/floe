#!/usr/bin/env python3
"""Validate the Customer 360 golden demo."""

from __future__ import annotations

import argparse
import os
import shlex
from dataclasses import replace
from pathlib import Path

from testing.ci.customer360_observability import (
    Customer360ObservabilityConfig,
    validate_customer360_observability,
)
from testing.demo.customer360_validator import (
    DEFAULT_VALIDATION_MANIFEST,
    Customer360Config,
    Customer360Validator,
    ValidationResult,
    load_customer360_config,
)


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


def _optional_float_env(parser: argparse.ArgumentParser, name: str) -> float | None:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return None
    try:
        return float(raw_value)
    except ValueError:
        parser.error(f"invalid {name}: expected a floating-point number, got {raw_value!r}")


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
        "--validation-manifest",
        default=os.environ.get("FLOE_DEMO_VALIDATION_MANIFEST", str(DEFAULT_VALIDATION_MANIFEST)),
        help="YAML manifest containing default Customer 360 validation evidence checks.",
    )
    parser.add_argument(
        "--namespace",
        default=os.environ.get("FLOE_DEMO_NAMESPACE"),
        help="Kubernetes namespace containing the demo platform.",
    )
    parser.add_argument(
        "--dagster-url",
        default=os.environ.get("FLOE_DEMO_DAGSTER_URL"),
        help="Base URL for Dagster webserver.",
    )
    parser.add_argument(
        "--marquez-url",
        default=os.environ.get("FLOE_DEMO_MARQUEZ_URL"),
        help="Base URL for Marquez API.",
    )
    parser.add_argument(
        "--jaeger-url",
        default=os.environ.get("FLOE_DEMO_JAEGER_URL"),
        help="Base URL for Jaeger query API.",
    )
    parser.add_argument(
        "--loki-url",
        default=os.environ.get("FLOE_DEMO_LOKI_URL"),
        help="Base URL for Loki query API.",
    )
    parser.add_argument(
        "--prometheus-url",
        default=os.environ.get("FLOE_DEMO_PROMETHEUS_URL"),
        help="Base URL for Prometheus API.",
    )
    parser.add_argument(
        "--run-id",
        default=os.environ.get("FLOE_DEMO_RUN_ID"),
        help="Customer 360 Dagster run id to validate. Defaults to the run evidence file.",
    )
    parser.add_argument(
        "--run-evidence-file",
        default=os.environ.get("FLOE_DEMO_RUN_EVIDENCE_FILE", ".customer360-run.env"),
        help="Path containing dagster.run_id output from make demo-customer-360-run.",
    )
    parser.add_argument(
        "--observability-freshness-seconds",
        type=float,
        default=_optional_float_env(parser, "FLOE_DEMO_OBSERVABILITY_FRESHNESS_SECONDS"),
        help="Maximum age for Customer 360 observability evidence.",
    )
    parser.add_argument(
        "--platform-expected-services",
        default=os.environ.get("FLOE_DEMO_PLATFORM_EXPECTED_SERVICES"),
        help="Comma-separated pod name fragments required for platform readiness.",
    )
    parser.add_argument(
        "--command-timeout-seconds",
        type=float,
        default=_optional_float_env(parser, "FLOE_DEMO_COMMAND_TIMEOUT_SECONDS"),
        help="Timeout for default validation commands.",
    )
    parser.add_argument(
        "--dagster-run-check-command",
        default=os.environ.get("FLOE_DEMO_DAGSTER_RUN_CHECK_COMMAND"),
        help="Command proving a Customer 360 Dagster run completed.",
    )
    parser.add_argument(
        "--dagster-expected-text",
        default=os.environ.get("FLOE_DEMO_DAGSTER_EXPECTED_TEXT"),
        help="Text expected in Dagster run check command output.",
    )
    parser.add_argument(
        "--lineage-check-command",
        default=os.environ.get("FLOE_DEMO_LINEAGE_CHECK_COMMAND"),
        help="Command proving Customer 360 lineage/job/dataset evidence exists.",
    )
    parser.add_argument(
        "--lineage-expected-text",
        default=os.environ.get("FLOE_DEMO_LINEAGE_EXPECTED_TEXT"),
        help="Text expected in lineage check command output.",
    )
    parser.add_argument(
        "--tracing-check-command",
        default=os.environ.get("FLOE_DEMO_TRACING_CHECK_COMMAND"),
        help="Command proving Customer 360 trace evidence exists.",
    )
    parser.add_argument(
        "--tracing-expected-text",
        default=os.environ.get("FLOE_DEMO_TRACING_EXPECTED_TEXT"),
        help="Text expected in tracing check command output.",
    )
    parser.add_argument(
        "--storage-check-command",
        default=os.environ.get("FLOE_DEMO_STORAGE_CHECK_COMMAND"),
        help="Command proving Customer 360 storage outputs exist.",
    )
    parser.add_argument(
        "--storage-expected-text",
        default=os.environ.get("FLOE_DEMO_STORAGE_EXPECTED_TEXT"),
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
    try:
        manifest_config = load_customer360_config(Path(args.validation_manifest))
    except (OSError, ValueError) as exc:
        parser.error(f"invalid --validation-manifest: {exc}")

    platform_expected_services = (
        _comma_separated(args.platform_expected_services)
        if args.platform_expected_services
        else manifest_config.platform_expected_services
    )
    config = Customer360Config(
        namespace=args.namespace or manifest_config.namespace,
        dagster_url=args.dagster_url or manifest_config.dagster_url,
        marquez_url=args.marquez_url or manifest_config.marquez_url,
        jaeger_url=args.jaeger_url or manifest_config.jaeger_url,
        platform_expected_services=platform_expected_services,
        command_timeout_seconds=args.command_timeout_seconds
        if args.command_timeout_seconds is not None
        else manifest_config.command_timeout_seconds,
        dagster_run_check_command=_parse_command_arg(
            parser,
            "--dagster-run-check-command",
            args.dagster_run_check_command,
        )
        or manifest_config.dagster_run_check_command,
        dagster_expected_text=args.dagster_expected_text or manifest_config.dagster_expected_text,
        lineage_check_command=_parse_command_arg(
            parser,
            "--lineage-check-command",
            args.lineage_check_command,
        )
        or manifest_config.lineage_check_command,
        lineage_expected_text=args.lineage_expected_text or manifest_config.lineage_expected_text,
        tracing_check_command=_parse_command_arg(
            parser,
            "--tracing-check-command",
            args.tracing_check_command,
        )
        or manifest_config.tracing_check_command,
        tracing_expected_text=args.tracing_expected_text or manifest_config.tracing_expected_text,
        storage_check_command=_parse_command_arg(
            parser,
            "--storage-check-command",
            args.storage_check_command,
        )
        or manifest_config.storage_check_command,
        storage_expected_text=args.storage_expected_text or manifest_config.storage_expected_text,
        customer_count_command=_parse_command_arg(
            parser,
            "--customer-count-command",
            args.customer_count_command,
        )
        or manifest_config.customer_count_command,
        lifetime_value_command=_parse_command_arg(
            parser,
            "--lifetime-value-command",
            args.lifetime_value_command,
        )
        or manifest_config.lifetime_value_command,
    )
    result = Customer360Validator(config=config).validate()
    observability_config = Customer360ObservabilityConfig.from_env()
    observability_result = validate_customer360_observability(
        replace(
            observability_config,
            dagster_url=config.dagster_url,
            jaeger_url=config.jaeger_url,
            loki_url=args.loki_url or observability_config.loki_url,
            prometheus_url=args.prometheus_url or observability_config.prometheus_url,
            marquez_url=config.marquez_url,
            run_id=args.run_id.strip() if args.run_id and args.run_id.strip() else None,
            run_evidence_file=Path(args.run_evidence_file) if args.run_evidence_file else None,
            freshness_window_seconds=args.observability_freshness_seconds
            if args.observability_freshness_seconds is not None
            else float(os.environ.get("FLOE_DEMO_OBSERVABILITY_FRESHNESS_SECONDS", "1800")),
            timeout_seconds=config.command_timeout_seconds,
        )
    )
    result = _merge_validation_results(
        result,
        observability_result.evidence,
        observability_result.failures,
    )
    return print_result(result)


def _merge_validation_results(
    result: ValidationResult,
    evidence: dict[str, str],
    failures: list[str],
) -> ValidationResult:
    merged_evidence = dict(result.evidence)
    merged_evidence.update(evidence)
    merged_failures = [*result.failures, *failures]
    return ValidationResult(
        status="FAIL" if merged_failures else "PASS",
        evidence=merged_evidence,
        failures=merged_failures,
    )


if __name__ == "__main__":
    raise SystemExit(main())

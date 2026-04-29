"""Tests for Customer 360 golden demo validation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from testing.demo.customer360_validator import (
    Customer360Config,
    Customer360Validator,
    ValidationResult,
)


class FakeRunner:
    """Command runner that returns predefined command output."""

    def __init__(self, responses: dict[tuple[str, ...], str]) -> None:
        self.responses = responses
        self.commands: list[tuple[str, ...]] = []

    def __call__(self, command: list[str]) -> str:
        key = tuple(command)
        self.commands.append(key)
        if key not in self.responses:
            raise AssertionError(f"Unexpected command: {command}")
        return self.responses[key]


def _healthy_runner() -> FakeRunner:
    return FakeRunner(
        {
            ("kubectl", "get", "pods", "-n", "floe-dev", "-o", "json"): json.dumps(
                {"items": [{"metadata": {"name": "dagster"}, "status": {"phase": "Running"}}]}
            ),
            ("curl", "-fsS", "http://localhost:3100/server_info"): "{}",
            ("curl", "-fsS", "http://localhost:5100/api/v1/namespaces"): json.dumps(
                {"namespaces": [{"name": "customer_360"}]}
            ),
            ("curl", "-fsS", "http://localhost:16686/api/services"): json.dumps(
                {"data": ["dagster"]}
            ),
        }
    )


@pytest.mark.requirement("alpha-demo")
def test_customer360_validator_reports_checked_service_evidence() -> None:
    """Validator does not treat reachable services as Customer 360 evidence."""
    runner = _healthy_runner()

    result = Customer360Validator(command_runner=runner).validate()

    assert result.status == "FAIL"
    assert result.evidence["platform.ready"] == "true"
    assert result.evidence["dagster.customer_360_run"] == "unknown"
    assert result.evidence["lineage.marquez_customer_360"] == "unknown"
    assert result.evidence["tracing.jaeger_customer_360"] == "unknown"
    assert result.evidence["storage.customer_360_outputs"] == "unknown"
    assert result.evidence["business.customer_count"] == "unknown"
    assert result.evidence["business.total_lifetime_value"] == "unknown"
    assert "Customer 360 Dagster run check is not configured" in result.failures
    assert "Customer 360 lineage check is not configured" in result.failures
    assert "Customer 360 tracing check is not configured" in result.failures
    assert "Customer 360 storage outputs check is not configured" in result.failures


@pytest.mark.requirement("alpha-demo")
def test_customer360_validator_fails_when_lineage_output_lacks_customer360_text() -> None:
    """Validator fails clearly when configured lineage evidence is not Customer 360-specific."""
    runner = _healthy_runner()
    runner.responses.update(
        {
            ("marquez", "lineage", "list"): "default.orders\n",
        }
    )
    config = Customer360Config(
        lineage_check_command=["marquez", "lineage", "list"],
        lineage_expected_text="customer_360",
    )

    result = Customer360Validator(config=config, command_runner=runner).validate()

    assert result.status == "FAIL"
    assert result.evidence["lineage.marquez_customer_360"] == "false"
    assert "Customer 360 lineage evidence was not found" in result.failures


@pytest.mark.requirement("alpha-demo")
def test_customer360_validator_uses_configurable_namespace_and_urls() -> None:
    """Validator command checks derive from config rather than hardcoded defaults."""
    config = Customer360Config(
        namespace="custom-ns",
        dagster_url="http://dagster.example",
        marquez_url="http://marquez.example",
        jaeger_url="http://jaeger.example",
    )
    runner = FakeRunner(
        {
            ("kubectl", "get", "pods", "-n", "custom-ns", "-o", "json"): json.dumps(
                {"items": [{"metadata": {"name": "dagster"}, "status": {"phase": "Running"}}]}
            ),
            ("curl", "-fsS", "http://dagster.example/server_info"): "{}",
            ("curl", "-fsS", "http://marquez.example/api/v1/namespaces"): json.dumps(
                {"namespaces": [{"name": "customer-360"}]}
            ),
            ("curl", "-fsS", "http://jaeger.example/api/services"): json.dumps({"data": ["floe"]}),
        }
    )

    Customer360Validator(config=config, command_runner=runner).validate()

    assert runner.commands == [
        ("kubectl", "get", "pods", "-n", "custom-ns", "-o", "json"),
        ("curl", "-fsS", "http://dagster.example/server_info"),
        ("curl", "-fsS", "http://marquez.example/api/v1/namespaces"),
        ("curl", "-fsS", "http://jaeger.example/api/services"),
    ]


@pytest.mark.requirement("alpha-demo")
def test_customer360_validator_can_check_storage_and_business_with_configured_commands() -> None:
    """Storage and business evidence can pass when explicit checks are configured."""
    runner = _healthy_runner()
    runner.responses.update(
        {
            ("dagster", "runs", "list"): "run_id=abc job=customer_360 status=SUCCESS\n",
            ("marquez", "lineage", "list"): "dataset=floe.customer_360_customers\n",
            ("jaeger", "trace", "list"): "trace service=floe op=customer_360_pipeline\n",
            ("mc", "ls", "local/floe/customer_360/"): "customer_360_outputs.parquet",
            ("duckdb", "customer360.duckdb", "-c", "select count(*) from customer_360"): "42\n",
            (
                "duckdb",
                "customer360.duckdb",
                "-c",
                "select sum(lifetime_value) from customer_360",
            ): "12345.67\n",
        }
    )
    config = Customer360Config(
        dagster_run_check_command=["dagster", "runs", "list"],
        lineage_check_command=["marquez", "lineage", "list"],
        tracing_check_command=["jaeger", "trace", "list"],
        storage_check_command=["mc", "ls", "local/floe/customer_360/"],
        storage_expected_text="customer_360_outputs",
        customer_count_command=[
            "duckdb",
            "customer360.duckdb",
            "-c",
            "select count(*) from customer_360",
        ],
        lifetime_value_command=[
            "duckdb",
            "customer360.duckdb",
            "-c",
            "select sum(lifetime_value) from customer_360",
        ],
    )

    result = Customer360Validator(config=config, command_runner=runner).validate()

    assert result.status == "PASS"
    assert result.evidence["storage.customer_360_outputs"] == "true"
    assert result.evidence["business.customer_count"] == "42"
    assert result.evidence["business.total_lifetime_value"] == "12345.67"


@pytest.mark.requirement("alpha-demo")
def test_customer360_validator_can_check_customer360_service_evidence_with_commands() -> None:
    """Dagster, lineage, and tracing evidence pass only from Customer 360-specific output."""
    runner = _healthy_runner()
    runner.responses.update(
        {
            ("dagster", "runs", "list"): "run_id=abc job=customer_360 status=SUCCESS\n",
            ("marquez", "lineage", "list"): "dataset=floe.customer_360_customers\n",
            ("jaeger", "trace", "list"): "trace service=floe op=customer_360_pipeline\n",
            ("mc", "ls", "local/floe/customer_360/"): "customer_360_outputs.parquet",
            ("duckdb", "customer360.duckdb", "-c", "select count(*) from customer_360"): "42\n",
            (
                "duckdb",
                "customer360.duckdb",
                "-c",
                "select sum(lifetime_value) from customer_360",
            ): "12345.67\n",
        }
    )
    config = Customer360Config(
        dagster_run_check_command=["dagster", "runs", "list"],
        dagster_expected_text="customer_360",
        lineage_check_command=["marquez", "lineage", "list"],
        lineage_expected_text="customer_360",
        tracing_check_command=["jaeger", "trace", "list"],
        tracing_expected_text="customer_360",
        storage_check_command=["mc", "ls", "local/floe/customer_360/"],
        storage_expected_text="customer_360_outputs",
        customer_count_command=[
            "duckdb",
            "customer360.duckdb",
            "-c",
            "select count(*) from customer_360",
        ],
        lifetime_value_command=[
            "duckdb",
            "customer360.duckdb",
            "-c",
            "select sum(lifetime_value) from customer_360",
        ],
    )

    result = Customer360Validator(config=config, command_runner=runner).validate()

    assert result.status == "PASS"
    assert result.evidence["dagster.customer_360_run"] == "true"
    assert result.evidence["lineage.marquez_customer_360"] == "true"
    assert result.evidence["tracing.jaeger_customer_360"] == "true"


@pytest.mark.requirement("alpha-demo")
def test_cli_prints_deterministic_output_and_returns_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI output is stable and returns nonzero when validation has failures."""
    module_path = Path("testing/ci/validate-customer-360-demo.py")
    spec = importlib.util.spec_from_file_location("validate_customer_360_demo", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    result = ValidationResult(
        status="FAIL",
        evidence={"z.key": "last", "a.key": "first"},
        failures=["first failure", "second failure"],
    )

    exit_code = module.print_result(result)

    assert exit_code == 1
    assert capsys.readouterr().out.splitlines() == [
        "status=FAIL",
        "evidence.a.key=first",
        "evidence.z.key=last",
        "failure=first failure",
        "failure=second failure",
    ]


@pytest.mark.requirement("alpha-demo")
def test_cli_accepts_customer360_evidence_command_arguments() -> None:
    """CLI parser exposes Customer 360-specific evidence command arguments."""
    module_path = Path("testing/ci/validate-customer-360-demo.py")
    spec = importlib.util.spec_from_file_location("validate_customer_360_demo", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    args = module.build_parser().parse_args(
        [
            "--dagster-run-check-command",
            "dagster runs list",
            "--dagster-expected-text",
            "customer-360",
            "--lineage-check-command",
            "marquez lineage list",
            "--lineage-expected-text",
            "customer-360",
            "--tracing-check-command",
            "jaeger trace list",
            "--tracing-expected-text",
            "customer-360",
        ]
    )

    assert args.dagster_run_check_command == "dagster runs list"
    assert args.dagster_expected_text == "customer-360"
    assert args.lineage_check_command == "marquez lineage list"
    assert args.lineage_expected_text == "customer-360"
    assert args.tracing_check_command == "jaeger trace list"
    assert args.tracing_expected_text == "customer-360"

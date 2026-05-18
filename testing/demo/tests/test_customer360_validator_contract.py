"""Contract tests for Customer 360 alpha validator evidence output."""

from __future__ import annotations

import json

from testing.demo.customer360_validator import (
    Customer360Config,
    Customer360Validator,
)


def test_customer360_validator_emits_normalized_evidence_and_compatibility_keys() -> None:
    """Successful validation emits alpha key families without dropping old keys."""
    config = Customer360Config(
        namespace="floe-test",
        dagster_run_check_command=["dagster-run"],
        lineage_check_command=["lineage"],
        tracing_check_command=["tracing"],
        storage_check_command=["storage"],
        customer_count_command=["customer-count"],
        lifetime_value_command=["lifetime-value"],
    )

    def run(command: list[str]) -> str:
        if command[:3] == ["kubectl", "get", "pods"]:
            return json.dumps(
                {
                    "items": [
                        _ready_pod("dagster-webserver"),
                        _ready_pod("polaris"),
                        _ready_pod("minio"),
                        _ready_pod("jaeger"),
                        _ready_pod("marquez"),
                    ]
                }
            )
        return {
            ("curl", "-fsS", "http://localhost:3100/server_info"): "{}",
            ("curl", "-fsS", "http://localhost:5100/api/v1/namespaces"): "{}",
            ("curl", "-fsS", "http://localhost:16686/api/services"): "{}",
            ("dagster-run",): "customer_360",
            ("lineage",): "customer_360",
            ("tracing",): "customer_360",
            ("storage",): "customer_360",
            ("customer-count",): "500",
            ("lifetime-value",): "1194501.08",
        }[tuple(command)]

    result = Customer360Validator(config=config, command_runner=run).validate()

    assert result.status == "PASS"
    assert result.failures == []
    assert result.evidence["dagster.customer_360_run"] == "true"
    assert result.evidence["storage.customer_360_outputs"] == "true"
    assert result.evidence["run_control.namespace"] == "floe-test"
    assert result.evidence["run_control.runtime_context"] == "devpod_flux"
    assert result.evidence["run_control.dagster.status"] == "pass"
    assert result.evidence["run_control.dagster.job_name"] == "customer_360"
    assert result.evidence["storage.iceberg.customer_360_outputs"] == "true"
    assert result.evidence["business.customer_count"] == "500"


def test_customer360_validator_classifies_unhealthy_platform_services() -> None:
    """Missing ready platform pods are platform service failures."""
    config = Customer360Config(platform_expected_services=("dagster",))

    def run(command: list[str]) -> str:
        if command[:3] == ["kubectl", "get", "pods"]:
            return json.dumps({"items": [_not_ready_pod("dagster-webserver")]})
        return "{}"

    result = Customer360Validator(config=config, command_runner=run).validate()

    assert result.status == "FAIL"
    assert result.evidence["platform.ready"] == "false"
    assert result.evidence["run_control.namespace"] == "floe-dev"
    assert result.evidence["run_control.runtime_context"] == "local"
    assert any(
        failure.startswith("platform_service_failure: Expected platform services")
        for failure in result.failures
    )


def test_customer360_validator_classifies_missing_checks_as_contract_gaps() -> None:
    """Missing validation commands are contract gaps, not product failures."""
    config = Customer360Config(platform_expected_services=("dagster",))

    def run(command: list[str]) -> str:
        if command[:3] == ["kubectl", "get", "pods"]:
            return json.dumps({"items": [_ready_pod("dagster-webserver")]})
        return "{}"

    result = Customer360Validator(config=config, command_runner=run).validate()

    assert result.status == "FAIL"
    assert any(
        failure == "contract_gap: Customer 360 storage outputs check is not configured"
        for failure in result.failures
    )
    assert any(
        failure == "contract_gap: Customer 360 customer count check is not configured"
        for failure in result.failures
    )


def test_customer360_validator_classifies_business_assertion_failures() -> None:
    """Invalid generated mart assertions are product failures."""
    config = Customer360Config(
        platform_expected_services=("dagster",),
        customer_count_command=["customer-count"],
    )

    def run(command: list[str]) -> str:
        if command[:3] == ["kubectl", "get", "pods"]:
            return json.dumps({"items": [_ready_pod("dagster-webserver")]})
        if command == ["customer-count"]:
            return "-1"
        return "{}"

    result = Customer360Validator(config=config, command_runner=run).validate()

    assert result.status == "FAIL"
    assert any(
        failure == "product_failure: Customer 360 customer count check returned negative value"
        for failure in result.failures
    )


def _ready_pod(name: str) -> dict[str, object]:
    return {
        "metadata": {"name": name},
        "status": {"phase": "Running", "conditions": [{"type": "Ready", "status": "True"}]},
    }


def _not_ready_pod(name: str) -> dict[str, object]:
    return {
        "metadata": {"name": name},
        "status": {"phase": "Running", "conditions": [{"type": "Ready", "status": "False"}]},
    }

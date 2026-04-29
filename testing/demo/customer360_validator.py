"""Customer 360 demo validation helpers."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

CommandRunner = Callable[[list[str]], str]
DEFAULT_COMMAND_TIMEOUT_SECONDS = 30.0
DEFAULT_PLATFORM_SERVICE_FRAGMENTS = ("dagster", "polaris", "minio", "jaeger", "marquez")

EXPECTED_EVIDENCE_KEYS = (
    "platform.ready",
    "dagster.customer_360_run",
    "storage.customer_360_outputs",
    "lineage.marquez_customer_360",
    "tracing.jaeger_customer_360",
    "business.customer_count",
    "business.total_lifetime_value",
)


def default_command_runner(
    command: list[str],
    *,
    timeout_seconds: float = DEFAULT_COMMAND_TIMEOUT_SECONDS,
) -> str:
    """Run a command without a shell and return stdout."""
    try:
        return subprocess.check_output(command, text=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"Command timed out after {timeout_seconds:g}s: {command}") from exc


@dataclass(frozen=True)
class Customer360Config:
    """Configuration for Customer 360 demo validation checks."""

    namespace: str = "floe-dev"
    dagster_url: str = "http://localhost:3100"
    marquez_url: str = "http://localhost:5100"
    jaeger_url: str = "http://localhost:16686"
    platform_expected_services: tuple[str, ...] = DEFAULT_PLATFORM_SERVICE_FRAGMENTS
    command_timeout_seconds: float = DEFAULT_COMMAND_TIMEOUT_SECONDS
    dagster_run_check_command: list[str] | None = None
    dagster_expected_text: str = "customer_360"
    lineage_check_command: list[str] | None = None
    lineage_expected_text: str = "customer_360"
    tracing_check_command: list[str] | None = None
    tracing_expected_text: str = "customer_360"
    storage_check_command: list[str] | None = None
    storage_expected_text: str = "customer_360"
    customer_count_command: list[str] | None = None
    lifetime_value_command: list[str] | None = None


@dataclass(frozen=True)
class ValidationResult:
    """Customer 360 validation result."""

    status: str
    evidence: dict[str, str] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


class Customer360Validator:
    """Validate Customer 360 demo outcomes through service APIs and commands."""

    def __init__(
        self,
        *,
        config: Customer360Config | None = None,
        command_runner: CommandRunner = default_command_runner,
    ) -> None:
        self._config = config or Customer360Config()
        self._run: CommandRunner
        if command_runner is default_command_runner:
            self._run = lambda command: default_command_runner(
                command,
                timeout_seconds=self._config.command_timeout_seconds,
            )
        else:
            self._run = command_runner

    def validate(self) -> ValidationResult:
        """Validate service health and Customer 360 evidence."""
        evidence = dict.fromkeys(EXPECTED_EVIDENCE_KEYS, "unknown")
        failures: list[str] = []

        self._check_platform(evidence, failures)
        self._check_dagster(evidence, failures)
        self._check_marquez(evidence, failures)
        self._check_jaeger(evidence, failures)
        self._check_storage(evidence, failures)
        self._check_business_metric(
            evidence=evidence,
            failures=failures,
            key="business.customer_count",
            command=self._config.customer_count_command,
            missing_message="Customer 360 customer count check is not configured",
            empty_message="Customer 360 customer count check returned no value",
            integer=True,
        )
        self._check_business_metric(
            evidence=evidence,
            failures=failures,
            key="business.total_lifetime_value",
            command=self._config.lifetime_value_command,
            missing_message="Customer 360 lifetime value check is not configured",
            empty_message="Customer 360 lifetime value check returned no value",
            integer=False,
        )

        return ValidationResult(
            status="FAIL" if failures else "PASS",
            evidence=evidence,
            failures=failures,
        )

    def _check_platform(self, evidence: dict[str, str], failures: list[str]) -> None:
        expected_services = tuple(
            service.strip()
            for service in self._config.platform_expected_services
            if service.strip()
        )
        if not expected_services:
            evidence["platform.ready"] = "false"
            failures.append("Platform expected services must contain at least one service fragment")
            return

        command = ["kubectl", "get", "pods", "-n", self._config.namespace, "-o", "json"]
        try:
            pods = json.loads(self._run(command))
        except Exception as exc:  # noqa: BLE001 - validation should report all failures.
            evidence["platform.ready"] = "false"
            failures.append(f"Unable to inspect Kubernetes pods: {exc}")
            return

        ready_pods = [
            item
            for item in pods.get("items", [])
            if isinstance(item, dict) and _is_ready_running_pod(item)
        ]
        ready_pod_names = [
            str(item.get("metadata", {}).get("name", ""))
            for item in ready_pods
            if isinstance(item.get("metadata"), dict)
        ]
        missing_services = [
            service
            for service in expected_services
            if not any(service in pod_name for pod_name in ready_pod_names)
        ]
        ready = not missing_services
        evidence["platform.ready"] = str(ready).lower()
        if missing_services:
            failures.append(
                f"Expected platform services are not ready in namespace {self._config.namespace}: "
                f"{', '.join(missing_services)}"
            )

    def _check_dagster(self, evidence: dict[str, str], failures: list[str]) -> None:
        url = _join_url(self._config.dagster_url, "server_info")
        try:
            self._run(["curl", "-fsS", url])
        except Exception as exc:  # noqa: BLE001
            failures.append(f"Dagster API is not reachable: {exc}")

        self._check_expected_text_command(
            evidence=evidence,
            failures=failures,
            key="dagster.customer_360_run",
            command=self._config.dagster_run_check_command,
            expected_text=self._config.dagster_expected_text,
            missing_message="Customer 360 Dagster run check is not configured",
            failed_message="Customer 360 Dagster run check failed",
            not_found_message="Customer 360 Dagster run evidence was not found",
            invalid_expected_message="Customer 360 Dagster expected text must be non-empty",
        )

    def _check_marquez(self, evidence: dict[str, str], failures: list[str]) -> None:
        url = _join_url(self._config.marquez_url, "api/v1/namespaces")
        try:
            json.loads(self._run(["curl", "-fsS", url]))
        except Exception as exc:  # noqa: BLE001
            failures.append(f"Unable to inspect Marquez namespaces: {exc}")

        self._check_expected_text_command(
            evidence=evidence,
            failures=failures,
            key="lineage.marquez_customer_360",
            command=self._config.lineage_check_command,
            expected_text=self._config.lineage_expected_text,
            missing_message="Customer 360 lineage check is not configured",
            failed_message="Customer 360 lineage check failed",
            not_found_message="Customer 360 lineage evidence was not found",
            invalid_expected_message="Customer 360 lineage expected text must be non-empty",
        )

    def _check_jaeger(self, evidence: dict[str, str], failures: list[str]) -> None:
        url = _join_url(self._config.jaeger_url, "api/services")
        try:
            json.loads(self._run(["curl", "-fsS", url]))
        except Exception as exc:  # noqa: BLE001
            failures.append(f"Unable to inspect Jaeger services: {exc}")

        self._check_expected_text_command(
            evidence=evidence,
            failures=failures,
            key="tracing.jaeger_customer_360",
            command=self._config.tracing_check_command,
            expected_text=self._config.tracing_expected_text,
            missing_message="Customer 360 tracing check is not configured",
            failed_message="Customer 360 tracing check failed",
            not_found_message="Customer 360 tracing evidence was not found",
            invalid_expected_message="Customer 360 tracing expected text must be non-empty",
        )

    def _check_storage(self, evidence: dict[str, str], failures: list[str]) -> None:
        command = self._config.storage_check_command
        if command is None:
            evidence["storage.customer_360_outputs"] = "unknown"
            failures.append("Customer 360 storage outputs check is not configured")
            return
        expected_text = self._config.storage_expected_text.strip()
        if not expected_text:
            evidence["storage.customer_360_outputs"] = "false"
            failures.append("Customer 360 storage expected text must be non-empty")
            return

        try:
            output = self._run(command)
        except Exception as exc:  # noqa: BLE001
            evidence["storage.customer_360_outputs"] = "false"
            failures.append(f"Customer 360 storage outputs check failed: {exc}")
            return

        found = expected_text in output
        evidence["storage.customer_360_outputs"] = str(found).lower()
        if not found:
            failures.append("Customer 360 storage outputs were not found")

    def _check_business_metric(
        self,
        *,
        evidence: dict[str, str],
        failures: list[str],
        key: str,
        command: list[str] | None,
        missing_message: str,
        empty_message: str,
        integer: bool,
    ) -> None:
        if command is None:
            evidence[key] = "unknown"
            failures.append(missing_message)
            return
        metric_label = empty_message.removesuffix(" returned no value")

        try:
            output = self._run(command).strip()
        except Exception as exc:  # noqa: BLE001
            evidence[key] = "false"
            failures.append(f"{metric_label} command failed: {exc}")
            return

        if not output:
            evidence[key] = "false"
            failures.append(empty_message)
            return
        if integer:
            try:
                value = Decimal(output)
            except InvalidOperation:
                evidence[key] = "false"
                failures.append(f"{metric_label} returned non-numeric value")
                return
            if not value.is_finite():
                evidence[key] = "false"
                failures.append(f"{metric_label} returned non-numeric value")
                return
            if value < 0:
                evidence[key] = "false"
                failures.append(f"{metric_label} returned negative value")
                return
            if value != value.to_integral_value():
                evidence[key] = "false"
                failures.append(f"{metric_label} returned non-integer value")
                return
        else:
            try:
                value = Decimal(output)
            except InvalidOperation:
                evidence[key] = "false"
                failures.append(f"{metric_label} returned non-numeric value")
                return
            if not value.is_finite():
                evidence[key] = "false"
                failures.append(f"{metric_label} returned non-numeric value")
                return
            if value < 0:
                evidence[key] = "false"
                failures.append(f"{metric_label} returned negative value")
                return

        evidence[key] = output

    def _check_expected_text_command(
        self,
        *,
        evidence: dict[str, str],
        failures: list[str],
        key: str,
        command: list[str] | None,
        expected_text: str,
        missing_message: str,
        failed_message: str,
        not_found_message: str,
        invalid_expected_message: str,
    ) -> None:
        if command is None:
            evidence[key] = "unknown"
            failures.append(missing_message)
            return
        expected_text = expected_text.strip()
        if not expected_text:
            evidence[key] = "false"
            failures.append(invalid_expected_message)
            return

        try:
            output = self._run(command)
        except Exception as exc:  # noqa: BLE001
            evidence[key] = "false"
            failures.append(f"{failed_message}: {exc}")
            return

        found = expected_text in output
        evidence[key] = str(found).lower()
        if not found:
            failures.append(not_found_message)


def _join_url(base_url: str, path: str) -> str:
    """Join a base URL and path without introducing duplicate slashes."""
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _is_ready_running_pod(item: dict[str, object]) -> bool:
    status = item.get("status", {})
    if not isinstance(status, dict) or status.get("phase") != "Running":
        return False
    conditions = status.get("conditions", [])
    if not isinstance(conditions, list):
        return False
    ready_conditions = [
        condition
        for condition in conditions
        if isinstance(condition, dict) and condition.get("type") == "Ready"
    ]
    if not ready_conditions:
        return False
    return any(condition.get("status") == "True" for condition in ready_conditions)

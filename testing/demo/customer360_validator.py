"""Customer 360 demo validation helpers."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field

CommandRunner = Callable[[list[str]], str]

EXPECTED_EVIDENCE_KEYS = (
    "platform.ready",
    "dagster.customer_360_run",
    "storage.customer_360_outputs",
    "lineage.marquez_customer_360",
    "tracing.jaeger_customer_360",
    "business.customer_count",
    "business.total_lifetime_value",
)


def default_command_runner(command: list[str]) -> str:
    """Run a command without a shell and return stdout."""
    return subprocess.check_output(command, text=True)


@dataclass(frozen=True)
class Customer360Config:
    """Configuration for Customer 360 demo validation checks."""

    namespace: str = "floe-dev"
    dagster_url: str = "http://localhost:3100"
    marquez_url: str = "http://localhost:5100"
    jaeger_url: str = "http://localhost:16686"
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
        )
        self._check_business_metric(
            evidence=evidence,
            failures=failures,
            key="business.total_lifetime_value",
            command=self._config.lifetime_value_command,
            missing_message="Customer 360 lifetime value check is not configured",
            empty_message="Customer 360 lifetime value check returned no value",
        )

        return ValidationResult(
            status="FAIL" if failures else "PASS",
            evidence=evidence,
            failures=failures,
        )

    def _check_platform(self, evidence: dict[str, str], failures: list[str]) -> None:
        command = ["kubectl", "get", "pods", "-n", self._config.namespace, "-o", "json"]
        try:
            pods = json.loads(self._run(command))
        except Exception as exc:  # noqa: BLE001 - validation should report all failures.
            evidence["platform.ready"] = "false"
            failures.append(f"Unable to inspect Kubernetes pods: {exc}")
            return

        items = pods.get("items", [])
        running_pods = [
            item
            for item in items
            if isinstance(item, dict) and item.get("status", {}).get("phase") == "Running"
        ]
        evidence["platform.ready"] = str(bool(running_pods)).lower()
        if not running_pods:
            failures.append(f"No running pods found in namespace {self._config.namespace}")

    def _check_dagster(self, evidence: dict[str, str], failures: list[str]) -> None:
        url = _join_url(self._config.dagster_url, "server_info")
        try:
            self._run(["curl", "-fsS", url])
        except Exception as exc:  # noqa: BLE001
            evidence["dagster.customer_360_run"] = "false"
            failures.append(f"Dagster Customer 360 endpoint is not reachable: {exc}")
            return

        evidence["dagster.customer_360_run"] = "true"

    def _check_marquez(self, evidence: dict[str, str], failures: list[str]) -> None:
        url = _join_url(self._config.marquez_url, "api/v1/namespaces")
        try:
            payload = json.loads(self._run(["curl", "-fsS", url]))
        except Exception as exc:  # noqa: BLE001
            evidence["lineage.marquez_customer_360"] = "false"
            failures.append(f"Unable to inspect Marquez namespaces: {exc}")
            return

        namespace_names = _extract_names(payload.get("namespaces", []))
        lineage_found = bool({"customer_360", "customer-360"} & namespace_names)
        evidence["lineage.marquez_customer_360"] = str(lineage_found).lower()
        if not lineage_found:
            failures.append("Customer 360 namespace not found in Marquez")

    def _check_jaeger(self, evidence: dict[str, str], failures: list[str]) -> None:
        url = _join_url(self._config.jaeger_url, "api/services")
        try:
            payload = json.loads(self._run(["curl", "-fsS", url]))
        except Exception as exc:  # noqa: BLE001
            evidence["tracing.jaeger_customer_360"] = "false"
            failures.append(f"Unable to inspect Jaeger services: {exc}")
            return

        services = {str(service) for service in payload.get("data", [])}
        tracing_found = bool({"dagster", "floe"} & services)
        evidence["tracing.jaeger_customer_360"] = str(tracing_found).lower()
        if not tracing_found:
            failures.append("Customer 360 trace service not found in Jaeger")

    def _check_storage(self, evidence: dict[str, str], failures: list[str]) -> None:
        command = self._config.storage_check_command
        if command is None:
            evidence["storage.customer_360_outputs"] = "unknown"
            failures.append("Customer 360 storage outputs check is not configured")
            return

        try:
            output = self._run(command)
        except Exception as exc:  # noqa: BLE001
            evidence["storage.customer_360_outputs"] = "false"
            failures.append(f"Customer 360 storage outputs check failed: {exc}")
            return

        found = self._config.storage_expected_text in output
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
    ) -> None:
        if command is None:
            evidence[key] = "unknown"
            failures.append(missing_message)
            return

        try:
            output = self._run(command).strip()
        except Exception as exc:  # noqa: BLE001
            evidence[key] = "false"
            failures.append(f"{empty_message}: {exc}")
            return

        if not output:
            evidence[key] = "false"
            failures.append(empty_message)
            return

        evidence[key] = output


def _join_url(base_url: str, path: str) -> str:
    """Join a base URL and path without introducing duplicate slashes."""
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _extract_names(values: object) -> set[str]:
    """Extract name fields from API list payloads."""
    if not isinstance(values, list):
        return set()

    names: set[str] = set()
    for value in values:
        if isinstance(value, dict) and isinstance(value.get("name"), str):
            names.add(value["name"])
        elif isinstance(value, str):
            names.add(value)
    return names

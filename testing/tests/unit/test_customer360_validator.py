"""Tests for Customer 360 golden demo validation."""

from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
import yaml

from testing.demo.customer360_validator import (
    Customer360Config,
    Customer360Validator,
    ValidationResult,
    default_command_runner,
    load_customer360_config,
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
                {
                    "items": [
                        _ready_pod("dagster"),
                        _ready_pod("polaris"),
                        _ready_pod("minio"),
                        _ready_pod("jaeger"),
                        _ready_pod("marquez"),
                    ]
                }
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


def _ready_pod(name: str) -> dict[str, object]:
    return {
        "metadata": {"name": name},
        "status": {
            "phase": "Running",
            "conditions": [{"type": "Ready", "status": "True"}],
        },
    }


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
def test_customer360_validator_fails_when_expected_text_is_empty() -> None:
    """Empty expected text is invalid and cannot make evidence checks pass."""
    runner = _healthy_runner()
    runner.responses[("marquez", "lineage", "list")] = "anything\n"
    config = Customer360Config(
        lineage_check_command=["marquez", "lineage", "list"],
        lineage_expected_text=" ",
    )

    result = Customer360Validator(config=config, command_runner=runner).validate()

    assert result.status == "FAIL"
    assert result.evidence["lineage.marquez_customer_360"] == "false"
    assert "Customer 360 lineage expected text must be non-empty" in result.failures


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
                {
                    "items": [
                        _ready_pod("dagster"),
                        _ready_pod("polaris"),
                        _ready_pod("minio"),
                        _ready_pod("jaeger"),
                        _ready_pod("marquez"),
                    ]
                }
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
def test_customer360_validator_requires_expected_platform_services() -> None:
    """Platform readiness requires configured critical services, not any running pod."""
    runner = FakeRunner(
        {
            ("kubectl", "get", "pods", "-n", "floe-dev", "-o", "json"): json.dumps(
                {"items": [_ready_pod("unrelated-worker")]}
            ),
            ("curl", "-fsS", "http://localhost:3100/server_info"): "{}",
            ("curl", "-fsS", "http://localhost:5100/api/v1/namespaces"): json.dumps(
                {"namespaces": []}
            ),
            ("curl", "-fsS", "http://localhost:16686/api/services"): json.dumps({"data": []}),
        }
    )

    result = Customer360Validator(command_runner=runner).validate()

    assert result.evidence["platform.ready"] == "false"
    assert (
        "Expected platform services are not ready in namespace floe-dev: "
        "dagster, polaris, minio, jaeger, marquez"
    ) in result.failures


@pytest.mark.requirement("alpha-demo")
def test_customer360_validator_rejects_empty_expected_platform_services() -> None:
    """Empty expected service configuration cannot bypass platform readiness."""
    runner = _healthy_runner()
    config = Customer360Config(platform_expected_services=())

    result = Customer360Validator(config=config, command_runner=runner).validate()

    assert result.evidence["platform.ready"] == "false"
    assert (
        "Platform expected services must contain at least one service fragment" in result.failures
    )


@pytest.mark.requirement("alpha-demo")
def test_customer360_validator_requires_ready_condition_for_running_pods() -> None:
    """Running pods without a Ready condition are not considered platform-ready."""
    runner = _healthy_runner()
    runner.responses[("kubectl", "get", "pods", "-n", "floe-dev", "-o", "json")] = json.dumps(
        {
            "items": [
                {
                    "metadata": {"name": "dagster"},
                    "status": {"phase": "Running", "conditions": []},
                },
                _ready_pod("polaris"),
                _ready_pod("minio"),
                _ready_pod("jaeger"),
                _ready_pod("marquez"),
            ]
        }
    )

    result = Customer360Validator(command_runner=runner).validate()

    assert result.evidence["platform.ready"] == "false"
    assert (
        "Expected platform services are not ready in namespace floe-dev: dagster" in result.failures
    )


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
@pytest.mark.parametrize(
    ("customer_count", "lifetime_value", "expected_failure"),
    [
        ("not-a-number", "123.45", "Customer 360 customer count check returned non-numeric value"),
        ("-1", "123.45", "Customer 360 customer count check returned negative value"),
        ("42.5", "123.45", "Customer 360 customer count check returned non-integer value"),
        ("42", "not-a-number", "Customer 360 lifetime value check returned non-numeric value"),
        ("42", "-0.1", "Customer 360 lifetime value check returned negative value"),
    ],
)
def test_customer360_validator_rejects_invalid_business_metrics(
    customer_count: str,
    lifetime_value: str,
    expected_failure: str,
) -> None:
    """Business metrics must be non-negative numeric values."""
    runner = _healthy_runner()
    runner.responses.update(
        {
            ("count",): f"{customer_count}\n",
            ("lifetime-value",): f"{lifetime_value}\n",
        }
    )
    config = Customer360Config(
        customer_count_command=["count"],
        lifetime_value_command=["lifetime-value"],
    )

    result = Customer360Validator(config=config, command_runner=runner).validate()

    assert result.status == "FAIL"
    assert expected_failure in result.failures


@pytest.mark.requirement("alpha-demo")
def test_customer360_validator_reports_business_metric_command_failure() -> None:
    """Business metric exceptions identify the command failure."""

    def runner(command: list[str]) -> str:
        if command[0] == "kubectl":
            return json.dumps(
                {
                    "items": [
                        _ready_pod("dagster"),
                        _ready_pod("polaris"),
                        _ready_pod("minio"),
                        _ready_pod("jaeger"),
                        _ready_pod("marquez"),
                    ]
                }
            )
        if command[0] == "curl":
            return "{}"
        raise RuntimeError("boom")

    config = Customer360Config(customer_count_command=["count"])

    result = Customer360Validator(config=config, command_runner=runner).validate()

    assert "Customer 360 customer count check command failed: boom" in result.failures


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
def test_customer360_validation_manifest_configures_default_evidence_commands() -> None:
    """Default Customer 360 evidence checks are manifest-driven, not caller-supplied."""
    config = load_customer360_config(Path("demo/customer-360/validation.yaml"))

    assert config.namespace == "floe-dev"
    assert config.platform_expected_services == (
        "dagster",
        "polaris",
        "minio",
        "jaeger",
        "marquez",
    )
    assert config.dagster_run_check_command is not None
    assert "tags" in config.dagster_run_check_command[-1], (
        "Dagster run evidence must query tags so the customer-360 code location "
        "is visible even when the Dagster job name is __ASSET_JOB."
    )
    assert config.lineage_check_command == [
        "curl",
        "-fsS",
        "http://localhost:5100/api/v1/namespaces/customer-360/jobs",
    ]
    assert config.lineage_expected_text == "mart_customer_360"
    assert config.storage_check_command is not None
    assert "floe_orchestrator_dagster.validation.iceberg_outputs" in config.storage_check_command
    assert config.customer_count_command == [
        "kubectl",
        "exec",
        "-n",
        "floe-dev",
        "deployment/floe-platform-dagster-webserver",
        "--",
        "python",
        "/app/demo/customer_360/scripts/customer360_metric.py",
        "--source",
        "iceberg",
        "--artifacts-path",
        "/app/demo/customer_360/compiled_artifacts.json",
        "customer-count",
    ]
    assert config.lifetime_value_command == [
        "kubectl",
        "exec",
        "-n",
        "floe-dev",
        "deployment/floe-platform-dagster-webserver",
        "--",
        "python",
        "/app/demo/customer_360/scripts/customer360_metric.py",
        "--source",
        "iceberg",
        "--artifacts-path",
        "/app/demo/customer_360/compiled_artifacts.json",
        "total-lifetime-value",
    ]


@pytest.mark.requirement("alpha-demo")
def test_customer360_validation_manifest_rejects_shell_command_strings(tmp_path: Path) -> None:
    """Validation manifests use explicit argv lists rather than shell command strings."""
    manifest = tmp_path / "validation.yaml"
    manifest.write_text(
        """
validation:
  evidence:
    lineage_check_command: "curl http://example.com | jq"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="lineage_check_command"):
        load_customer360_config(manifest)


@pytest.mark.requirement("alpha-demo")
def test_cli_prints_deterministic_output_and_returns_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI output is stable and returns nonzero when validation has failures."""
    module = importlib.import_module("testing.ci.validate_customer_360_demo")

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
    module = importlib.import_module("testing.ci.validate_customer_360_demo")

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


@pytest.mark.requirement("alpha-demo")
def test_cli_loads_customer360_validation_manifest_by_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The release validation CLI gets runnable evidence checks from a manifest by default."""
    module = importlib.import_module("testing.ci.validate_customer_360_demo")
    manifest = tmp_path / "validation.yaml"
    manifest.write_text(
        """
validation:
  namespace: manifest-ns
  evidence:
    dagster_run_check_command: [dagster, runs, list]
    dagster_expected_text: customer-360
    lineage_check_command: [marquez, jobs, list]
    lineage_expected_text: mart_customer_360
    tracing_check_command: [jaeger, traces, list]
    tracing_expected_text: customer-360
    storage_check_command: [storage, list]
    storage_expected_text: mart_customer_360
    customer_count_command: [count]
    lifetime_value_command: [lifetime]
""",
        encoding="utf-8",
    )
    captured: dict[str, Customer360Config] = {}

    class FakeValidator:
        def __init__(self, *, config: Customer360Config) -> None:
            captured["config"] = config

        def validate(self) -> ValidationResult:
            return ValidationResult(status="PASS")

    monkeypatch.setenv("FLOE_DEMO_VALIDATION_MANIFEST", str(manifest))
    monkeypatch.setattr("sys.argv", ["validate_customer_360_demo"])
    monkeypatch.setattr(module, "Customer360Validator", FakeValidator)

    exit_code = module.main()

    assert exit_code == 0
    assert captured["config"].namespace == "manifest-ns"
    assert captured["config"].dagster_run_check_command == ["dagster", "runs", "list"]
    assert captured["config"].storage_check_command == ["storage", "list"]


@pytest.mark.requirement("alpha-demo")
def test_cli_reports_malformed_command_as_parser_error(capsys: pytest.CaptureFixture[str]) -> None:
    """Malformed command strings produce argparse-style parser failures."""
    module = importlib.import_module("testing.ci.validate_customer_360_demo")

    with pytest.raises(SystemExit) as exc_info:
        module._parse_command_arg(module.build_parser(), "--lineage-check-command", "'unterminated")

    assert exc_info.value.code == 2
    assert "invalid --lineage-check-command" in capsys.readouterr().err


@pytest.mark.requirement("alpha-demo")
def test_cli_reports_malformed_timeout_env_as_parser_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Malformed timeout environment values produce argparse-style parser failures."""
    module = importlib.import_module("testing.ci.validate_customer_360_demo")
    monkeypatch.setenv("FLOE_DEMO_COMMAND_TIMEOUT_SECONDS", "abc")

    with pytest.raises(SystemExit) as exc_info:
        module.build_parser()

    assert exc_info.value.code == 2
    assert "invalid FLOE_DEMO_COMMAND_TIMEOUT_SECONDS" in capsys.readouterr().err


@pytest.mark.requirement("alpha-demo")
def test_customer360_validator_module_help_invocation_works() -> None:
    """The importable module entry point can render help without live services."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "testing.ci.validate_customer_360_demo", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Validate the Customer 360 golden demo" in result.stdout
    assert "--platform-expected-services" in result.stdout


@pytest.mark.requirement("alpha-demo")
def test_customer360_validator_legacy_script_help_invocation_works() -> None:
    """The legacy hyphenated wrapper can render help without live services."""
    result = subprocess.run(
        ["uv", "run", "python", "testing/ci/validate-customer-360-demo.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Validate the Customer 360 golden demo" in result.stdout
    assert "--platform-expected-services" in result.stdout


@pytest.mark.requirement("alpha-demo")
def test_default_command_runner_reports_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default command execution uses a bounded timeout and reports it clearly."""

    def fake_check_output(command: list[str], *, text: bool, timeout: float) -> str:
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)

    with pytest.raises(TimeoutError, match="Command timed out after 0.01s"):
        default_command_runner(["slow"], timeout_seconds=0.01)


@pytest.mark.requirement("alpha-demo")
def test_make_dry_run_does_not_expose_dangerous_command_override_values() -> None:
    """Make dry-run must not interpolate user command override values into shell recipes."""
    result = subprocess.run(
        [
            "make",
            "-n",
            "demo-customer-360-validate",
            "FLOE_DEMO_DAGSTER_RUN_CHECK_COMMAND=echo $$(touch /tmp/pwn)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "touch /tmp/pwn" not in result.stdout


@pytest.mark.requirement("alpha-demo")
def test_make_dry_run_uses_importable_customer360_validator_module() -> None:
    """Make target executes the importable module rather than a fragile file path."""
    result = subprocess.run(
        ["make", "-n", "demo-customer-360-validate"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "uv run python -m testing.ci.validate_customer_360_demo" in result.stdout


@pytest.mark.requirement("alpha-demo")
def test_makefile_does_not_override_manifest_expected_text_defaults() -> None:
    """Make target must let validation.yaml provide default evidence expectations."""
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "FLOE_DEMO_DAGSTER_EXPECTED_TEXT ?=" not in makefile
    assert "FLOE_DEMO_LINEAGE_EXPECTED_TEXT ?=" not in makefile
    assert "FLOE_DEMO_TRACING_EXPECTED_TEXT ?=" not in makefile
    assert "FLOE_DEMO_STORAGE_EXPECTED_TEXT ?=" not in makefile


@pytest.mark.requirement("alpha-demo")
def test_customer360_metric_script_queries_duckdb_metrics(tmp_path: Path) -> None:
    """Customer 360 business metrics live in a copied script, not inline manifest code."""
    database = tmp_path / "customer_360.duckdb"
    with duckdb.connect(str(database)) as conn:
        conn.execute("create table mart_customer_360 (total_spend decimal(10, 2))")
        conn.execute("insert into mart_customer_360 values (10.50), (5.25)")

    script = Path("demo/customer-360/scripts/customer360_metric.py")

    count_result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--database",
            str(database),
            "customer-count",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    lifetime_value_result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--database",
            str(database),
            "total-lifetime-value",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert count_result.stdout.strip() == "2"
    assert lifetime_value_result.stdout.strip() == "15.75"


@pytest.mark.requirement("alpha-demo")
def test_customer360_metric_script_queries_iceberg_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Customer 360 validation can query business metrics from persisted Iceberg outputs."""
    script = Path("demo/customer-360/scripts/customer360_metric.py")
    spec = importlib.util.spec_from_file_location("customer360_metric", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    artifacts_path = tmp_path / "compiled_artifacts.json"
    artifacts_path.write_text("{}", encoding="utf-8")

    class FakeScan:
        def __init__(self, selected_fields: Sequence[str]) -> None:
            self.selected_fields = tuple(selected_fields)

        def to_arrow(self) -> object:
            import pyarrow as pa

            assert self.selected_fields in {("customer_id",), ("total_spend",)}
            return pa.table({"customer_id": [1, 2], "total_spend": [10.50, 5.25]})

    class FakeTable:
        def scan(self, *, selected_fields: Sequence[str]) -> FakeScan:
            return FakeScan(selected_fields)

    class FakeCatalog:
        def __init__(self) -> None:
            self.loaded: list[str] = []

        def load_table(self, identifier: str) -> FakeTable:
            self.loaded.append(identifier)
            return FakeTable()

    fake_catalog = FakeCatalog()
    monkeypatch.setattr(
        module,
        "CompiledArtifacts",
        SimpleNamespace(model_validate_json=lambda _content: object()),
    )
    monkeypatch.setattr(module, "expected_iceberg_tables", lambda _artifacts, tables: tables)
    monkeypatch.setattr(module, "connect_catalog_from_artifacts", lambda _artifacts: fake_catalog)

    count = module.query_metric(
        source="iceberg",
        artifacts_path=artifacts_path,
        database="unused.duckdb",
        table="mart_customer_360",
        metric="customer-count",
        lifetime_value_column="total_spend",
    )
    lifetime_value = module.query_metric(
        source="iceberg",
        artifacts_path=artifacts_path,
        database="unused.duckdb",
        table="mart_customer_360",
        metric="total-lifetime-value",
        lifetime_value_column="total_spend",
    )

    assert count == 2
    assert lifetime_value == 15.75
    assert fake_catalog.loaded == ["mart_customer_360", "mart_customer_360"]


@pytest.mark.requirement("alpha-demo")
def test_customer360_metric_cli_keeps_stdout_numeric(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Metric CLI should keep diagnostic logs off stdout so validators can parse it."""
    script = Path("demo/customer-360/scripts/customer360_metric.py")
    spec = importlib.util.spec_from_file_location("customer360_metric_clean_stdout", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def noisy_query_metric(**_kwargs: object) -> int:
        print("diagnostic noise")
        return 500

    monkeypatch.setattr(module, "query_metric", noisy_query_metric)

    assert module.main(["customer-count"]) == 0

    captured = capsys.readouterr()
    assert captured.out == "500\n"
    assert "diagnostic noise" in captured.err


@pytest.mark.requirement("alpha-demo")
def test_customer360_validation_manifest_does_not_embed_python_code() -> None:
    """Validation manifest should configure commands, not carry inline Python snippets."""
    manifest = yaml.safe_load(Path("demo/customer-360/validation.yaml").read_text(encoding="utf-8"))
    evidence = manifest["validation"]["evidence"]
    commands = [
        evidence["customer_count_command"],
        evidence["lifetime_value_command"],
    ]

    assert all("python" in command for command in commands)
    assert all("-c" not in command for command in commands)
    assert "duckdb.connect" not in str(manifest)

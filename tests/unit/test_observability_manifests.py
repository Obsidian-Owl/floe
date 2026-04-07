"""Structural tests: Job manifests include observability flags and env vars.

Validates that the e2e and e2e-destructive Job templates rendered from the
``charts/floe-platform`` Helm chart pass the correct ``--html``,
``--json-report-file``, and ``--log-cli-level`` flags, and set the required
``OTEL_EXPORTER_OTLP_ENDPOINT`` and ``OTEL_SERVICE_NAME`` environment variables.

The chart is the single source of truth for test infrastructure, so these
tests render the templates directly via ``helm template -s`` rather than
reading raw YAML files. This makes chart-level regressions detectable here
in addition to the contract tier.

Requirements Covered:
    - AC-1: HTML and JSON report output flags in Job args
    - AC-2: OTEL endpoint and service name env vars
    - AC-4: Live logging via --log-cli-level=INFO
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CHART_DIR = _REPO_ROOT / "charts" / "floe-platform"
_STANDARD_TEMPLATE = "templates/tests/job-e2e.yaml"
_DESTRUCTIVE_TEMPLATE = "templates/tests/job-e2e-destructive.yaml"

# Expected report file paths (AC-1)
_STANDARD_HTML_REPORT = "--html=/artifacts/e2e-report.html"
_STANDARD_JSON_REPORT = "--json-report-file=/artifacts/e2e-report.json"
_DESTRUCTIVE_HTML_REPORT = "--html=/artifacts/e2e-destructive-report.html"
_DESTRUCTIVE_JSON_REPORT = "--json-report-file=/artifacts/e2e-destructive-report.json"

# Expected OTel env vars (AC-2)
_OTEL_ENDPOINT_NAME = "OTEL_EXPORTER_OTLP_ENDPOINT"
_OTEL_ENDPOINT_VALUE = "http://floe-platform-otel:4317"
_OTEL_SERVICE_NAME = "OTEL_SERVICE_NAME"
_OTEL_SERVICE_VALUE = "floe-test-runner"

# Expected log flag (AC-4)
_LOG_CLI_LEVEL_FLAG = "--log-cli-level=INFO"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_job_manifest(template: str) -> dict[str, Any]:
    """Render a Job template from the chart and return the parsed Job doc.

    Uses ``helm template -s`` with ``tests.enabled=true`` so the chart-gated
    test resources are emitted. Fails fast if helm is missing or the template
    renders no Job. The release name is fixed to ``floe-platform`` so the
    rendered service hostnames (``floe-platform-otel`` etc.) match what the
    callers of this test infrastructure deploy in CI.

    Args:
        template: Chart-relative template path, e.g.
            ``templates/tests/job-e2e.yaml``.

    Returns:
        Parsed Job manifest as a dictionary.
    """
    if shutil.which("helm") is None:
        pytest.fail(
            "helm CLI not available on PATH — required to render test Job "
            "templates for observability manifest verification."
        )

    result = subprocess.run(
        [
            "helm",
            "template",
            "floe-platform",
            str(_CHART_DIR),
            "--set",
            "tests.enabled=true",
            "-s",
            template,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            f"helm template rendering failed for {template}:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    docs = list(yaml.safe_load_all(result.stdout))
    jobs: list[dict[str, Any]] = []
    for doc_any in docs:
        if not isinstance(doc_any, dict):
            continue
        doc: dict[str, Any] = cast("dict[str, Any]", doc_any)
        if doc.get("kind") == "Job":
            jobs.append(doc)
    assert len(jobs) == 1, f"Expected exactly one Job in rendered {template}, found {len(jobs)}"
    return jobs[0]


def _get_container_args(manifest: dict[str, Any]) -> list[str]:
    """Extract the args list from the first container in a Job manifest.

    Args:
        manifest: Parsed K8s Job manifest.

    Returns:
        List of string arguments passed to the container.
    """
    containers: list[dict[str, Any]] = manifest["spec"]["template"]["spec"]["containers"]
    args: list[str] = containers[0].get("args", [])
    return args


def _get_env_vars(manifest: dict[str, Any]) -> dict[str, str | None]:
    """Extract env vars from the first container as a name->value mapping.

    For env vars using ``valueFrom`` (secrets), the value is stored as None.

    Args:
        manifest: Parsed K8s Job manifest.

    Returns:
        Dict mapping env var names to their literal values (or None for
        secret-backed vars).
    """
    containers: list[dict[str, Any]] = manifest["spec"]["template"]["spec"]["containers"]
    env_list: list[dict[str, Any]] = containers[0].get("env", [])
    result: dict[str, str | None] = {}
    for entry in env_list:
        name: str = entry["name"]
        value: str | None = entry.get("value")
        result[name] = value
    return result


# ===================================================================
# AC-1: HTML and JSON report flags in Job args
# ===================================================================


class TestStandardJobReportFlags:
    """Verify standard E2E Job passes correct report output flags."""

    @pytest.mark.requirement("AC-1")
    def test_standard_job_has_html_report_flag(self) -> None:
        """Standard Job args MUST include --html=/artifacts/e2e-report.html.

        Without this flag, pytest-html will not generate the HTML report
        artifact for the standard E2E test run.
        """
        manifest = _render_job_manifest(_STANDARD_TEMPLATE)
        args = _get_container_args(manifest)

        assert _STANDARD_HTML_REPORT in args, (
            f"Standard Job args must include '{_STANDARD_HTML_REPORT}'. Current args: {args}"
        )

    @pytest.mark.requirement("AC-1")
    def test_standard_job_has_json_report_flag(self) -> None:
        """Standard Job args MUST include --json-report-file=/artifacts/e2e-report.json.

        Without this flag, pytest-json-report will not generate the JSON
        report artifact for the standard E2E test run.
        """
        manifest = _render_job_manifest(_STANDARD_TEMPLATE)
        args = _get_container_args(manifest)

        assert _STANDARD_JSON_REPORT in args, (
            f"Standard Job args must include '{_STANDARD_JSON_REPORT}'. Current args: {args}"
        )
        # pytest-json-report requires the bare --json-report enable flag
        # alongside --json-report-file; without it the plugin stays inactive
        # and no JSON artifact is produced.
        assert "--json-report" in args, (
            "Standard Job args must include '--json-report' to enable the plugin. "
            f"Current args: {args}"
        )

    @pytest.mark.requirement("AC-1")
    def test_standard_job_html_report_path_is_exact(self) -> None:
        """Standard Job HTML report path must be exactly e2e-report.html.

        A sloppy implementation might use a generic name like 'report.html'
        or accidentally use the destructive prefix. This test catches that.
        """
        manifest = _render_job_manifest(_STANDARD_TEMPLATE)
        args = _get_container_args(manifest)

        html_args = [a for a in args if a.startswith("--html=")]
        assert len(html_args) == 1, (
            f"Expected exactly one --html= flag, found {len(html_args)}: {html_args}"
        )
        assert html_args[0] == _STANDARD_HTML_REPORT, (
            f"HTML report path must be exactly '{_STANDARD_HTML_REPORT}', got '{html_args[0]}'"
        )

    @pytest.mark.requirement("AC-1")
    def test_standard_job_json_report_path_is_exact(self) -> None:
        """Standard Job JSON report path must be exactly e2e-report.json.

        Prevents using a wrong filename like 'results.json' or the
        destructive variant.
        """
        manifest = _render_job_manifest(_STANDARD_TEMPLATE)
        args = _get_container_args(manifest)

        json_args = [a for a in args if a.startswith("--json-report-file=")]
        assert len(json_args) == 1, (
            f"Expected exactly one --json-report-file= flag, found {len(json_args)}: {json_args}"
        )
        assert json_args[0] == _STANDARD_JSON_REPORT, (
            f"JSON report path must be exactly '{_STANDARD_JSON_REPORT}', got '{json_args[0]}'"
        )


class TestDestructiveJobReportFlags:
    """Verify destructive E2E Job passes correct report output flags."""

    @pytest.mark.requirement("AC-1")
    def test_destructive_job_has_html_report_flag(self) -> None:
        """Destructive Job args MUST include --html=/artifacts/e2e-destructive-report.html.

        The destructive job must use a distinct filename to avoid
        overwriting the standard report.
        """
        manifest = _render_job_manifest(_DESTRUCTIVE_TEMPLATE)
        args = _get_container_args(manifest)

        assert _DESTRUCTIVE_HTML_REPORT in args, (
            f"Destructive Job args must include '{_DESTRUCTIVE_HTML_REPORT}'. Current args: {args}"
        )

    @pytest.mark.requirement("AC-1")
    def test_destructive_job_has_json_report_flag(self) -> None:
        """Destructive Job args MUST include JSON report flag with distinct path.

        The destructive job must use a distinct filename to avoid
        overwriting the standard JSON report.
        """
        manifest = _render_job_manifest(_DESTRUCTIVE_TEMPLATE)
        args = _get_container_args(manifest)

        assert _DESTRUCTIVE_JSON_REPORT in args, (
            f"Destructive Job args must include '{_DESTRUCTIVE_JSON_REPORT}'. Current args: {args}"
        )
        # pytest-json-report requires the bare --json-report enable flag
        # alongside --json-report-file; without it the plugin stays inactive
        # and no JSON artifact is produced.
        assert "--json-report" in args, (
            "Destructive Job args must include '--json-report' to enable the plugin. "
            f"Current args: {args}"
        )

    @pytest.mark.requirement("AC-1")
    def test_destructive_job_html_report_path_is_exact(self) -> None:
        """Destructive Job HTML report path must be exactly e2e-destructive-report.html.

        Catches swapped filenames (standard path in destructive job) or
        wrong prefixes.
        """
        manifest = _render_job_manifest(_DESTRUCTIVE_TEMPLATE)
        args = _get_container_args(manifest)

        html_args = [a for a in args if a.startswith("--html=")]
        assert len(html_args) == 1, (
            f"Expected exactly one --html= flag, found {len(html_args)}: {html_args}"
        )
        assert html_args[0] == _DESTRUCTIVE_HTML_REPORT, (
            f"HTML report path must be exactly '{_DESTRUCTIVE_HTML_REPORT}', got '{html_args[0]}'"
        )

    @pytest.mark.requirement("AC-1")
    def test_destructive_job_json_report_path_is_exact(self) -> None:
        """Destructive Job JSON report path must be exactly e2e-destructive-report.json.

        Catches wrong filenames or missing 'destructive' prefix.
        """
        manifest = _render_job_manifest(_DESTRUCTIVE_TEMPLATE)
        args = _get_container_args(manifest)

        json_args = [a for a in args if a.startswith("--json-report-file=")]
        assert len(json_args) == 1, (
            f"Expected exactly one --json-report-file= flag, found {len(json_args)}: {json_args}"
        )
        assert json_args[0] == _DESTRUCTIVE_JSON_REPORT, (
            f"JSON report path must be exactly '{_DESTRUCTIVE_JSON_REPORT}', got '{json_args[0]}'"
        )


class TestReportFilenameDistinctness:
    """Verify standard and destructive jobs use DIFFERENT report filenames."""

    @pytest.mark.requirement("AC-1")
    def test_html_report_filenames_differ(self) -> None:
        """Standard and destructive HTML reports MUST use different filenames.

        If both jobs write to the same path, the second job overwrites
        the first job's report.
        """
        std_manifest = _render_job_manifest(_STANDARD_TEMPLATE)
        dest_manifest = _render_job_manifest(_DESTRUCTIVE_TEMPLATE)

        std_args = _get_container_args(std_manifest)
        dest_args = _get_container_args(dest_manifest)

        std_html = [a for a in std_args if a.startswith("--html=")]
        dest_html = [a for a in dest_args if a.startswith("--html=")]

        assert len(std_html) == 1, "Standard job must have exactly one --html= flag"
        assert len(dest_html) == 1, "Destructive job must have exactly one --html= flag"
        assert std_html[0] != dest_html[0], (
            f"Standard and destructive jobs must use different HTML report paths. "
            f"Both use: {std_html[0]}"
        )

    @pytest.mark.requirement("AC-1")
    def test_json_report_filenames_differ(self) -> None:
        """Standard and destructive JSON reports MUST use different filenames.

        Same rationale as HTML: overwrite prevention.
        """
        std_manifest = _render_job_manifest(_STANDARD_TEMPLATE)
        dest_manifest = _render_job_manifest(_DESTRUCTIVE_TEMPLATE)

        std_args = _get_container_args(std_manifest)
        dest_args = _get_container_args(dest_manifest)

        std_json = [a for a in std_args if a.startswith("--json-report-file=")]
        dest_json = [a for a in dest_args if a.startswith("--json-report-file=")]

        assert len(std_json) == 1, "Standard job must have exactly one --json-report-file= flag"
        assert len(dest_json) == 1, "Destructive job must have exactly one --json-report-file= flag"
        assert std_json[0] != dest_json[0], (
            f"Standard and destructive jobs must use different JSON report paths. "
            f"Both use: {std_json[0]}"
        )


# ===================================================================
# AC-2: OTEL endpoint and service name env vars
# ===================================================================


class TestStandardJobOtelEnvVars:
    """Verify standard E2E Job sets required OTel env vars."""

    @pytest.mark.requirement("AC-2")
    def test_standard_job_has_otel_endpoint(self) -> None:
        """Standard Job MUST set OTEL_EXPORTER_OTLP_ENDPOINT env var.

        This is the standard OpenTelemetry env var that SDK auto-configures
        exporters with. Without it, traces/metrics go nowhere.
        """
        manifest = _render_job_manifest(_STANDARD_TEMPLATE)
        env_vars = _get_env_vars(manifest)

        assert _OTEL_ENDPOINT_NAME in env_vars, (
            f"Standard Job must set '{_OTEL_ENDPOINT_NAME}' env var. "
            f"Current env vars: {sorted(env_vars.keys())}"
        )

    @pytest.mark.requirement("AC-2")
    def test_standard_job_otel_endpoint_value(self) -> None:
        """Standard Job OTEL_EXPORTER_OTLP_ENDPOINT must point to the OTel collector.

        The value must be exactly 'http://floe-platform-otel:4317' -- the
        gRPC endpoint of the in-cluster OTel collector.
        """
        manifest = _render_job_manifest(_STANDARD_TEMPLATE)
        env_vars = _get_env_vars(manifest)

        actual = env_vars.get(_OTEL_ENDPOINT_NAME)
        assert actual == _OTEL_ENDPOINT_VALUE, (
            f"'{_OTEL_ENDPOINT_NAME}' must be '{_OTEL_ENDPOINT_VALUE}', got '{actual}'"
        )

    @pytest.mark.requirement("AC-2")
    def test_standard_job_has_otel_service_name(self) -> None:
        """Standard Job MUST set OTEL_SERVICE_NAME env var.

        This identifies the test runner in traces, making it easy to
        filter test-runner spans in Jaeger/Grafana.
        """
        manifest = _render_job_manifest(_STANDARD_TEMPLATE)
        env_vars = _get_env_vars(manifest)

        assert _OTEL_SERVICE_NAME in env_vars, (
            f"Standard Job must set '{_OTEL_SERVICE_NAME}' env var. "
            f"Current env vars: {sorted(env_vars.keys())}"
        )

    @pytest.mark.requirement("AC-2")
    def test_standard_job_otel_service_name_value(self) -> None:
        """Standard Job OTEL_SERVICE_NAME must be 'floe-test-runner'.

        The exact value matters for trace filtering and dashboards.
        """
        manifest = _render_job_manifest(_STANDARD_TEMPLATE)
        env_vars = _get_env_vars(manifest)

        actual = env_vars.get(_OTEL_SERVICE_NAME)
        assert actual == _OTEL_SERVICE_VALUE, (
            f"'{_OTEL_SERVICE_NAME}' must be '{_OTEL_SERVICE_VALUE}', got '{actual}'"
        )


class TestDestructiveJobOtelEnvVars:
    """Verify destructive E2E Job sets required OTel env vars."""

    @pytest.mark.requirement("AC-2")
    def test_destructive_job_has_otel_endpoint(self) -> None:
        """Destructive Job MUST set OTEL_EXPORTER_OTLP_ENDPOINT env var.

        Same requirement as the standard job -- both need OTel export.
        """
        manifest = _render_job_manifest(_DESTRUCTIVE_TEMPLATE)
        env_vars = _get_env_vars(manifest)

        assert _OTEL_ENDPOINT_NAME in env_vars, (
            f"Destructive Job must set '{_OTEL_ENDPOINT_NAME}' env var. "
            f"Current env vars: {sorted(env_vars.keys())}"
        )

    @pytest.mark.requirement("AC-2")
    def test_destructive_job_otel_endpoint_value(self) -> None:
        """Destructive Job OTEL_EXPORTER_OTLP_ENDPOINT must point to the OTel collector.

        Must be the same endpoint as the standard job.
        """
        manifest = _render_job_manifest(_DESTRUCTIVE_TEMPLATE)
        env_vars = _get_env_vars(manifest)

        actual = env_vars.get(_OTEL_ENDPOINT_NAME)
        assert actual == _OTEL_ENDPOINT_VALUE, (
            f"'{_OTEL_ENDPOINT_NAME}' must be '{_OTEL_ENDPOINT_VALUE}', got '{actual}'"
        )

    @pytest.mark.requirement("AC-2")
    def test_destructive_job_has_otel_service_name(self) -> None:
        """Destructive Job MUST set OTEL_SERVICE_NAME env var.

        Both jobs identify as the same service for unified trace querying.
        """
        manifest = _render_job_manifest(_DESTRUCTIVE_TEMPLATE)
        env_vars = _get_env_vars(manifest)

        assert _OTEL_SERVICE_NAME in env_vars, (
            f"Destructive Job must set '{_OTEL_SERVICE_NAME}' env var. "
            f"Current env vars: {sorted(env_vars.keys())}"
        )

    @pytest.mark.requirement("AC-2")
    def test_destructive_job_otel_service_name_value(self) -> None:
        """Destructive Job OTEL_SERVICE_NAME must be 'floe-test-runner'.

        Must match the standard job's service name.
        """
        manifest = _render_job_manifest(_DESTRUCTIVE_TEMPLATE)
        env_vars = _get_env_vars(manifest)

        actual = env_vars.get(_OTEL_SERVICE_NAME)
        assert actual == _OTEL_SERVICE_VALUE, (
            f"'{_OTEL_SERVICE_NAME}' must be '{_OTEL_SERVICE_VALUE}', got '{actual}'"
        )


class TestOtelEnvVarNotConfusedWithOtelHost:
    """Verify OTEL_EXPORTER_OTLP_ENDPOINT is distinct from OTEL_HOST.

    A sloppy implementation might think the existing OTEL_HOST env var
    satisfies AC-2. It does not: OTEL_HOST is a floe-internal variable,
    while OTEL_EXPORTER_OTLP_ENDPOINT is the standard OTel SDK variable.
    """

    @pytest.mark.requirement("AC-2")
    def test_standard_job_has_both_otel_host_and_endpoint(self) -> None:
        """Standard Job must have OTEL_EXPORTER_OTLP_ENDPOINT in addition to OTEL_HOST.

        OTEL_HOST alone does not satisfy AC-2. The standard OTel SDK
        env var is required.
        """
        manifest = _render_job_manifest(_STANDARD_TEMPLATE)
        env_vars = _get_env_vars(manifest)

        assert "OTEL_HOST" in env_vars, "OTEL_HOST should still be present (not removed)"
        assert _OTEL_ENDPOINT_NAME in env_vars, (
            f"'{_OTEL_ENDPOINT_NAME}' must be present IN ADDITION TO 'OTEL_HOST'. "
            f"OTEL_HOST is a floe-internal var; {_OTEL_ENDPOINT_NAME} is the "
            f"standard OTel SDK env var required by AC-2."
        )

    @pytest.mark.requirement("AC-2")
    def test_otel_endpoint_includes_protocol_and_port(self) -> None:
        """OTEL_EXPORTER_OTLP_ENDPOINT must include http:// prefix and :4317 port.

        A bare hostname like 'floe-platform-otel' won't work -- the OTel
        SDK needs a full URL with protocol and port.
        """
        manifest = _render_job_manifest(_STANDARD_TEMPLATE)
        env_vars = _get_env_vars(manifest)

        value = env_vars.get(_OTEL_ENDPOINT_NAME, "")
        assert value is not None and value.startswith("http://"), (
            f"'{_OTEL_ENDPOINT_NAME}' must start with 'http://', got '{value}'"
        )
        assert value is not None and value.endswith(":4317"), (
            f"'{_OTEL_ENDPOINT_NAME}' must end with ':4317' (gRPC port), got '{value}'"
        )


# ===================================================================
# AC-4: Live logging via --log-cli-level=INFO
# ===================================================================


class TestStandardJobLogCliLevel:
    """Verify standard E2E Job enables live logging."""

    @pytest.mark.requirement("AC-4")
    def test_standard_job_has_log_cli_level(self) -> None:
        """Standard Job args MUST include --log-cli-level=INFO.

        Without this flag, pytest suppresses live log output, making it
        impossible to observe test progress in real time via kubectl logs.
        """
        manifest = _render_job_manifest(_STANDARD_TEMPLATE)
        args = _get_container_args(manifest)

        assert _LOG_CLI_LEVEL_FLAG in args, (
            f"Standard Job args must include '{_LOG_CLI_LEVEL_FLAG}'. Current args: {args}"
        )

    @pytest.mark.requirement("AC-4")
    def test_standard_job_log_level_is_info_not_debug(self) -> None:
        """Log level must be INFO, not DEBUG or WARNING.

        DEBUG is too noisy for CI; WARNING misses important progress info.
        INFO is the correct level per AC-4.
        """
        manifest = _render_job_manifest(_STANDARD_TEMPLATE)
        args = _get_container_args(manifest)

        log_args = [a for a in args if a.startswith("--log-cli-level=")]
        assert len(log_args) == 1, (
            f"Expected exactly one --log-cli-level= flag, found {len(log_args)}: {log_args}"
        )
        assert log_args[0] == _LOG_CLI_LEVEL_FLAG, (
            f"Log level must be exactly '{_LOG_CLI_LEVEL_FLAG}', got '{log_args[0]}'"
        )


class TestDestructiveJobLogCliLevel:
    """Verify destructive E2E Job enables live logging."""

    @pytest.mark.requirement("AC-4")
    def test_destructive_job_has_log_cli_level(self) -> None:
        """Destructive Job args MUST include --log-cli-level=INFO.

        Same requirement as the standard job -- both need live logging.
        """
        manifest = _render_job_manifest(_DESTRUCTIVE_TEMPLATE)
        args = _get_container_args(manifest)

        assert _LOG_CLI_LEVEL_FLAG in args, (
            f"Destructive Job args must include '{_LOG_CLI_LEVEL_FLAG}'. Current args: {args}"
        )

    @pytest.mark.requirement("AC-4")
    def test_destructive_job_log_level_is_info_not_debug(self) -> None:
        """Destructive Job log level must be INFO, not DEBUG or WARNING."""
        manifest = _render_job_manifest(_DESTRUCTIVE_TEMPLATE)
        args = _get_container_args(manifest)

        log_args = [a for a in args if a.startswith("--log-cli-level=")]
        assert len(log_args) == 1, (
            f"Expected exactly one --log-cli-level= flag, found {len(log_args)}: {log_args}"
        )
        assert log_args[0] == _LOG_CLI_LEVEL_FLAG, (
            f"Log level must be exactly '{_LOG_CLI_LEVEL_FLAG}', got '{log_args[0]}'"
        )

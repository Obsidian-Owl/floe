"""Unit contracts for the pivoted MinIO chart bump work.

These tests cover the revised Unit B contract:

- the MinIO dependency and lockfile must move to 14.10.5
- values-test.yaml must preserve the defaultBuckets-first path
- Bitnami provisioning must remain off in the normal test render
- values.yaml must expose a dormant fallbackJob flag for the emergency path
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
CHART_YAML = REPO_ROOT / "charts" / "floe-platform" / "Chart.yaml"
CHART_LOCK = REPO_ROOT / "charts" / "floe-platform" / "Chart.lock"
VALUES_TEST = REPO_ROOT / "charts" / "floe-platform" / "values-test.yaml"
VALUES_DEMO = REPO_ROOT / "charts" / "floe-platform" / "values-demo.yaml"
VALUES_DEFAULTS = REPO_ROOT / "charts" / "floe-platform" / "values.yaml"
DEMO_MANIFEST = REPO_ROOT / "demo" / "manifest.yaml"
BUCKET_INIT_TEMPLATE = "templates/job-minio-bucket-init.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    assert path.exists(), f"Expected YAML file at {path}"
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict), f"{path} did not parse to a dict"
    return data


def _find_dependency(config: dict[str, Any], name: str) -> dict[str, Any]:
    dependencies = config.get("dependencies")
    assert isinstance(dependencies, list), "Chart metadata is missing the dependencies list"
    for dependency in dependencies:
        if isinstance(dependency, dict) and dependency.get("name") == name:
            return dependency
    pytest.fail(f"Could not find dependency {name!r} in Chart metadata")


def _render_template(template: str, values_file: Path) -> list[dict[str, Any]]:
    """Render a single chart template through a synthetic dependency-free chart."""

    if shutil.which("helm") is None:
        pytest.fail("helm CLI not available on PATH — required for chart render assertions.")

    helpers_source = REPO_ROOT / "charts" / "floe-platform" / "templates" / "_helpers.tpl"
    template_source = REPO_ROOT / "charts" / "floe-platform" / template
    assert helpers_source.exists(), f"Missing chart helpers at {helpers_source}"
    assert template_source.exists(), f"Missing chart template at {template_source}"

    with tempfile.TemporaryDirectory(prefix="floe-minio-chart-") as temp_dir:
        temp_chart_dir = Path(temp_dir)
        (temp_chart_dir / "Chart.yaml").write_text(
            'apiVersion: v2\nname: floe-platform\nversion: 0.1.0\nappVersion: "1.0.0"\n'
        )
        shutil.copy2(VALUES_DEFAULTS, temp_chart_dir / "values.yaml")

        temp_template_path = temp_chart_dir / template
        temp_template_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(helpers_source, temp_chart_dir / "templates" / "_helpers.tpl")
        shutil.copy2(template_source, temp_template_path)

        result = subprocess.run(
            [
                "helm",
                "template",
                "floe-platform",
                str(temp_chart_dir),
                "-f",
                str(values_file),
                "-s",
                template,
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=120,
            check=False,
        )
    assert result.returncode == 0, f"helm template failed: {result.stderr}"

    docs: list[dict[str, Any]] = []
    for raw in yaml.safe_load_all(result.stdout):
        if isinstance(raw, dict) and raw:
            docs.append(raw)
    return docs


def _render_full_chart(values_file: Path, release_name: str = "floe-test") -> list[dict[str, Any]]:
    """Render the real floe-platform chart with dependencies enabled."""

    if shutil.which("helm") is None:
        pytest.fail("helm CLI not available on PATH — required for chart render assertions.")

    result = subprocess.run(
        [
            "helm",
            "template",
            release_name,
            str(REPO_ROOT / "charts" / "floe-platform"),
            "-f",
            str(VALUES_DEFAULTS),
            "-f",
            str(values_file),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, f"helm template failed: {result.stderr}"

    docs: list[dict[str, Any]] = []
    for raw in yaml.safe_load_all(result.stdout):
        if isinstance(raw, dict) and raw:
            docs.append(raw)
    return docs


def _metadata_name(doc: dict[str, Any]) -> str:
    metadata = doc.get("metadata", {})
    assert isinstance(metadata, dict), "Rendered document metadata is missing."
    name = metadata.get("name")
    assert isinstance(name, str), "Rendered document metadata.name is missing."
    return name


@pytest.fixture(scope="module")
def chart_config() -> dict[str, Any]:
    """Parse Chart.yaml into a dictionary."""
    return _load_yaml(CHART_YAML)


@pytest.fixture(scope="module")
def chart_lock() -> dict[str, Any]:
    """Parse Chart.lock into a dictionary."""
    return _load_yaml(CHART_LOCK)


@pytest.fixture(scope="module")
def values_test_config() -> dict[str, Any]:
    """Parse values-test.yaml into a dictionary."""
    return _load_yaml(VALUES_TEST)


@pytest.fixture(scope="module")
def values_defaults_config() -> dict[str, Any]:
    """Parse values.yaml into a dictionary."""
    return _load_yaml(VALUES_DEFAULTS)


@pytest.fixture(scope="module")
def values_demo_config() -> dict[str, Any]:
    """Parse values-demo.yaml into a dictionary."""
    return _load_yaml(VALUES_DEMO)


@pytest.fixture(scope="module")
def demo_manifest_config() -> dict[str, Any]:
    """Parse the demo manifest into a dictionary."""
    return _load_yaml(DEMO_MANIFEST)


class TestMinioDependencyVersion:
    """Revised AC-1 / AC-8: MinIO dependency must bump to 14.10.5."""

    @pytest.mark.requirement("AC-1")
    def test_chart_yaml_pins_minio_14_10_5(self, chart_config: dict[str, Any]) -> None:
        """Chart.yaml should pin the MinIO dependency at 14.10.5."""
        minio_dependency = _find_dependency(chart_config, "minio")
        assert minio_dependency.get("version") == "14.10.5", (
            "charts/floe-platform/Chart.yaml still pins bitnami/minio to "
            f"{minio_dependency.get('version')!r}. Unit B requires 14.10.5."
        )

    @pytest.mark.requirement("AC-8")
    def test_chart_lock_pins_minio_14_10_5(self, chart_lock: dict[str, Any]) -> None:
        """Chart.lock should be regenerated for the 14.10.5 MinIO dependency."""
        minio_dependency = _find_dependency(chart_lock, "minio")
        assert minio_dependency.get("version") == "14.10.5", (
            "charts/floe-platform/Chart.lock is stale for the MinIO dependency. "
            f"Expected 14.10.5, found {minio_dependency.get('version')!r}."
        )


class TestDefaultBucketsFirstPath:
    """Revised AC-2 / AC-3: keep the normal path on defaultBuckets."""

    @pytest.mark.requirement("AC-2")
    def test_values_test_keeps_floe_iceberg_in_default_buckets(
        self,
        values_test_config: dict[str, Any],
    ) -> None:
        """values-test.yaml should keep defaultBuckets as the primary bucket contract."""
        minio_config = values_test_config.get("minio", {})
        assert isinstance(minio_config, dict), "values-test.yaml minio section is missing"
        default_buckets = minio_config.get("defaultBuckets")
        assert isinstance(default_buckets, str) and default_buckets, (
            "values-test.yaml must keep minio.defaultBuckets as a non-empty string."
        )
        bucket_names = [bucket.strip() for bucket in default_buckets.split(",")]
        assert "floe-iceberg" in bucket_names, (
            "values-test.yaml minio.defaultBuckets must include 'floe-iceberg'. "
            f"Found: {bucket_names}"
        )

    @pytest.mark.requirement("AC-2")
    def test_demo_manifest_bucket_matches_chart_bucket_contracts(
        self,
        values_defaults_config: dict[str, Any],
        values_test_config: dict[str, Any],
        values_demo_config: dict[str, Any],
        demo_manifest_config: dict[str, Any],
    ) -> None:
        """The user-facing demo manifest must match all discoverable chart entrypoints."""

        manifest_bucket = (
            demo_manifest_config.get("plugins", {})
            .get("storage", {})
            .get("config", {})
            .get("bucket")
        )
        assert isinstance(manifest_bucket, str) and manifest_bucket, (
            "demo/manifest.yaml must declare plugins.storage.config.bucket so users "
            "have a discoverable bucket contract."
        )

        def assert_chart_bucket_contract(values_name: str, values_config: dict[str, Any]) -> None:
            minio_config = values_config.get("minio", {})
            polaris_config = values_config.get("polaris", {})
            assert isinstance(minio_config, dict), f"{values_name} minio section is missing"
            assert isinstance(polaris_config, dict), f"{values_name} polaris section is missing"

            default_buckets = minio_config.get("defaultBuckets")
            assert isinstance(default_buckets, str) and default_buckets, (
                f"{values_name} must keep minio.defaultBuckets as a non-empty string."
            )
            bucket_names = [
                bucket.strip() for bucket in default_buckets.split(",") if bucket.strip()
            ]
            assert manifest_bucket in bucket_names, (
                f"demo/manifest.yaml bucket must be provisioned by {values_name} "
                f"minio.defaultBuckets. Manifest bucket: {manifest_bucket!r}, "
                f"defaultBuckets: {bucket_names!r}"
            )

            bootstrap = polaris_config.get("bootstrap")
            assert isinstance(bootstrap, dict), f"{values_name} polaris.bootstrap is missing"
            base_location = bootstrap.get("defaultBaseLocation")
            assert isinstance(base_location, str) and base_location.startswith("s3://"), (
                f"{values_name} polaris.bootstrap.defaultBaseLocation must be an s3:// URI."
            )
            assert base_location == f"s3://{manifest_bucket}", (
                f"{values_name} polaris.bootstrap.defaultBaseLocation must match the "
                f"demo manifest bucket. Expected s3://{manifest_bucket}, got {base_location!r}"
            )

            allowed_locations = bootstrap.get("allowedLocations")
            assert isinstance(allowed_locations, list), (
                f"{values_name} polaris.bootstrap.allowedLocations must be a list."
            )
            assert f"s3://{manifest_bucket}" in allowed_locations, (
                f"{values_name} polaris.bootstrap.allowedLocations must include the "
                f"demo manifest bucket. Allowed locations: {allowed_locations!r}"
            )

        assert_chart_bucket_contract("values.yaml", values_defaults_config)
        assert_chart_bucket_contract("values-test.yaml", values_test_config)
        assert_chart_bucket_contract("values-demo.yaml", values_demo_config)

    @pytest.mark.requirement("AC-2")
    def test_values_test_enables_bucket_init_fallback_hook(
        self,
        values_test_config: dict[str, Any],
    ) -> None:
        """values-test.yaml must enable the chart-owned bucket-init hook.

        The parent chart intentionally overrides MinIO to upstream
        ``minio/minio`` for local/dev compatibility. That image does not honor
        the Bitnami chart's ``MINIO_DEFAULT_BUCKETS`` startup contract, so the
        test path must enable the explicit ``minio/mc`` fallback hook instead.
        """
        minio_config = values_test_config.get("minio", {})
        assert isinstance(minio_config, dict), "values-test.yaml minio section is missing"

        provisioning = minio_config.get("provisioning")
        assert isinstance(provisioning, dict), (
            "values-test.yaml must define minio.provisioning so the test-path "
            "bucket-init contract is explicit."
        )
        assert provisioning.get("enabled") is not True, (
            "values-test.yaml must keep Bitnami provisioning disabled; Unit B "
            "uses the chart-owned bucket-init hook instead."
        )
        assert provisioning.get("fallbackJob") is True, (
            "values-test.yaml must enable minio.provisioning.fallbackJob so "
            "fresh test installs create floe-iceberg on the supported image path."
        )

    @pytest.mark.requirement("AC-3")
    def test_values_test_leaves_minio_provisioning_disabled(
        self,
        values_test_config: dict[str, Any],
    ) -> None:
        """values-test.yaml should not enable Bitnami provisioning for the normal test path."""
        minio_config = values_test_config.get("minio", {})
        assert isinstance(minio_config, dict), "values-test.yaml minio section is missing"
        provisioning = minio_config.get("provisioning")
        assert isinstance(provisioning, dict), (
            "values-test.yaml must define minio.provisioning so the normal-path contract "
            "cannot pass vacuously."
        )
        assert provisioning.get("enabled") is not True, (
            "values-test.yaml must keep Bitnami provisioning disabled in the normal path."
        )

    @pytest.mark.requirement("AC-3")
    def test_values_test_render_has_no_minio_provisioning_job(self) -> None:
        """The offline bucket-init template render must stay on the fallback path."""
        docs = _render_template(BUCKET_INIT_TEMPLATE, VALUES_TEST)
        assert len(docs) == 1, (
            "values-test.yaml must render exactly one chart-owned minio-bucket-init Job "
            "from templates/job-minio-bucket-init.yaml."
        )
        job = docs[0]
        assert job.get("kind") == "Job", "Fallback render must produce a Kubernetes Job."

        metadata = job.get("metadata", {})
        assert isinstance(metadata, dict), "Rendered bucket-init Job metadata is missing."
        labels = metadata.get("labels", {})
        assert isinstance(labels, dict), "Rendered bucket-init Job labels are missing."
        assert labels.get("app.kubernetes.io/component") == "minio-bucket-init", (
            "values-test.yaml must render the chart-owned minio-bucket-init hook "
            "so fresh test installs create floe-iceberg before Polaris bootstrap."
        )

        containers = job.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        assert isinstance(containers, list) and containers, (
            "Rendered bucket-init Job must include a container definition."
        )
        container = containers[0]
        assert isinstance(container, dict), "Rendered bucket-init container must be a mapping."
        command = container.get("command", [])
        assert isinstance(command, list) and command, (
            "Rendered bucket-init Job must define the shell command that creates the bucket."
        )
        shell_script = command[-1]
        assert isinstance(shell_script, str), "Bucket-init shell script must be a string."
        assert 'mc mb --ignore-existing "local/floe-iceberg"' in shell_script, (
            "values-test.yaml must render the fallback hook against the floe-iceberg bucket."
        )

    @pytest.mark.requirement("AC-3")
    def test_values_test_bucket_init_references_rendered_minio_service_and_secret(self) -> None:
        """The parent fallback hook must use the actual MinIO subchart names."""
        docs = _render_full_chart(VALUES_TEST)

        minio_secret_names = {
            _metadata_name(doc)
            for doc in docs
            if doc.get("kind") == "Secret"
            and isinstance(doc.get("data"), dict)
            and "root-user" in doc["data"]
            and "root-password" in doc["data"]
        }
        assert minio_secret_names, (
            "Full chart render must include the MinIO root credential Secret."
        )

        minio_service_names = {
            _metadata_name(doc)
            for doc in docs
            if doc.get("kind") == "Service"
            and isinstance(doc.get("spec"), dict)
            and any(
                isinstance(port, dict) and port.get("port") == 9000
                for port in doc["spec"].get("ports", [])
            )
        }
        assert minio_service_names, "Full chart render must include the MinIO API Service."

        bucket_jobs = [
            doc
            for doc in docs
            if doc.get("kind") == "Job" and _metadata_name(doc).endswith("-minio-bucket-init")
        ]
        assert len(bucket_jobs) == 1, "Full chart render must include one bucket-init fallback Job."

        container = bucket_jobs[0]["spec"]["template"]["spec"]["containers"][0]
        env = {item["name"]: item for item in container["env"]}

        assert env["MINIO_HOST"]["value"] in minio_service_names, (
            "Bucket-init MINIO_HOST must match the rendered MinIO Service name."
        )
        secret_refs = {
            env["MINIO_ROOT_USER"]["valueFrom"]["secretKeyRef"]["name"],
            env["MINIO_ROOT_PASSWORD"]["valueFrom"]["secretKeyRef"]["name"],
        }
        assert secret_refs == minio_secret_names, (
            "Bucket-init credential references must match the rendered MinIO Secret name."
        )


class TestFallbackJobDefault:
    """Revised AC-7: values.yaml must expose the dormant fallback flag."""

    @pytest.mark.requirement("AC-7")
    def test_values_yaml_sets_fallback_job_default_false(
        self,
        values_defaults_config: dict[str, Any],
    ) -> None:
        """values.yaml must define minio.provisioning.fallbackJob: false."""
        minio_config = values_defaults_config.get("minio", {})
        assert isinstance(minio_config, dict), "values.yaml minio section is missing"
        provisioning = minio_config.get("provisioning")
        assert isinstance(provisioning, dict), (
            "values.yaml must define minio.provisioning so the fallback flag is discoverable."
        )
        assert provisioning.get("fallbackJob") is False, (
            "values.yaml must define minio.provisioning.fallbackJob: false for the dormant path. "
            f"Found: {provisioning.get('fallbackJob')!r}"
        )

    @pytest.mark.requirement("AC-7")
    def test_values_yaml_exposes_fallback_job_resources(
        self,
        values_defaults_config: dict[str, Any],
    ) -> None:
        """values.yaml must expose fallback-job resources as discoverable config."""
        minio_config = values_defaults_config.get("minio", {})
        assert isinstance(minio_config, dict), "values.yaml minio section is missing"
        provisioning = minio_config.get("provisioning")
        assert isinstance(provisioning, dict), (
            "values.yaml must define minio.provisioning so fallback-job tuning is discoverable."
        )
        resources = provisioning.get("fallbackJobResources")
        assert isinstance(resources, dict), (
            "values.yaml must define minio.provisioning.fallbackJobResources instead of "
            "hardcoding hook resources in the template."
        )
        requests = resources.get("requests")
        limits = resources.get("limits")
        assert isinstance(requests, dict), "fallbackJobResources.requests must be a mapping."
        assert isinstance(limits, dict), "fallbackJobResources.limits must be a mapping."
        assert requests.get("cpu") == "50m"
        assert requests.get("memory") == "64Mi"
        assert limits.get("cpu") == "100m"
        assert limits.get("memory") == "128Mi"

"""Unit contracts for the pivoted MinIO chart bump work.

These tests cover the revised Unit B contract:

- the MinIO dependency and lockfile must move to 14.10.5
- values-test.yaml must preserve the defaultBuckets-first path
- Bitnami provisioning must remain off in the normal test render
- values.yaml must expose a dormant fallbackJob flag for the emergency path
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
CHART_YAML = REPO_ROOT / "charts" / "floe-platform" / "Chart.yaml"
CHART_LOCK = REPO_ROOT / "charts" / "floe-platform" / "Chart.lock"
VALUES_TEST = REPO_ROOT / "charts" / "floe-platform" / "values-test.yaml"
VALUES_DEFAULTS = REPO_ROOT / "charts" / "floe-platform" / "values.yaml"


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
        if provisioning is None:
            return
        assert isinstance(provisioning, dict), "minio.provisioning must be a mapping when present"
        assert provisioning.get("enabled") is not True, (
            "values-test.yaml must keep Bitnami provisioning disabled in the normal path."
        )

    @pytest.mark.requirement("AC-3")
    def test_values_test_render_has_no_minio_provisioning_job(self) -> None:
        """Full chart render should include the fallback hook, not Bitnami provisioning."""
        result = subprocess.run(
            [
                "helm",
                "template",
                "floe-platform",
                "charts/floe-platform",
                "-f",
                "charts/floe-platform/values-test.yaml",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=120,
            check=False,
        )
        assert result.returncode == 0, f"helm template failed: {result.stderr}"
        assert "app.kubernetes.io/component: minio-provisioning" not in result.stdout, (
            "values-test.yaml unexpectedly renders a MinIO provisioning Job. "
            "Unit B keeps Bitnami provisioning disabled on the test path."
        )
        assert "app.kubernetes.io/component: minio-bucket-init" in result.stdout, (
            "values-test.yaml must render the chart-owned minio-bucket-init hook "
            "so fresh test installs create floe-iceberg before Polaris bootstrap."
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

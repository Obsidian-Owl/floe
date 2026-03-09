"""Structural validation: MinIO bucket provisioning key in values-test.yaml.

Tests that ``charts/floe-platform/values-test.yaml`` uses the Bitnami MinIO
14.8.5 subchart's ``defaultBuckets`` key (comma-separated string) instead of
the dead ``buckets`` key (list format) that the subchart silently ignores.

The ``buckets`` key was valid in older Bitnami MinIO chart versions but is
completely ignored in 14.8.5 standalone mode, meaning no buckets are created
on first boot. The correct key is ``defaultBuckets`` -- a comma-separated
string like ``"floe-data,floe-artifacts,floe-iceberg"``.

AC-1: values-test.yaml uses valid Bitnami bucket key
  - ``minio.defaultBuckets`` MUST be a non-empty string containing ``floe-iceberg``
  - ``minio.buckets`` key MUST NOT exist
  - ``minio.defaultBuckets`` MUST NOT be empty string

These are structural tests. They parse YAML files and check key presence
and value format. No infrastructure or K8s cluster is required.

Requirements:
    AC-1: values-test.yaml uses valid Bitnami bucket key
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
VALUES_TEST = REPO_ROOT / "charts" / "floe-platform" / "values-test.yaml"
VALUES_DEV = REPO_ROOT / "charts" / "floe-platform" / "values-dev.yaml"


@pytest.fixture(scope="module")
def values_test_config() -> dict[str, Any]:
    """Parse values-test.yaml into a dict.

    Returns:
        The full parsed YAML configuration.

    Raises:
        AssertionError: If the file does not exist or cannot be parsed.
    """
    assert VALUES_TEST.exists(), (
        f"values-test.yaml not found at {VALUES_TEST}. "
        "Cannot validate MinIO bucket configuration."
    )
    content = VALUES_TEST.read_text()
    parsed = yaml.safe_load(content)
    assert isinstance(parsed, dict), (
        "values-test.yaml did not parse to a dict. "
        f"Got type: {type(parsed).__name__}"
    )
    return parsed


@pytest.fixture(scope="module")
def minio_config(values_test_config: dict[str, Any]) -> dict[str, Any]:
    """Extract the minio: block from values-test.yaml.

    Returns:
        The minio configuration dict.

    Raises:
        AssertionError: If the minio key is missing.
    """
    assert "minio" in values_test_config, (
        "values-test.yaml does not contain a 'minio:' top-level key. "
        "MinIO must be configured for E2E tests."
    )
    minio = values_test_config["minio"]
    assert isinstance(minio, dict), (
        f"minio: key in values-test.yaml is not a dict. "
        f"Got type: {type(minio).__name__}"
    )
    return minio


class TestDefaultBucketsKeyExists:
    """AC-1: values-test.yaml must use the ``defaultBuckets`` key."""

    @pytest.mark.requirement("AC-1")
    def test_minio_has_default_buckets_key(self, minio_config: dict[str, Any]) -> None:
        """The ``minio:`` block must contain the ``defaultBuckets`` key.

        The Bitnami MinIO 14.8.5 subchart in standalone mode uses
        ``defaultBuckets`` (a comma-separated string) to create buckets
        at first boot. Without this key, no buckets are provisioned and
        all S3 operations fail with NoSuchBucket.
        """
        assert "defaultBuckets" in minio_config, (
            "minio.defaultBuckets key is missing from values-test.yaml. "
            "The Bitnami MinIO 14.8.5 subchart requires 'defaultBuckets' "
            "(comma-separated string) to provision buckets in standalone mode. "
            "Without it, no buckets are created and E2E tests fail."
        )

    @pytest.mark.requirement("AC-1")
    def test_default_buckets_is_string(self, minio_config: dict[str, Any]) -> None:
        """The ``defaultBuckets`` value must be a string, not a list.

        The Bitnami subchart expects a comma-separated string like
        ``"floe-data,floe-artifacts,floe-iceberg"``. A list value would
        be silently ignored or cause a template rendering error.
        """
        default_buckets = minio_config.get("defaultBuckets")
        assert isinstance(default_buckets, str), (
            f"minio.defaultBuckets must be a string (comma-separated bucket names). "
            f"Got type: {type(default_buckets).__name__}, value: {default_buckets!r}. "
            "Example: 'floe-data,floe-artifacts,floe-iceberg'"
        )


class TestDefaultBucketsValue:
    """AC-1: ``defaultBuckets`` must be a non-empty string containing ``floe-iceberg``."""

    @pytest.mark.requirement("AC-1")
    def test_default_buckets_is_not_empty(self, minio_config: dict[str, Any]) -> None:
        """The ``defaultBuckets`` value must not be an empty string.

        An empty string would result in no buckets being created,
        causing all Iceberg and S3 operations to fail.
        """
        default_buckets = minio_config.get("defaultBuckets", "")
        assert default_buckets != "", (
            "minio.defaultBuckets is an empty string in values-test.yaml. "
            "At minimum, 'floe-iceberg' must be listed for E2E tests to function."
        )

    @pytest.mark.requirement("AC-1")
    def test_default_buckets_contains_floe_iceberg(
        self, minio_config: dict[str, Any]
    ) -> None:
        """The ``defaultBuckets`` string must contain ``floe-iceberg``.

        The ``floe-iceberg`` bucket is required by Polaris and PyIceberg
        for Iceberg table storage. Without it, all catalog and table
        operations fail. This test splits on commas and checks individual
        bucket names to avoid false positives from substring matching
        (e.g., ``floe-iceberg-archive`` should not satisfy this check if
        ``floe-iceberg`` itself is missing).
        """
        default_buckets = minio_config.get("defaultBuckets", "")
        # Guard: must be a string for split to work
        assert isinstance(default_buckets, str), (
            f"minio.defaultBuckets is not a string: {type(default_buckets).__name__}"
        )
        bucket_names = [b.strip() for b in default_buckets.split(",")]
        assert "floe-iceberg" in bucket_names, (
            f"minio.defaultBuckets does not contain 'floe-iceberg' as a "
            f"discrete bucket name. Found buckets: {bucket_names}. "
            "The floe-iceberg bucket is required for Polaris/Iceberg operations."
        )

    @pytest.mark.requirement("AC-1")
    def test_default_buckets_has_no_empty_entries(
        self, minio_config: dict[str, Any]
    ) -> None:
        """The ``defaultBuckets`` string must not have empty entries from extra commas.

        Trailing commas or double commas (e.g., ``"floe-data,,floe-iceberg"``)
        would produce empty bucket name entries that could cause errors or
        unexpected behavior in the subchart's provisioning script.
        """
        default_buckets = minio_config.get("defaultBuckets", "")
        assert isinstance(default_buckets, str) and default_buckets != "", (
            "minio.defaultBuckets is missing or empty. Cannot validate "
            "comma-separated format. This test requires defaultBuckets "
            "to be a non-empty string."
        )
        bucket_names = [b.strip() for b in default_buckets.split(",")]
        empty_entries = [i for i, name in enumerate(bucket_names) if name == ""]
        assert len(empty_entries) == 0, (
            f"minio.defaultBuckets contains empty entries at positions "
            f"{empty_entries}. Value: {default_buckets!r}. "
            "Remove trailing/double commas."
        )


class TestDeadBucketsKeyAbsent:
    """AC-1: The dead ``minio.buckets`` key must NOT be present."""

    @pytest.mark.requirement("AC-1")
    def test_minio_buckets_key_does_not_exist(
        self, minio_config: dict[str, Any]
    ) -> None:
        """The ``minio.buckets`` key (list format) must not be present.

        The ``buckets`` key with list-of-dicts format was used by older
        Bitnami MinIO chart versions. In 14.8.5 standalone mode, this
        key is silently ignored -- no error, no warning, no buckets.
        Its presence is a configuration bug: the operator believes
        buckets are being created, but they are not.
        """
        assert "buckets" not in minio_config, (
            "minio.buckets key is present in values-test.yaml. "
            "This is a DEAD key -- the Bitnami MinIO 14.8.5 subchart "
            "silently ignores it in standalone mode. Buckets configured "
            "under this key are never created. "
            "Use 'defaultBuckets' (comma-separated string) instead. "
            f"Current dead value: {minio_config.get('buckets')!r}"
        )

    @pytest.mark.requirement("AC-1")
    def test_no_list_format_bucket_definition(
        self, minio_config: dict[str, Any]
    ) -> None:
        """No bucket provisioning key should use the list-of-dicts format.

        This catches variations like ``provisioning.buckets``, ``initBuckets``,
        or any other key that uses the old list format. The only valid
        approach in Bitnami 14.8.5 standalone mode is ``defaultBuckets``
        as a comma-separated string.
        """
        # Check top-level minio keys for any list value containing bucket defs
        bucket_list_keys: list[str] = []
        for key, value in minio_config.items():
            if key == "defaultBuckets":
                continue  # This is the correct key
            if isinstance(value, list) and len(value) > 0:
                # Check if any list item looks like a bucket definition
                first_item = value[0]
                if isinstance(first_item, dict) and "name" in first_item:
                    bucket_list_keys.append(key)

        assert len(bucket_list_keys) == 0, (
            f"Found list-format bucket definitions under minio keys: "
            f"{bucket_list_keys}. The Bitnami MinIO 14.8.5 subchart ignores "
            "list-format bucket definitions in standalone mode. "
            "Use 'defaultBuckets' (comma-separated string) instead."
        )


class TestConsistencyWithValuesDev:
    """Cross-reference values-test.yaml against values-dev.yaml for consistency."""

    @pytest.mark.requirement("AC-1")
    def test_values_dev_uses_default_buckets(self) -> None:
        """Confirm values-dev.yaml uses ``defaultBuckets`` as the reference format.

        This test establishes the known-good reference: values-dev.yaml
        already correctly uses ``defaultBuckets``. If this test fails,
        the reference itself has regressed.
        """
        assert VALUES_DEV.exists(), (
            f"values-dev.yaml not found at {VALUES_DEV}."
        )
        dev_config = yaml.safe_load(VALUES_DEV.read_text())
        assert isinstance(dev_config, dict), "values-dev.yaml is not a dict"
        minio_dev = dev_config.get("minio", {})
        assert isinstance(minio_dev, dict), "minio: in values-dev.yaml is not a dict"
        assert "defaultBuckets" in minio_dev, (
            "values-dev.yaml minio: block does not contain 'defaultBuckets'. "
            "This is the known-good reference file."
        )
        assert isinstance(minio_dev["defaultBuckets"], str), (
            "values-dev.yaml minio.defaultBuckets is not a string."
        )
        assert minio_dev["defaultBuckets"] != "", (
            "values-dev.yaml minio.defaultBuckets is empty."
        )

    @pytest.mark.requirement("AC-1")
    def test_values_dev_does_not_have_dead_buckets_key(self) -> None:
        """Confirm values-dev.yaml does not have the dead ``buckets`` key.

        If values-dev.yaml gained a ``buckets`` key, it would indicate
        a regression or copy-paste error.
        """
        dev_config = yaml.safe_load(VALUES_DEV.read_text())
        minio_dev = dev_config.get("minio", {})
        assert "buckets" not in minio_dev, (
            "values-dev.yaml minio: block contains the dead 'buckets' key. "
            "This is a regression -- values-dev.yaml should use 'defaultBuckets' only."
        )

    @pytest.mark.requirement("AC-1")
    def test_floe_iceberg_bucket_in_both_files(
        self, minio_config: dict[str, Any]
    ) -> None:
        """Both values-test.yaml and values-dev.yaml must provision ``floe-iceberg``.

        The ``floe-iceberg`` bucket is critical for E2E tests. Both
        environments must provision it. This test cross-references
        the two files to catch drift.
        """
        dev_config = yaml.safe_load(VALUES_DEV.read_text())
        dev_default_buckets = dev_config.get("minio", {}).get("defaultBuckets", "")
        dev_buckets = [b.strip() for b in dev_default_buckets.split(",")]

        test_default_buckets = minio_config.get("defaultBuckets", "")
        # If defaultBuckets is missing from values-test.yaml, this test should
        # still fail clearly (not just get an empty list from splitting None)
        if not isinstance(test_default_buckets, str):
            pytest.fail(
                f"minio.defaultBuckets in values-test.yaml is not a string "
                f"(type: {type(test_default_buckets).__name__}). "
                "Cannot compare bucket lists."
            )
        test_buckets = [b.strip() for b in test_default_buckets.split(",")]

        assert "floe-iceberg" in dev_buckets, (
            f"values-dev.yaml minio.defaultBuckets does not contain 'floe-iceberg'. "
            f"Found: {dev_buckets}"
        )
        assert "floe-iceberg" in test_buckets, (
            f"values-test.yaml minio.defaultBuckets does not contain 'floe-iceberg'. "
            f"Found: {test_buckets}"
        )

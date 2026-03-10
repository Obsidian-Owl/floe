"""Structural validation: MinIO bucket provisioning in values-test.yaml and test-e2e.sh.

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

AC-2: test-e2e.sh bucket check has retry loop
  - The ``ensure-bucket.py`` invocation MUST be inside a retry loop
  - Max retry count MUST be <= 10
  - On exhaustion, MUST exit non-zero and print error to stderr
  - MUST use ``uv run python3`` (AC-3 consistency)

These are structural tests. They parse YAML files and shell scripts and
check key presence, value format, and control flow patterns. No
infrastructure or K8s cluster is required.

Requirements:
    AC-1: values-test.yaml uses valid Bitnami bucket key
    AC-2: test-e2e.sh bucket check has retry loop
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
VALUES_TEST = REPO_ROOT / "charts" / "floe-platform" / "values-test.yaml"
VALUES_DEV = REPO_ROOT / "charts" / "floe-platform" / "values-dev.yaml"
TEST_E2E_SH = REPO_ROOT / "testing" / "ci" / "test-e2e.sh"


@pytest.fixture(scope="module")
def values_test_config() -> dict[str, Any]:
    """Parse values-test.yaml into a dict.

    Returns:
        The full parsed YAML configuration.

    Raises:
        AssertionError: If the file does not exist or cannot be parsed.
    """
    assert VALUES_TEST.exists(), (
        f"values-test.yaml not found at {VALUES_TEST}. Cannot validate MinIO bucket configuration."
    )
    content = VALUES_TEST.read_text()
    parsed = yaml.safe_load(content)
    assert isinstance(parsed, dict), (
        f"values-test.yaml did not parse to a dict. Got type: {type(parsed).__name__}"
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
        f"minio: key in values-test.yaml is not a dict. Got type: {type(minio).__name__}"
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
    def test_default_buckets_contains_floe_iceberg(self, minio_config: dict[str, Any]) -> None:
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
    def test_default_buckets_has_no_empty_entries(self, minio_config: dict[str, Any]) -> None:
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
    def test_minio_buckets_key_does_not_exist(self, minio_config: dict[str, Any]) -> None:
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
    def test_no_list_format_bucket_definition(self, minio_config: dict[str, Any]) -> None:
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
        assert VALUES_DEV.exists(), f"values-dev.yaml not found at {VALUES_DEV}."
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
        assert minio_dev["defaultBuckets"] != "", "values-dev.yaml minio.defaultBuckets is empty."

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
    def test_floe_iceberg_bucket_in_both_files(self, minio_config: dict[str, Any]) -> None:
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


# ---------------------------------------------------------------------------
# AC-2: test-e2e.sh bucket check has retry loop
# ---------------------------------------------------------------------------


def _extract_bucket_section(script_text: str) -> str:
    """Extract the MinIO bucket verification section from test-e2e.sh.

    The section starts at the "Verify MinIO bucket exists" comment and ends
    at the next top-level section comment (``# Verify Polaris`` or similar).

    Args:
        script_text: Full text of test-e2e.sh.

    Returns:
        The bucket verification section as a string.

    Raises:
        AssertionError: If the section boundaries cannot be found.
    """
    # Find the start: the comment marking bucket verification
    start_match = re.search(
        r"^# Verify MinIO bucket exists",
        script_text,
        re.MULTILINE,
    )
    assert start_match is not None, (
        "Could not find '# Verify MinIO bucket exists' comment in test-e2e.sh. "
        "The bucket verification section is missing or has been renamed."
    )
    start_pos = start_match.start()

    # Find the end: the next top-level section starting with "# Verify" or
    # "# Install" or "# Run" after the bucket section.
    end_match = re.search(
        r"^# (?:Verify Polaris|Install|Run)",
        script_text[start_pos + 1 :],
        re.MULTILINE,
    )
    if end_match is not None:
        end_pos = start_pos + 1 + end_match.start()
    else:
        end_pos = len(script_text)

    return script_text[start_pos:end_pos]


@pytest.fixture(scope="module")
def test_e2e_script() -> str:
    """Read test-e2e.sh content.

    Returns:
        The full text of test-e2e.sh.

    Raises:
        AssertionError: If the file does not exist.
    """
    assert TEST_E2E_SH.exists(), (
        f"test-e2e.sh not found at {TEST_E2E_SH}. Cannot validate bucket retry loop."
    )
    return TEST_E2E_SH.read_text()


@pytest.fixture(scope="module")
def bucket_section(test_e2e_script: str) -> str:
    """Extract the MinIO bucket verification section from test-e2e.sh.

    Returns:
        The bucket verification section text.
    """
    return _extract_bucket_section(test_e2e_script)


class TestBucketRetryLoopExists:
    """AC-2: The ensure-bucket.py call in test-e2e.sh must have a retry loop."""

    @pytest.mark.requirement("AC-2")
    def test_bucket_section_contains_loop_keyword(self, bucket_section: str) -> None:
        """The bucket section must contain a ``while`` or ``for`` loop.

        A bare invocation of ``ensure-bucket.py`` without a loop means a
        transient failure (e.g., MinIO still starting) will crash the entire
        E2E run with no retry.

        Only non-comment lines are checked to prevent false positives from
        comments like "for both existing and non-existing buckets".
        """
        # Strip comment lines before checking for loop keywords
        code_lines = [
            line for line in bucket_section.splitlines() if not line.lstrip().startswith("#")
        ]
        code_only = "\n".join(code_lines)
        has_while = re.search(r"\bwhile\b", code_only) is not None
        has_for = re.search(r"\bfor\b", code_only) is not None
        assert has_while or has_for, (
            "The bucket verification section in test-e2e.sh does not contain "
            "a 'while' or 'for' loop in executable code. The ensure-bucket.py "
            "call must be wrapped in a retry loop for resilience against "
            "transient failures."
        )

    @pytest.mark.requirement("AC-2")
    def test_bucket_section_has_attempt_counter(self, bucket_section: str) -> None:
        """The retry loop must have an attempt counter variable.

        Without a counter, the loop either runs forever (infinite loop) or
        has no visibility into progress. The counter variable must be
        incremented (e.g., ``ATTEMPT=$((ATTEMPT + 1))`` or similar).
        """
        # Match arithmetic increment patterns: VAR=$((VAR + 1)) or
        # VAR=$(( VAR + 1 )) or ((VAR++)) or ((VAR+=1))
        has_increment = (
            re.search(
                r"\w+\s*=\s*\$\(\(\s*\w+\s*\+\s*1\s*\)\)|"
                r"\(\(\s*\w+\s*\+\+\s*\)\)|"
                r"\(\(\s*\w+\s*\+=\s*1\s*\)\)",
                bucket_section,
            )
            is not None
        )
        assert has_increment, (
            "The bucket verification section in test-e2e.sh does not contain "
            "an attempt counter increment (e.g., ATTEMPT=$((ATTEMPT + 1))). "
            "Without a counter, the retry loop has no progress tracking and "
            "no mechanism to enforce a maximum attempt limit."
        )


class TestBucketRetryMaxAttempts:
    """AC-2: The retry loop must cap at <= 10 attempts."""

    @pytest.mark.requirement("AC-2")
    def test_max_attempts_variable_defined(self, bucket_section: str) -> None:
        """A max-attempts variable must be defined in the bucket section.

        The variable name should follow shell convention (e.g.,
        ``MAX_ATTEMPTS=10`` or ``MINIO_MAX_ATTEMPTS=10``). Without it,
        the loop either runs forever or the limit is inlined and fragile.
        """
        max_pattern = re.search(
            r"(?:MAX_ATTEMPTS|MAX_RETRIES)\s*=\s*(\d+)",
            bucket_section,
            re.IGNORECASE,
        )
        assert max_pattern is not None, (
            "The bucket verification section in test-e2e.sh does not define "
            "a MAX_ATTEMPTS or MAX_RETRIES variable. The retry loop must have "
            "a named constant for the attempt limit."
        )

    @pytest.mark.requirement("AC-2")
    def test_max_attempts_at_most_ten(self, bucket_section: str) -> None:
        """The max attempt count must be <= 10.

        The bucket should exist from ``defaultBuckets`` server startup,
        so this retry is defense-in-depth only. More than 10 attempts
        (at 3s intervals = 30s total) would waste CI time waiting for
        something that should already exist.
        """
        max_match = re.search(
            r"(?:MAX_ATTEMPTS|MAX_RETRIES)\s*=\s*(\d+)",
            bucket_section,
            re.IGNORECASE,
        )
        assert max_match is not None, (
            "Cannot verify max attempts: no MAX_ATTEMPTS/MAX_RETRIES variable found."
        )
        max_value = int(max_match.group(1))
        assert max_value <= 10, (
            f"Bucket retry MAX_ATTEMPTS is {max_value}, which exceeds the "
            f"allowed maximum of 10. The bucket should exist from "
            f"defaultBuckets startup. 10 attempts at 3s intervals (30s total) "
            f"is sufficient for defense-in-depth."
        )

    @pytest.mark.requirement("AC-2")
    def test_max_attempts_at_least_two(self, bucket_section: str) -> None:
        """The max attempt count must be >= 2 (at least one retry).

        A max of 1 means no retry at all, defeating the purpose of the
        retry loop.
        """
        max_match = re.search(
            r"(?:MAX_ATTEMPTS|MAX_RETRIES)\s*=\s*(\d+)",
            bucket_section,
            re.IGNORECASE,
        )
        assert max_match is not None, (
            "Cannot verify min attempts: no MAX_ATTEMPTS/MAX_RETRIES variable found."
        )
        max_value = int(max_match.group(1))
        assert max_value >= 2, (
            f"Bucket retry MAX_ATTEMPTS is {max_value}. A value of 1 means "
            f"no retry occurs. The loop must allow at least one retry (>= 2)."
        )

    @pytest.mark.requirement("AC-2")
    def test_loop_has_max_check(self, bucket_section: str) -> None:
        """The loop body must compare the attempt counter against the max.

        Without this comparison (e.g., ``-ge $MAX_ATTEMPTS``), the loop
        either runs forever or has a hardcoded inlined limit.
        """
        # Match patterns like: $ATTEMPT -ge $MAX_ATTEMPTS or
        # $ATTEMPT -ge $MINIO_MAX_ATTEMPTS or
        # [[ $ATTEMPT -ge $MAX ]] etc.
        has_max_check = (
            re.search(
                r"-ge\s+\$\{?\w*MAX_ATTEMPTS\}?|"
                r"-ge\s+\$\{?\w*MAX_RETRIES\}?|"
                r"-gt\s+\$\{?\w*MAX_ATTEMPTS\}?|"
                r"-gt\s+\$\{?\w*MAX_RETRIES\}?",
                bucket_section,
                re.IGNORECASE,
            )
            is not None
        )
        assert has_max_check, (
            "The bucket retry loop does not compare the attempt counter "
            "against a max-attempts variable (e.g., -ge $MAX_ATTEMPTS). "
            "Without this guard, the loop may run indefinitely."
        )


class TestBucketRetryExhaustion:
    """AC-2: On retry exhaustion, must exit non-zero with stderr message."""

    @pytest.mark.requirement("AC-2")
    def test_exhaustion_exits_nonzero(self, bucket_section: str) -> None:
        """When retries are exhausted, the script must exit with non-zero code.

        Without ``exit 1`` (or similar), the script continues to the E2E
        test runner and runs tests against a broken environment.
        """
        has_exit = (
            re.search(
                r"exit\s+[1-9]",
                bucket_section,
            )
            is not None
        )
        assert has_exit, (
            "The bucket verification section does not contain 'exit 1' (or "
            "any non-zero exit). On retry exhaustion, the script must abort "
            "to prevent running E2E tests without a working MinIO bucket."
        )

    @pytest.mark.requirement("AC-2")
    def test_exhaustion_prints_to_stderr(self, bucket_section: str) -> None:
        """The exhaustion error message must be printed to stderr (``>&2``).

        Error messages on stdout get mixed with test output and are hard to
        find. The project standard (code-quality.md) requires errors to go
        to stderr.
        """
        # Look for stderr redirect near an ERROR echo in the bucket section
        # The pattern should be: echo "ERROR: ..." >&2 somewhere after the
        # max-attempts check
        has_stderr_error = (
            re.search(
                r'echo\s+"ERROR:.*>&2',
                bucket_section,
            )
            is not None
        )
        assert has_stderr_error, (
            "The bucket verification section does not print an ERROR message "
            "to stderr (>&2) on retry exhaustion. Error output must go to "
            "stderr per project standards."
        )


class TestBucketRetryDelay:
    """AC-2: The retry loop must have a sleep between attempts."""

    @pytest.mark.requirement("AC-2")
    def test_retry_has_sleep_between_attempts(self, bucket_section: str) -> None:
        """The retry loop must include a ``sleep`` call between attempts.

        Without a delay, the retry loop hammers MinIO as fast as possible,
        which is wasteful and unlikely to help if the service is still
        starting up.
        """
        has_sleep = re.search(r"\bsleep\s+\d+", bucket_section) is not None
        assert has_sleep, (
            "The bucket verification section does not contain a 'sleep N' "
            "command. The retry loop must pause between attempts to allow "
            "MinIO time to initialize."
        )

    @pytest.mark.requirement("AC-2")
    def test_retry_sleep_interval_is_three_seconds(self, bucket_section: str) -> None:
        """The sleep interval must be 3 seconds.

        The spec requires 3-second intervals. Shorter intervals waste CPU;
        longer intervals waste CI wall-clock time.
        """
        sleep_match = re.search(r"\bsleep\s+(\d+)", bucket_section)
        assert sleep_match is not None, (
            "No 'sleep N' found in bucket section. Cannot verify interval."
        )
        interval = int(sleep_match.group(1))
        assert interval == 3, (
            f"Bucket retry sleep interval is {interval}s, expected 3s. "
            f"The spec requires 3-second intervals between retry attempts."
        )


class TestBucketInvocationConsistency:
    """AC-2/AC-3: ensure-bucket.py must be invoked with ``uv run python3``."""

    @pytest.mark.requirement("AC-2")
    def test_ensure_bucket_uses_uv_run_python3(self, bucket_section: str) -> None:
        """The ensure-bucket.py call must use ``uv run python3``.

        AC-3 requires all Python invocations in CI scripts to use
        ``uv run python3`` for environment consistency. A bare ``python3``
        call may use a different Python than the one managed by uv.
        """
        has_uv_call = (
            re.search(
                r"uv\s+run\s+python3\s+.*ensure-bucket\.py",
                bucket_section,
            )
            is not None
        )
        assert has_uv_call, (
            "The ensure-bucket.py invocation in the bucket section does not "
            "use 'uv run python3'. All Python calls in CI scripts must use "
            "'uv run python3' for environment consistency (AC-3)."
        )

    @pytest.mark.requirement("AC-2")
    def test_no_bare_python3_ensure_bucket(self, bucket_section: str) -> None:
        """There must be no bare ``python3`` call to ensure-bucket.py.

        This is the inverse check: even if a ``uv run python3`` call exists,
        there must not also be a bare ``python3`` call (e.g., from the old
        code not being updated).
        """
        # Find all lines invoking ensure-bucket.py
        invocations = re.findall(
            r"^.*ensure-bucket\.py.*$",
            bucket_section,
            re.MULTILINE,
        )
        bare_calls = [
            line.strip()
            for line in invocations
            if "ensure-bucket.py" in line
            and "uv run" not in line
            and not line.lstrip().startswith("#")
        ]
        assert len(bare_calls) == 0, (
            f"Found bare python3 invocation(s) of ensure-bucket.py without "
            f"'uv run': {bare_calls}. All calls must use 'uv run python3'."
        )


# ---------------------------------------------------------------------------
# AC-3: wait-for-services.sh uses uv run for ensure-bucket.py
# ---------------------------------------------------------------------------

WAIT_FOR_SERVICES_SH = REPO_ROOT / "testing" / "ci" / "wait-for-services.sh"


@pytest.fixture(scope="module")
def wait_for_services_script() -> str:
    """Read wait-for-services.sh content.

    Returns:
        The full text of wait-for-services.sh.

    Raises:
        AssertionError: If the file does not exist.
    """
    assert WAIT_FOR_SERVICES_SH.exists(), (
        f"wait-for-services.sh not found at {WAIT_FOR_SERVICES_SH}."
    )
    return WAIT_FOR_SERVICES_SH.read_text()


class TestWaitForServicesUvRun:
    """AC-3: wait-for-services.sh must use ``uv run python3`` for ensure-bucket.py."""

    @pytest.mark.requirement("AC-3")
    def test_ensure_bucket_uses_uv_run_in_wait_for_services(
        self, wait_for_services_script: str
    ) -> None:
        """The ensure-bucket.py invocation must use ``uv run python3``.

        System python3 may not have boto3 installed. The uv virtual
        environment has it as a transitive dependency. This must match
        the pattern used in test-e2e.sh.
        """
        # Find non-comment lines that invoke ensure-bucket.py
        lines = wait_for_services_script.splitlines()
        invocation_lines = [
            line
            for line in lines
            if "ensure-bucket.py" in line and not line.lstrip().startswith("#")
        ]
        assert len(invocation_lines) > 0, (
            "No invocation of ensure-bucket.py found in wait-for-services.sh."
        )
        for line in invocation_lines:
            assert "uv run python3" in line or "uv run python" in line, (
                f"ensure-bucket.py invocation in wait-for-services.sh does not "
                f"use 'uv run python3'. Found: {line.strip()!r}. "
                "System python3 may not have boto3."
            )

    @pytest.mark.requirement("AC-3")
    def test_no_bare_python3_ensure_bucket_in_wait_for_services(
        self, wait_for_services_script: str
    ) -> None:
        """No bare ``python3`` invocation of ensure-bucket.py should exist.

        All invocations must go through ``uv run python3`` to ensure
        boto3 is available from the uv virtual environment.
        """
        lines = wait_for_services_script.splitlines()
        bare_calls = [
            line.strip()
            for line in lines
            if "ensure-bucket.py" in line
            and "python3" in line
            and "uv run" not in line
            and not line.lstrip().startswith("#")
        ]
        assert len(bare_calls) == 0, (
            f"Found bare python3 invocation(s) of ensure-bucket.py in "
            f"wait-for-services.sh: {bare_calls}. "
            "Use 'uv run python3' instead."
        )


# ---------------------------------------------------------------------------
# AC-4: Bootstrap job documents curl limitation
# ---------------------------------------------------------------------------

BOOTSTRAP_JOB = REPO_ROOT / "charts" / "floe-platform" / "templates" / "job-polaris-bootstrap.yaml"


class TestBootstrapJobCurlDocumentation:
    """AC-4: Bootstrap job must document the anonymous curl limitation."""

    @pytest.mark.requirement("AC-4")
    def test_bootstrap_job_documents_403_behavior(self) -> None:
        """The bootstrap job template must document the 403-for-both-states behavior.

        Anonymous curl to MinIO returns HTTP 403 for both existing and
        non-existing buckets. The comment block near the curl check must
        explain this limitation so future maintainers don't misinterpret
        the check as a bucket existence verification.
        """
        assert BOOTSTRAP_JOB.exists(), f"Bootstrap job template not found at {BOOTSTRAP_JOB}."
        content = BOOTSTRAP_JOB.read_text()
        assert "403" in content, (
            "Bootstrap job template does not mention HTTP 403 anywhere. "
            "The anonymous curl bucket check returns 403 for both existing "
            "and non-existing buckets — this must be documented."
        )

    @pytest.mark.requirement("AC-4")
    def test_bootstrap_job_documents_default_buckets_guarantee(self) -> None:
        """The bootstrap job template must reference the ``defaultBuckets`` guarantee.

        Since ``defaultBuckets`` creates the bucket at MinIO startup
        (before the bootstrap job runs), the curl check is a health
        check, not a bucket existence check. The comment must explain
        this relationship.
        """
        assert BOOTSTRAP_JOB.exists(), f"Bootstrap job template not found at {BOOTSTRAP_JOB}."
        content = BOOTSTRAP_JOB.read_text()
        assert "defaultBuckets" in content, (
            "Bootstrap job template does not mention 'defaultBuckets'. "
            "The comment block must explain that defaultBuckets guarantees "
            "the bucket exists at MinIO startup, making this curl check "
            "a health verification rather than a bucket existence check."
        )

"""Unit tests for the recovery-based pod assertion helper.

Tests the ``_assert_pod_recovery`` helper function that replaces the flaky
"downtime detection" pattern with UID-change-based recovery assertions.

This file tests the helper logic in isolation using mocks -- it does NOT
require a running Kind cluster.

See Also:
    - .specwright/work/test-hardening-audit/spec.md: WU-3
    - tests/e2e/test_service_failure_resilience_e2e.py: E2E consumer
"""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Fixture: import the helper under test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin NAMESPACE so kubectl mocks match deterministically."""
    monkeypatch.setenv("FLOE_E2E_NAMESPACE", "floe-test")


def _import_helper() -> Any:
    """Import _assert_pod_recovery from the E2E module.

    Returns:
        The _assert_pod_recovery callable.

    Raises:
        AttributeError: If the helper has not been implemented yet (RED phase).
    """
    import tests.e2e.test_service_failure_resilience_e2e as mod

    return mod._assert_pod_recovery


# ---------------------------------------------------------------------------
# AC-1: Pod replacement detected via UID change
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU3-AC-1")
class TestUIDChangeDetection:
    """Verify recovery is detected by UID change, not downtime polling."""

    def test_returns_different_uids(self) -> None:
        """Happy path: original UID differs from new UID after recovery."""
        helper = _import_helper()

        original_uid = "aaa-111-original"
        new_uid = "bbb-222-replacement"

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                side_effect=[original_uid, new_uid],
            ) as mock_get_uid,
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="pod deleted", stderr=""
                ),
            ) as mock_kubectl,
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                return_value=True,
            ) as mock_wait,
        ):
            result = helper("app.kubernetes.io/name=minio", "MinIO")

        orig, new, recovery_secs = result
        assert orig == original_uid, f"Expected original UID {original_uid!r}, got {orig!r}"
        assert new == new_uid, f"Expected new UID {new_uid!r}, got {new!r}"
        assert orig != new, "UIDs must differ to prove pod replacement"

        # Verify _get_pod_uid was called (not hardcoded)
        assert mock_get_uid.call_count >= 1, "_get_pod_uid must be called to obtain original UID"
        # Verify kubectl delete was invoked
        mock_kubectl.assert_called_once()
        # Verify wait_for_condition was invoked for recovery polling
        mock_wait.assert_called_once()

    def test_uid_values_come_from_get_pod_uid(self) -> None:
        """The returned UIDs must originate from _get_pod_uid, not be invented."""
        helper = _import_helper()

        sentinel_orig = "sentinel-original-uid-xyz"
        sentinel_new = "sentinel-replacement-uid-abc"

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                side_effect=[sentinel_orig, sentinel_new],
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                return_value=True,
            ),
        ):
            orig, new, _ = helper("app.kubernetes.io/name=minio", "MinIO")

        # Exact sentinel values must appear -- prevents hardcoded returns
        assert orig == sentinel_orig
        assert new == sentinel_new

    def test_delete_uses_correct_label_selector(self) -> None:
        """kubectl delete must target the label selector passed to helper."""
        helper = _import_helper()

        selector = "app.kubernetes.io/component=polaris"

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                side_effect=["uid-before", "uid-after"],
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ) as mock_kubectl,
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                return_value=True,
            ),
        ):
            helper(selector, "Polaris")

        # Verify the label selector ended up in the kubectl delete call
        kubectl_args = mock_kubectl.call_args
        # Flatten all args to find the selector
        all_args_flat = []
        for a in kubectl_args.args:
            if isinstance(a, list):
                all_args_flat.extend(a)
            else:
                all_args_flat.append(str(a))
        for _k, v in (kubectl_args.kwargs or {}).items():
            if isinstance(v, list):
                all_args_flat.extend(str(x) for x in v)
            else:
                all_args_flat.append(str(v))

        assert selector in all_args_flat, (
            f"Label selector {selector!r} not found in kubectl call args: {all_args_flat}"
        )


# ---------------------------------------------------------------------------
# AC-2: Recovery within timeout
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU3-AC-2")
class TestRecoveryTiming:
    """Verify recovery_seconds is measured and bounded."""

    def test_recovery_seconds_is_positive_float(self) -> None:
        """recovery_seconds must be a real elapsed time, not zero or negative."""
        helper = _import_helper()

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                side_effect=["uid-1", "uid-2"],
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                return_value=True,
            ),
        ):
            _, _, recovery_secs = helper("app.kubernetes.io/name=minio", "MinIO")

        assert isinstance(recovery_secs, float), (
            f"recovery_seconds must be float, got {type(recovery_secs).__name__}"
        )
        assert recovery_secs > 0.0, f"recovery_seconds must be positive, got {recovery_secs}"

    def test_default_timeout_is_30_seconds(self) -> None:
        """The default timeout parameter must be 30.0 seconds."""
        helper = _import_helper()

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                side_effect=["uid-1", "uid-2"],
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                return_value=True,
            ) as mock_wait,
        ):
            # Call WITHOUT explicit timeout -- should use default 30.0
            helper("app.kubernetes.io/name=minio", "MinIO")

        wait_call = mock_wait.call_args
        # timeout could be positional or keyword
        all_kwargs = wait_call.kwargs if wait_call.kwargs else {}
        all_args = wait_call.args if wait_call.args else ()

        # Check keyword first, then fall back to positional arg inspection
        if "timeout" in all_kwargs:
            assert all_kwargs["timeout"] == pytest.approx(30.0), (
                f"Default timeout should be 30.0, got {all_kwargs['timeout']}"
            )
        else:
            # If timeout is passed positionally, it should be 30.0 somewhere
            assert any(
                isinstance(a, (int, float)) and a == pytest.approx(30.0) for a in all_args
            ), f"Default timeout 30.0 not found in wait_for_condition args: {all_args}"

    def test_custom_timeout_propagated_to_wait(self) -> None:
        """A custom timeout value must be forwarded to wait_for_condition."""
        helper = _import_helper()

        custom_timeout = 60.0

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                side_effect=["uid-1", "uid-2"],
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                return_value=True,
            ) as mock_wait,
        ):
            helper("app.kubernetes.io/name=minio", "MinIO", timeout=custom_timeout)

        wait_call = mock_wait.call_args
        all_kwargs = wait_call.kwargs if wait_call.kwargs else {}
        all_args = wait_call.args if wait_call.args else ()

        if "timeout" in all_kwargs:
            assert all_kwargs["timeout"] == pytest.approx(custom_timeout), (
                f"Custom timeout {custom_timeout} not propagated, got {all_kwargs['timeout']}"
            )
        else:
            assert any(
                isinstance(a, (int, float)) and a == pytest.approx(custom_timeout) for a in all_args
            ), f"Custom timeout {custom_timeout} not found in wait_for_condition args: {all_args}"


# ---------------------------------------------------------------------------
# AC-3: No service_down variable or downtime detection
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU3-AC-3")
class TestNoDowntimeDetection:
    """Verify the helper does NOT use the old downtime-polling pattern."""

    def test_helper_source_has_no_service_down_variable(self) -> None:
        """The _assert_pod_recovery function must not reference 'service_down'."""
        import inspect

        import tests.e2e.test_service_failure_resilience_e2e as mod

        source = inspect.getsource(mod._assert_pod_recovery)
        assert "service_down" not in source, (
            "_assert_pod_recovery must NOT contain 'service_down' variable. "
            "The recovery-based pattern detects replacement via UID change, "
            "not downtime polling."
        )

    def test_helper_does_not_poll_http_health(self) -> None:
        """The helper must not make HTTP health checks to detect downtime."""
        import inspect

        import tests.e2e.test_service_failure_resilience_e2e as mod

        source = inspect.getsource(mod._assert_pod_recovery)
        assert "httpx.get" not in source, (
            "_assert_pod_recovery must NOT call httpx.get. "
            "Recovery is detected via UID change, not HTTP health polling."
        )
        assert "health/ready" not in source, (
            "_assert_pod_recovery must NOT reference health endpoints."
        )


# ---------------------------------------------------------------------------
# AC-4: Both MinIO and Polaris use the helper
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU3-AC-4")
class TestBothServicesUseHelper:
    """Verify the helper works for both MinIO and Polaris selectors."""

    @pytest.mark.parametrize(
        "label_selector,service_name",
        [
            ("app.kubernetes.io/name=minio", "MinIO"),
            ("app.kubernetes.io/component=polaris", "Polaris"),
        ],
        ids=["minio", "polaris"],
    )
    def test_helper_accepts_service_specific_selectors(
        self,
        label_selector: str,
        service_name: str,
    ) -> None:
        """Helper must work with both MinIO and Polaris label selectors."""
        helper = _import_helper()

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                side_effect=[f"{service_name}-orig", f"{service_name}-new"],
            ) as mock_get_uid,
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                return_value=True,
            ),
        ):
            orig, new, secs = helper(label_selector, service_name)

        assert orig == f"{service_name}-orig"
        assert new == f"{service_name}-new"
        assert orig != new

        # Verify _get_pod_uid received the correct selector
        first_call_args = mock_get_uid.call_args_list[0]
        assert label_selector in (first_call_args.args + tuple(first_call_args.kwargs.values())), (
            f"_get_pod_uid was not called with selector {label_selector!r}"
        )


# ---------------------------------------------------------------------------
# BC-1: Pod not found before deletion
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU3-BC-1")
class TestPodNotFoundBeforeDeletion:
    """Verify pytest.fail when pod does not exist before deletion."""

    def test_none_uid_raises_fail(self) -> None:
        """If _get_pod_uid returns None, helper must call pytest.fail."""
        helper = _import_helper()

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                return_value=None,
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                return_value=True,
            ),
            pytest.raises(pytest.fail.Exception) as exc_info,
        ):
            helper("app.kubernetes.io/name=minio", "MinIO")

        error_msg = str(exc_info.value).lower()
        # Error message must mention the service and the problem
        assert "minio" in error_msg or "pod" in error_msg or "not found" in error_msg, (
            f"pytest.fail message should mention the service or 'not found', got: {exc_info.value}"
        )

    def test_empty_string_uid_raises_fail(self) -> None:
        """An empty-string UID should be treated as 'not found'."""
        helper = _import_helper()

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                return_value="",
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                return_value=True,
            ),
            pytest.raises(pytest.fail.Exception),
        ):
            helper("app.kubernetes.io/name=minio", "MinIO")

    def test_no_kubectl_delete_when_pod_missing(self) -> None:
        """kubectl delete must NOT be called if pod is not found."""
        helper = _import_helper()

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                return_value=None,
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ) as mock_kubectl,
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                return_value=True,
            ),
        ):
            try:
                helper("app.kubernetes.io/name=minio", "MinIO")
            except pytest.fail.Exception:
                pass  # Expected

        mock_kubectl.assert_not_called()


# ---------------------------------------------------------------------------
# BC-2: Recovery timeout
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU3-BC-2")
class TestRecoveryTimeout:
    """Verify pytest.fail when pod recovery times out."""

    def test_wait_timeout_raises_fail(self) -> None:
        """If wait_for_condition returns False, helper must call pytest.fail."""
        helper = _import_helper()

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                side_effect=["uid-original", "uid-original"],  # UID never changes
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="pod deleted", stderr=""
                ),
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                return_value=False,  # Timeout!
            ),
            pytest.raises(pytest.fail.Exception) as exc_info,
        ):
            helper("app.kubernetes.io/name=minio", "MinIO")

        error_msg = str(exc_info.value).lower()
        assert "timeout" in error_msg or "recover" in error_msg or "30" in error_msg, (
            f"Timeout failure message should mention timeout/recovery, got: {exc_info.value}"
        )

    def test_timeout_message_includes_service_name(self) -> None:
        """Timeout error message must identify which service failed to recover."""
        helper = _import_helper()

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                side_effect=["uid-1", "uid-1"],
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                return_value=False,
            ),
            pytest.raises(pytest.fail.Exception) as exc_info,
        ):
            helper("app.kubernetes.io/component=polaris", "Polaris")

        error_msg = str(exc_info.value)
        assert "Polaris" in error_msg or "polaris" in error_msg, (
            f"Timeout message must name the service. Got: {exc_info.value}"
        )


# ---------------------------------------------------------------------------
# Return type structural tests (prevent hardcoded returns)
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU3-AC-1")
class TestReturnTypeStructure:
    """Verify the return value is a proper 3-tuple with correct semantics."""

    def test_return_is_three_tuple(self) -> None:
        """Return value must be a 3-element tuple (orig_uid, new_uid, seconds)."""
        helper = _import_helper()

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                side_effect=["uid-aaa", "uid-bbb"],
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                return_value=True,
            ),
        ):
            result = helper("app.kubernetes.io/name=minio", "MinIO")

        assert isinstance(result, tuple), f"Expected tuple, got {type(result).__name__}"
        assert len(result) == 3, f"Expected 3-tuple, got {len(result)}-tuple"

    def test_uids_are_strings(self) -> None:
        """Both UID elements must be strings."""
        helper = _import_helper()

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                side_effect=["str-uid-1", "str-uid-2"],
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                return_value=True,
            ),
        ):
            orig, new, _ = helper("app.kubernetes.io/name=minio", "MinIO")

        assert isinstance(orig, str), f"original_uid must be str, got {type(orig).__name__}"
        assert isinstance(new, str), f"new_uid must be str, got {type(new).__name__}"


# ---------------------------------------------------------------------------
# Anti-hardcoding: parameterized sentinels
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU3-AC-1")
@pytest.mark.parametrize(
    "orig_uid,new_uid",
    [
        ("aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa", "bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb"),
        ("12345678-abcd-efgh-ijkl-123456789012", "87654321-dcba-hgfe-lkji-210987654321"),
        ("x", "y"),
    ],
    ids=["uuid-style", "mixed-style", "minimal"],
)
def test_uid_passthrough_not_hardcoded(orig_uid: str, new_uid: str) -> None:
    """UIDs returned must match what _get_pod_uid provides -- prevents hardcoding."""
    helper = _import_helper()

    with (
        patch(
            "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
            side_effect=[orig_uid, new_uid],
        ),
        patch(
            "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ),
        patch(
            "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
            return_value=True,
        ),
    ):
        result_orig, result_new, _ = helper("app.kubernetes.io/name=minio", "MinIO")

    assert result_orig == orig_uid
    assert result_new == new_uid


# ---------------------------------------------------------------------------
# F-03: Callable verification — wait_for_condition receives a closure
# that actually checks UID change
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU3-AC-1")
class TestWaitCallableVerifiesUIDChange:
    """Verify the closure passed to wait_for_condition checks UID change."""

    def test_callable_returns_false_when_uid_unchanged(self) -> None:
        """The closure must return False when _get_pod_uid returns the same UID."""
        helper = _import_helper()
        captured_callable: list[Any] = []

        def capture_wait(fn: Any, **kwargs: Any) -> bool:
            captured_callable.append(fn)
            return True  # Let the helper proceed

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                side_effect=["uid-original", "uid-new"],
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                side_effect=capture_wait,
            ),
        ):
            helper("app.kubernetes.io/name=minio", "MinIO")

        assert len(captured_callable) == 1, "wait_for_condition must be called exactly once"
        condition_fn = captured_callable[0]

        # When _get_pod_uid returns same UID, closure should return False
        with patch(
            "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
            return_value="uid-original",
        ):
            assert condition_fn() is False, "Closure must return False when UID has not changed"

    def test_callable_returns_true_when_uid_changed_and_ready(self) -> None:
        """The closure must return True when UID changed AND pod is Ready."""
        helper = _import_helper()
        captured_callable: list[Any] = []

        def capture_wait(fn: Any, **kwargs: Any) -> bool:
            captured_callable.append(fn)
            return True

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                side_effect=["uid-original", "uid-new"],
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                side_effect=capture_wait,
            ),
        ):
            helper("app.kubernetes.io/name=minio", "MinIO")

        condition_fn = captured_callable[0]

        # When UID changed AND pod is ready, closure should return True
        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                return_value="uid-different",
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._check_pod_ready",
                return_value=True,
            ),
        ):
            assert condition_fn() is True, (
                "Closure must return True when UID changed and pod is Ready"
            )


# ---------------------------------------------------------------------------
# BC-1 extension: kubectl delete failure (F-04, F-06)
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU3-BC-1")
class TestKubectlDeleteFailure:
    """Verify clear error when kubectl delete command fails."""

    def test_delete_returncode_nonzero_raises(self) -> None:
        """AssertionError when kubectl delete returns non-zero exit code."""
        helper = _import_helper()

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                return_value="uid-exists",
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[],
                    returncode=1,
                    stdout="",
                    stderr="error: pod not found",
                ),
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                return_value=True,
            ),
            pytest.raises(AssertionError) as exc_info,
        ):
            helper("app.kubernetes.io/name=minio", "MinIO")

        error_msg = str(exc_info.value)
        assert "MinIO" in error_msg, (
            f"Delete failure message must name the service. Got: {error_msg}"
        )
        assert "error: pod not found" in error_msg, (
            f"Delete failure message must include stderr. Got: {error_msg}"
        )


# ---------------------------------------------------------------------------
# BC-3: Multiple pods match selector (F-01)
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU3-BC-3")
class TestMultiplePodsMatchSelector:
    """Verify helper handles multi-pod scenarios gracefully."""

    def test_uses_first_pod_uid_from_items(self) -> None:
        """When multiple pods exist, _get_pod_uid returns items[0] UID.

        The helper documents this as a single-replica assumption. Verify
        it still produces a valid result (no crash, correct UID tracking).
        """
        helper = _import_helper()

        # _get_pod_uid uses items[0] — returns first pod's UID regardless
        # of how many pods exist. We verify the helper works correctly
        # when this function returns deterministic results.
        first_pod_uid = "pod-0-uid-original"
        replacement_uid = "pod-0-uid-replacement"

        with (
            patch(
                "tests.e2e.test_service_failure_resilience_e2e._get_pod_uid",
                side_effect=[first_pod_uid, replacement_uid],
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="pod deleted", stderr=""
                ),
            ),
            patch(
                "tests.e2e.test_service_failure_resilience_e2e.wait_for_condition",
                return_value=True,
            ),
        ):
            orig, new, secs = helper("app.kubernetes.io/name=minio", "MinIO")

        assert orig == first_pod_uid, "Must track the first pod's UID"
        assert new == replacement_uid, "Must return the replacement pod's UID"
        assert orig != new, "UIDs must differ"

    def test_get_pod_uid_uses_items_zero(self) -> None:
        """Verify _get_pod_uid queries items[0] specifically (not items[*])."""
        import tests.e2e.test_service_failure_resilience_e2e as mod

        with patch(
            "tests.e2e.test_service_failure_resilience_e2e.run_kubectl",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="uid-first-pod", stderr=""
            ),
        ) as mock_kubectl:
            result = mod._get_pod_uid("app.kubernetes.io/name=minio")

        assert result == "uid-first-pod"
        # Verify the jsonpath uses items[0] (single pod selection)
        kubectl_args = mock_kubectl.call_args
        all_args_flat: list[str] = []
        for a in kubectl_args.args:
            if isinstance(a, list):
                all_args_flat.extend(str(x) for x in a)
            else:
                all_args_flat.append(str(a))
        jsonpath_args = [a for a in all_args_flat if "items[0]" in a]
        assert len(jsonpath_args) > 0, (
            "_get_pod_uid must use items[0] in jsonpath to select a single pod"
        )

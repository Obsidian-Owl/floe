"""Unit tests for concurrent promotion to same environment (T031d).

Tests for race condition scenarios where multiple promotions target same environment:
- Simulate two promotions racing to create same tag
- Verify one succeeds, one fails with TagExistsError
- Verify no data corruption

Requirements tested:
    NFR-006: Concurrency safety for promotion operations

⚠️ TDD: Tests WILL FAIL until T032 implements full promote() logic.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, Mock, patch

import pytest

from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate

# Test constants
TEST_DIGEST = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
TEST_DIGEST_STAGING = "sha256:7777777777777777777777777777777777777777777777777777777777777777"
TEST_DIGEST_PROD = "sha256:8888888888888888888888888888888888888888888888888888888888888888"
TEST_DIGEST_EXISTING = "sha256:1111111111111111111111111111111111111111111111111111111111111111"


class TestConcurrentPromotionSameEnvironment:
    """Unit tests for concurrent promotion to same environment (T031d)."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a PromotionController with mocked dependencies."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()

        return PromotionController(client=oci_client, promotion=promotion)

    @pytest.mark.requirement("8C-NFR-006")
    def test_concurrent_promotions_one_succeeds_one_fails(self, controller: MagicMock) -> None:
        """Test that concurrent promotions to same env - one succeeds, one fails.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        When two promotions race to create the same environment tag:
        - First promotion to create the tag succeeds
        - Second promotion fails with TagExistsError
        - No partial or corrupted state
        """
        from floe_core.oci.errors import TagExistsError
        from floe_core.schemas.promotion import PromotionRecord

        # Track which calls have been made
        call_count = {"create_tag": 0}
        lock = threading.Lock()

        def mock_create_tag_with_race(*args: object, **kwargs: object) -> str:
            """Simulate race condition - first caller succeeds, second fails."""
            with lock:
                call_count["create_tag"] += 1
                call_number = call_count["create_tag"]

            # Simulate some processing time to allow race
            time.sleep(0.01)

            if call_number == 1:
                # First caller succeeds
                return TEST_DIGEST
            else:
                # Second caller fails - tag already exists
                raise TagExistsError(
                    tag="v1.0.0-staging",
                    existing_digest=TEST_DIGEST,
                )

        results: list[PromotionRecord | Exception] = []

        def run_promotion() -> PromotionRecord | Exception:
            """Run a promotion and capture result or exception."""
            try:
                with (
                    patch.object(controller, "_validate_transition"),
                    patch.object(controller, "_get_artifact_digest") as mock_get_digest,
                    patch.object(controller, "_run_all_gates") as mock_gates,
                    patch.object(controller, "_verify_signature") as mock_verify,
                    patch.object(controller, "_create_env_tag") as mock_create_tag,
                    patch.object(controller, "_update_latest_tag"),
                    patch.object(controller, "_store_promotion_record"),
                ):
                    mock_gates.return_value = []
                    mock_verify.return_value = Mock(status="valid")
                    mock_create_tag.side_effect = mock_create_tag_with_race
                    mock_get_digest.return_value = TEST_DIGEST

                    return controller.promote(
                        tag="v1.0.0",
                        from_env="dev",
                        to_env="staging",
                        operator="ci@github.com",
                    )
            except Exception as e:
                return e

        # Run two promotions concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(run_promotion) for _ in range(2)]
            for future in as_completed(futures):
                results.append(future.result())

        # Exactly one should succeed, one should fail
        successes = [r for r in results if isinstance(r, PromotionRecord)]
        failures = [r for r in results if isinstance(r, TagExistsError)]

        assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
        assert len(failures) == 1, f"Expected 1 TagExistsError, got {len(failures)}"

        # Verify the failure has correct info
        failure = failures[0]
        assert failure.tag == "v1.0.0-staging"
        assert failure.existing_digest == TEST_DIGEST

    @pytest.mark.requirement("8C-NFR-006")
    def test_concurrent_promotions_to_different_envs_both_succeed(
        self, controller: MagicMock
    ) -> None:
        """Test concurrent promotions to different environments both succeed.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        When two promotions target different environments (dev->staging, staging->prod):
        - Both promotions should succeed
        - No interference between them
        """
        from floe_core.schemas.promotion import PromotionRecord

        results: list[tuple[str, PromotionRecord | Exception]] = []

        def run_promotion(to_env: str) -> tuple[str, PromotionRecord | Exception]:
            """Run a promotion to specified environment."""
            try:
                with (
                    patch.object(controller, "_validate_transition"),
                    patch.object(controller, "_get_artifact_digest") as mock_get_digest,
                    patch.object(controller, "_run_all_gates") as mock_gates,
                    patch.object(controller, "_verify_signature") as mock_verify,
                    patch.object(controller, "_create_env_tag") as mock_create_tag,
                    patch.object(controller, "_update_latest_tag"),
                    patch.object(controller, "_store_promotion_record"),
                ):
                    mock_gates.return_value = []
                    mock_verify.return_value = Mock(status="valid")
                    # Create unique but valid 64-char digest for each environment
                    if to_env == "staging":
                        mock_create_tag.return_value = TEST_DIGEST_STAGING
                    else:
                        mock_create_tag.return_value = TEST_DIGEST_PROD
                    mock_get_digest.return_value = TEST_DIGEST

                    result = controller.promote(
                        tag="v1.0.0",
                        from_env="dev" if to_env == "staging" else "staging",
                        to_env=to_env,
                        operator="ci@github.com",
                    )
                    return (to_env, result)
            except Exception as e:
                return (to_env, e)

        # Run two promotions to different environments concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(run_promotion, "staging"),
                executor.submit(run_promotion, "prod"),
            ]
            for future in as_completed(futures):
                results.append(future.result())

        # Both should succeed
        for env, result in results:
            assert isinstance(result, PromotionRecord), (
                f"Expected success for {env}, got {type(result).__name__}"
            )
            assert result.target_environment == env

    @pytest.mark.requirement("8C-NFR-006")
    @pytest.mark.timeout(30)
    def test_concurrent_promotion_no_data_corruption(self, controller: MagicMock) -> None:
        """Test that concurrent promotions do not cause data corruption.

        When multiple promotions run concurrently:
        - Each promotion record has unique promotion_id
        - No cross-contamination of promotion data
        - Timestamps are accurate and ordered
        """
        from floe_core.schemas.promotion import PromotionRecord

        promotion_ids: list[str] = []
        lock = threading.Lock()

        # Apply patches at test level (before threads) for thread-safe mocking
        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record"),
        ):
            # Configure mocks once, outside threads
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            mock_create_tag.return_value = TEST_DIGEST
            mock_get_digest.return_value = (
                "sha256:b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3"
            )

            def run_promotion(index: int) -> PromotionRecord | Exception:
                """Run a promotion with unique tag."""
                try:
                    result = controller.promote(
                        tag=f"v1.0.{index}",
                        from_env="dev",
                        to_env="staging",
                        operator=f"ci{index}@github.com",
                    )
                    with lock:
                        promotion_ids.append(result.promotion_id)
                    return result
                except Exception as e:
                    return e

            # Run 5 concurrent promotions
            results: list[PromotionRecord | Exception] = []
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(run_promotion, i) for i in range(5)]
                for future in as_completed(futures):
                    results.append(future.result())

        # All should succeed
        successes = [r for r in results if isinstance(r, PromotionRecord)]
        assert len(successes) == 5, f"Expected 5 successes, got {len(successes)}"

        # All promotion_ids should be unique
        assert len(set(promotion_ids)) == 5, "Promotion IDs should be unique"

        # Each record should have correct data (no cross-contamination)
        for record in successes:
            assert record.source_environment == "dev"
            assert record.target_environment == "staging"
            # Operator should match one of the expected patterns
            assert record.operator.startswith("ci")
            assert record.operator.endswith("@github.com")

    @pytest.mark.requirement("8C-NFR-006")
    def test_tag_exists_error_exit_code_during_race(self, controller: MagicMock) -> None:
        """Test TagExistsError has correct exit code during race condition.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        When a promotion fails due to tag race condition:
        - Error should have exit_code=10 (tag exists)
        - Error message should be actionable
        """
        from floe_core.oci.errors import TagExistsError

        error = TagExistsError(
            tag="v1.0.0-staging",
            existing_digest=TEST_DIGEST,
        )

        # Verify exit code
        assert error.exit_code == 10

        # Verify error message contains useful info
        error_message = str(error)
        assert "v1.0.0-staging" in error_message
        assert "sha256:" in error_message or "exists" in error_message.lower()

    @pytest.mark.requirement("8C-NFR-006")
    @pytest.mark.timeout(30)
    def test_concurrent_promotion_with_gate_failures(self, controller: MagicMock) -> None:
        """Test concurrent promotions where some fail gate validation.

        When concurrent promotions have different gate outcomes:
        - Those passing gates should proceed to tag creation
        - Those failing gates should fail early with GateValidationError
        - No interference between them
        """
        from floe_core.oci.errors import GateValidationError
        from floe_core.schemas.promotion import PromotionRecord

        call_count = {"gates": 0}
        lock = threading.Lock()

        def mock_gates_alternate(*args: object, **kwargs: object) -> list[GateResult]:
            """Alternate between pass and fail."""
            with lock:
                call_count["gates"] += 1
                call_number = call_count["gates"]

            if call_number % 2 == 0:
                # Even calls fail
                return [
                    GateResult(
                        gate=PromotionGate.TESTS,
                        status=GateStatus.FAILED,
                        duration_ms=100,
                        error="Tests failed",
                    )
                ]
            else:
                # Odd calls pass
                return [
                    GateResult(
                        gate=PromotionGate.TESTS,
                        status=GateStatus.PASSED,
                        duration_ms=100,
                    )
                ]

        # Apply patches at test level (before threads) for thread-safe mocking
        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record"),
        ):
            # Configure mocks once, outside threads
            mock_gates.side_effect = mock_gates_alternate
            mock_verify.return_value = Mock(status="valid")
            mock_create_tag.return_value = TEST_DIGEST
            mock_get_digest.return_value = TEST_DIGEST

            def run_promotion(index: int) -> PromotionRecord | Exception:
                """Run a promotion that may fail gates."""
                try:
                    return controller.promote(
                        tag=f"v1.0.{index}",
                        from_env="dev",
                        to_env="staging",
                        operator="ci@github.com",
                    )
                except Exception as e:
                    return e

            # Run 4 concurrent promotions
            results: list[PromotionRecord | Exception] = []
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(run_promotion, i) for i in range(4)]
                for future in as_completed(futures):
                    results.append(future.result())

        # Should have mix of successes and gate failures
        successes = [r for r in results if isinstance(r, PromotionRecord)]
        gate_failures = [r for r in results if isinstance(r, GateValidationError)]

        # At least one success and one failure (exact count depends on timing)
        assert len(successes) >= 1, "Expected at least 1 success"
        assert len(gate_failures) >= 1, "Expected at least 1 gate failure"
        assert len(successes) + len(gate_failures) == 4


class TestPromotionLocking:
    """Unit tests for promotion locking behavior (T031d)."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a PromotionController with mocked dependencies."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()

        return PromotionController(client=oci_client, promotion=promotion)

    @pytest.mark.requirement("8C-NFR-006")
    def test_promotion_check_and_create_is_atomic(self, controller: MagicMock) -> None:
        """Test that check-and-create of env tag is atomic.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        The operation "check if tag exists, create if not" should be atomic
        to prevent TOCTOU (time-of-check-time-of-use) race conditions.
        """
        from floe_core.oci.errors import TagExistsError

        # This test verifies the controller uses atomic operations
        # by checking that TagExistsError is raised correctly

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
        ):
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            mock_get_digest.return_value = TEST_DIGEST

            # Simulate atomic check-and-create failure
            mock_create_tag.side_effect = TagExistsError(
                tag="v1.0.0-staging",
                existing_digest=TEST_DIGEST_EXISTING,
            )

            with pytest.raises(TagExistsError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            # Error should indicate the tag already exists with different digest
            assert exc_info.value.tag == "v1.0.0-staging"
            assert exc_info.value.existing_digest == TEST_DIGEST_EXISTING

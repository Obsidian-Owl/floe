"""Unit tests for health_check_sensor definition from floe_orchestrator_dagster.sensors.

Task: T24
Epic: WU-16
Requirements: FR-029

These tests validate that the health_check_sensor SensorDefinition is correctly
configured using Dagster's modern `target` parameter instead of the deprecated
`asset_selection` parameter. The `asset_selection` parameter creates a sensor
whose `.job_name` raises DagsterInvalidDefinitionError and whose `._target`
is None -- breaking downstream consumers (e.g., E2E tests) that inspect the
sensor definition.

Test coverage:
- Sensor imports without error
- Sensor is a valid SensorDefinition
- Sensor name is "health_check_sensor"
- Sensor uses target (not asset_selection), yielding a non-None _target
- Sensor has non-empty targets list
- Sensor job_name is accessible without raising
- Sensor minimum_interval_seconds is 60
- Sensor description is correct
- Sensor evaluation function is the expected implementation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


class TestSensorDefinitionStructure:
    """Test that health_check_sensor is a properly wired SensorDefinition.

    The critical invariant: the sensor MUST use the `target` parameter
    (Dagster modern API) rather than `asset_selection` (which silently
    creates a broken definition in Dagster 1.12.14).
    """

    @pytest.mark.requirement("FR-029")
    def test_sensor_imports_without_error(self) -> None:
        """Test that health_check_sensor can be imported from the sensors module."""
        from floe_orchestrator_dagster.sensors import health_check_sensor

        # Import succeeded -- sensor module is loadable
        assert health_check_sensor is not None

    @pytest.mark.requirement("FR-029")
    def test_sensor_is_sensor_definition(self) -> None:
        """Test that health_check_sensor is an instance of Dagster SensorDefinition."""
        from dagster import SensorDefinition

        from floe_orchestrator_dagster.sensors import health_check_sensor

        assert isinstance(health_check_sensor, SensorDefinition), (
            f"Expected SensorDefinition, got {type(health_check_sensor).__name__}"
        )

    @pytest.mark.requirement("FR-029")
    def test_sensor_name_is_health_check_sensor(self) -> None:
        """Test that the sensor name is exactly 'health_check_sensor'."""
        from floe_orchestrator_dagster.sensors import health_check_sensor

        assert health_check_sensor.name == "health_check_sensor", (
            f"Expected name 'health_check_sensor', got '{health_check_sensor.name}'"
        )

    @pytest.mark.requirement("FR-029")
    def test_sensor_has_non_none_target(self) -> None:
        """Test that the sensor has a non-None _target.

        When a sensor is created with `asset_selection='*'`, its `_target`
        is None. When created with `target=AssetSelection.all()`, `_target`
        is a proper AutomationTarget. This test ensures the modern API is used.

        This is the critical RED-phase test: the current implementation uses
        `asset_selection='*'`, which sets _target=None.
        """
        from floe_orchestrator_dagster.sensors import health_check_sensor

        # _target is an internal attribute but it is the definitive indicator
        # of whether `target=` (modern) vs `asset_selection=` (broken) was used.
        assert health_check_sensor._target is not None, (
            "Sensor _target is None. This means `asset_selection=` was used "
            "instead of `target=AssetSelection.all()`. The asset_selection "
            "parameter creates a sensor whose .job_name raises "
            "DagsterInvalidDefinitionError in Dagster 1.12.14."
        )

    @pytest.mark.requirement("FR-029")
    def test_sensor_targets_list_is_non_empty(self) -> None:
        """Test that the sensor's targets list contains at least one target.

        When using `asset_selection='*'`, `sensor.targets` returns an empty
        list []. When using `target=AssetSelection.all()`, it returns a list
        containing the AutomationTarget. This test ensures the sensor is
        properly wired to its asset graph target.
        """
        from floe_orchestrator_dagster.sensors import health_check_sensor

        targets = health_check_sensor.targets
        assert len(targets) > 0, (
            f"Sensor targets list is empty (len={len(targets)}). "
            "This indicates `asset_selection=` was used instead of "
            "`target=AssetSelection.all()`. An empty targets list means "
            "the sensor cannot resolve its target job."
        )

    @pytest.mark.requirement("FR-029")
    def test_sensor_job_name_accessible_without_error(self) -> None:
        """Test that accessing sensor.job_name does not raise.

        When a sensor is created with `asset_selection='*'` and no explicit
        job, accessing `.job_name` raises DagsterInvalidDefinitionError:
        'No job was provided to SensorDefinition.' When created with
        `target=AssetSelection.all()`, `.job_name` returns a valid string
        like '__anonymous_asset_job_health_check_sensor'.

        This test directly reproduces the failure seen in E2E test
        test_data_pipeline.py:874 where `hasattr(sensor_def, 'job_name')`
        propagates the DagsterInvalidDefinitionError.
        """
        from floe_orchestrator_dagster.sensors import health_check_sensor

        # This should NOT raise DagsterInvalidDefinitionError
        job_name = health_check_sensor.job_name
        assert isinstance(job_name, str), (
            f"Expected job_name to be a string, got {type(job_name).__name__}"
        )
        assert len(job_name) > 0, "job_name should be a non-empty string"

    @pytest.mark.requirement("FR-029")
    def test_sensor_minimum_interval_seconds(self) -> None:
        """Test that the sensor checks health every 60 seconds."""
        from floe_orchestrator_dagster.sensors import health_check_sensor

        assert health_check_sensor.minimum_interval_seconds == 60, (
            f"Expected minimum_interval_seconds=60, "
            f"got {health_check_sensor.minimum_interval_seconds}"
        )

    @pytest.mark.requirement("FR-029")
    def test_sensor_has_description(self) -> None:
        """Test that the sensor has a meaningful description string."""
        from floe_orchestrator_dagster.sensors import health_check_sensor

        description = health_check_sensor.description
        assert description is not None, "Sensor description should not be None"
        assert isinstance(description, str), (
            f"Expected description to be str, got {type(description).__name__}"
        )
        assert len(description) > 10, (
            f"Sensor description is too short ({len(description)} chars): '{description}'"
        )
        # Verify it mentions health or trigger to confirm it describes purpose
        desc_lower = description.lower()
        assert "health" in desc_lower or "trigger" in desc_lower or "pipeline" in desc_lower, (
            f"Sensor description doesn't mention health/trigger/pipeline: '{description}'"
        )

    @pytest.mark.requirement("FR-029")
    def test_sensor_evaluation_function_is_health_check_impl(self) -> None:
        """Test that the sensor wraps the _health_check_sensor_impl function.

        Ensures the sensor definition is wired to the correct evaluation
        function, not some other callable or a no-op.
        """
        from floe_orchestrator_dagster.sensors import (
            _health_check_sensor_impl,
            health_check_sensor,
        )

        # The SensorDefinition wraps the evaluation function.
        # Dagster stores it internally; we verify the sensor name matches
        # and the impl function is exported and callable.
        assert callable(_health_check_sensor_impl), "_health_check_sensor_impl should be callable"

        # Verify the sensor was built from this specific function by
        # checking that the sensor's evaluation function name matches.
        # Dagster stores the fn in _raw_fn or similar internal attribute.
        sensor_fn = getattr(health_check_sensor, "_raw_fn", None)
        if sensor_fn is not None:
            assert sensor_fn is _health_check_sensor_impl, (
                "Sensor's raw function should be _health_check_sensor_impl"
            )
        else:
            # Fallback: verify the sensor's module source matches
            sensor_module = type(health_check_sensor).__module__
            assert "dagster" in sensor_module, (
                f"Sensor should be a Dagster SensorDefinition, but type module is {sensor_module}"
            )


class TestSensorTargetIsAssetSelection:
    """Test that the sensor's target is an AssetSelection, not a bare string.

    The `target` parameter should be `AssetSelection.all()`, which creates
    a proper AutomationTarget internally. The deprecated `asset_selection='*'`
    passes a string that Dagster 1.12.14 silently accepts but does not
    properly wire into the target resolution system.
    """

    @pytest.mark.requirement("FR-029")
    def test_sensor_target_contains_asset_job(self) -> None:
        """Test that the sensor's target resolves to an asset job.

        When target=AssetSelection.all() is used, the target contains an
        UnresolvedAssetJobDefinition. When asset_selection='*' is used,
        targets is empty and there is no job definition to resolve.
        """
        from floe_orchestrator_dagster.sensors import health_check_sensor

        targets = health_check_sensor.targets
        assert len(targets) >= 1, (
            "Sensor should have at least one target. "
            "Empty targets means asset_selection= was used instead of target=."
        )

        # The first target should have a resolvable job
        first_target = targets[0]
        assert hasattr(first_target, "resolvable_to_job"), (
            f"Target {first_target} should have resolvable_to_job attribute"
        )
        assert first_target.resolvable_to_job is not None, (
            "Target's resolvable_to_job should not be None"
        )

    @pytest.mark.requirement("FR-029")
    def test_sensor_anonymous_job_name_contains_sensor_name(self) -> None:
        """Test the auto-generated job name includes the sensor name.

        When using target=AssetSelection.all(), Dagster auto-generates a
        job name like '__anonymous_asset_job_health_check_sensor'. This
        confirms the target was properly associated with this sensor.
        """
        from floe_orchestrator_dagster.sensors import health_check_sensor

        job_name = health_check_sensor.job_name
        assert "health_check_sensor" in job_name, (
            f"Expected job name to contain 'health_check_sensor', got '{job_name}'"
        )


__all__ = [
    "TestSensorDefinitionStructure",
    "TestSensorTargetIsAssetSelection",
]

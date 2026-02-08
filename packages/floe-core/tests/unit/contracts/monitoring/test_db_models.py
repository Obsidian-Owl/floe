"""Unit tests for SQLAlchemy async models.

Tasks: T052 (Epic 3D)
Requirements: FR-001, FR-002, FR-031, FR-032
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect as sa_inspect

from floe_core.contracts.monitoring.db.models import (
    AlertDedupStateModel,
    Base,
    ContractCheckResultModel,
    ContractDailyAggregateModel,
    ContractSLAStatusModel,
    ContractViolationModel,
    RegisteredContractModel,
)


@pytest.mark.requirement("3D-FR-031")
def test_check_result_table_name() -> None:
    """Test ContractCheckResultModel has correct table name."""
    assert ContractCheckResultModel.__tablename__ == "contract_check_results"


@pytest.mark.requirement("3D-FR-031")
def test_check_result_columns() -> None:
    """Test ContractCheckResultModel has all required columns."""
    mapper = sa_inspect(ContractCheckResultModel)
    column_names = {col.key for col in mapper.columns}

    assert "id" in column_names
    assert "contract_name" in column_names
    assert "check_type" in column_names
    assert "status" in column_names
    assert "duration_seconds" in column_names
    assert "timestamp" in column_names
    assert "details" in column_names


@pytest.mark.requirement("3D-FR-031")
def test_check_result_indexes() -> None:
    """Test ContractCheckResultModel has required indexes."""
    indexes = ContractCheckResultModel.__table__.indexes
    index_names = {idx.name for idx in indexes}

    assert "ix_check_results_contract_time" in index_names
    assert "ix_check_results_type_time" in index_names


@pytest.mark.requirement("3D-FR-031")
def test_check_result_instantiation() -> None:
    """Test ContractCheckResultModel can be instantiated with correct types."""
    now = datetime.now(timezone.utc)
    test_id = uuid.uuid4()
    model = ContractCheckResultModel(
        id=test_id,
        contract_name="test_contract",
        check_type="FRESHNESS",
        status="PASS",
        duration_seconds=1.234,
        timestamp=now,
        details={"key": "value"},
    )

    assert model.id == test_id
    assert model.contract_name == "test_contract"
    assert model.check_type == "FRESHNESS"
    assert model.status == "PASS"
    assert model.duration_seconds == 1.234
    assert model.timestamp == now
    assert model.details == {"key": "value"}


@pytest.mark.requirement("3D-FR-031")
def test_violation_table_name() -> None:
    """Test ContractViolationModel has correct table name."""
    assert ContractViolationModel.__tablename__ == "contract_violations"


@pytest.mark.requirement("3D-FR-031")
def test_violation_columns() -> None:
    """Test ContractViolationModel has all required columns."""
    mapper = sa_inspect(ContractViolationModel)
    column_names = {col.key for col in mapper.columns}

    assert "id" in column_names
    assert "contract_name" in column_names
    assert "contract_version" in column_names
    assert "violation_type" in column_names
    assert "severity" in column_names
    assert "message" in column_names
    assert "element" in column_names
    assert "expected_value" in column_names
    assert "actual_value" in column_names
    assert "timestamp" in column_names
    assert "affected_consumers" in column_names
    assert "check_duration_seconds" in column_names
    # metadata_ is the Python attribute name, but column name is "metadata"
    assert "metadata" in column_names


@pytest.mark.requirement("3D-FR-031")
def test_violation_indexes() -> None:
    """Test ContractViolationModel has required indexes."""
    indexes = ContractViolationModel.__table__.indexes
    index_names = {idx.name for idx in indexes}

    assert "ix_violations_contract_time" in index_names
    assert "ix_violations_severity_time" in index_names
    assert "ix_violations_type_contract" in index_names


@pytest.mark.requirement("3D-FR-031")
def test_violation_optional_fields() -> None:
    """Test ContractViolationModel optional fields work correctly."""
    now = datetime.now(timezone.utc)
    model = ContractViolationModel(
        contract_name="test_contract",
        contract_version="1.0.0",
        violation_type="SCHEMA_DRIFT",
        severity="ERROR",
        message="Test violation",
        element=None,  # Optional
        expected_value=None,  # Optional
        actual_value=None,  # Optional
        timestamp=now,
        affected_consumers=["consumer1"],
        check_duration_seconds=0.5,
        metadata_={"env": "test"},
    )

    assert model.element is None
    assert model.expected_value is None
    assert model.actual_value is None


@pytest.mark.requirement("3D-FR-031")
def test_sla_status_table_name() -> None:
    """Test ContractSLAStatusModel has correct table name."""
    assert ContractSLAStatusModel.__tablename__ == "contract_sla_status"


@pytest.mark.requirement("3D-FR-031")
def test_sla_status_columns() -> None:
    """Test ContractSLAStatusModel has all required columns."""
    mapper = sa_inspect(ContractSLAStatusModel)
    column_names = {col.key for col in mapper.columns}

    assert "id" in column_names
    assert "contract_name" in column_names
    assert "check_type" in column_names
    assert "current_status" in column_names
    assert "compliance_pct" in column_names
    assert "last_violation_at" in column_names
    assert "consecutive_violations" in column_names
    assert "updated_at" in column_names


@pytest.mark.requirement("3D-FR-031")
def test_sla_status_unique_constraint() -> None:
    """Test ContractSLAStatusModel has unique constraint on contract_name."""
    mapper = sa_inspect(ContractSLAStatusModel)
    contract_name_col = mapper.columns["contract_name"]

    assert contract_name_col.unique is True


@pytest.mark.requirement("3D-FR-031")
def test_daily_aggregate_table_name() -> None:
    """Test ContractDailyAggregateModel has correct table name."""
    assert ContractDailyAggregateModel.__tablename__ == "contract_daily_aggregates"


@pytest.mark.requirement("3D-FR-031")
def test_daily_aggregate_columns() -> None:
    """Test ContractDailyAggregateModel has all required columns."""
    mapper = sa_inspect(ContractDailyAggregateModel)
    column_names = {col.key for col in mapper.columns}

    assert "id" in column_names
    assert "contract_name" in column_names
    assert "check_type" in column_names
    assert "date" in column_names
    assert "total_checks" in column_names
    assert "passed_checks" in column_names
    assert "failed_checks" in column_names
    assert "error_checks" in column_names
    assert "avg_duration_seconds" in column_names
    assert "violation_count" in column_names


@pytest.mark.requirement("3D-FR-031")
def test_daily_aggregate_indexes() -> None:
    """Test ContractDailyAggregateModel has required indexes."""
    indexes = ContractDailyAggregateModel.__table__.indexes
    index_names = {idx.name for idx in indexes}

    assert "ix_daily_agg_contract_date" in index_names
    assert "ix_daily_agg_type_date" in index_names


@pytest.mark.requirement("3D-FR-031")
def test_daily_aggregate_defaults() -> None:
    """Test ContractDailyAggregateModel has correct default values in column definition.

    Note: Defaults only apply when inserting into database, not on instantiation.
    """
    mapper = sa_inspect(ContractDailyAggregateModel)

    # Check that columns have the correct default values defined
    assert mapper.columns["total_checks"].default.arg == 0
    assert mapper.columns["passed_checks"].default.arg == 0
    assert mapper.columns["failed_checks"].default.arg == 0
    assert mapper.columns["error_checks"].default.arg == 0
    assert mapper.columns["avg_duration_seconds"].default.arg == 0.0
    assert mapper.columns["violation_count"].default.arg == 0


@pytest.mark.requirement("3D-FR-032")
def test_registered_contract_table_name() -> None:
    """Test RegisteredContractModel has correct table name."""
    assert RegisteredContractModel.__tablename__ == "registered_contracts"


@pytest.mark.requirement("3D-FR-032")
def test_registered_contract_columns() -> None:
    """Test RegisteredContractModel has all required columns."""
    mapper = sa_inspect(RegisteredContractModel)
    column_names = {col.key for col in mapper.columns}

    assert "id" in column_names
    assert "contract_name" in column_names
    assert "contract_version" in column_names
    assert "contract_data" in column_names
    assert "connection_config" in column_names
    assert "monitoring_overrides" in column_names
    assert "registered_at" in column_names
    assert "last_check_times" in column_names
    assert "active" in column_names


@pytest.mark.requirement("3D-FR-032")
def test_registered_contract_unique_constraint() -> None:
    """Test RegisteredContractModel has unique constraint on contract_name."""
    mapper = sa_inspect(RegisteredContractModel)
    contract_name_col = mapper.columns["contract_name"]

    assert contract_name_col.unique is True


@pytest.mark.requirement("3D-FR-032")
def test_registered_contract_defaults() -> None:
    """Test RegisteredContractModel has correct default values in column definition.

    Note: Defaults only apply when inserting into database, not on instantiation.
    """
    mapper = sa_inspect(RegisteredContractModel)

    # Check that columns have the correct default values defined
    assert callable(mapper.columns["last_check_times"].default.arg)
    assert mapper.columns["last_check_times"].default.arg.__name__ == "dict"
    assert mapper.columns["active"].default.arg is True
    # monitoring_overrides should be nullable with no default
    assert mapper.columns["monitoring_overrides"].nullable is True


@pytest.mark.requirement("3D-FR-031")
def test_alert_dedup_table_name() -> None:
    """Test AlertDedupStateModel has correct table name."""
    assert AlertDedupStateModel.__tablename__ == "alert_dedup_state"


@pytest.mark.requirement("3D-FR-031")
def test_alert_dedup_columns() -> None:
    """Test AlertDedupStateModel has all required columns."""
    mapper = sa_inspect(AlertDedupStateModel)
    column_names = {col.key for col in mapper.columns}

    assert "id" in column_names
    assert "contract_name" in column_names
    assert "violation_type" in column_names
    assert "last_alerted_at" in column_names


@pytest.mark.requirement("3D-FR-031")
def test_alert_dedup_indexes() -> None:
    """Test AlertDedupStateModel has required indexes."""
    indexes = AlertDedupStateModel.__table__.indexes
    index_names = {idx.name for idx in indexes}

    assert "ix_dedup_contract_type" in index_names


@pytest.mark.requirement("3D-FR-031")
def test_jsonb_defaults_empty_dict() -> None:
    """Test JSONB columns have dict defaults defined in schema.

    Note: Defaults only apply when inserting into database, not on instantiation.
    """
    # ContractCheckResultModel
    check_mapper = sa_inspect(ContractCheckResultModel)
    assert callable(check_mapper.columns["details"].default.arg)
    assert check_mapper.columns["details"].default.arg.__name__ == "dict"

    # ContractViolationModel - metadata is reserved name, use iteration
    violation_mapper = sa_inspect(ContractViolationModel)
    metadata_col = [c for c in violation_mapper.columns if c.key == "metadata"][0]
    assert callable(metadata_col.default.arg)
    assert metadata_col.default.arg.__name__ == "dict"

    # RegisteredContractModel
    registered_mapper = sa_inspect(RegisteredContractModel)
    assert callable(registered_mapper.columns["last_check_times"].default.arg)
    assert registered_mapper.columns["last_check_times"].default.arg.__name__ == "dict"


@pytest.mark.requirement("3D-FR-031")
def test_jsonb_defaults_empty_list() -> None:
    """Test JSONB columns have list defaults defined in schema.

    Note: Defaults only apply when inserting into database, not on instantiation.
    """
    violation_mapper = sa_inspect(ContractViolationModel)
    assert callable(violation_mapper.columns["affected_consumers"].default.arg)
    assert violation_mapper.columns["affected_consumers"].default.arg.__name__ == "list"


@pytest.mark.requirement("3D-FR-031")
def test_uuid_primary_key_generation() -> None:
    """Test UUID primary keys have default generator configured."""
    mapper = sa_inspect(ContractCheckResultModel)
    id_column = mapper.columns["id"]

    # Check that UUID column has default callable (uuid.uuid4)
    assert id_column.default is not None
    assert callable(id_column.default.arg)
    assert id_column.default.arg.__name__ == "uuid4"

    # The default function in SQLAlchemy wrapped context expects a ctx parameter
    # But we can verify it's the right function by checking the name and that
    # uuid.uuid4 produces UUIDs when called directly
    uuid1 = uuid.uuid4()
    uuid2 = uuid.uuid4()
    assert isinstance(uuid1, uuid.UUID)
    assert isinstance(uuid2, uuid.UUID)
    assert uuid1 != uuid2


@pytest.mark.requirement("3D-FR-031")
def test_base_class_inheritance() -> None:
    """Test all models inherit from Base."""
    assert issubclass(ContractCheckResultModel, Base)
    assert issubclass(ContractViolationModel, Base)
    assert issubclass(ContractSLAStatusModel, Base)
    assert issubclass(ContractDailyAggregateModel, Base)
    assert issubclass(RegisteredContractModel, Base)
    assert issubclass(AlertDedupStateModel, Base)


@pytest.mark.requirement("3D-FR-031")
def test_column_types_match_pydantic_models() -> None:
    """Test SQLAlchemy column types are compatible with Pydantic models.

    Validates that field types in SQLAlchemy models match the corresponding
    Pydantic models from violations.py and config.py.
    """
    # ContractCheckResultModel vs CheckResult
    check_mapper = sa_inspect(ContractCheckResultModel)
    assert "UUID" in str(check_mapper.columns["id"].type)
    assert str(check_mapper.columns["contract_name"].type) == "VARCHAR(255)"
    assert str(check_mapper.columns["check_type"].type) == "VARCHAR(50)"
    assert str(check_mapper.columns["status"].type) == "VARCHAR(20)"
    assert str(check_mapper.columns["duration_seconds"].type) == "FLOAT"
    # SQLAlchemy uses DATETIME for DateTime columns
    assert "DATETIME" in str(check_mapper.columns["timestamp"].type)
    assert check_mapper.columns["timestamp"].type.timezone is True
    assert str(check_mapper.columns["details"].type) == "JSONB"

    # ContractViolationModel vs ContractViolationEvent
    violation_mapper = sa_inspect(ContractViolationModel)
    assert str(violation_mapper.columns["contract_version"].type) == "VARCHAR(50)"
    assert str(violation_mapper.columns["severity"].type) == "VARCHAR(20)"
    assert str(violation_mapper.columns["message"].type) == "TEXT"
    assert str(violation_mapper.columns["affected_consumers"].type) == "JSONB"
    # metadata is reserved name, use iteration
    metadata_col = [c for c in violation_mapper.columns if c.key == "metadata"][0]
    assert str(metadata_col.type) == "JSONB"

    # RegisteredContractModel vs RegisteredContract
    registered_mapper = sa_inspect(RegisteredContractModel)
    assert str(registered_mapper.columns["contract_data"].type) == "JSONB"
    assert str(registered_mapper.columns["connection_config"].type) == "JSONB"
    assert str(registered_mapper.columns["active"].type) == "BOOLEAN"

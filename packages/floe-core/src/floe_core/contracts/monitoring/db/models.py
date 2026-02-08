"""SQLAlchemy async models for contract monitoring persistence.

Tasks: T056 (Epic 3D)
Requirements: FR-001, FR-002, FR-031, FR-032
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all monitoring models."""

    pass


class ContractCheckResultModel(Base):
    """Persisted check result.

    Maps to CheckResult Pydantic model from violations.py.
    Stores individual check executions with status and duration.
    """

    __tablename__ = "contract_check_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    check_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_check_results_contract_time", "contract_name", "timestamp"),
        Index("ix_check_results_type_time", "check_type", "timestamp"),
    )


class ContractViolationModel(Base):
    """Persisted violation event.

    Maps to ContractViolationEvent Pydantic model from violations.py.
    Stores contract violations with severity and affected consumers.
    """

    __tablename__ = "contract_violations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    contract_version: Mapped[str] = mapped_column(String(50), nullable=False)
    violation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    element: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    affected_consumers: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    check_duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    metadata_: Mapped[dict[str, str]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )  # metadata is reserved

    __table_args__ = (
        Index("ix_violations_contract_time", "contract_name", "timestamp"),
        Index("ix_violations_severity_time", "severity", "timestamp"),
        Index("ix_violations_type_contract", "violation_type", "contract_name"),
    )


class ContractSLAStatusModel(Base):
    """Current SLA status per contract.

    Tracks compliance percentage and violation history.
    One row per contract, updated on each check.
    """

    __tablename__ = "contract_sla_status"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    check_type: Mapped[str] = mapped_column(String(50), nullable=False)
    current_status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # compliant/breached/degraded
    compliance_pct: Mapped[float] = mapped_column(Float, nullable=False)
    last_violation_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consecutive_violations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ContractDailyAggregateModel(Base):
    """Daily aggregated metrics per contract.

    Stores rollup of check results for efficient historical queries.
    One row per contract per day per check type.
    """

    __tablename__ = "contract_daily_aggregates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    check_type: Mapped[str] = mapped_column(String(50), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_checks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_checks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_checks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_checks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    violation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_daily_agg_contract_date", "contract_name", "date", unique=True),
        Index("ix_daily_agg_type_date", "check_type", "date"),
    )


class RegisteredContractModel(Base):
    """Persisted registered contract state.

    Maps to RegisteredContract Pydantic model from config.py.
    Stores contract definition and monitoring configuration.
    """

    __tablename__ = "registered_contracts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    contract_version: Mapped[str] = mapped_column(String(50), nullable=False)
    contract_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    connection_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    monitoring_overrides: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_check_times: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AlertDedupStateModel(Base):
    """Alert deduplication state per contract+violation_type.

    Prevents duplicate alerts within configured window.
    One row per contract per violation type.
    """

    __tablename__ = "alert_dedup_state"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_name: Mapped[str] = mapped_column(String(255), nullable=False)
    violation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    last_alerted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_dedup_contract_type", "contract_name", "violation_type", unique=True),
    )

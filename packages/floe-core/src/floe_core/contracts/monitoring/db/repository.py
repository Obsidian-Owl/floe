"""Data access repository for contract monitoring persistence.

Provides async CRUD operations for check results, violations, SLA status,
and daily aggregates backed by SQLAlchemy async sessions.

Tasks: T057 (Epic 3D)
Requirements: FR-001, FR-002, FR-031, FR-032
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine.cursor import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from floe_core.contracts.monitoring.db.models import (
    ContractCheckResultModel,
    ContractDailyAggregateModel,
    ContractSLAStatusModel,
    ContractViolationModel,
    RegisteredContractModel,
)

logger = structlog.get_logger(__name__)


class MonitoringRepository:
    """Async data access repository for monitoring persistence.

    All methods accept an AsyncSession and perform database operations
    within that session. Transaction management (commit/rollback) is the
    caller's responsibility.

    Args:
        session: SQLAlchemy async session for database operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._log = logger.bind(component="monitoring_repository")

    async def save_check_result(self, result: dict[str, Any]) -> uuid.UUID:
        """Persist a check result.

        Args:
            result: Dict with keys matching ContractCheckResultModel columns.
                Required: contract_name, check_type, status, duration_seconds,
                         timestamp, details.

        Returns:
            UUID of the saved record.
        """
        record_id = result.get("id", uuid.uuid4())
        if isinstance(record_id, str):
            record_id = uuid.UUID(record_id)

        model = ContractCheckResultModel(
            id=record_id,
            contract_name=result["contract_name"],
            check_type=result["check_type"],
            status=result["status"],
            duration_seconds=result["duration_seconds"],
            timestamp=result["timestamp"],
            details=result.get("details", {}),
        )
        self._session.add(model)
        await self._session.flush()
        self._log.debug("check_result_saved", contract_name=result["contract_name"])
        return uuid.UUID(str(record_id))

    async def save_violation(self, violation: dict[str, Any]) -> uuid.UUID:
        """Persist a violation event.

        Args:
            violation: Dict with keys matching ContractViolationModel columns.

        Returns:
            UUID of the saved record.
        """
        record_id = uuid.uuid4()
        model = ContractViolationModel(
            id=record_id,
            contract_name=violation["contract_name"],
            contract_version=violation["contract_version"],
            violation_type=violation["violation_type"],
            severity=violation["severity"],
            message=violation["message"],
            element=violation.get("element"),
            expected_value=violation.get("expected_value"),
            actual_value=violation.get("actual_value"),
            timestamp=violation["timestamp"],
            affected_consumers=violation.get("affected_consumers", []),
            check_duration_seconds=violation["check_duration_seconds"],
            metadata_=violation.get("metadata", {}),
        )
        self._session.add(model)
        await self._session.flush()
        self._log.debug("violation_saved", contract_name=violation["contract_name"])
        return record_id

    async def upsert_sla_status(
        self,
        contract_name: str,
        check_type: str,
        current_status: str,
        compliance_pct: float,
        last_violation_at: datetime | None = None,
        consecutive_violations: int = 0,
    ) -> None:
        """Upsert SLA status for a contract.

        Uses PostgreSQL INSERT ... ON CONFLICT to atomically upsert.

        Args:
            contract_name: Contract to update.
            check_type: Check type for this SLA status.
            current_status: One of "compliant", "breached", "degraded".
            compliance_pct: Current compliance percentage (0-100).
            last_violation_at: When the last violation occurred.
            consecutive_violations: Current consecutive violation count.
        """
        now = datetime.now(tz=timezone.utc)
        stmt = pg_insert(ContractSLAStatusModel).values(
            id=uuid.uuid4(),
            contract_name=contract_name,
            check_type=check_type,
            current_status=current_status,
            compliance_pct=compliance_pct,
            last_violation_at=last_violation_at,
            consecutive_violations=consecutive_violations,
            updated_at=now,
        ).on_conflict_do_update(
            index_elements=["contract_name"],
            set_={
                "check_type": check_type,
                "current_status": current_status,
                "compliance_pct": compliance_pct,
                "last_violation_at": last_violation_at,
                "consecutive_violations": consecutive_violations,
                "updated_at": now,
            },
        )
        await self._session.execute(stmt)
        self._log.debug("sla_status_upserted", contract_name=contract_name)

    async def get_violations(
        self,
        contract_name: str | None = None,
        severity: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query violations with optional filters.

        Args:
            contract_name: Filter by contract name.
            severity: Filter by severity level.
            since: Return violations after this timestamp.
            limit: Maximum number of results.

        Returns:
            List of violation dicts.
        """
        stmt = select(ContractViolationModel).order_by(
            ContractViolationModel.timestamp.desc()
        ).limit(limit)

        if contract_name is not None:
            stmt = stmt.where(ContractViolationModel.contract_name == contract_name)
        if severity is not None:
            stmt = stmt.where(ContractViolationModel.severity == severity)
        if since is not None:
            stmt = stmt.where(ContractViolationModel.timestamp >= since)

        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "id": str(row.id),
                "contract_name": row.contract_name,
                "contract_version": row.contract_version,
                "violation_type": row.violation_type,
                "severity": row.severity,
                "message": row.message,
                "element": row.element,
                "expected_value": row.expected_value,
                "actual_value": row.actual_value,
                "timestamp": row.timestamp,
                "affected_consumers": row.affected_consumers,
                "check_duration_seconds": row.check_duration_seconds,
                "metadata": row.metadata_,
            }
            for row in rows
        ]

    async def get_daily_aggregates(
        self,
        contract_name: str,
        check_type: str | None = None,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get daily aggregated metrics for a contract.

        Args:
            contract_name: Contract to query.
            check_type: Optional check type filter.
            since: Return aggregates after this date.

        Returns:
            List of daily aggregate dicts.
        """
        stmt = select(ContractDailyAggregateModel).where(
            ContractDailyAggregateModel.contract_name == contract_name
        ).order_by(ContractDailyAggregateModel.date.desc())

        if check_type is not None:
            stmt = stmt.where(ContractDailyAggregateModel.check_type == check_type)
        if since is not None:
            stmt = stmt.where(ContractDailyAggregateModel.date >= since)

        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "contract_name": row.contract_name,
                "check_type": row.check_type,
                "date": row.date,
                "total_checks": row.total_checks,
                "passed_checks": row.passed_checks,
                "failed_checks": row.failed_checks,
                "error_checks": row.error_checks,
                "avg_duration_seconds": row.avg_duration_seconds,
                "violation_count": row.violation_count,
            }
            for row in rows
        ]

    async def cleanup_expired(self, retention_days: int = 90) -> int:
        """Delete raw check results and violations older than retention period.

        Daily aggregates are NEVER deleted (indefinite retention).

        Args:
            retention_days: Number of days to retain raw data.

        Returns:
            Total number of deleted records.
        """
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=retention_days)
        deleted_count: int = 0

        # Delete old check results
        stmt_checks = delete(ContractCheckResultModel).where(
            ContractCheckResultModel.timestamp < cutoff
        )
        result_checks: CursorResult[Any] = await self._session.execute(stmt_checks)  # type: ignore[assignment]
        deleted_count += result_checks.rowcount or 0

        # Delete old violations
        stmt_violations = delete(ContractViolationModel).where(
            ContractViolationModel.timestamp < cutoff
        )
        result_violations: CursorResult[Any] = await self._session.execute(stmt_violations)  # type: ignore[assignment]
        deleted_count += result_violations.rowcount or 0

        self._log.info(
            "cleanup_completed",
            retention_days=retention_days,
            deleted_count=deleted_count,
        )
        return deleted_count

    async def compute_daily_aggregate(
        self,
        contract_name: str,
        check_type: str,
        date: datetime,
    ) -> dict[str, Any]:
        """Compute and upsert a daily aggregate from raw check results.

        Queries ContractCheckResultModel for the given day and computes
        aggregate metrics, then upserts into ContractDailyAggregateModel.

        Args:
            contract_name: Contract to aggregate.
            check_type: Check type to aggregate.
            date: Date to aggregate (uses date part only).

        Returns:
            Dict with computed aggregate values.
        """
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        # Query raw check results for the day
        stmt = select(
            func.count().label("total"),
            func.count().filter(ContractCheckResultModel.status == "pass").label("passed"),
            func.count().filter(ContractCheckResultModel.status == "fail").label("failed"),
            func.count().filter(ContractCheckResultModel.status == "error").label("errors"),
            func.coalesce(
                func.avg(ContractCheckResultModel.duration_seconds), 0.0
            ).label("avg_duration"),
        ).where(
            ContractCheckResultModel.contract_name == contract_name,
            ContractCheckResultModel.check_type == check_type,
            ContractCheckResultModel.timestamp >= day_start,
            ContractCheckResultModel.timestamp < day_end,
        )

        result = await self._session.execute(stmt)
        row = result.one()

        # Count violations for the day
        violation_stmt = select(func.count()).where(
            ContractViolationModel.contract_name == contract_name,
            ContractViolationModel.violation_type == check_type,
            ContractViolationModel.timestamp >= day_start,
            ContractViolationModel.timestamp < day_end,
        )
        violation_result = await self._session.execute(violation_stmt)
        violation_count = violation_result.scalar() or 0

        aggregate = {
            "contract_name": contract_name,
            "check_type": check_type,
            "date": day_start,
            "total_checks": row.total,
            "passed_checks": row.passed,
            "failed_checks": row.failed,
            "error_checks": row.errors,
            "avg_duration_seconds": float(row.avg_duration),
            "violation_count": violation_count,
        }

        # Upsert the aggregate
        upsert_stmt = pg_insert(ContractDailyAggregateModel).values(
            id=uuid.uuid4(),
            **aggregate,
        ).on_conflict_do_update(
            index_elements=["contract_name", "date"],
            set_={
                "check_type": aggregate["check_type"],
                "total_checks": aggregate["total_checks"],
                "passed_checks": aggregate["passed_checks"],
                "failed_checks": aggregate["failed_checks"],
                "error_checks": aggregate["error_checks"],
                "avg_duration_seconds": aggregate["avg_duration_seconds"],
                "violation_count": aggregate["violation_count"],
            },
        )
        await self._session.execute(upsert_stmt)

        self._log.debug(
            "daily_aggregate_computed",
            contract_name=contract_name,
            check_type=check_type,
            date=day_start.isoformat(),
        )
        return aggregate

    async def get_registered_contracts(self, active_only: bool = True) -> list[dict[str, Any]]:
        """Get all registered contracts from DB.

        Args:
            active_only: If True, only return active contracts.

        Returns:
            List of registered contract dicts.
        """
        stmt = select(RegisteredContractModel)
        if active_only:
            stmt = stmt.where(RegisteredContractModel.active.is_(True))

        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "contract_name": row.contract_name,
                "contract_version": row.contract_version,
                "contract_data": row.contract_data,
                "connection_config": row.connection_config,
                "monitoring_overrides": row.monitoring_overrides,
                "registered_at": row.registered_at,
                "last_check_times": row.last_check_times,
                "active": row.active,
            }
            for row in rows
        ]

    async def save_registered_contract(self, contract: dict[str, Any]) -> uuid.UUID:
        """Persist a registered contract.

        Args:
            contract: Dict with keys matching RegisteredContractModel columns.

        Returns:
            UUID of the saved record.
        """
        record_id = uuid.uuid4()
        model = RegisteredContractModel(
            id=record_id,
            contract_name=contract["contract_name"],
            contract_version=contract["contract_version"],
            contract_data=contract["contract_data"],
            connection_config=contract["connection_config"],
            monitoring_overrides=contract.get("monitoring_overrides"),
            registered_at=contract["registered_at"],
            last_check_times=contract.get("last_check_times", {}),
            active=contract.get("active", True),
        )
        self._session.add(model)
        await self._session.flush()
        return record_id

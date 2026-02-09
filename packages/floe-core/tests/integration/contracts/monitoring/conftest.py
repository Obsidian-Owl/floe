"""Integration test fixtures for contract monitoring.

Provides PostgreSQL async fixtures for testing the contract monitoring module.
All fixtures use SQLAlchemy async with asyncpg driver.

Task: Epic 3D - Contract Monitoring Integration Tests
Requirements: FR-3D-001, FR-3D-002, FR-3D-003, FR-3D-004, FR-3D-005
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from floe_core.contracts.monitoring.config import MonitoringConfig, RegisteredContract
from floe_core.contracts.monitoring.db.models import Base
from floe_core.contracts.monitoring.db.repository import MonitoringRepository
from floe_core.contracts.monitoring.monitor import ContractMonitor

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionType


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Get PostgreSQL URL from environment.

    Returns:
        PostgreSQL connection URL with asyncpg driver.

    Note:
        Tests will FAIL if PostgreSQL is not available (no skip).
        Start infrastructure: make test-k8s
    """
    return os.environ.get(
        "FLOE_TEST_POSTGRES_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/floe_test",
    )


@pytest_asyncio.fixture(scope="session")
async def async_engine(postgres_url: str) -> AsyncGenerator[AsyncEngine, None]:
    """Create async SQLAlchemy engine.

    Args:
        postgres_url: PostgreSQL connection URL

    Yields:
        Async SQLAlchemy engine

    Note:
        Tests will FAIL if connection cannot be established.
    """
    engine = create_async_engine(postgres_url, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def create_tables(async_engine: AsyncEngine) -> AsyncGenerator[None, None]:
    """Create database tables for monitoring.

    Creates all 6 monitoring tables:
    - contract_check_results
    - contract_violations
    - contract_sla_status
    - contract_daily_aggregates
    - registered_contracts
    - alert_dedup_state

    Args:
        async_engine: Async SQLAlchemy engine

    Yields:
        None after tables are created

    Note:
        Drops all tables on teardown.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def async_session(
    async_engine: AsyncEngine, create_tables: None
) -> AsyncGenerator[AsyncSessionType, None]:
    """Create async session for test.

    Args:
        async_engine: Async SQLAlchemy engine
        create_tables: Ensures tables exist before session creation

    Yields:
        Async SQLAlchemy session

    Note:
        Rolls back and closes session on teardown.
    """
    async_session_maker = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_maker() as session:
        yield session
        await session.rollback()
        await session.close()


@pytest.fixture
def monitoring_repository(async_session: AsyncSessionType) -> MonitoringRepository:
    """Create monitoring repository.

    Args:
        async_session: Async SQLAlchemy session

    Returns:
        MonitoringRepository instance
    """
    return MonitoringRepository(session=async_session)


@pytest.fixture
def monitoring_config() -> MonitoringConfig:
    """Create monitoring configuration with defaults.

    Returns:
        MonitoringConfig with default values
    """
    return MonitoringConfig()


@pytest.fixture
def sample_contract() -> RegisteredContract:
    """Create sample contract for testing.

    Returns:
        RegisteredContract with unique name per test

    Note:
        Uses unique UUID suffix to prevent test pollution.
    """
    return RegisteredContract(
        contract_name=f"test_contract_{uuid.uuid4().hex[:8]}",
        contract_version="1.0.0",
        contract_data={
            "apiVersion": "v3.1.0",
            "kind": "DataContract",
            "info": {"title": "Test Contract"},
        },
        connection_config={
            "catalog": "test-catalog",
            "warehouse": "test-warehouse",
        },
        registered_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def contract_monitor(
    monitoring_config: MonitoringConfig,
    monitoring_repository: MonitoringRepository,
) -> ContractMonitor:
    """Create contract monitor.

    Args:
        monitoring_config: Monitoring configuration
        monitoring_repository: Monitoring repository

    Returns:
        ContractMonitor instance

    Note:
        This fixture provides a minimal monitor without alert router,
        quality plugin, or compute plugin. Tests requiring these
        should create their own fixtures.
    """
    return ContractMonitor(
        config=monitoring_config,
        repository=monitoring_repository,
    )

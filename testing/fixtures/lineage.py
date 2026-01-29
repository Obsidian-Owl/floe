"""Pytest fixtures for lineage testing.

This module provides shared fixtures for testing lineage functionality,
including mock backends, emitters, and sample lineage events.

Fixtures:
    mock_lineage_backend: Returns a MarquezLineageBackendPlugin instance
    mock_lineage_emitter: Returns a LineageEmitter with NoOpLineageTransport
    sample_lineage_event: Creates a sample LineageEvent for assertions

Example:
    >>> from testing.fixtures.lineage import sample_lineage_event
    >>> event = sample_lineage_event()
    >>> assert event.job.name == "test_job"
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from floe_core.lineage.emitter import LineageEmitter
from floe_core.lineage.events import EventBuilder
from floe_core.lineage.transport import NoOpLineageTransport
from floe_core.lineage.types import (
    LineageDataset,
    LineageEvent,
    LineageJob,
    LineageRun,
    RunState,
)
from floe_lineage_marquez import MarquezLineageBackendPlugin


@pytest.fixture
def mock_lineage_backend() -> MarquezLineageBackendPlugin:
    """Create a mock Marquez lineage backend plugin.

    Returns:
        MarquezLineageBackendPlugin configured for localhost testing.

    Example:
        >>> def test_backend(mock_lineage_backend):
        ...     config = mock_lineage_backend.get_transport_config()
        ...     assert config["type"] == "http"
    """
    return MarquezLineageBackendPlugin(url="http://localhost:5000")


@pytest.fixture
def mock_lineage_emitter() -> LineageEmitter:
    """Create a mock lineage emitter with NoOp transport.

    Returns:
        LineageEmitter configured with NoOpLineageTransport for testing.

    Example:
        >>> def test_emitter(mock_lineage_emitter):
        ...     run_id = await mock_lineage_emitter.emit_start("test_job")
        ...     assert run_id is not None
    """
    transport = NoOpLineageTransport()
    event_builder = EventBuilder(producer="floe-test", default_namespace="test")
    return LineageEmitter(transport, event_builder, default_namespace="test")


@pytest.fixture
def sample_lineage_event() -> LineageEvent:
    """Create a sample lineage event for testing.

    Returns:
        LineageEvent with sample job, run, and dataset information.

    Example:
        >>> def test_event_structure(sample_lineage_event):
        ...     assert sample_lineage_event.event_type == RunState.START
        ...     assert sample_lineage_event.job.name == "test_job"
    """
    return LineageEvent(
        event_type=RunState.START,
        job=LineageJob(
            namespace="test",
            name="test_job",
            facets={},
        ),
        run=LineageRun(
            run_id=uuid4(),
            facets={},
        ),
        inputs=[
            LineageDataset(
                namespace="test",
                name="input_table",
                facets={},
            )
        ],
        outputs=[
            LineageDataset(
                namespace="test",
                name="output_table",
                facets={},
            )
        ],
        producer="floe-test",
    )

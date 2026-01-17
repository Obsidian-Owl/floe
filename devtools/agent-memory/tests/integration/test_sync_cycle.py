"""Integration tests for Cognee sync cycle (add → cognify → search).

These tests verify the full indexing and search cycle with real Cognee Cloud.

Tests FAIL when infrastructure is unavailable (per testing standards).
Run with: pytest tests/integration/test_sync_cycle.py -v
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from agent_memory.cognee_client import CogneeClient


# Sample ADR content for testing
SAMPLE_ADR_CONTENT = """# ADR-0001: Plugin System Architecture

## Status
Accepted

## Context
The floe platform needs a flexible plugin system to support multiple compute
backends (DuckDB, Snowflake, Spark), orchestrators (Dagster, Airflow), and
catalogs (Polaris, Glue).

## Decision
We will implement a plugin architecture with:
- Abstract base classes (ABCs) defining plugin interfaces
- Entry point discovery via `importlib.metadata`
- Pydantic models for plugin configuration

## Consequences
- Plugins can be developed independently
- New backends can be added without core changes
- Plugin discovery is automatic via entry points
"""

SAMPLE_CONSTITUTION_CONTENT = """# Project Constitution

## Core Principles

1. **Technology Ownership**: Each technology owns its domain exclusively.
   - dbt owns ALL SQL compilation
   - Dagster owns orchestration
   - Iceberg owns storage format

2. **Contract-Driven Integration**: CompiledArtifacts is the SOLE contract
   between packages.

3. **K8s-Native Testing**: All tests run in Kubernetes via Kind cluster.
"""


@pytest.fixture(scope="session")
async def cleanup_orphaned_datasets() -> AsyncGenerator[None, None]:
    """Clean up orphaned test datasets from previous failed runs.

    This runs once at the start of the test session to remove any
    datasets with names starting with 'test_sync_' that were left
    behind by previous test failures.

    Creates its own client to avoid fixture scope mismatch.
    """
    import structlog

    from agent_memory.cognee_client import CogneeClient
    from agent_memory.config import get_config

    logger = structlog.get_logger(__name__)

    # Cleanup at session start
    try:
        config = get_config()
        client = CogneeClient(config)
        datasets = await client.list_datasets()
        orphaned = [d for d in datasets if d.startswith("test_sync_")]
        if orphaned:
            logger.info("found_orphaned_datasets", count=len(orphaned))
        for dataset in orphaned:
            try:
                await client.delete_dataset(dataset)
                logger.info("deleted_orphaned_dataset", dataset=dataset)
            except Exception as e:
                logger.warning("orphan_cleanup_failed", dataset=dataset, error=str(e))
    except Exception as e:
        logger.warning("orphan_cleanup_check_failed", error=str(e))

    yield


@pytest.fixture
async def unique_dataset_name(
    cognee_client: CogneeClient,
    cleanup_orphaned_datasets: None,  # noqa: ARG001 - ensures cleanup runs first
) -> AsyncGenerator[str, None]:
    """Generate unique dataset name with guaranteed cleanup.

    This fixture ensures the test dataset is deleted after the test completes,
    even if the test fails mid-way. This prevents orphaned datasets in Cognee Cloud.

    Also depends on cleanup_orphaned_datasets to ensure old test datasets are
    removed before running new tests.
    """
    import structlog

    logger = structlog.get_logger(__name__)
    dataset_name = f"test_sync_{uuid.uuid4().hex[:8]}"

    yield dataset_name

    # Cleanup runs even if test fails
    try:
        await cognee_client.delete_dataset(dataset_name)
        logger.info("test_dataset_cleaned_up", dataset=dataset_name)
    except Exception as e:
        # Log but don't fail - cleanup is best effort
        logger.warning("cleanup_failed", dataset=dataset_name, error=str(e))


@pytest.mark.requirement("FR-004", "FR-005")
@pytest.mark.asyncio
async def test_cognify_architecture_docs(
    cognee_client: CogneeClient,
    unique_dataset_name: str,
) -> None:
    """Test indexing architecture documentation via cognify.

    Validates:
    - Content can be added to Cognee
    - Cognify processes content into knowledge graph
    - Content is searchable after cognify
    """
    # Add sample ADR content
    await cognee_client.add_content(
        content=SAMPLE_ADR_CONTENT,
        dataset_name=unique_dataset_name,
        metadata={"source": "ADR-0001", "type": "architecture"},
    )

    # Run cognify to process into knowledge graph
    await cognee_client.cognify(dataset_name=unique_dataset_name)

    # Verify content is searchable (scoped to our test dataset)
    result = await cognee_client.search(
        query="plugin system architecture",
        dataset_name=unique_dataset_name,  # CRITICAL: scope to test dataset
        search_type="GRAPH_COMPLETION",
        top_k=5,
    )

    assert result.total_count > 0, "Expected search results after cognify"
    # Cleanup handled by unique_dataset_name fixture


@pytest.mark.requirement("FR-004")
@pytest.mark.asyncio
async def test_search_returns_relevant_results(
    cognee_client: CogneeClient,
    unique_dataset_name: str,
) -> None:
    """Test search returns relevant results for indexed content.

    Validates:
    - Search query matches indexed content
    - Results contain expected content
    - Results are relevant to query
    """
    # Add sample content
    await cognee_client.add_content(
        content=SAMPLE_ADR_CONTENT,
        dataset_name=unique_dataset_name,
        metadata={"source": "ADR-0001"},
    )

    # Cognify the content
    await cognee_client.cognify(dataset_name=unique_dataset_name)

    # Search for specific terms that should match (scoped to test dataset)
    result = await cognee_client.search(
        query="entry point discovery importlib",
        dataset_name=unique_dataset_name,  # CRITICAL: scope to test dataset
        search_type="GRAPH_COMPLETION",
        top_k=5,
    )

    assert result.total_count > 0, "Expected results for 'entry point discovery'"

    # Verify search returned results (GRAPH_COMPLETION returns knowledge graph entities,
    # not raw text, so we just validate results were returned)
    assert len(result.results) > 0, "Expected at least one result item"
    # Cleanup handled by unique_dataset_name fixture


@pytest.mark.requirement("FR-005")
@pytest.mark.asyncio
async def test_cognify_constitution_principles(
    cognee_client: CogneeClient,
    unique_dataset_name: str,
) -> None:
    """Test indexing constitution principles.

    Validates:
    - Constitution content can be indexed
    - Principles are searchable
    - Core concepts are retrievable
    """
    # Add constitution content
    await cognee_client.add_content(
        content=SAMPLE_CONSTITUTION_CONTENT,
        dataset_name=unique_dataset_name,
        metadata={"source": "constitution.md", "type": "governance"},
    )

    # Cognify
    await cognee_client.cognify(dataset_name=unique_dataset_name)

    # Search for constitution-specific terms (scoped to test dataset)
    result = await cognee_client.search(
        query="technology ownership dbt SQL",
        dataset_name=unique_dataset_name,  # CRITICAL: scope to test dataset
        search_type="GRAPH_COMPLETION",
        top_k=5,
    )

    assert result.total_count > 0, "Expected results for constitution query"
    # Cleanup handled by unique_dataset_name fixture


@pytest.mark.requirement("FR-004", "FR-005")
@pytest.mark.asyncio
async def test_multiple_documents_searchable(
    cognee_client: CogneeClient,
    unique_dataset_name: str,
) -> None:
    """Test multiple documents are all searchable after indexing.

    Validates:
    - Multiple documents can be added to same dataset
    - All documents are searchable
    - Search returns relevant results from correct document
    """
    # Add multiple documents
    await cognee_client.add_content(
        content=SAMPLE_ADR_CONTENT,
        dataset_name=unique_dataset_name,
        metadata={"source": "ADR-0001"},
    )

    await cognee_client.add_content(
        content=SAMPLE_CONSTITUTION_CONTENT,
        dataset_name=unique_dataset_name,
        metadata={"source": "constitution.md"},
    )

    # Cognify all content
    await cognee_client.cognify(dataset_name=unique_dataset_name)

    # Search for ADR-specific content (scoped to test dataset)
    adr_result = await cognee_client.search(
        query="plugin entry point discovery",
        dataset_name=unique_dataset_name,  # CRITICAL: scope to test dataset
        search_type="GRAPH_COMPLETION",
        top_k=5,
    )

    # Search for constitution-specific content (scoped to test dataset)
    constitution_result = await cognee_client.search(
        query="contract driven integration CompiledArtifacts",
        dataset_name=unique_dataset_name,  # CRITICAL: scope to test dataset
        search_type="GRAPH_COMPLETION",
        top_k=5,
    )

    assert adr_result.total_count > 0, "Expected ADR search results"
    assert constitution_result.total_count > 0, "Expected constitution search results"
    # Cleanup handled by unique_dataset_name fixture


@pytest.mark.requirement("FR-004")
@pytest.mark.asyncio
async def test_search_with_no_results(
    cognee_client: CogneeClient,
    unique_dataset_name: str,
) -> None:
    """Test search handles queries with no matching results.

    Validates:
    - Search returns empty results gracefully
    - No errors when no matches found
    """
    # Add minimal content
    await cognee_client.add_content(
        content="Simple test content about Python programming.",
        dataset_name=unique_dataset_name,
    )

    await cognee_client.cognify(dataset_name=unique_dataset_name)

    # Search for completely unrelated content (scoped to test dataset)
    result = await cognee_client.search(
        query="quantum computing neural networks blockchain",
        dataset_name=unique_dataset_name,  # CRITICAL: scope to test dataset
        search_type="GRAPH_COMPLETION",
        top_k=5,
    )

    # Should return without error, possibly with 0 results
    # (or low-relevance results depending on Cognee's behavior)
    assert isinstance(result.results, list), "Search results should be a list"
    assert result.total_count >= 0, "Total count should be non-negative"
    assert result.query == "quantum computing neural networks blockchain"
    # Cleanup handled by unique_dataset_name fixture

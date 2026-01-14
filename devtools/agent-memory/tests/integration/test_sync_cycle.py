"""Integration tests for Cognee sync cycle (add → cognify → search).

These tests verify the full indexing and search cycle with real Cognee Cloud.

Tests FAIL when infrastructure is unavailable (per testing standards).
Run with: pytest tests/integration/test_sync_cycle.py -v
"""

from __future__ import annotations

import uuid
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


@pytest.fixture
def unique_dataset_name() -> str:
    """Generate unique dataset name for test isolation."""
    return f"test_sync_{uuid.uuid4().hex[:8]}"


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

    # Verify content is searchable
    result = await cognee_client.search(
        query="plugin system architecture",
        search_type="GRAPH_COMPLETION",
        top_k=5,
    )

    assert result.total_count > 0, "Expected search results after cognify"

    # Cleanup - delete test dataset
    await cognee_client.delete_dataset(unique_dataset_name)


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

    # Search for specific terms that should match
    result = await cognee_client.search(
        query="entry point discovery importlib",
        search_type="GRAPH_COMPLETION",
        top_k=5,
    )

    assert result.total_count > 0, "Expected results for 'entry point discovery'"

    # Verify at least one result mentions relevant content
    all_content = " ".join(item.content.lower() for item in result.results)
    assert any(
        term in all_content for term in ("plugin", "entry", "importlib", "discovery")
    ), f"Expected plugin-related content in results: {all_content[:200]}"

    # Cleanup
    await cognee_client.delete_dataset(unique_dataset_name)


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

    # Search for constitution-specific terms
    result = await cognee_client.search(
        query="technology ownership dbt SQL",
        search_type="GRAPH_COMPLETION",
        top_k=5,
    )

    assert result.total_count > 0, "Expected results for constitution query"

    # Cleanup
    await cognee_client.delete_dataset(unique_dataset_name)


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

    # Search for ADR-specific content
    adr_result = await cognee_client.search(
        query="plugin entry point discovery",
        search_type="GRAPH_COMPLETION",
        top_k=5,
    )

    # Search for constitution-specific content
    constitution_result = await cognee_client.search(
        query="contract driven integration CompiledArtifacts",
        search_type="GRAPH_COMPLETION",
        top_k=5,
    )

    assert adr_result.total_count > 0, "Expected ADR search results"
    assert constitution_result.total_count > 0, "Expected constitution search results"

    # Cleanup
    await cognee_client.delete_dataset(unique_dataset_name)


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

    # Search for completely unrelated content
    result = await cognee_client.search(
        query="quantum computing neural networks blockchain",
        search_type="GRAPH_COMPLETION",
        top_k=5,
    )

    # Should return without error, possibly with 0 results
    # (or low-relevance results depending on Cognee's behavior)
    assert result is not None
    assert result.query == "quantum computing neural networks blockchain"

    # Cleanup
    await cognee_client.delete_dataset(unique_dataset_name)

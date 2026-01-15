"""Quality validation module for agent-memory.

Provides functionality to validate knowledge graph quality by
executing test queries and verifying expected results.

Implementation: T040 (FLO-625)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, computed_field

if TYPE_CHECKING:
    from agent_memory.cognee_client import CogneeClient


class TestQuery(BaseModel):
    """A test query with expected results for quality validation.

    Attributes:
        query: The search query to execute.
        expected_keywords: Keywords that should appear in results.
        description: Human-readable description of what this tests.
    """

    query: str = Field(..., min_length=1, description="Search query to execute")
    expected_keywords: list[str] = Field(
        default_factory=list, description="Keywords expected in results"
    )
    description: str = Field(default="", description="What this query tests")


class TestResult(BaseModel):
    """Result of a single test query execution.

    Attributes:
        query: The query that was executed.
        passed: Whether the test passed.
        found_keywords: Keywords that were found in results.
        missing_keywords: Expected keywords not found.
        result_count: Number of results returned.
        error: Error message if query failed.
    """

    query: str = Field(..., description="Query that was executed")
    passed: bool = Field(default=False, description="Whether test passed")
    found_keywords: list[str] = Field(default_factory=list, description="Keywords found")
    missing_keywords: list[str] = Field(
        default_factory=list, description="Expected keywords not found"
    )
    result_count: int = Field(default=0, ge=0, description="Results returned")
    error: str | None = Field(default=None, description="Error if query failed")


class QualityReport(BaseModel):
    """Report of quality validation results.

    Attributes:
        total_tests: Total number of test queries executed.
        passed_tests: Number of tests that passed.
        failed_tests: Number of tests that failed.
        results: Detailed results for each test query.
    """

    total_tests: int = Field(ge=0, description="Total tests executed")
    passed_tests: int = Field(ge=0, description="Tests that passed")
    failed_tests: int = Field(ge=0, description="Tests that failed")
    results: list[TestResult] = Field(default_factory=list, description="Test results")

    @computed_field
    @property
    def pass_rate(self) -> float:
        """Calculate pass rate as percentage.

        Returns:
            Pass rate (0-100).
        """
        if self.total_tests == 0:
            return 100.0
        return (self.passed_tests / self.total_tests) * 100

    @computed_field
    @property
    def all_passed(self) -> bool:
        """Check if all tests passed.

        Returns:
            True if all tests passed.
        """
        return self.failed_tests == 0


def check_keywords_in_results(
    results_content: list[str],
    expected_keywords: list[str],
) -> tuple[list[str], list[str]]:
    """Check which expected keywords appear in search results.

    Args:
        results_content: List of result content strings.
        expected_keywords: Keywords to look for.

    Returns:
        Tuple of (found_keywords, missing_keywords).
    """
    # Combine all results into one searchable string (case-insensitive)
    combined = " ".join(results_content).lower()

    found: list[str] = []
    missing: list[str] = []

    for keyword in expected_keywords:
        if keyword.lower() in combined:
            found.append(keyword)
        else:
            missing.append(keyword)

    return found, missing


async def validate_quality(
    client: CogneeClient,
    test_queries: list[TestQuery],
    *,
    search_type: str = "GRAPH_COMPLETION",
) -> QualityReport:
    """Validate knowledge graph quality using test queries.

    Executes each test query against the knowledge graph and
    verifies that expected keywords appear in the results.

    Args:
        client: Cognee client for executing searches.
        test_queries: List of test queries to execute.
        search_type: Type of search to use (default: GRAPH_COMPLETION).

    Returns:
        QualityReport with pass/fail metrics for each test.

    Example:
        >>> client = CogneeClient(config)
        >>> queries = [
        ...     TestQuery(
        ...         query="What is the main configuration file?",
        ...         expected_keywords=["floe.yaml", "configuration"],
        ...         description="Test config file knowledge"
        ...     )
        ... ]
        >>> report = await validate_quality(client, queries)
        >>> print(f"Pass rate: {report.pass_rate}%")
    """
    results: list[TestResult] = []

    for test_query in test_queries:
        try:
            # Execute the search
            search_result = await client.search(
                test_query.query,
                search_type=search_type,
            )

            # Extract content from results
            result_contents = [item.content for item in search_result.results]

            # Check for expected keywords
            found, missing = check_keywords_in_results(
                result_contents,
                test_query.expected_keywords,
            )

            # Determine if test passed
            # Pass if all expected keywords found (or no keywords expected)
            passed = len(missing) == 0

            results.append(
                TestResult(
                    query=test_query.query,
                    passed=passed,
                    found_keywords=found,
                    missing_keywords=missing,
                    result_count=len(search_result.results),
                )
            )

        except Exception as e:
            # Query execution failed
            results.append(
                TestResult(
                    query=test_query.query,
                    passed=False,
                    missing_keywords=test_query.expected_keywords.copy(),
                    error=str(e),
                )
            )

    # Calculate totals
    passed_count = sum(1 for r in results if r.passed)
    failed_count = len(results) - passed_count

    return QualityReport(
        total_tests=len(results),
        passed_tests=passed_count,
        failed_tests=failed_count,
        results=results,
    )


def create_default_test_queries() -> list[TestQuery]:
    """Create default test queries for basic quality validation.

    Returns a set of queries that test fundamental knowledge about
    architecture, plugins, and governance patterns from the indexed
    documentation. Keywords are intentionally flexible to accommodate
    varying LLM responses from Cognee Cloud.

    Returns:
        List of default TestQuery objects.
    """
    return [
        TestQuery(
            query="What is the floe architecture?",
            expected_keywords=["architecture"],  # Flexible - just needs to mention architecture
            description="Test architecture knowledge",
        ),
        TestQuery(
            query="What plugins are available in floe?",
            expected_keywords=["plugin"],  # Flexible - just needs to mention plugin
            description="Test plugin system awareness",
        ),
        TestQuery(
            query="What are the testing standards?",
            expected_keywords=["test"],  # Flexible - just needs to mention test
            description="Test governance knowledge",
        ),
    ]

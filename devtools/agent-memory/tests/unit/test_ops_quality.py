"""Unit tests for ops/quality.py - quality validation module.

Tests for quality validation functionality:
- TestQuery model
- TestResult model
- QualityReport model with computed fields
- check_keywords_in_results helper
- validate_quality function
- create_default_test_queries function

Implementation: T040 (FLO-625)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestTestQueryModel:
    """Tests for TestQuery model."""

    @pytest.mark.requirement("FR-023")
    def test_test_query_has_required_fields(self) -> None:
        """Test TestQuery model has all required fields."""
        from agent_memory.ops.quality import TestQuery

        query = TestQuery(
            query="What is the config?",
            expected_keywords=["config", "yaml"],
            description="Test config knowledge",
        )

        assert query.query == "What is the config?"
        assert query.expected_keywords == ["config", "yaml"]
        assert query.description == "Test config knowledge"

    @pytest.mark.requirement("FR-023")
    def test_test_query_defaults(self) -> None:
        """Test TestQuery model default values."""
        from agent_memory.ops.quality import TestQuery

        query = TestQuery(query="Simple query")

        assert query.query == "Simple query"
        assert query.expected_keywords == []
        assert query.description == ""

    @pytest.mark.requirement("FR-023")
    def test_test_query_requires_query(self) -> None:
        """Test TestQuery model requires non-empty query."""
        from pydantic import ValidationError

        from agent_memory.ops.quality import TestQuery

        with pytest.raises(ValidationError):
            TestQuery(query="")


class TestTestResultModel:
    """Tests for TestResult model."""

    @pytest.mark.requirement("FR-023")
    def test_test_result_passed(self) -> None:
        """Test TestResult model for passed test."""
        from agent_memory.ops.quality import TestResult

        result = TestResult(
            query="What is config?",
            passed=True,
            found_keywords=["config", "yaml"],
            missing_keywords=[],
            result_count=5,
        )

        assert result.passed is True
        assert result.found_keywords == ["config", "yaml"]
        assert result.missing_keywords == []
        assert result.result_count == 5
        assert result.error is None

    @pytest.mark.requirement("FR-023")
    def test_test_result_failed(self) -> None:
        """Test TestResult model for failed test."""
        from agent_memory.ops.quality import TestResult

        result = TestResult(
            query="What is missing?",
            passed=False,
            found_keywords=["found"],
            missing_keywords=["missing1", "missing2"],
            result_count=1,
        )

        assert result.passed is False
        assert result.missing_keywords == ["missing1", "missing2"]

    @pytest.mark.requirement("FR-023")
    def test_test_result_with_error(self) -> None:
        """Test TestResult model with error."""
        from agent_memory.ops.quality import TestResult

        result = TestResult(
            query="Bad query",
            passed=False,
            error="Connection failed",
        )

        assert result.passed is False
        assert result.error == "Connection failed"
        assert result.result_count == 0


class TestQualityReportModel:
    """Tests for QualityReport model."""

    @pytest.mark.requirement("FR-023")
    def test_quality_report_has_required_fields(self) -> None:
        """Test QualityReport model has all required fields."""
        from agent_memory.ops.quality import QualityReport, TestResult

        results = [
            TestResult(query="q1", passed=True),
            TestResult(query="q2", passed=False),
        ]

        report = QualityReport(
            total_tests=2,
            passed_tests=1,
            failed_tests=1,
            results=results,
        )

        assert report.total_tests == 2
        assert report.passed_tests == 1
        assert report.failed_tests == 1
        assert len(report.results) == 2

    @pytest.mark.requirement("FR-023")
    def test_quality_report_pass_rate(self) -> None:
        """Test QualityReport.pass_rate computed property."""
        from agent_memory.ops.quality import QualityReport

        report = QualityReport(
            total_tests=10,
            passed_tests=8,
            failed_tests=2,
            results=[],
        )

        assert report.pass_rate == pytest.approx(80.0)

    @pytest.mark.requirement("FR-023")
    def test_quality_report_pass_rate_zero_tests(self) -> None:
        """Test QualityReport.pass_rate with zero tests."""
        from agent_memory.ops.quality import QualityReport

        report = QualityReport(
            total_tests=0,
            passed_tests=0,
            failed_tests=0,
            results=[],
        )

        assert report.pass_rate == pytest.approx(100.0)

    @pytest.mark.requirement("FR-023")
    def test_quality_report_all_passed(self) -> None:
        """Test QualityReport.all_passed computed property."""
        from agent_memory.ops.quality import QualityReport

        all_pass = QualityReport(
            total_tests=5,
            passed_tests=5,
            failed_tests=0,
            results=[],
        )
        assert all_pass.all_passed is True

        some_fail = QualityReport(
            total_tests=5,
            passed_tests=4,
            failed_tests=1,
            results=[],
        )
        assert some_fail.all_passed is False


class TestCheckKeywordsInResults:
    """Tests for check_keywords_in_results helper function."""

    @pytest.mark.requirement("FR-023")
    def test_all_keywords_found(self) -> None:
        """Test when all keywords are found in results."""
        from agent_memory.ops.quality import check_keywords_in_results

        results = ["The config file is floe.yaml", "Configuration options"]
        keywords = ["config", "yaml"]

        found, missing = check_keywords_in_results(results, keywords)

        assert found == ["config", "yaml"]
        assert missing == []

    @pytest.mark.requirement("FR-023")
    def test_some_keywords_missing(self) -> None:
        """Test when some keywords are missing."""
        from agent_memory.ops.quality import check_keywords_in_results

        results = ["The config file exists"]
        keywords = ["config", "yaml", "json"]

        found, missing = check_keywords_in_results(results, keywords)

        assert found == ["config"]
        assert "yaml" in missing
        assert "json" in missing

    @pytest.mark.requirement("FR-023")
    def test_case_insensitive(self) -> None:
        """Test keyword matching is case insensitive."""
        from agent_memory.ops.quality import check_keywords_in_results

        results = ["The CONFIG file is YAML format"]
        keywords = ["config", "yaml"]

        found, missing = check_keywords_in_results(results, keywords)

        assert found == ["config", "yaml"]
        assert missing == []

    @pytest.mark.requirement("FR-023")
    def test_empty_results(self) -> None:
        """Test with empty results."""
        from agent_memory.ops.quality import check_keywords_in_results

        found, missing = check_keywords_in_results([], ["config"])

        assert found == []
        assert missing == ["config"]

    @pytest.mark.requirement("FR-023")
    def test_empty_keywords(self) -> None:
        """Test with no expected keywords."""
        from agent_memory.ops.quality import check_keywords_in_results

        found, missing = check_keywords_in_results(["Some content"], [])

        assert found == []
        assert missing == []


class TestValidateQuality:
    """Tests for validate_quality function."""

    @pytest.mark.requirement("FR-023")
    @pytest.mark.asyncio
    async def test_validate_quality_all_pass(self) -> None:
        """Test validate_quality when all tests pass."""
        from agent_memory.ops.quality import TestQuery, validate_quality

        # Mock client
        mock_client = AsyncMock()
        mock_result = MagicMock()
        mock_result.results = [
            MagicMock(content="The configuration uses yaml format"),
            MagicMock(content="Config file settings"),
        ]
        mock_client.search = AsyncMock(return_value=mock_result)

        queries = [
            TestQuery(
                query="What is the config format?",
                expected_keywords=["config", "yaml"],
            )
        ]

        report = await validate_quality(mock_client, queries)

        assert report.total_tests == 1
        assert report.passed_tests == 1
        assert report.failed_tests == 0
        assert report.all_passed is True
        assert report.results[0].passed is True

    @pytest.mark.requirement("FR-023")
    @pytest.mark.asyncio
    async def test_validate_quality_some_fail(self) -> None:
        """Test validate_quality when some tests fail."""
        from agent_memory.ops.quality import TestQuery, validate_quality

        mock_client = AsyncMock()
        mock_result = MagicMock()
        mock_result.results = [MagicMock(content="Some content")]
        mock_client.search = AsyncMock(return_value=mock_result)

        queries = [
            TestQuery(query="q1", expected_keywords=["found"]),
            TestQuery(query="q2", expected_keywords=["missing"]),
        ]

        # First query finds "Some content" which doesn't have "found"
        # Second query also won't find "missing"
        report = await validate_quality(mock_client, queries)

        assert report.total_tests == 2
        # Both fail since "found" and "missing" not in "Some content"
        assert report.all_passed is False

    @pytest.mark.requirement("FR-023")
    @pytest.mark.asyncio
    async def test_validate_quality_handles_search_error(self) -> None:
        """Test validate_quality handles search errors gracefully."""
        from agent_memory.ops.quality import TestQuery, validate_quality

        mock_client = AsyncMock()
        mock_client.search = AsyncMock(side_effect=Exception("Connection failed"))

        queries = [TestQuery(query="Test query", expected_keywords=["keyword"])]

        report = await validate_quality(mock_client, queries)

        assert report.total_tests == 1
        assert report.passed_tests == 0
        assert report.failed_tests == 1
        assert report.results[0].error == "Connection failed"
        assert report.results[0].passed is False

    @pytest.mark.requirement("FR-023")
    @pytest.mark.asyncio
    async def test_validate_quality_no_keywords_required(self) -> None:
        """Test validate_quality passes when no keywords required."""
        from agent_memory.ops.quality import TestQuery, validate_quality

        mock_client = AsyncMock()
        mock_result = MagicMock()
        mock_result.results = [MagicMock(content="Any content")]
        mock_client.search = AsyncMock(return_value=mock_result)

        # No expected keywords - just check query returns results
        queries = [TestQuery(query="General query", expected_keywords=[])]

        report = await validate_quality(mock_client, queries)

        assert report.total_tests == 1
        assert report.passed_tests == 1
        assert report.all_passed is True

    @pytest.mark.requirement("FR-023")
    @pytest.mark.asyncio
    async def test_validate_quality_empty_queries(self) -> None:
        """Test validate_quality with empty query list."""
        from agent_memory.ops.quality import validate_quality

        mock_client = AsyncMock()

        report = await validate_quality(mock_client, [])

        assert report.total_tests == 0
        assert report.passed_tests == 0
        assert report.failed_tests == 0
        assert report.all_passed is True

    @pytest.mark.requirement("FR-023")
    @pytest.mark.asyncio
    async def test_validate_quality_tracks_result_count(self) -> None:
        """Test validate_quality tracks result count."""
        from agent_memory.ops.quality import TestQuery, validate_quality

        mock_client = AsyncMock()
        mock_result = MagicMock()
        mock_result.results = [
            MagicMock(content="Result 1"),
            MagicMock(content="Result 2"),
            MagicMock(content="Result 3"),
        ]
        mock_client.search = AsyncMock(return_value=mock_result)

        queries = [TestQuery(query="Test", expected_keywords=[])]

        report = await validate_quality(mock_client, queries)

        assert report.results[0].result_count == 3


class TestCreateDefaultTestQueries:
    """Tests for create_default_test_queries function."""

    @pytest.mark.requirement("FR-023")
    def test_returns_list_of_queries(self) -> None:
        """Test create_default_test_queries returns queries."""
        from agent_memory.ops.quality import TestQuery, create_default_test_queries

        queries = create_default_test_queries()

        assert isinstance(queries, list)
        assert len(queries) > 0
        assert all(isinstance(q, TestQuery) for q in queries)

    @pytest.mark.requirement("FR-023")
    def test_queries_have_descriptions(self) -> None:
        """Test default queries have descriptions."""
        from agent_memory.ops.quality import create_default_test_queries

        queries = create_default_test_queries()

        for query in queries:
            assert query.description != ""


class TestQualityReportSerialization:
    """Tests for QualityReport serialization."""

    @pytest.mark.requirement("FR-023")
    def test_quality_report_to_dict(self) -> None:
        """Test QualityReport can be serialized to dict."""
        from agent_memory.ops.quality import QualityReport, TestResult

        report = QualityReport(
            total_tests=2,
            passed_tests=1,
            failed_tests=1,
            results=[
                TestResult(query="q1", passed=True),
                TestResult(query="q2", passed=False),
            ],
        )

        data = report.model_dump()

        assert data["total_tests"] == 2
        assert data["pass_rate"] == pytest.approx(50.0)
        assert data["all_passed"] is False

    @pytest.mark.requirement("FR-023")
    def test_quality_report_json_serializable(self) -> None:
        """Test QualityReport can be serialized to JSON."""
        import json

        from agent_memory.ops.quality import QualityReport

        report = QualityReport(
            total_tests=5,
            passed_tests=5,
            failed_tests=0,
            results=[],
        )

        json_str = report.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["pass_rate"] == pytest.approx(100.0)
        assert parsed["all_passed"] is True

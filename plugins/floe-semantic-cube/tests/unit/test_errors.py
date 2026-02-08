"""Unit tests for Cube semantic layer error types.

Tests cover: inheritance hierarchy, error messages, context data,
and exception handling patterns.
"""

from __future__ import annotations

import pytest

from floe_semantic_cube.errors import (
    CubeDatasourceError,
    CubeHealthCheckError,
    CubeSemanticError,
    SchemaGenerationError,
)


class TestCubeSemanticError:
    """Tests for CubeSemanticError base class."""

    @pytest.mark.requirement("FR-008")
    def test_base_error_message(self) -> None:
        """Test that base error stores message correctly."""
        error = CubeSemanticError("something went wrong")
        assert str(error) == "something went wrong"
        assert error.message == "something went wrong"

    @pytest.mark.requirement("FR-008")
    def test_base_error_is_exception(self) -> None:
        """Test that CubeSemanticError inherits from Exception."""
        assert issubclass(CubeSemanticError, Exception)

    @pytest.mark.requirement("FR-008")
    def test_base_error_catchable(self) -> None:
        """Test that CubeSemanticError can be caught as Exception."""
        with pytest.raises(CubeSemanticError):
            raise CubeSemanticError("test")


class TestSchemaGenerationError:
    """Tests for SchemaGenerationError."""

    @pytest.mark.requirement("FR-008")
    def test_inherits_from_base(self) -> None:
        """Test that SchemaGenerationError inherits from CubeSemanticError."""
        assert issubclass(SchemaGenerationError, CubeSemanticError)

    @pytest.mark.requirement("FR-008")
    def test_message_without_model(self) -> None:
        """Test error message without model_name context."""
        error = SchemaGenerationError("Invalid column type")
        assert str(error) == "Invalid column type"
        assert error.model_name is None

    @pytest.mark.requirement("FR-008")
    def test_message_with_model(self) -> None:
        """Test error message includes model_name when provided."""
        error = SchemaGenerationError("Invalid column type", model_name="orders")
        assert str(error) == "Invalid column type (model: orders)"
        assert error.model_name == "orders"

    @pytest.mark.requirement("FR-008")
    def test_catchable_as_base(self) -> None:
        """Test that SchemaGenerationError is catchable as CubeSemanticError."""
        with pytest.raises(CubeSemanticError):
            raise SchemaGenerationError("test")


class TestCubeHealthCheckError:
    """Tests for CubeHealthCheckError."""

    @pytest.mark.requirement("FR-008")
    def test_inherits_from_base(self) -> None:
        """Test that CubeHealthCheckError inherits from CubeSemanticError."""
        assert issubclass(CubeHealthCheckError, CubeSemanticError)

    @pytest.mark.requirement("FR-008")
    def test_message_without_server(self) -> None:
        """Test error message without server_url context."""
        error = CubeHealthCheckError("Connection refused")
        assert str(error) == "Connection refused"
        assert error.server_url is None

    @pytest.mark.requirement("FR-008")
    def test_message_with_server(self) -> None:
        """Test error message includes server_url when provided."""
        error = CubeHealthCheckError(
            "Connection refused",
            server_url="http://cube:4000",
        )
        assert str(error) == "Connection refused (server: http://cube:4000)"
        assert error.server_url == "http://cube:4000"

    @pytest.mark.requirement("FR-008")
    def test_catchable_as_base(self) -> None:
        """Test that CubeHealthCheckError is catchable as CubeSemanticError."""
        with pytest.raises(CubeSemanticError):
            raise CubeHealthCheckError("test")


class TestCubeDatasourceError:
    """Tests for CubeDatasourceError."""

    @pytest.mark.requirement("FR-008")
    def test_inherits_from_base(self) -> None:
        """Test that CubeDatasourceError inherits from CubeSemanticError."""
        assert issubclass(CubeDatasourceError, CubeSemanticError)

    @pytest.mark.requirement("FR-008")
    def test_message_without_compute_type(self) -> None:
        """Test error message without compute_type context."""
        error = CubeDatasourceError("Unsupported compute")
        assert str(error) == "Unsupported compute"
        assert error.compute_type is None

    @pytest.mark.requirement("FR-008")
    def test_message_with_compute_type(self) -> None:
        """Test error message includes compute_type when provided."""
        error = CubeDatasourceError(
            "Unsupported compute",
            compute_type="bigquery",
        )
        assert str(error) == "Unsupported compute (compute: bigquery)"
        assert error.compute_type == "bigquery"

    @pytest.mark.requirement("FR-008")
    def test_catchable_as_base(self) -> None:
        """Test that CubeDatasourceError is catchable as CubeSemanticError."""
        with pytest.raises(CubeSemanticError):
            raise CubeDatasourceError("test")


class TestErrorHierarchy:
    """Tests for the complete error hierarchy."""

    @pytest.mark.requirement("FR-008")
    def test_all_errors_are_cube_semantic_errors(self) -> None:
        """Test that all error types inherit from CubeSemanticError."""
        error_types = [
            SchemaGenerationError,
            CubeHealthCheckError,
            CubeDatasourceError,
        ]
        for error_type in error_types:
            assert issubclass(
                error_type, CubeSemanticError
            ), f"{error_type.__name__} should inherit from CubeSemanticError"

    @pytest.mark.requirement("FR-008")
    def test_all_errors_are_exceptions(self) -> None:
        """Test that all error types inherit from Exception."""
        error_types = [
            CubeSemanticError,
            SchemaGenerationError,
            CubeHealthCheckError,
            CubeDatasourceError,
        ]
        for error_type in error_types:
            assert issubclass(
                error_type, Exception
            ), f"{error_type.__name__} should inherit from Exception"

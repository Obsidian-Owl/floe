"""Unit tests for data generation fixture.

Tests for testing.fixtures.data module including test ID generation,
random string generation, and Pydantic model factories.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import BaseModel, Field

from testing.fixtures.data import (
    create_model_instance,
    generate_random_string,
    generate_test_data,
    generate_test_email,
    generate_test_id,
    generate_test_timestamp,
    sample_customer_data,
    sample_order_data,
    sample_records,
)


class TestGenerateTestId:
    """Tests for generate_test_id function."""

    @pytest.mark.requirement("9c-FR-015")
    def test_generates_unique_ids(self) -> None:
        """Test that generated IDs are unique."""
        ids = [generate_test_id() for _ in range(100)]
        assert len(ids) == len(set(ids))

    @pytest.mark.requirement("9c-FR-015")
    def test_uses_prefix(self) -> None:
        """Test that prefix is included in ID."""
        test_id = generate_test_id("custom")
        assert test_id.startswith("custom_")

    @pytest.mark.requirement("9c-FR-015")
    def test_default_prefix(self) -> None:
        """Test default prefix is 'test'."""
        test_id = generate_test_id()
        assert test_id.startswith("test_")

    @pytest.mark.requirement("9c-FR-015")
    def test_id_format(self) -> None:
        """Test ID format is prefix_hex8."""
        test_id = generate_test_id("prefix")
        parts = test_id.split("_")
        assert len(parts) == 2
        assert parts[0] == "prefix"
        assert len(parts[1]) == 8


class TestGenerateRandomString:
    """Tests for generate_random_string function."""

    @pytest.mark.requirement("9c-FR-015")
    def test_default_length(self) -> None:
        """Test default string length is 10."""
        s = generate_random_string()
        assert len(s) == 10

    @pytest.mark.requirement("9c-FR-015")
    def test_custom_length(self) -> None:
        """Test custom string length."""
        s = generate_random_string(length=20)
        assert len(s) == 20

    @pytest.mark.requirement("9c-FR-015")
    def test_custom_charset(self) -> None:
        """Test custom character set."""
        s = generate_random_string(length=100, charset="abc")
        assert all(c in "abc" for c in s)

    @pytest.mark.requirement("9c-FR-015")
    def test_randomness(self) -> None:
        """Test strings are random (not all same)."""
        strings = [generate_random_string() for _ in range(10)]
        # Very unlikely all 10 are identical
        assert len(set(strings)) > 1


class TestGenerateTestEmail:
    """Tests for generate_test_email function."""

    @pytest.mark.requirement("9c-FR-015")
    def test_generates_valid_email(self) -> None:
        """Test generated email has valid format."""
        email = generate_test_email()
        assert "@" in email
        assert "." in email.split("@")[1]

    @pytest.mark.requirement("9c-FR-015")
    def test_custom_domain(self) -> None:
        """Test custom domain."""
        email = generate_test_email(domain="custom.org")
        assert email.endswith("@custom.org")

    @pytest.mark.requirement("9c-FR-015")
    def test_unique_emails(self) -> None:
        """Test generated emails are unique."""
        emails = [generate_test_email() for _ in range(100)]
        assert len(emails) == len(set(emails))


class TestGenerateTestTimestamp:
    """Tests for generate_test_timestamp function."""

    @pytest.mark.requirement("9c-FR-015")
    def test_returns_datetime(self) -> None:
        """Test returns datetime object."""
        ts = generate_test_timestamp()
        assert isinstance(ts, datetime)

    @pytest.mark.requirement("9c-FR-015")
    def test_utc_timezone(self) -> None:
        """Test timestamp is in UTC."""
        ts = generate_test_timestamp()
        assert ts.tzinfo == timezone.utc

    @pytest.mark.requirement("9c-FR-015")
    def test_recent_timestamp(self) -> None:
        """Test timestamp is recent (within last minute)."""
        ts = generate_test_timestamp()
        now = datetime.now(timezone.utc)
        diff = (now - ts).total_seconds()
        assert abs(diff) < 60


class TestGenerateTestData:
    """Tests for generate_test_data function."""

    @pytest.mark.requirement("9c-FR-015")
    def test_generates_from_schema(self) -> None:
        """Test generates data from type schema."""
        data = generate_test_data({"name": str, "count": int})
        assert "name" in data
        assert "count" in data
        assert isinstance(data["name"], str)
        assert isinstance(data["count"], int)

    @pytest.mark.requirement("9c-FR-015")
    def test_supports_all_basic_types(self) -> None:
        """Test supports all basic Python types."""
        schema = {
            "text": str,
            "number": int,
            "decimal": float,
            "flag": bool,
            "items": list,
            "mapping": dict,
        }
        data = generate_test_data(schema)
        assert isinstance(data["text"], str)
        assert isinstance(data["number"], int)
        assert isinstance(data["decimal"], float)
        assert isinstance(data["flag"], bool)
        assert isinstance(data["items"], list)
        assert isinstance(data["mapping"], dict)

    @pytest.mark.requirement("9c-FR-015")
    def test_applies_overrides(self) -> None:
        """Test overrides are applied."""
        data = generate_test_data(
            {"name": str, "value": int},
            overrides={"name": "custom_name"},
        )
        assert data["name"] == "custom_name"
        assert isinstance(data["value"], int)

    @pytest.mark.requirement("9c-FR-015")
    def test_unknown_type_returns_none(self) -> None:
        """Test unknown types return None."""

        class CustomType:
            pass

        data = generate_test_data({"custom": CustomType})
        assert data["custom"] is None


class SampleModel(BaseModel):
    """Sample model for testing create_model_instance."""

    name: str
    value: int
    optional: str | None = None
    with_default: str = "default_value"


class TestCreateModelInstance:
    """Tests for create_model_instance function."""

    @pytest.mark.requirement("9c-FR-015")
    def test_creates_valid_instance(self) -> None:
        """Test creates valid Pydantic model instance."""
        instance = create_model_instance(SampleModel)
        assert isinstance(instance, SampleModel)
        assert instance.name
        assert isinstance(instance.value, int)

    @pytest.mark.requirement("9c-FR-015")
    def test_uses_overrides(self) -> None:
        """Test applies field overrides."""
        instance = create_model_instance(SampleModel, {"name": "custom"})
        assert instance.name == "custom"

    @pytest.mark.requirement("9c-FR-015")
    def test_respects_defaults(self) -> None:
        """Test respects default values."""
        instance = create_model_instance(SampleModel)
        assert instance.with_default == "default_value"

    @pytest.mark.requirement("9c-FR-015")
    def test_optional_fields_not_required(self) -> None:
        """Test optional fields don't need generation."""
        instance = create_model_instance(SampleModel)
        # optional field should be None (default) or generated
        assert instance.optional is None or isinstance(instance.optional, str)


class TestSampleRecords:
    """Tests for sample_records function."""

    @pytest.mark.requirement("9c-FR-015")
    def test_generates_correct_count(self) -> None:
        """Test generates requested number of records."""
        records = sample_records(count=5)
        assert len(records) == 5

    @pytest.mark.requirement("9c-FR-015")
    def test_default_count(self) -> None:
        """Test default count is 10."""
        records = sample_records()
        assert len(records) == 10

    @pytest.mark.requirement("9c-FR-015")
    def test_record_structure(self) -> None:
        """Test records have expected fields."""
        records = sample_records(count=1)
        record = records[0]
        assert "id" in record
        assert "name" in record
        assert "value" in record
        assert "created_at" in record

    @pytest.mark.requirement("9c-FR-015")
    def test_unique_ids(self) -> None:
        """Test record IDs are unique."""
        records = sample_records(count=100)
        ids = [r["id"] for r in records]
        assert len(ids) == len(set(ids))


class TestSampleCustomerData:
    """Tests for sample_customer_data function."""

    @pytest.mark.requirement("9c-FR-015")
    def test_generates_customer_fields(self) -> None:
        """Test generates all customer fields."""
        customer = sample_customer_data()
        assert "customer_id" in customer
        assert "name" in customer
        assert "email" in customer
        assert "created_at" in customer
        assert "active" in customer

    @pytest.mark.requirement("9c-FR-015")
    def test_unique_customer_ids(self) -> None:
        """Test customer IDs are unique."""
        customers = [sample_customer_data() for _ in range(100)]
        ids = [c["customer_id"] for c in customers]
        assert len(ids) == len(set(ids))


class TestSampleOrderData:
    """Tests for sample_order_data function."""

    @pytest.mark.requirement("9c-FR-015")
    def test_generates_order_fields(self) -> None:
        """Test generates all order fields."""
        order = sample_order_data()
        assert "order_id" in order
        assert "customer_id" in order
        assert "amount" in order
        assert "status" in order
        assert "created_at" in order

    @pytest.mark.requirement("9c-FR-015")
    def test_uses_provided_customer_id(self) -> None:
        """Test uses provided customer ID."""
        order = sample_order_data(customer_id="cust_123")
        assert order["customer_id"] == "cust_123"

    @pytest.mark.requirement("9c-FR-015")
    def test_valid_status(self) -> None:
        """Test status is one of expected values."""
        orders = [sample_order_data() for _ in range(50)]
        valid_statuses = {"pending", "completed", "cancelled"}
        for order in orders:
            assert order["status"] in valid_statuses

    @pytest.mark.requirement("9c-FR-015")
    def test_amount_is_numeric(self) -> None:
        """Test amount is a valid number."""
        order = sample_order_data()
        assert isinstance(order["amount"], (int, float))
        assert order["amount"] > 0

"""Test data generation helpers.

Provides utilities for generating test data, including Pydantic model factories
and common test data patterns.

Example:
    from testing.fixtures.data import generate_test_id, generate_test_data

    def test_with_generated_data():
        test_id = generate_test_id("test")
        data = generate_test_data({"name": str, "count": int})
        assert data["name"]
        assert isinstance(data["count"], int)
"""

from __future__ import annotations

import random
import string
import uuid
from datetime import datetime, timezone
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def generate_test_id(prefix: str = "test") -> str:
    """Generate a unique test identifier.

    Args:
        prefix: Prefix for the ID.

    Returns:
        Unique ID like 'test_a1b2c3d4'.
    """
    suffix = uuid.uuid4().hex[:8]
    return f"{prefix}_{suffix}"


def generate_random_string(
    length: int = 10,
    charset: str | None = None,
) -> str:
    """Generate a random string.

    Args:
        length: Length of string to generate.
        charset: Character set to use (default: lowercase + digits).

    Returns:
        Random string.
    """
    if charset is None:
        charset = string.ascii_lowercase + string.digits
    return "".join(random.choice(charset) for _ in range(length))  # noqa: S311


def generate_test_email(domain: str = "test.example.com") -> str:
    """Generate a unique test email address.

    Args:
        domain: Email domain to use.

    Returns:
        Unique email like 'test_a1b2c3d4@test.example.com'.
    """
    local_part = generate_test_id("test")
    return f"{local_part}@{domain}"


def generate_test_timestamp() -> datetime:
    """Generate current UTC timestamp.

    Returns:
        Current datetime in UTC.
    """
    return datetime.now(timezone.utc)


def generate_test_data(
    schema: dict[str, type],
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate test data from a type schema.

    Args:
        schema: Dictionary mapping field names to types.
        overrides: Optional values to use instead of generated ones.

    Returns:
        Dictionary with generated test data.

    Example:
        data = generate_test_data({
            "name": str,
            "age": int,
            "active": bool,
        })
        # {'name': 'test_xyz', 'age': 42, 'active': True}
    """
    overrides = overrides or {}
    result: dict[str, Any] = {}

    generators: dict[type, Any] = {
        str: lambda: generate_random_string(10),
        int: lambda: random.randint(1, 1000),  # noqa: S311
        float: lambda: random.uniform(0.0, 100.0),  # noqa: S311
        bool: lambda: random.choice([True, False]),  # noqa: S311
        list: lambda: [],
        dict: lambda: {},
        datetime: generate_test_timestamp,
    }

    for field, field_type in schema.items():
        if field in overrides:
            result[field] = overrides[field]
        elif field_type in generators:
            result[field] = generators[field_type]()
        else:
            result[field] = None

    return result


def create_model_instance(
    model_class: type[T],
    overrides: dict[str, Any] | None = None,
) -> T:
    """Create a Pydantic model instance with generated data.

    Generates values for required fields and uses defaults for optional fields.

    Args:
        model_class: Pydantic model class.
        overrides: Optional field values to use.

    Returns:
        Model instance with generated data.

    Example:
        class User(BaseModel):
            name: str
            email: str

        user = create_model_instance(User, {"name": "Test User"})
    """
    overrides = overrides or {}

    # Get model fields and their types
    field_data: dict[str, Any] = {}
    for field_name, field_info in model_class.model_fields.items():
        if field_name in overrides:
            field_data[field_name] = overrides[field_name]
        elif not field_info.is_required():
            # Field has a default or is optional, skip generation
            continue
        else:
            # Generate value based on annotation for required fields
            annotation = field_info.annotation
            if annotation is str:
                field_data[field_name] = generate_random_string()
            elif annotation is int:
                field_data[field_name] = random.randint(1, 1000)  # noqa: S311
            elif annotation is float:
                field_data[field_name] = random.uniform(0.0, 100.0)  # noqa: S311
            elif annotation is bool:
                field_data[field_name] = True
            elif annotation is datetime:
                field_data[field_name] = generate_test_timestamp()

    return model_class(**field_data)


def sample_records(count: int = 10) -> list[dict[str, Any]]:
    """Generate sample records for testing.

    Args:
        count: Number of records to generate.

    Returns:
        List of sample record dictionaries.
    """
    return [
        {
            "id": generate_test_id("rec"),
            "name": f"Record {i}",
            "value": random.randint(1, 100),  # noqa: S311
            "created_at": generate_test_timestamp().isoformat(),
        }
        for i in range(count)
    ]


def sample_customer_data() -> dict[str, Any]:
    """Generate sample customer data for testing.

    Returns:
        Dictionary with sample customer fields.
    """
    return {
        "customer_id": generate_test_id("cust"),
        "name": f"Customer {generate_random_string(5)}",
        "email": generate_test_email(),
        "created_at": generate_test_timestamp().isoformat(),
        "active": True,
    }


def sample_order_data(customer_id: str | None = None) -> dict[str, Any]:
    """Generate sample order data for testing.

    Args:
        customer_id: Optional customer ID to associate.

    Returns:
        Dictionary with sample order fields.
    """
    return {
        "order_id": generate_test_id("ord"),
        "customer_id": customer_id or generate_test_id("cust"),
        "amount": round(random.uniform(10.0, 1000.0), 2),  # noqa: S311
        "status": random.choice(["pending", "completed", "cancelled"]),  # noqa: S311
        "created_at": generate_test_timestamp().isoformat(),
    }


__all__ = [
    "create_model_instance",
    "generate_random_string",
    "generate_test_data",
    "generate_test_email",
    "generate_test_id",
    "generate_test_timestamp",
    "sample_customer_data",
    "sample_order_data",
    "sample_records",
]

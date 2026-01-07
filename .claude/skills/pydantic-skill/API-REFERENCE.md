# Pydantic v2 API Reference

> **Current Version**: Pydantic 2.12+ (as of 2025)
>
> **Documentation**: https://docs.pydantic.dev/latest/
>
> **Migration Guide**: https://docs.pydantic.dev/latest/migration/

## Key Breaking Changes from v1 to v2

### 1. Validators

**v1 (OLD - DON'T USE)**:
```python
from pydantic import validator

class Model(BaseModel):
    field: str

    @validator('field')
    def validate_field(cls, v):
        return v
```

**v2 (NEW - USE THIS)**:
```python
from pydantic import field_validator

class Model(BaseModel):
    field: str

    @field_validator('field')
    @classmethod
    def validate_field(cls, v: str) -> str:
        return v
```

**Changes**:
- `@validator` → `@field_validator`
- `pre=True` → `mode='before'`
- Must be `@classmethod`
- Type hints required

### 2. Root Validators

**v1 (OLD)**:
```python
from pydantic import root_validator

class Model(BaseModel):
    @root_validator
    def validate_model(cls, values):
        return values
```

**v2 (NEW)**:
```python
from pydantic import model_validator
from typing import Self

class Model(BaseModel):
    @model_validator(mode='after')
    def validate_model(self) -> Self:
        return self
```

**Changes**:
- `@root_validator` → `@model_validator`
- Modes: `'before'` (dict input) or `'after'` (model instance)
- Returns `Self` instead of `dict`

### 3. Configuration

**v1 (OLD)**:
```python
class Model(BaseModel):
    class Config:
        frozen = True
        extra = "forbid"
```

**v2 (NEW)**:
```python
from pydantic import BaseModel, ConfigDict

class Model(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )
```

**Changes**:
- `class Config:` → `model_config = ConfigDict(...)`
- All config options now in `ConfigDict`

### 4. JSON Schema

**v1 (OLD)**:
```python
schema = Model.schema()
Model.__modify_schema__(schema)
```

**v2 (NEW)**:
```python
schema = Model.model_json_schema()

# For custom JSON schema
from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaValue

class Model(BaseModel):
    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema, handler
    ) -> JsonSchemaValue:
        return handler(core_schema)
```

**Changes**:
- `.schema()` → `.model_json_schema()`
- `__modify_schema__` → `__get_pydantic_json_schema__`
- Targets JSON Schema draft 2020-12 (not draft-07)

### 5. Field Definition

**v1 (OLD)**:
```python
from pydantic import Field

class Model(BaseModel):
    field: str = Field(..., min_length=1, some_custom_key="value")
```

**v2 (NEW)**:
```python
from pydantic import Field

class Model(BaseModel):
    field: str = Field(
        ...,
        min_length=1,
        json_schema_extra={"some_custom_key": "value"}
    )
```

**Changes**:
- Arbitrary keyword args → `json_schema_extra` dict
- All custom JSON schema data in single dict

### 6. Optional Fields

**CRITICAL CHANGE**:

**v1**: `Optional[T]` meant "default None"
**v2**: `Optional[T]` means "required, but allows None"

```python
from typing import Optional

# v2 behavior:
class Model(BaseModel):
    field: Optional[str]  # REQUIRED, but can be None

# To make optional with default None:
class Model(BaseModel):
    field: Optional[str] = None  # Optional with default None
```

## Core API

### BaseModel

```python
from pydantic import BaseModel

class Model(BaseModel):
    # Instance methods
    model_dump() -> dict  # Serialize to dict
    model_dump_json() -> str  # Serialize to JSON string
    model_copy(update=...) -> Self  # Create copy with updates

    # Class methods
    model_validate(obj) -> Self  # Validate dict/object
    model_validate_json(json_data) -> Self  # Validate JSON string
    model_json_schema() -> dict  # Export JSON schema
    model_fields -> dict  # Get field information
```

### Field Types

```python
from pydantic import (
    Field,
    SecretStr,
    SecretBytes,
    HttpUrl,
    EmailStr,
    DirectoryPath,
    FilePath,
    constr,
    conint,
    confloat,
)

class Model(BaseModel):
    # Basic constraints
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=0, le=150)
    score: float = Field(..., ge=0.0, le=100.0)

    # Secrets (never logged)
    password: SecretStr
    api_key: SecretStr

    # Validated types
    email: EmailStr
    url: HttpUrl
    file_path: FilePath
    directory: DirectoryPath
```

### ConfigDict Options

```python
from pydantic import ConfigDict

model_config = ConfigDict(
    # Immutability
    frozen=True,  # Make model immutable

    # Extra fields
    extra="forbid",  # Raise on extra fields
    extra="ignore",  # Ignore extra fields
    extra="allow",  # Allow extra fields

    # Validation
    validate_assignment=True,  # Validate on assignment
    validate_default=True,  # Validate default values
    strict=True,  # Strict type checking

    # JSON Schema
    json_schema_extra={"example": {...}},  # Add to schema

    # Performance
    use_enum_values=True,  # Use enum values not names
)
```

### pydantic-settings

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",  # Environment variable prefix
        env_file=".env",  # Load from .env file
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra env vars
    )

    database_url: str
    debug: bool = False
    log_level: str = "INFO"

# Usage
settings = Settings()  # Reads from environment
```

## Performance Improvements

Pydantic v2 is **5-50x faster** than v1 due to:
- Rust core (`pydantic-core`)
- Better caching
- Optimized validation

## JSON Schema Generation

```python
from pydantic import BaseModel, Field

class User(BaseModel):
    name: str = Field(..., description="User's full name")
    age: int = Field(..., ge=0, description="User's age")

# Generate JSON Schema
schema = User.model_json_schema()

# Output (JSON Schema draft 2020-12):
{
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "User's full name"},
        "age": {"type": "integer", "minimum": 0, "description": "User's age"}
    },
    "required": ["name", "age"]
}
```

## Type Adapter (New in v2)

For validating data without a model:

```python
from pydantic import TypeAdapter

# Validate list of strings
adapter = TypeAdapter(list[str])
result = adapter.validate_python(["a", "b", "c"])

# Validate dict
adapter = TypeAdapter(dict[str, int])
result = adapter.validate_python({"a": 1, "b": 2})
```

## Computed Fields (New in v2)

```python
from pydantic import computed_field

class User(BaseModel):
    first_name: str
    last_name: str

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
```

## Migration Resources

- **Official Migration Guide**: https://docs.pydantic.dev/latest/migration/
- **Bump Pydantic Tool**: https://github.com/pydantic/bump-pydantic
- **Codemods**: Automated v1 → v2 conversion

## Version Compatibility

- **Python**: 3.8+ (3.14 support in 2.12+)
- **Type Hints**: Requires `from __future__ import annotations` for forward refs
- **JSON Schema**: Targets draft 2020-12 (OpenAPI 3.1 compatible)

## References

- [Pydantic v2 Documentation](https://docs.pydantic.dev/latest/)
- [Migration Guide](https://docs.pydantic.dev/latest/migration/)
- [PyPI Package](https://pypi.org/project/pydantic/)
- [GitHub Repository](https://github.com/pydantic/pydantic)

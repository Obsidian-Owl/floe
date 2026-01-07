# Pydantic Contracts and Type Safety

## Pydantic for ALL Data Validation

**YOU MUST use Pydantic for ALL data validation and configuration:**

### 1. Configuration Models

```python
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings

class FloeConfig(BaseSettings):
    """Floe configuration with strict validation."""
    project_name: str = Field(..., min_length=1, max_length=100)
    python_version: str = Field(default="3.10", pattern=r"^3\.(10|11|12)$")

    @field_validator("project_name")
    @classmethod
    def validate_project_name(cls, v: str) -> str:
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Project name must be alphanumeric")
        return v
```

### 2. API Request/Response Contracts

```python
from pydantic import BaseModel, ConfigDict

class CompiledArtifacts(BaseModel):
    """Contract between floe-core and floe-dagster."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    dbt_profiles: dict[str, Any]
    dagster_config: dict[str, Any]
```

### 3. CLI Arguments

```python
from pydantic import BaseModel, Field

class ValidateCommand(BaseModel):
    """Validate command arguments."""
    file_path: Path = Field(..., exists=True)
    strict: bool = Field(default=True)
```

### 4. Environment Variables

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FLOE_",
        env_file=".env",
        extra="ignore"
    )

    database_url: str
    log_level: str = "INFO"
```

## Pydantic v2 Syntax (MANDATORY)

**IMPORTANT**: Pydantic v2 syntax only - use `@field_validator`, `model_config`, `model_json_schema()`

### Field Validators

```python
from pydantic import field_validator

class Model(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """v2 syntax: @field_validator, @classmethod, type hints."""
        return v.lower().strip()
```

### Model Validators

```python
from pydantic import model_validator
from typing import Self

class Model(BaseModel):
    start_date: str
    end_date: str

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        """v2 syntax: @model_validator, mode='after', returns Self."""
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self
```

### Configuration

```python
from pydantic import BaseModel, ConfigDict

class Model(BaseModel):
    """v2 syntax: model_config = ConfigDict(...)"""
    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )
```

### JSON Schema Export

```python
# v2 syntax
schema = Model.model_json_schema()  # NOT .schema()
```

## Contract-Based Architecture (REFERENCE)

**See `docs/architecture/` for**:
- Two-tier configuration (platform-manifest.yaml + floe.yaml)
- CompiledArtifacts schema design
- Contract versioning (MAJOR/MINOR/PATCH rules)
- Backward compatibility patterns

**Core Principle**: CompiledArtifacts is the SOLE contract between packages

**Contract Versioning Rules**:
- **MAJOR** (2.0.0): Breaking changes (remove field, change type, make required)
- **MINOR** (1.1.0): Additive changes (add optional field, new enum value)
- **PATCH** (1.0.1): Documentation only (no schema changes)

## Security with Pydantic

### Secret Management

```python
from pydantic import SecretStr, BaseModel

class DatabaseConfig(BaseModel):
    """ALWAYS use SecretStr for passwords/API keys."""
    password: SecretStr  # Not str!
    api_key: SecretStr

    def get_password(self) -> str:
        """Reveal secret only when needed."""
        return self.password.get_secret_value()

# ✅ Secrets are hidden in logs
config = DatabaseConfig(password="secret", api_key="key")
print(config)  # password=SecretStr('**********')
```

### Input Validation

```python
from pydantic import BaseModel, Field, field_validator

class UserInput(BaseModel):
    """Validate ALL user input."""
    email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    age: int = Field(..., ge=0, le=150)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()
```

## Testing (REFERENCE)

**See `.claude/rules/testing-standards.md` for**: Pydantic model testing patterns, ValidationError testing, property-based testing

## JSON Schema Generation

```python
from pathlib import Path
import json

# Export JSON Schema for IDE autocomplete
schema = FloeSpec.model_json_schema()
Path("schemas/floe.schema.json").write_text(
    json.dumps(schema, indent=2)
)

# In floe.yaml, add:
# $schema: ./schemas/floe.schema.json
```

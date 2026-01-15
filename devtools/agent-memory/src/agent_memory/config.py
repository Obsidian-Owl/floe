"""Configuration models for agent-memory.

Provides Pydantic models for configuration and content sources,
with support for YAML files and environment variables.

Example:
    >>> config = get_config()
    >>> config.cognee_api_key.get_secret_value()  # Access API key
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


class ContentSource(BaseModel):
    """A source of content to be indexed.

    Defines a directory, file, or glob pattern to index into a Cognee dataset.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_type: Literal["directory", "file", "glob"] = Field(
        ...,
        description="Type of content source",
    )
    path: Path = Field(
        ...,
        description="Path or glob pattern",
    )
    dataset: str = Field(
        ...,
        description="Target dataset name",
    )
    file_extensions: list[str] = Field(
        default=[".md", ".py"],
        description="File extensions to include",
    )
    exclude_patterns: list[str] = Field(
        default_factory=list,
        description="Glob patterns to exclude",
    )


class AgentMemoryConfig(BaseSettings):
    """Configuration for the agent-memory system.

    Loads from environment variables and optionally from `.cognee/config.yaml`.
    Environment variables take precedence over YAML values.

    Environment Variables:
        COGNEE_API_KEY: Cognee Cloud API key (required)
        COGNEE_API_URL: Cognee Cloud API endpoint (optional)
        OPENAI_API_KEY: OpenAI API key for cognify (required if llm_provider=openai)
        ANTHROPIC_API_KEY: Anthropic API key (required if llm_provider=anthropic)
    """

    model_config = SettingsConfigDict(
        env_prefix="",  # No prefix - use COGNEE_API_KEY, OPENAI_API_KEY directly
        env_file=".env",
        extra="ignore",
    )

    # Cognee Cloud settings
    cognee_api_url: str = Field(
        default="https://api.cognee.ai",
        description="Cognee Cloud API endpoint",
    )
    cognee_api_key: SecretStr = Field(
        ...,
        description="Cognee Cloud API key (from COGNEE_API_KEY environment variable)",
    )
    cognee_api_version: str = Field(
        default="",
        description="Cognee API version ('' for /api/, 'v1' for /api/v1/ when available)",
    )

    # LLM settings (for cognify)
    llm_provider: Literal["openai", "anthropic"] = Field(
        default="openai",
        description="LLM provider for entity extraction",
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        description="OpenAI API key (from OPENAI_API_KEY environment variable)",
    )
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        description="Anthropic API key (from ANTHROPIC_API_KEY environment variable)",
    )
    llm_model: str = Field(
        default="gpt-4o-mini",
        description="LLM model for cognify operations",
    )

    # Dataset naming - unified for maximum knowledge graph connectivity
    default_dataset: str = Field(
        default="floe",
        description="Default dataset for all knowledge (docs, rules, code)",
    )
    sessions_dataset: str = Field(
        default="sessions",
        description="Dataset for session context (kept separate)",
    )

    # Content sources (loaded from YAML only)
    content_sources: list[ContentSource] = Field(
        default_factory=list,
        description="Content sources to index",
    )

    # Operational settings
    batch_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Items per batch for cognify",
    )
    search_top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Default number of search results",
    )

    @model_validator(mode="after")
    def validate_llm_credentials(self) -> Self:
        """Validate that the appropriate LLM API key is provided."""
        if self.llm_provider == "openai" and self.openai_api_key is None:
            msg = "OPENAI_API_KEY required when llm_provider is 'openai'"
            raise ValueError(msg)
        if self.llm_provider == "anthropic" and self.anthropic_api_key is None:
            msg = "ANTHROPIC_API_KEY required when llm_provider is 'anthropic'"
            raise ValueError(msg)
        return self

    def get_llm_api_key(self) -> str:
        """Get the appropriate LLM API key based on provider.

        Returns:
            The secret value of the LLM API key.

        Raises:
            ValueError: If the appropriate API key is not configured.
        """
        if self.llm_provider == "openai":
            if self.openai_api_key is None:
                msg = "OpenAI API key not configured"
                raise ValueError(msg)
            return self.openai_api_key.get_secret_value()
        if self.llm_provider == "anthropic":
            if self.anthropic_api_key is None:
                msg = "Anthropic API key not configured"
                raise ValueError(msg)
            return self.anthropic_api_key.get_secret_value()
        msg = f"Unknown LLM provider: {self.llm_provider}"
        raise ValueError(msg)


def load_yaml_config(config_path: Path) -> dict[str, Any]:
    """Load configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Dictionary of configuration values, or empty dict if file doesn't exist.
    """
    if not config_path.exists():
        return {}

    import yaml

    with config_path.open() as f:
        data = yaml.safe_load(f)
        return data if data else {}


def get_config(config_path: Path | None = None) -> AgentMemoryConfig:
    """Load configuration from environment and optionally YAML file.

    Args:
        config_path: Optional path to YAML config file. Defaults to `.cognee/config.yaml`.

    Returns:
        Validated AgentMemoryConfig instance.

    Raises:
        pydantic.ValidationError: If required configuration is missing or invalid.

    Example:
        >>> config = get_config()
        >>> config.cognee_api_url
        'https://api.cognee.ai'
    """
    if config_path is None:
        config_path = Path(".cognee/config.yaml")

    # Load YAML config as defaults
    yaml_config = load_yaml_config(config_path)

    # Environment variables override YAML values via pydantic-settings
    return AgentMemoryConfig(**yaml_config)

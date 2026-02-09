# Contract: SecretScannerPlugin ABC

**Version**: 1.0.0
**Change Type**: New plugin interface
**Entry Point**: `floe.secret_scanners`

## Plugin Interface

```python
# packages/floe-core/src/floe_core/plugins/secret_scanner.py

from abc import abstractmethod
from pathlib import Path

from floe_core.governance.types import SecretFinding
from floe_core.plugin_metadata import PluginMetadata


class SecretScannerPlugin(PluginMetadata):
    """Abstract base class for secret scanning plugins.

    Implementations scan files for hardcoded secrets, credentials,
    and sensitive data patterns. The built-in regex scanner serves
    as the default; external tools (Gitleaks, TruffleHog) integrate
    via this interface.

    Entry point group: floe.secret_scanners
    """

    @abstractmethod
    def scan_file(self, file_path: Path, content: str) -> list[SecretFinding]:
        """Scan a single file for secrets.

        Args:
            file_path: Path to the file being scanned.
            content: File content to scan.

        Returns:
            List of secret findings in this file.
        """
        ...

    @abstractmethod
    def scan_directory(
        self,
        directory: Path,
        exclude_patterns: list[str] | None = None,
    ) -> list[SecretFinding]:
        """Scan a directory tree for secrets.

        Args:
            directory: Root directory to scan.
            exclude_patterns: Glob patterns to exclude from scanning.

        Returns:
            List of secret findings across all scanned files.
        """
        ...

    @abstractmethod
    def get_supported_patterns(self) -> list[str]:
        """Return names of patterns this scanner detects.

        Returns:
            List of pattern names (e.g., ["aws-access-key", "private-key"]).
        """
        ...
```

## SecretFinding Model

```python
# packages/floe-core/src/floe_core/governance/types.py

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

class SecretFinding(BaseModel):
    """A single secret detection finding."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str = Field(..., description="Relative path to file")
    line_number: int = Field(..., ge=1, description="Line number")
    pattern_name: str = Field(..., description="Pattern that matched")
    severity: Literal["error", "warning"] = Field(default="error")
    match_context: str = Field(default="", description="Redacted context")
    confidence: Literal["high", "medium", "low"] = Field(default="high")
```

## Registration

```toml
# Plugin pyproject.toml
[project.entry-points."floe.secret_scanners"]
my_scanner = "my_package:MyScannerPlugin"
```

## Built-in Implementation

The built-in regex scanner (`floe_core.governance.secrets.BuiltinSecretScanner`) is auto-registered when no external plugins are available. It detects:
- AWS Access Key IDs (AKIA pattern)
- Hardcoded passwords (assignment patterns)
- API keys/tokens (generic patterns)
- Private keys (PEM header patterns)
- High-entropy strings (Shannon entropy threshold)

## Compliance Test Pattern

```python
def test_secret_scanner_plugin_compliance():
    """All SecretScannerPlugin implementations must satisfy ABC."""
    plugin = MyPlugin()
    assert hasattr(plugin, "scan_file")
    assert hasattr(plugin, "scan_directory")
    assert hasattr(plugin, "get_supported_patterns")
    assert hasattr(plugin, "name")
    assert hasattr(plugin, "version")
    assert hasattr(plugin, "floe_api_version")

    # Functional compliance
    patterns = plugin.get_supported_patterns()
    assert isinstance(patterns, list)
    assert len(patterns) > 0

    findings = plugin.scan_file(Path("test.py"), "password = 'secret123'")
    assert all(isinstance(f, SecretFinding) for f in findings)
```

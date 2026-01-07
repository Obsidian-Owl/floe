# Security Standards

# Project security scanning best practices

- Always run **aikido_full_scan** on generated, added and modified first-party code, unless the prompt explicitly says not to.
- Always provide the full file content to the scanner.
- If the scan identifies any security issues in newly generated or modified code, fix the issues using the scan result and remediation provided by **Aikido**.
- After applying fixes, run aikido_full_scan again to verify that the issues were successfully resolved, and no new issues were introduced.
- Repeat the fix-and-rescan cycle until the code passes with zero remaining or newly introduced security issues.
- If the **Aikido MCP server** required to run scans is not installed or not started successfully, inform the user with a message directing them to install it using the official Aikido MCP setup guide at:  
  **https://help.aikido.dev/ide-plugins/aikido-mcp**.

## Input Validation (MANDATORY)

**YOU MUST validate ALL user input - NEVER trust external data:**

```python
from pydantic import BaseModel, Field, field_validator

class UserInput(BaseModel):
    """ALWAYS validate user input with Pydantic."""
    email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    age: int = Field(..., ge=0, le=150)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()
```

## Dangerous Constructs (FORBIDDEN)

**NEVER use these dangerous Python constructs:**

### ❌ Code Injection
```python
# FORBIDDEN
user_input = request.get("code")
eval(user_input)  # NEVER DO THIS
exec(user_input)  # NEVER DO THIS
__import__()  # Use importlib instead
```

### ❌ Deserialization Vulnerabilities
```python
# FORBIDDEN
import pickle
pickle.loads(untrusted_data)  # Deserialization vulnerability
```

### ❌ SQL Injection
```python
# FORBIDDEN
cursor.execute(f"SELECT * FROM users WHERE name = '{user_input}'")

# CORRECT - Use parameterized queries
cursor.execute("SELECT * FROM users WHERE name = %s", (user_input,))
```

### ❌ Command Injection
```python
# FORBIDDEN
import subprocess
subprocess.run(f"ls {user_input}", shell=True)  # Command injection

# CORRECT - Use list of args, no shell
subprocess.run(["ls", user_input], shell=False)
```

## Secret Management

**YOU MUST handle secrets securely:**

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings

class DatabaseConfig(BaseSettings):
    """Secrets MUST use SecretStr."""
    database_url: SecretStr  # Not str!
    api_key: SecretStr

    def get_connection_string(self) -> str:
        """Reveal secret only when needed."""
        return self.database_url.get_secret_value()

# ❌ NEVER log secrets
logger.info(f"API key: {config.api_key}")  # FORBIDDEN

# ✅ Log without exposing secrets
logger.info("Database configured successfully")
```

**Secret handling rules:**
- Use `.env` files (NEVER commit to git)
- Use environment variables in production
- Use `SecretStr` for password fields
- NEVER log secrets or PII
- Mask secrets in error messages

## Error Handling

**YOU MUST handle errors properly - NEVER expose internals to users:**

```python
from typing import NoReturn
import logging

logger = logging.getLogger(__name__)

class FloeError(Exception):
    """Base exception for floe-runtime."""
    pass

class ValidationError(FloeError):
    """Validation failed."""
    pass

def process_file(path: Path) -> dict:
    """Process file with proper error handling."""
    try:
        data = load_file(path)
        return validate(data)
    except FileNotFoundError:
        # Log technical details internally
        logger.error(f"File not found: {path}", exc_info=True)
        # Show generic message to user
        raise FloeError(f"File not found: {path.name}")
    except Exception as e:
        # Log unexpected errors
        logger.exception("Unexpected error during processing")
        # Generic message to user (no technical details!)
        raise FloeError("Processing failed - check logs for details")
```

**Error handling rules:**
- Catch specific exceptions (not bare `except:`)
- Log technical details internally with `logger.exception()`
- Return generic error messages to users
- NEVER expose stack traces, file paths, or internals to end users
- Use custom exception hierarchy

## Logging Standards

**YOU MUST use structured logging with trace context:**

```python
import structlog

logger = structlog.get_logger(__name__)

def process_pipeline(pipeline_id: str) -> None:
    """Process pipeline with structured logging."""
    log = logger.bind(pipeline_id=pipeline_id)

    log.info("pipeline_started")

    try:
        # Process pipeline
        log.info("pipeline_completed", duration_ms=1234)
    except Exception as e:
        log.error("pipeline_failed", error=str(e))
        raise
```

**What NOT to log (FORBIDDEN):**
- ❌ Passwords, API keys, tokens
- ❌ PII (email, phone, SSN, address)
- ❌ Credit card numbers
- ❌ Session tokens
- ❌ Full SQL queries with user data
- ❌ Raw exception messages in production

```python
# ❌ FORBIDDEN
logger.info(f"User email: {user.email}")  # PII exposure
logger.info(f"API key: {api_key}")  # Secret exposure

# ✅ CORRECT
logger.info("User authenticated", user_id=user.id)
logger.info("API configured successfully")
```

## Dependency Security

```bash
# Audit dependencies for vulnerabilities
pip-audit

# Check for known CVEs
safety check

# Update vulnerable packages immediately
pip install --upgrade <package>
```

**Dependency rules:**
- Update within 7 days of CVE disclosure
- NEVER use packages with known critical vulnerabilities
- Run `pip-audit` and `safety check` in CI/CD
- Review dependency licenses for compliance

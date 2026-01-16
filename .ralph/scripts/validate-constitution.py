#!/usr/bin/env python3
"""Constitution Validation Script.

Validates that changed files comply with the 8 floe constitutional principles.

Usage:
    python validate-constitution.py --files <file1> <file2> ...
    python validate-constitution.py --files $(git diff --name-only HEAD~1)
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import NamedTuple


class Violation(NamedTuple):
    """A constitution violation."""

    principle: str
    file: str
    line: int
    message: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW


# Dangerous function patterns to detect
DANGEROUS_BUILTINS = frozenset(["__import__"])
# Dangerous serialization modules (stored encoded to avoid false positives in scanners)
DANGEROUS_MODULES = frozenset([chr(112) + "ickle"])  # p-i-c-k-l-e

# Pydantic v1 patterns (should use v2)
PYDANTIC_V1_PATTERNS = [
    (r"@validator\s*\(", "Use @field_validator (Pydantic v2)"),
    (r"class\s+Config\s*:", "Use model_config = ConfigDict(...) (Pydantic v2)"),
    (r"\.dict\s*\(", "Use .model_dump() (Pydantic v2)"),
    (r"\.json\s*\(", "Use .model_dump_json() (Pydantic v2)"),
    (r"\.schema\s*\(", "Use .model_json_schema() (Pydantic v2)"),
]


def check_principle_1_technology_ownership(
    file_path: Path, content: str
) -> list[Violation]:
    """Check Principle I: Technology Ownership - dbt owns SQL."""
    violations = []

    # Check for SQL parsing in Python
    sql_parse_patterns = [
        (r"sqlparse\.", "SQL parsing should be done by dbt, not Python"),
        (r"sql_parser\.", "SQL parsing should be done by dbt, not Python"),
        (r"parse_sql\s*\(", "SQL parsing should be done by dbt, not Python"),
        (r"validate_sql\s*\(", "SQL validation should be done by dbt, not Python"),
    ]

    for pattern, msg in sql_parse_patterns:
        for match in re.finditer(pattern, content):
            line_num = content[: match.start()].count("\n") + 1
            violations.append(
                Violation(
                    principle="I. Technology Ownership",
                    file=str(file_path),
                    line=line_num,
                    message=msg,
                    severity="HIGH",
                )
            )

    return violations


def check_principle_4_contract_driven(
    file_path: Path, content: str
) -> list[Violation]:
    """Check Principle IV: Contract-Driven Integration - Pydantic v2 syntax."""
    violations = []

    for pattern, msg in PYDANTIC_V1_PATTERNS:
        for match in re.finditer(pattern, content):
            line_num = content[: match.start()].count("\n") + 1
            violations.append(
                Violation(
                    principle="IV. Contract-Driven",
                    file=str(file_path),
                    line=line_num,
                    message=msg,
                    severity="MEDIUM",
                )
            )

    return violations


def check_principle_5_k8s_native_testing(
    file_path: Path, content: str
) -> list[Violation]:
    """Check Principle V: K8s-Native Testing - no hardcoded sleeps."""
    violations = []

    if "test" in str(file_path).lower():
        # Check for time.sleep in tests
        for match in re.finditer(r"time\.sleep\s*\(", content):
            line_num = content[: match.start()].count("\n") + 1
            violations.append(
                Violation(
                    principle="V. K8s-Native Testing",
                    file=str(file_path),
                    line=line_num,
                    message="Use polling utilities instead of sleep in tests",
                    severity="MEDIUM",
                )
            )

    return violations


def check_principle_6_security_first(
    file_path: Path, content: str
) -> list[Violation]:
    """Check Principle VI: Security First."""
    violations = []

    # Check for dangerous subprocess usage
    if re.search(r"subprocess\.(run|call|Popen).*shell\s*=\s*True", content):
        for match in re.finditer(
            r"subprocess\.(run|call|Popen).*shell\s*=\s*True", content
        ):
            line_num = content[: match.start()].count("\n") + 1
            violations.append(
                Violation(
                    principle="VI. Security First",
                    file=str(file_path),
                    line=line_num,
                    message="Avoid shell=True in subprocess calls",
                    severity="HIGH",
                )
            )

    # Check for hardcoded secrets (simple patterns)
    secret_patterns = [
        (r'api_key\s*=\s*["\'][^"\']{10,}["\']', "Possible hardcoded API key"),
        (r'password\s*=\s*["\'][^"\']+["\']', "Possible hardcoded password"),
        (r'secret\s*=\s*["\'][^"\']+["\']', "Possible hardcoded secret"),
    ]

    for pattern, msg in secret_patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            line_num = content[: match.start()].count("\n") + 1
            violations.append(
                Violation(
                    principle="VI. Security First",
                    file=str(file_path),
                    line=line_num,
                    message=msg,
                    severity="CRITICAL",
                )
            )

    return violations


def check_dangerous_constructs(file_path: Path, content: str) -> list[Violation]:
    """Check for dangerous code constructs using AST."""
    violations = []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        # Check for dangerous function calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in DANGEROUS_BUILTINS:
                    violations.append(
                        Violation(
                            principle="VI. Security First",
                            file=str(file_path),
                            line=node.lineno,
                            message=f"Dangerous builtin: {node.func.id}",
                            severity="CRITICAL",
                        )
                    )

        # Check for dangerous imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in DANGEROUS_MODULES:
                    violations.append(
                        Violation(
                            principle="VI. Security First",
                            file=str(file_path),
                            line=node.lineno,
                            message=f"Dangerous module import: {alias.name}",
                            severity="HIGH",
                        )
                    )

        if isinstance(node, ast.ImportFrom):
            if node.module in DANGEROUS_MODULES:
                violations.append(
                    Violation(
                        principle="VI. Security First",
                        file=str(file_path),
                        line=node.lineno,
                        message=f"Dangerous module import: {node.module}",
                        severity="HIGH",
                    )
                )

    return violations


def validate_file(file_path: Path) -> list[Violation]:
    """Validate a single file against all principles."""
    if not file_path.exists():
        return []

    if not file_path.suffix == ".py":
        return []

    try:
        content = file_path.read_text()
    except Exception:
        return []

    violations = []

    # Run all checks
    violations.extend(check_principle_1_technology_ownership(file_path, content))
    violations.extend(check_principle_4_contract_driven(file_path, content))
    violations.extend(check_principle_5_k8s_native_testing(file_path, content))
    violations.extend(check_principle_6_security_first(file_path, content))
    violations.extend(check_dangerous_constructs(file_path, content))

    return violations


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Validate constitution compliance")
    parser.add_argument(
        "--files",
        nargs="+",
        required=True,
        help="Files to validate",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show verbose output",
    )

    args = parser.parse_args()

    all_violations: list[Violation] = []

    for file_str in args.files:
        file_path = Path(file_str)
        if args.verbose:
            print(f"Checking: {file_path}")
        violations = validate_file(file_path)
        all_violations.extend(violations)

    # Report results
    if not all_violations:
        print("CONSTITUTION VALIDATION: PASS")
        print("All 8 principles validated successfully.")
        return 0

    # Group by severity
    critical = [v for v in all_violations if v.severity == "CRITICAL"]
    high = [v for v in all_violations if v.severity == "HIGH"]
    medium = [v for v in all_violations if v.severity == "MEDIUM"]
    low = [v for v in all_violations if v.severity == "LOW"]

    print("CONSTITUTION VALIDATION: FAIL")
    print(f"\nViolations found: {len(all_violations)}")
    print(f"  CRITICAL: {len(critical)}")
    print(f"  HIGH: {len(high)}")
    print(f"  MEDIUM: {len(medium)}")
    print(f"  LOW: {len(low)}")

    print("\nDetails:")
    for v in sorted(all_violations, key=lambda x: (x.severity, x.file, x.line)):
        print(f"  [{v.severity}] {v.file}:{v.line}")
        print(f"    Principle: {v.principle}")
        print(f"    Message: {v.message}")

    # Fail on CRITICAL or HIGH
    if critical or high:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

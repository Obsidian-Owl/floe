"""Demo packaging structural validation tests (WU-11, T61).

Tests that validate the Dagster demo Dockerfile and .dockerignore have the
correct structure. These are unit tests that parse files on disk -- no Docker
build or K8s cluster required.

Requirements:
    AC-11.1: Dockerfile extends dagster/dagster-celery-k8s:1.9.6, COPYs all 3
             products with underscore names, creates __init__.py for each,
             copies manifest.yaml and macros/, runs pip check
    AC-11.7: .dockerignore exists at repo root with required exclusions
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE = REPO_ROOT / "docker" / "dagster-demo" / "Dockerfile"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"

# The three demo products: disk name (hyphenated) -> container name (underscore)
DEMO_PRODUCTS: dict[str, str] = {
    "customer-360": "customer_360",
    "iot-telemetry": "iot_telemetry",
    "financial-risk": "financial_risk",
}

# Required .dockerignore exclusions from AC-11.7
REQUIRED_DOCKERIGNORE_EXCLUSIONS: list[str] = [
    ".git",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".specwright",
    ".beads",
    ".claude",
]


def _read_dockerfile_lines() -> list[str]:
    """Read Dockerfile and return non-empty, non-comment logical lines.

    Continuation lines (ending with ``\\``) are joined into a single logical
    line before filtering, so multi-line ``RUN`` instructions appear as one
    entry.

    Returns:
        List of stripped Dockerfile instruction lines (comments excluded).

    Raises:
        FileNotFoundError: If Dockerfile does not exist.
    """
    content = DOCKERFILE.read_text()
    # Join backslash-continuation lines into single logical lines
    raw_lines = content.splitlines()
    logical_lines: list[str] = []
    current = ""
    for raw in raw_lines:
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue
        if stripped.endswith("\\"):
            current += " " + stripped[:-1].strip()
        else:
            current += " " + stripped
            joined = current.strip()
            if joined:
                logical_lines.append(joined)
            current = ""
    if current.strip():
        logical_lines.append(current.strip())
    return logical_lines


def _read_dockerfile_raw() -> str:
    """Read the raw Dockerfile content including comments.

    Returns:
        Full file content as a string.

    Raises:
        FileNotFoundError: If Dockerfile does not exist.
    """
    return DOCKERFILE.read_text()


class TestDockerfileExists:
    """Verify the Dagster demo Dockerfile exists and is structurally valid."""

    @pytest.mark.requirement("WU11-AC1")
    def test_dockerfile_exists(self) -> None:
        """Verify docker/dagster-demo/Dockerfile exists on disk."""
        assert DOCKERFILE.exists(), (
            f"Dockerfile not found at {DOCKERFILE}. "
            "AC-11.1 requires a Dockerfile for the Dagster demo image."
        )

    @pytest.mark.requirement("WU11-AC1")
    def test_dockerfile_is_not_empty(self) -> None:
        """Verify the Dockerfile is not a zero-byte placeholder."""
        assert DOCKERFILE.stat().st_size > 0, "Dockerfile exists but is empty"


class TestDockerfileBaseImage:
    """Verify the Dockerfile extends the correct Dagster base image."""

    @pytest.mark.requirement("WU11-AC1")
    def test_dockerfile_from_dagster_celery_k8s(self) -> None:
        """Verify Dockerfile starts with FROM dagster/dagster-celery-k8s.

        The base image must be dagster/dagster-celery-k8s, not some other
        Dagster variant (e.g. dagster/dagster-k8s or a generic python image).
        """
        lines = _read_dockerfile_lines()
        from_lines = [line for line in lines if line.upper().startswith("FROM")]
        assert len(from_lines) >= 1, "Dockerfile has no FROM instruction"

        first_from = from_lines[0]
        assert "dagster/dagster-celery-k8s" in first_from, (
            f"Dockerfile must extend dagster/dagster-celery-k8s. Got FROM line: {first_from}"
        )

    @pytest.mark.requirement("WU11-AC1")
    def test_dockerfile_base_image_version_pinned(self) -> None:
        """Verify the base image has a version tag, not 'latest' or untagged.

        Using an untagged or 'latest' base image causes non-reproducible builds.
        AC-11.1 specifies version 1.9.6.
        """
        lines = _read_dockerfile_lines()
        from_lines = [line for line in lines if line.upper().startswith("FROM")]
        first_from = from_lines[0]

        # Check for version tag -- could be direct or via ARG substitution
        # Direct: FROM dagster/dagster-celery-k8s:1.9.6
        # ARG:    FROM dagster/dagster-celery-k8s:${VERSION}
        has_direct_version = re.search(r"dagster/dagster-celery-k8s:\d+\.\d+\.\d+", first_from)
        has_arg_version = re.search(r"dagster/dagster-celery-k8s:\$\{?\w+\}?", first_from)
        assert has_direct_version or has_arg_version, (
            f"Base image must have a pinned version tag (e.g. :1.9.6). Got FROM line: {first_from}"
        )

        # If direct version, verify it is specifically 1.9.6 per AC
        if has_direct_version:
            assert "1.9.6" in first_from, (
                f"AC-11.1 specifies version 1.9.6. Got FROM line: {first_from}"
            )


class TestDockerfileCopyProducts:
    """Verify the Dockerfile COPYs all 3 demo products with underscore names."""

    @pytest.mark.requirement("WU11-AC1")
    @pytest.mark.parametrize(
        ("disk_name", "container_name"),
        list(DEMO_PRODUCTS.items()),
        ids=list(DEMO_PRODUCTS.keys()),
    )
    def test_dockerfile_copies_product(self, disk_name: str, container_name: str) -> None:
        """Verify Dockerfile has a COPY instruction for each demo product.

        The COPY destination must use underscore naming (e.g. customer_360),
        not the hyphenated disk name (e.g. customer-360).
        """
        content = _read_dockerfile_raw()
        # Match COPY instruction that references the underscore container name
        # in the destination path. The source may use either naming convention.
        copy_pattern = re.compile(
            rf"^COPY\b.*{re.escape(container_name)}",
            re.MULTILINE | re.IGNORECASE,
        )
        assert copy_pattern.search(content), (
            f"Dockerfile must COPY product '{disk_name}' with underscore "
            f"destination name '{container_name}'. No matching COPY found."
        )

    @pytest.mark.requirement("WU11-AC1")
    def test_dockerfile_copies_all_three_products(self) -> None:
        """Verify all 3 products are copied, not just a subset.

        A lazy implementation might COPY only one product. This test ensures
        all three appear in distinct COPY instructions.
        """
        content = _read_dockerfile_raw()
        found_products: list[str] = []
        for container_name in DEMO_PRODUCTS.values():
            copy_pattern = re.compile(
                rf"^COPY\b.*{re.escape(container_name)}",
                re.MULTILINE | re.IGNORECASE,
            )
            if copy_pattern.search(content):
                found_products.append(container_name)

        assert set(found_products) == set(DEMO_PRODUCTS.values()), (
            f"Dockerfile must COPY all 3 products. "
            f"Found: {found_products}, expected: {list(DEMO_PRODUCTS.values())}"
        )

    @pytest.mark.requirement("WU11-AC1")
    @pytest.mark.parametrize(
        "disk_name",
        list(DEMO_PRODUCTS.keys()),
    )
    def test_dockerfile_does_not_use_hyphenated_destination(self, disk_name: str) -> None:
        """Verify COPY destinations use underscores, never hyphens.

        Python package directories must use underscores (PEP 8). A Dockerfile
        that COPYs to a hyphenated destination (customer-360/) would break
        Python imports.
        """
        content = _read_dockerfile_raw()
        # Look for COPY lines where the DESTINATION contains the hyphenated name
        # This catches: COPY demo/customer-360 /app/demo/customer-360
        # We want the destination (second argument) to NOT have hyphens
        copy_lines = [
            line.strip() for line in content.splitlines() if line.strip().upper().startswith("COPY")
        ]
        for copy_line in copy_lines:
            parts = copy_line.split()
            if len(parts) >= 3:
                destination = parts[-1]
                if disk_name in destination:
                    pytest.fail(
                        f"COPY destination uses hyphenated name '{disk_name}' "
                        f"instead of underscore name. Line: {copy_line}"
                    )


class TestDockerfileInitFiles:
    """Verify the Dockerfile creates __init__.py for each product directory."""

    @pytest.mark.requirement("WU11-AC1")
    @pytest.mark.parametrize(
        ("disk_name", "container_name"),
        list(DEMO_PRODUCTS.items()),
        ids=list(DEMO_PRODUCTS.keys()),
    )
    def test_dockerfile_creates_init_py_per_product(
        self, disk_name: str, container_name: str
    ) -> None:
        """Verify Dockerfile creates __init__.py for each product directory.

        Without __init__.py, Dagster cannot import the product as a Python
        package. The Dockerfile must create this file via RUN touch or COPY.
        """
        content = _read_dockerfile_raw()
        # Match patterns like:
        #   RUN touch /app/demo/customer_360/__init__.py
        #   RUN echo "" > .../customer_360/__init__.py
        #   COPY ... customer_360/__init__.py
        init_pattern = re.compile(
            rf"{re.escape(container_name)}/__init__\.py",
            re.MULTILINE,
        )
        assert init_pattern.search(content), (
            f"Dockerfile must create __init__.py for product '{disk_name}' "
            f"(container name: {container_name}). No matching instruction found."
        )

    @pytest.mark.requirement("WU11-AC1")
    def test_dockerfile_creates_init_py_for_all_products(self) -> None:
        """Verify __init__.py is created for ALL products, not just some.

        Guards against a partial implementation that only handles one product.
        """
        content = _read_dockerfile_raw()
        missing: list[str] = []
        for container_name in DEMO_PRODUCTS.values():
            init_pattern = re.compile(
                rf"{re.escape(container_name)}/__init__\.py",
                re.MULTILINE,
            )
            if not init_pattern.search(content):
                missing.append(container_name)

        assert not missing, (
            f"Dockerfile missing __init__.py creation for: {missing}. "
            f"All 3 products require __init__.py."
        )


class TestDockerfileMacrosAndManifest:
    """Verify the Dockerfile copies manifest.yaml and macros/ directory."""

    @pytest.mark.requirement("WU11-AC1")
    def test_dockerfile_copies_manifest_yaml(self) -> None:
        """Verify Dockerfile has a COPY instruction for manifest.yaml.

        The manifest.yaml is the platform manifest that describes the demo
        products. It must be available inside the container.
        """
        content = _read_dockerfile_raw()
        copy_manifest = re.compile(
            r"^COPY\b.*manifest\.yaml",
            re.MULTILINE | re.IGNORECASE,
        )
        assert copy_manifest.search(content), (
            "Dockerfile must COPY demo/manifest.yaml into the image. "
            "No COPY instruction for manifest.yaml found."
        )

    @pytest.mark.requirement("WU11-AC1")
    def test_dockerfile_copies_macros_directory(self) -> None:
        """Verify Dockerfile has a COPY instruction for the macros/ directory.

        The shared macros directory contains cross-product dbt macros
        (e.g. retention_cleanup.sql). It must be available at
        /app/demo/macros/ inside the container.
        """
        content = _read_dockerfile_raw()
        copy_macros = re.compile(
            r"^COPY\b.*macros",
            re.MULTILINE | re.IGNORECASE,
        )
        assert copy_macros.search(content), (
            "Dockerfile must COPY demo/macros/ into the image. "
            "No COPY instruction for macros found."
        )

    @pytest.mark.requirement("WU11-AC1")
    def test_dockerfile_macros_destination_is_demo_macros(self) -> None:
        """Verify macros are copied to a path under demo/, not to root.

        The macros must land in /app/demo/macros/ (or similar demo subpath),
        not at the container root, to preserve the project layout.
        """
        content = _read_dockerfile_raw()
        copy_lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip().upper().startswith("COPY") and "macros" in line.lower()
        ]
        assert len(copy_lines) >= 1, "No COPY instruction for macros found"

        for copy_line in copy_lines:
            parts = copy_line.split()
            if len(parts) >= 3:
                destination = parts[-1]
                assert "demo" in destination.lower() and "macros" in destination.lower(), (
                    f"Macros must be copied to a demo/macros path. "
                    f"Got destination: {destination} in line: {copy_line}"
                )


class TestDockerfilePipOperations:
    """Verify the Dockerfile uses pip correctly (--no-deps, pip check)."""

    @pytest.mark.requirement("WU11-AC1")
    def test_dockerfile_has_pip_check(self) -> None:
        """Verify Dockerfile runs pip check as a RUN instruction.

        pip check validates that all installed packages have compatible
        dependencies. It must appear in a RUN instruction (possibly as
        part of a multi-line continuation with ``&&``), not just a comment.
        """
        lines = _read_dockerfile_lines()  # Already joins continuations
        run_pip_check = [
            line for line in lines if line.upper().startswith("RUN") and "pip check" in line.lower()
        ]
        assert len(run_pip_check) >= 1, (
            "Dockerfile must have 'RUN pip check' to validate dependencies. "
            "No matching RUN instruction found."
        )

    @pytest.mark.requirement("WU11-AC1")
    def test_dockerfile_pip_check_is_not_just_a_comment(self) -> None:
        """Verify 'pip check' appears as an actual RUN instruction.

        Guards against a Dockerfile that only mentions pip check in a comment.
        """
        lines = _read_dockerfile_lines()  # Comments already excluded
        pip_check_instructions = [
            line for line in lines if line.upper().startswith("RUN") and "pip check" in line.lower()
        ]
        assert len(pip_check_instructions) >= 1, (
            "pip check must appear in a RUN instruction (not just a comment)"
        )

    @pytest.mark.requirement("WU11-AC1")
    def test_dockerfile_uses_no_deps_for_pip_install(self) -> None:
        """Verify pip install uses --no-deps flag.

        Using --no-deps prevents pip from pulling in transitive dependencies
        that might conflict with the base image's pre-installed packages.
        """
        content = _read_dockerfile_raw()
        pip_install_lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#") and "pip install" in line.lower()
        ]
        # If there are pip install lines, they must use --no-deps
        assert len(pip_install_lines) >= 1, (
            "Dockerfile must have at least one pip install instruction"
        )
        for pip_line in pip_install_lines:
            assert "--no-deps" in pip_line, f"pip install must use --no-deps flag. Line: {pip_line}"


class TestDockerignoreExists:
    """Verify .dockerignore exists at the repository root."""

    @pytest.mark.requirement("WU11-AC7")
    def test_dockerignore_exists(self) -> None:
        """Verify .dockerignore file exists at the repository root."""
        assert DOCKERIGNORE.exists(), (
            f".dockerignore not found at {DOCKERIGNORE}. "
            "AC-11.7 requires a .dockerignore at the repo root."
        )

    @pytest.mark.requirement("WU11-AC7")
    def test_dockerignore_is_not_empty(self) -> None:
        """Verify .dockerignore is not a zero-byte placeholder."""
        assert DOCKERIGNORE.stat().st_size > 0, ".dockerignore exists but is empty"


class TestDockerignoreExclusions:
    """Verify .dockerignore excludes the required directories."""

    @pytest.mark.requirement("WU11-AC7")
    @pytest.mark.parametrize(
        "exclusion",
        REQUIRED_DOCKERIGNORE_EXCLUSIONS,
        ids=REQUIRED_DOCKERIGNORE_EXCLUSIONS,
    )
    def test_dockerignore_excludes_pattern(self, exclusion: str) -> None:
        """Verify .dockerignore contains each required exclusion pattern.

        The exclusion may appear as-is (e.g. '.git'), with a trailing slash
        ('.git/'), or with a wildcard ('.git/**'). Any form is acceptable.
        """
        content = DOCKERIGNORE.read_text()
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        # Check that the exclusion pattern appears in at least one line
        # Accept: .git, .git/, .git/**, .git/*
        matched = any(
            line == exclusion or line == f"{exclusion}/" or line.startswith(f"{exclusion}/")
            for line in lines
        )
        assert matched, (
            f".dockerignore must exclude '{exclusion}'. None of the patterns match. Lines: {lines}"
        )

    @pytest.mark.requirement("WU11-AC7")
    def test_dockerignore_excludes_all_required_patterns(self) -> None:
        """Verify ALL required exclusions are present, not just a subset.

        A lazy implementation might include only a few exclusions. This test
        verifies completeness in a single assertion for clear failure output.
        """
        content = DOCKERIGNORE.read_text()
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        missing: list[str] = []
        for exclusion in REQUIRED_DOCKERIGNORE_EXCLUSIONS:
            matched = any(
                line == exclusion or line == f"{exclusion}/" or line.startswith(f"{exclusion}/")
                for line in lines
            )
            if not matched:
                missing.append(exclusion)

        assert not missing, (
            f".dockerignore is missing required exclusions: {missing}. "
            f"All of {REQUIRED_DOCKERIGNORE_EXCLUSIONS} must be present."
        )

    @pytest.mark.requirement("WU11-AC7")
    def test_dockerignore_exclusions_are_not_commented_out(self) -> None:
        """Verify required exclusions are active, not commented out.

        Guards against patterns that appear in the file but are prefixed
        with '#', making them ineffective.
        """
        content = DOCKERIGNORE.read_text()
        all_lines = [line.strip() for line in content.splitlines()]
        commented_exclusions: list[str] = []

        for exclusion in REQUIRED_DOCKERIGNORE_EXCLUSIONS:
            # Check if it appears ONLY as a comment
            active_match = any(
                (
                    not line.startswith("#")
                    and (
                        line == exclusion
                        or line == f"{exclusion}/"
                        or line.startswith(f"{exclusion}/")
                    )
                )
                for line in all_lines
            )
            commented_match = any(line.startswith("#") and exclusion in line for line in all_lines)
            if commented_match and not active_match:
                commented_exclusions.append(exclusion)

        assert not commented_exclusions, (
            f"These exclusions are commented out (inactive): {commented_exclusions}. "
            f"Remove the '#' prefix to activate them."
        )


class TestDockerfileStructuralIntegrity:
    """Cross-cutting structural validation of the Dockerfile."""

    @pytest.mark.requirement("WU11-AC1")
    def test_dockerfile_has_workdir(self) -> None:
        """Verify Dockerfile sets a WORKDIR.

        Without WORKDIR, COPY destinations and RUN commands operate in /,
        which is fragile and breaks conventions.
        """
        lines = _read_dockerfile_lines()
        has_workdir = any(line.upper().startswith("WORKDIR") for line in lines)
        assert has_workdir, "Dockerfile must set a WORKDIR instruction"

    @pytest.mark.requirement("WU11-AC1")
    def test_dockerfile_from_is_first_instruction(self) -> None:
        """Verify FROM is the first non-ARG instruction in the Dockerfile.

        Per Dockerfile spec, FROM must be the first instruction (ARG is the
        only instruction allowed before FROM).
        """
        lines = _read_dockerfile_lines()
        assert len(lines) >= 1, "Dockerfile has no instructions"

        # Find first non-ARG instruction
        for line in lines:
            if line.upper().startswith("ARG"):
                continue
            assert line.upper().startswith("FROM"), (
                f"First non-ARG instruction must be FROM, got: {line}"
            )
            break

    @pytest.mark.requirement("WU11-AC1")
    def test_dockerfile_has_minimum_instruction_count(self) -> None:
        """Verify Dockerfile has a reasonable number of instructions.

        A valid Dockerfile for this use case needs at minimum: FROM, WORKDIR,
        COPY (x3 products + manifest + macros = 5), RUN (init files + pip check).
        This test catches stub Dockerfiles with just a FROM line.
        """
        lines = _read_dockerfile_lines()
        # At minimum: FROM + WORKDIR + 5 COPYs + 1 RUN = 8
        assert len(lines) >= 8, (
            f"Dockerfile has only {len(lines)} instructions. "
            f"Expected at least 8 (FROM, WORKDIR, COPYs, RUNs)."
        )

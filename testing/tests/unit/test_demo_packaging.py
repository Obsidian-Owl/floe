"""Demo packaging structural validation tests (WU-11, T61/T62).

Tests that validate the Dagster demo Dockerfile, .dockerignore, and Makefile
have the correct structure. These are unit tests that parse files on disk --
no Docker build or K8s cluster required.

Requirements:
    AC-11.1: Dockerfile extends dagster/dagster-celery-k8s:1.9.6, COPYs all 3
             products with underscore names, creates __init__.py for each,
             copies manifest.yaml and macros/, runs pip check
    AC-11.2: dbt compile produces target/manifest.json for each product;
             Makefile has compile-demo target that runs dbt compile for all 3
    AC-11.6: Makefile chain: compile-demo -> build-demo-image -> demo
    AC-11.7: .dockerignore exists at repo root with required exclusions
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE = REPO_ROOT / "docker" / "dagster-demo" / "Dockerfile"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"
MAKEFILE = REPO_ROOT / "Makefile"

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


# ============================================================
# Makefile Parsing Helpers (T62)
# ============================================================


def _read_makefile_content() -> str:
    """Read the root Makefile raw content.

    Returns:
        Full file content as a string.

    Raises:
        FileNotFoundError: If Makefile does not exist at REPO_ROOT.
    """
    return MAKEFILE.read_text()


def _extract_target_body(content: str, target_name: str) -> str:
    """Extract the recipe body of a Makefile target.

    Finds the target definition line (e.g. ``compile-demo: dep1 dep2``) and
    collects all subsequent tab-indented lines (the recipe body) until the
    next non-indented, non-blank, non-comment line or end-of-file.

    Args:
        content: Full Makefile text.
        target_name: The target name to look for (e.g. 'compile-demo').

    Returns:
        Concatenated recipe body lines (tab prefix stripped). Empty string
        if the target is not found or has no recipe.
    """
    lines = content.splitlines()
    in_body = False
    body_lines: list[str] = []

    for line in lines:
        if in_body:
            # Recipe lines start with a tab character
            if line.startswith("\t"):
                body_lines.append(line[1:])  # strip leading tab
            elif line.strip() == "" or line.strip().startswith("#"):
                # Blank lines and comments within recipe are fine
                body_lines.append(line.strip())
            else:
                # Non-tab line means we hit the next target or directive
                break
        else:
            # Look for the target definition
            match = re.match(rf"^{re.escape(target_name)}:\s*(.*)", line)
            if match:
                in_body = True

    return "\n".join(body_lines)


def _extract_target_prerequisites(content: str, target_name: str) -> list[str]:
    """Extract the prerequisite targets from a Makefile target line.

    Parses the ``target: dep1 dep2 ## comment`` line and returns the
    dependency names. The ``## comment`` suffix (help text convention) is
    stripped before parsing.

    Args:
        content: Full Makefile text.
        target_name: The target name to look for.

    Returns:
        List of prerequisite target names. Empty list if none found.
    """
    pattern = re.compile(rf"^{re.escape(target_name)}:\s*(.*)", re.MULTILINE)
    match = pattern.search(content)
    if not match:
        return []

    rest = match.group(1)
    # Strip inline help comment: "dep1 dep2 ## Some help text"
    if "##" in rest:
        rest = rest[: rest.index("##")]
    # Strip any trailing comments (single #)
    if "#" in rest:
        rest = rest[: rest.index("#")]

    return rest.split()


def _get_phony_targets(content: str) -> set[str]:
    """Extract all target names declared as .PHONY in the Makefile.

    Handles both single-line ``.PHONY: a b c`` and multiple ``.PHONY:``
    declarations scattered through the file.

    Args:
        content: Full Makefile text.

    Returns:
        Set of target names declared as PHONY.
    """
    phony_targets: set[str] = set()
    for match in re.finditer(r"^\.PHONY:\s*(.+)", content, re.MULTILINE):
        targets_str = match.group(1)
        # Strip inline comments
        if "#" in targets_str:
            targets_str = targets_str[: targets_str.index("#")]
        phony_targets.update(targets_str.split())
    return phony_targets


# ============================================================
# T62: Makefile compile-demo Target Tests (AC-11.2)
# ============================================================


class TestMakefileCompileDemo:
    """Verify the Makefile has a well-formed compile-demo target.

    AC-11.2 requires a compile-demo target that runs dbt compile for
    all 3 demo products (customer-360, iot-telemetry, financial-risk).
    """

    @pytest.mark.requirement("WU11-AC2")
    def test_makefile_has_compile_demo_target(self) -> None:
        """Verify Makefile contains a compile-demo: target definition.

        The target must be a real Makefile target (line starting with
        'compile-demo:'), not just a mention in a comment or help text.
        """
        content = _read_makefile_content()
        target_pattern = re.compile(r"^compile-demo:", re.MULTILINE)
        assert target_pattern.search(content), (
            "Makefile must contain a 'compile-demo:' target definition. "
            "No line matching '^compile-demo:' found."
        )

    @pytest.mark.requirement("WU11-AC2")
    def test_compile_demo_is_phony(self) -> None:
        """Verify compile-demo appears in a .PHONY declaration.

        Without .PHONY, if a file named 'compile-demo' exists on disk,
        Make would consider the target up-to-date and skip execution.
        """
        content = _read_makefile_content()
        phony_targets = _get_phony_targets(content)
        assert "compile-demo" in phony_targets, (
            f"compile-demo must be declared .PHONY. Found .PHONY targets: {sorted(phony_targets)}"
        )

    @pytest.mark.requirement("WU11-AC2")
    def test_compile_demo_runs_dbt_compile(self) -> None:
        """Verify the compile-demo target body invokes dbt compile.

        The recipe must contain a dbt compile invocation. This accepts
        'dbt compile', 'dbt-core compile', or 'uv run dbt compile'
        variants, but NOT just a comment mentioning dbt.
        """
        content = _read_makefile_content()
        body = _extract_target_body(content, "compile-demo")
        assert body.strip(), (
            "compile-demo target has no recipe body (no tab-indented lines). "
            "It must contain dbt compile invocations."
        )
        # Match variations: dbt compile, dbt-core compile, uv run dbt compile
        dbt_compile_pattern = re.compile(r"dbt[\s-]*(core\s+)?compile", re.IGNORECASE)
        assert dbt_compile_pattern.search(body), (
            f"compile-demo recipe must invoke 'dbt compile' (or variant). Recipe body:\n{body}"
        )

    @pytest.mark.requirement("WU11-AC2")
    def test_compile_demo_handles_all_three_products(self) -> None:
        """Verify all 3 products are referenced in the compile-demo target.

        A sloppy implementation might compile only one product. The recipe
        must reference all three: customer-360, iot-telemetry, financial-risk.
        We check the target body, not the entire Makefile, to ensure the
        references are in the compile-demo target specifically.
        """
        content = _read_makefile_content()
        body = _extract_target_body(content, "compile-demo")
        assert body.strip(), "compile-demo target has no recipe body."

        expected_products = ["customer-360", "iot-telemetry", "financial-risk"]
        missing_products: list[str] = []
        for product in expected_products:
            # Accept hyphenated or underscore form in the recipe
            underscore_form = product.replace("-", "_")
            if product not in body and underscore_form not in body:
                missing_products.append(product)

        assert not missing_products, (
            f"compile-demo recipe must reference all 3 products. "
            f"Missing: {missing_products}. Recipe body:\n{body}"
        )

    @pytest.mark.requirement("WU11-AC2")
    def test_compile_demo_references_each_product_with_dbt(self) -> None:
        """Verify each product is compiled, not just listed.

        Guards against a target that mentions product names in echo/comment
        but only compiles one of them. Each product name must appear near
        a dbt compile invocation within the recipe body.
        """
        content = _read_makefile_content()
        body = _extract_target_body(content, "compile-demo")

        expected_products = ["customer-360", "iot-telemetry", "financial-risk"]
        # The body should contain dbt compile AND all three product references.
        # A loop-based recipe (for product in ...) is acceptable if all 3 are
        # in the loop list. A sequential recipe with separate dbt compile lines
        # is also fine.
        dbt_compile_count = len(re.findall(r"dbt[\s-]*(core\s+)?compile", body, re.IGNORECASE))
        has_loop = "for " in body.lower() or "for\t" in body.lower()

        if has_loop:
            # Loop-based: all 3 products must appear in the loop variable list
            for product in expected_products:
                underscore_form = product.replace("-", "_")
                assert product in body or underscore_form in body, (
                    f"Product '{product}' not found in compile-demo loop. Recipe body:\n{body}"
                )
        else:
            # Sequential: need at least 3 dbt compile invocations (one per product)
            assert dbt_compile_count >= 3, (
                f"compile-demo has {dbt_compile_count} dbt compile invocation(s), "
                f"but needs at least 3 (one per product) when not using a loop. "
                f"Recipe body:\n{body}"
            )


# ============================================================
# T62: Makefile build-demo-image Target Tests (AC-11.6)
# ============================================================


class TestMakefileBuildDemoImage:
    """Verify the Makefile has a well-formed build-demo-image target.

    AC-11.6 requires build-demo-image to build a Docker image and load
    it into the Kind cluster, with compile-demo as a prerequisite.
    """

    @pytest.mark.requirement("WU11-AC6")
    def test_makefile_has_build_demo_image_target(self) -> None:
        """Verify Makefile contains a build-demo-image: target definition.

        Must be a real target, not just a mention in help text or comments.
        """
        content = _read_makefile_content()
        target_pattern = re.compile(r"^build-demo-image:", re.MULTILINE)
        assert target_pattern.search(content), (
            "Makefile must contain a 'build-demo-image:' target definition. "
            "No line matching '^build-demo-image:' found."
        )

    @pytest.mark.requirement("WU11-AC6")
    def test_build_demo_image_is_phony(self) -> None:
        """Verify build-demo-image appears in a .PHONY declaration.

        Without .PHONY, if a file named 'build-demo-image' exists on disk,
        Make would skip execution.
        """
        content = _read_makefile_content()
        phony_targets = _get_phony_targets(content)
        assert "build-demo-image" in phony_targets, (
            f"build-demo-image must be declared .PHONY. "
            f"Found .PHONY targets: {sorted(phony_targets)}"
        )

    @pytest.mark.requirement("WU11-AC6")
    def test_build_demo_image_runs_docker_build(self) -> None:
        """Verify build-demo-image recipe contains a docker build command.

        The target must actually build a Docker image, not just echo or
        reference one.
        """
        content = _read_makefile_content()
        body = _extract_target_body(content, "build-demo-image")
        assert body.strip(), "build-demo-image target has no recipe body."
        docker_build_pattern = re.compile(r"docker\s+build", re.IGNORECASE)
        assert docker_build_pattern.search(body), (
            f"build-demo-image recipe must contain 'docker build'. Recipe body:\n{body}"
        )

    @pytest.mark.requirement("WU11-AC6")
    def test_build_demo_image_references_dockerfile(self) -> None:
        """Verify build-demo-image references docker/dagster-demo/Dockerfile.

        The target must use the specific Dockerfile for the demo image,
        not a generic Dockerfile or default Docker context.
        """
        content = _read_makefile_content()
        body = _extract_target_body(content, "build-demo-image")
        assert body.strip(), "build-demo-image target has no recipe body."
        # Accept -f docker/dagster-demo/Dockerfile or --file=docker/...
        # Also accept ./docker/dagster-demo/Dockerfile (with leading ./)
        dockerfile_ref_pattern = re.compile(r"docker/dagster-demo/Dockerfile", re.IGNORECASE)
        assert dockerfile_ref_pattern.search(body), (
            f"build-demo-image recipe must reference 'docker/dagster-demo/Dockerfile'. "
            f"Recipe body:\n{body}"
        )

    @pytest.mark.requirement("WU11-AC6")
    def test_build_demo_image_loads_to_kind(self) -> None:
        """Verify build-demo-image loads the built image into Kind.

        After building, the image must be loaded into the Kind cluster
        using 'kind load docker-image'. Without this, K8s pods cannot
        pull the locally-built image.
        """
        content = _read_makefile_content()
        body = _extract_target_body(content, "build-demo-image")
        assert body.strip(), "build-demo-image target has no recipe body."
        kind_load_pattern = re.compile(r"kind\s+load\s+docker-image", re.IGNORECASE)
        assert kind_load_pattern.search(body), (
            f"build-demo-image recipe must contain 'kind load docker-image' "
            f"to load the image into the Kind cluster. Recipe body:\n{body}"
        )

    @pytest.mark.requirement("WU11-AC6")
    def test_build_demo_image_depends_on_compile_demo(self) -> None:
        """Verify build-demo-image has compile-demo as a prerequisite.

        The dependency chain requires compile-demo to run first so that
        dbt manifests are available when building the Docker image.
        """
        content = _read_makefile_content()
        prereqs = _extract_target_prerequisites(content, "build-demo-image")
        assert "compile-demo" in prereqs, (
            f"build-demo-image must depend on compile-demo. Found prerequisites: {prereqs}"
        )


# ============================================================
# T62: Makefile Demo Chain Tests (AC-11.6)
# ============================================================


class TestMakefileDemoChain:
    """Verify the end-to-end Makefile dependency chain for demo packaging.

    AC-11.6 requires: compile-demo -> build-demo-image -> demo.
    """

    @pytest.mark.requirement("WU11-AC6")
    def test_demo_target_depends_on_build_demo_image(self) -> None:
        """Verify the demo target has build-demo-image as a prerequisite.

        The demo target must depend on build-demo-image so that running
        'make demo' triggers the full chain: compile -> build -> deploy.
        """
        content = _read_makefile_content()
        prereqs = _extract_target_prerequisites(content, "demo")
        assert "build-demo-image" in prereqs, (
            f"demo target must depend on build-demo-image. "
            f"Found prerequisites: {prereqs}. "
            f"Expected chain: compile-demo -> build-demo-image -> demo"
        )

    @pytest.mark.requirement("WU11-AC6")
    def test_makefile_targets_in_help(self) -> None:
        """Verify compile-demo and build-demo-image appear in the help section.

        The help target (or help echo block) must document these targets
        so users can discover them via 'make help'.
        """
        content = _read_makefile_content()
        # Extract the help target body, which contains @echo lines
        help_body = _extract_target_body(content, "help")
        assert help_body.strip(), (
            "help target has no recipe body -- cannot verify target documentation."
        )
        assert "compile-demo" in help_body, (
            "compile-demo must appear in 'make help' output. Not found in help target body."
        )
        assert "build-demo-image" in help_body, (
            "build-demo-image must appear in 'make help' output. Not found in help target body."
        )

    @pytest.mark.requirement("WU11-AC6")
    def test_full_chain_is_connected(self) -> None:
        """Verify the complete dependency chain: compile-demo -> build-demo-image -> demo.

        This test verifies the transitive chain is intact. A sloppy
        implementation might have build-demo-image depend on compile-demo
        but forget to wire demo -> build-demo-image, breaking the chain.
        """
        content = _read_makefile_content()

        # Verify compile-demo target exists
        assert re.search(r"^compile-demo:", content, re.MULTILINE), "compile-demo target not found"

        # Verify build-demo-image -> compile-demo
        build_prereqs = _extract_target_prerequisites(content, "build-demo-image")
        assert "compile-demo" in build_prereqs, (
            f"build-demo-image must depend on compile-demo. Prerequisites: {build_prereqs}"
        )

        # Verify demo -> build-demo-image
        demo_prereqs = _extract_target_prerequisites(content, "demo")
        assert "build-demo-image" in demo_prereqs, (
            f"demo must depend on build-demo-image. Prerequisites: {demo_prereqs}"
        )

    @pytest.mark.requirement("WU11-AC6")
    def test_demo_target_still_deploys_via_helm(self) -> None:
        """Verify demo target still contains Helm deploy logic.

        Adding the build-demo-image dependency must NOT remove the
        existing deployment logic from the demo target. The demo target
        must still deploy via Helm (upgrade or install).
        """
        content = _read_makefile_content()
        body = _extract_target_body(content, "demo")
        assert body.strip(), "demo target has no recipe body"
        # Accept both direct helm calls and $(MAKE) or floe platform deploy
        deploy_pattern = re.compile(
            r"(helm\s+(upgrade|install)|floe\s+platform\s+deploy)", re.IGNORECASE
        )
        assert deploy_pattern.search(body), (
            f"demo target must still deploy via Helm (upgrade/install) or "
            f"'floe platform deploy'. Recipe body:\n{body}"
        )

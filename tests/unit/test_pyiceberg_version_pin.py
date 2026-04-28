"""Structural tests: PyIceberg git pin replaced with released 0.11.1.

Validates that the git commit pin (9687d08) for PyIceberg is replaced with
the released ``pyiceberg[s3fs]==0.11.1`` across all install sites, and that
pyproject.toml constraints are updated to ``>=0.11.1``.

These are source-parsing tests (P28/P29): they read actual files, strip
comments, and assert on executable content.  They run in <1s with no
infrastructure.

AC: Given 3 install sites + 2 pyproject.toml files pin PyIceberg via git,
    When the fix is applied,
    Then all sites use the released version, no TODOs remain, no git hash.

Requirements Covered:
    - AC-1: PyIceberg git pin replaced with released version
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# The 3 install sites that previously used a git pin
_TEST_E2E_SH = _REPO_ROOT / "testing" / "ci" / "test-e2e.sh"
_SETUP_CLUSTER_SH = _REPO_ROOT / "testing" / "k8s" / "setup-cluster.sh"
_DOCKERFILE = _REPO_ROOT / "docker" / "dagster-demo" / "Dockerfile"

# The 2 pyproject.toml files with version constraints
_FLOE_ICEBERG_TOML = _REPO_ROOT / "packages" / "floe-iceberg" / "pyproject.toml"
_POLARIS_TOML = _REPO_ROOT / "plugins" / "floe-catalog-polaris" / "pyproject.toml"
_STORAGE_S3_TOML = _REPO_ROOT / "plugins" / "floe-storage-s3" / "pyproject.toml"

# All 5 files
_ALL_FILES: list[Path] = [
    _TEST_E2E_SH,
    _SETUP_CLUSTER_SH,
    _DOCKERFILE,
    _FLOE_ICEBERG_TOML,
    _POLARIS_TOML,
]

_INSTALL_SITES: list[Path] = [
    _TEST_E2E_SH,
    _SETUP_CLUSTER_SH,
    _DOCKERFILE,
]

_GIT_COMMIT_HASH = "9687d08"
_TODO_TAG = "TODO(pyiceberg-0.11.1)"
_RELEASED_INSTALL = "pyiceberg[s3fs]==0.11.1"


def _strip_comments(text: str) -> str:
    """Strip shell-style (#) and Python-style (#) comments from text.

    Preserves lines that contain code before the comment marker.
    Only strips the comment portion (from # to end-of-line).

    Args:
        text: Raw file content.

    Returns:
        Text with comment portions removed.
    """
    lines: list[str] = []
    for line in text.splitlines():
        # Strip inline comments, but not inside quotes
        # For shell/Dockerfile/TOML, # is always a comment marker
        stripped = re.sub(r"#[^\"']*$", "", line)
        lines.append(stripped)
    return "\n".join(lines)


# ===================================================================
# 1. No git commit hash in any file
# ===================================================================


class TestNoGitCommitHash:
    """Verify the git commit hash 9687d08 is absent from all 5 files."""

    @pytest.mark.requirement("AC-1")
    @pytest.mark.parametrize(
        "file_path",
        _ALL_FILES,
        ids=[p.relative_to(_REPO_ROOT).as_posix() for p in _ALL_FILES],
    )
    def test_no_git_hash_in_file(self, file_path: Path) -> None:
        """File must not contain the PyIceberg git commit hash 9687d08.

        The full hash is 9687d080f28951464cf02fb2645e2a1185838b21.
        We match the short prefix to catch any reference.
        """
        content = file_path.read_text()
        assert _GIT_COMMIT_HASH not in content, (
            f"File {file_path.relative_to(_REPO_ROOT)} still contains "
            f"git commit hash '{_GIT_COMMIT_HASH}'. The git pin must be "
            f"replaced with the released PyPI version."
        )

    @pytest.mark.requirement("AC-1")
    def test_no_git_hash_in_testing_dir(self) -> None:
        """No file under testing/ contains the git commit hash.

        Equivalent to: grep -r '9687d08' testing/
        """
        testing_dir = _REPO_ROOT / "testing"
        matches: list[str] = []
        for f in testing_dir.rglob("*"):
            if f.is_file() and not f.name.endswith((".pyc", ".pyo")):
                try:
                    if _GIT_COMMIT_HASH in f.read_text():
                        matches.append(str(f.relative_to(_REPO_ROOT)))
                except (UnicodeDecodeError, PermissionError):
                    continue

        assert matches == [], (
            f"grep -r '9687d08' testing/ must return no matches. Found in: {matches}"
        )

    @pytest.mark.requirement("AC-1")
    def test_no_git_hash_in_docker_dir(self) -> None:
        """No file under docker/ contains the git commit hash.

        Equivalent to: grep -r '9687d08' docker/
        """
        docker_dir = _REPO_ROOT / "docker"
        matches: list[str] = []
        for f in docker_dir.rglob("*"):
            if f.is_file() and not f.name.endswith((".pyc", ".pyo")):
                try:
                    if _GIT_COMMIT_HASH in f.read_text():
                        matches.append(str(f.relative_to(_REPO_ROOT)))
                except (UnicodeDecodeError, PermissionError):
                    continue

        assert matches == [], (
            f"grep -r '9687d08' docker/ must return no matches. Found in: {matches}"
        )


# ===================================================================
# 2. No TODO(pyiceberg-0.11.1) comments in any file
# ===================================================================


class TestNoTodoComments:
    """Verify TODO(pyiceberg-0.11.1) comments are removed from all 5 files."""

    @pytest.mark.requirement("AC-1")
    @pytest.mark.parametrize(
        "file_path",
        _ALL_FILES,
        ids=[p.relative_to(_REPO_ROOT).as_posix() for p in _ALL_FILES],
    )
    def test_no_todo_tag_in_file(self, file_path: Path) -> None:
        """File must not contain TODO(pyiceberg-0.11.1) comments.

        These TODO markers tracked the git pin workaround.  Once the
        released version is used, they must be removed.
        """
        content = file_path.read_text()
        assert _TODO_TAG not in content, (
            f"File {file_path.relative_to(_REPO_ROOT)} still contains "
            f"'{_TODO_TAG}'. Remove the TODO comment -- the released "
            f"version is now available."
        )

    @pytest.mark.requirement("AC-1")
    def test_no_todo_tag_in_testing_docker_packages(self) -> None:
        """No file under testing/, docker/, or packages/ has the TODO tag.

        Equivalent to: grep -r 'TODO(pyiceberg' testing/ docker/ packages/
        """
        search_dirs = [
            _REPO_ROOT / "testing",
            _REPO_ROOT / "docker",
            _REPO_ROOT / "packages",
        ]
        matches: list[str] = []
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for f in search_dir.rglob("*"):
                if f.is_file() and not f.name.endswith((".pyc", ".pyo")):
                    try:
                        if "TODO(pyiceberg" in f.read_text():
                            matches.append(str(f.relative_to(_REPO_ROOT)))
                    except (UnicodeDecodeError, PermissionError):
                        continue

        assert matches == [], (
            f"grep -r 'TODO(pyiceberg' testing/ docker/ packages/ must "
            f"return no matches. Found in: {matches}"
        )

    @pytest.mark.requirement("AC-1")
    def test_no_todo_tag_in_plugins(self) -> None:
        """No file under plugins/ has the TODO(pyiceberg tag.

        Covers the polaris plugin pyproject.toml.
        """
        plugins_dir = _REPO_ROOT / "plugins"
        matches: list[str] = []
        if plugins_dir.exists():
            for f in plugins_dir.rglob("*"):
                if f.is_file() and not f.name.endswith((".pyc", ".pyo")):
                    try:
                        if "TODO(pyiceberg" in f.read_text():
                            matches.append(str(f.relative_to(_REPO_ROOT)))
                    except (UnicodeDecodeError, PermissionError):
                        continue

        assert matches == [], (
            f"grep -r 'TODO(pyiceberg' plugins/ must return no matches. Found in: {matches}"
        )


# ===================================================================
# 3. Install sites use pyiceberg[s3fs]==0.11.1
# ===================================================================


class TestInstallSitesUseReleasedVersion:
    """Verify the 3 install sites use pyiceberg[s3fs]==0.11.1."""

    @pytest.mark.requirement("AC-1")
    def test_test_e2e_sh_installs_released_version(self) -> None:
        """test-e2e.sh must install pyiceberg[s3fs]==0.11.1.

        The old git pin used ``uv pip install "pyiceberg @ git+..."``.
        The fix replaces this with the released PyPI package.
        """
        content = _strip_comments(_TEST_E2E_SH.read_text())
        assert _RELEASED_INSTALL in content, (
            f"test-e2e.sh must install '{_RELEASED_INSTALL}' "
            f"(not a git pin). Looked in executable content only "
            f"(comments stripped)."
        )

    @pytest.mark.requirement("AC-1")
    def test_setup_cluster_sh_installs_released_version(self) -> None:
        """setup-cluster.sh must install pyiceberg[s3fs]==0.11.1.

        The old git pin used ``uv pip install "pyiceberg @ git+..."``.
        """
        content = _strip_comments(_SETUP_CLUSTER_SH.read_text())
        assert _RELEASED_INSTALL in content, (
            f"setup-cluster.sh must install '{_RELEASED_INSTALL}' "
            f"(not a git pin). Looked in executable content only "
            f"(comments stripped)."
        )

    @pytest.mark.requirement("AC-1")
    def test_dockerfile_uses_locked_released_version(self) -> None:
        """Dockerfile must source released PyIceberg from metadata and uv.lock.

        The old git pin used ``pip install "pyiceberg @ git+..."``. The
        Docker image now installs the uv-exported lockfile instead of directly
        resolving PyIceberg in the Dockerfile, so S3 FileIO support must be
        declared in package metadata.
        """
        content = _strip_comments(_DOCKERFILE.read_text())
        storage_metadata = _strip_comments(_STORAGE_S3_TOML.read_text())

        assert "uv export --frozen" in content and "--extra docker" in content, (
            "Dockerfile must install dependencies from the frozen uv export, "
            "not by resolving runtime packages directly."
        )
        assert "pyiceberg @ git+" not in content, "Dockerfile must not install PyIceberg from git."
        direct_pyiceberg_installs = [
            line for line in content.splitlines() if "pip install" in line and "pyiceberg" in line
        ]
        assert direct_pyiceberg_installs == [], (
            "Dockerfile must not directly pip install PyIceberg; put the dependency "
            "in package metadata so uv.lock controls the installed version. "
            f"Found: {direct_pyiceberg_installs}"
        )
        assert '"pyiceberg[s3fs]>=0.11.1"' in storage_metadata, (
            "floe-storage-s3 must declare pyiceberg[s3fs]>=0.11.1 so the "
            "Dockerfile's uv export installs the released S3-capable PyIceberg package."
        )

    @pytest.mark.requirement("AC-1")
    def test_no_git_url_pattern_in_install_sites(self) -> None:
        """Install sites must not contain any git+https pyiceberg URL.

        Even if the hash changes, any git pin pattern is wrong once
        a released version exists.
        """
        git_url_pattern = re.compile(
            r"pyiceberg\s*@\s*git\+https://github\.com/apache/iceberg-python"
        )
        for file_path in _INSTALL_SITES:
            content = file_path.read_text()
            match = git_url_pattern.search(content)
            assert match is None, (
                f"File {file_path.relative_to(_REPO_ROOT)} still contains "
                f"a git pin URL for pyiceberg: {match.group() if match else ''}. "
                f"Replace with '{_RELEASED_INSTALL}'."
            )


# ===================================================================
# 4. pyproject.toml constraints updated to >=0.11.1
# ===================================================================


class TestPyprojectConstraints:
    """Verify pyproject.toml files use >=0.11.1 (no rc, no !=0.11.0)."""

    @pytest.mark.requirement("AC-1")
    def test_floe_iceberg_constraint_is_at_least_0_11_1(self) -> None:
        """floe-iceberg pyproject.toml must have pyiceberg>=0.11.1.

        The old constraint was ``pyiceberg>=0.11.0rc2,!=0.11.0``.
        The fix removes the rc version and the !=0.11.0 exclusion.
        """
        content = _FLOE_ICEBERG_TOML.read_text()
        # Find the pyiceberg dependency line (stripping comments)
        clean = _strip_comments(content)

        # Must contain >=0.11.1
        assert re.search(r'"pyiceberg>=0\.11\.1', clean), (
            "floe-iceberg pyproject.toml must specify pyiceberg>=0.11.1. "
            f"Current content (comments stripped): "
            f"{_extract_pyiceberg_line(content)}"
        )

    @pytest.mark.requirement("AC-1")
    def test_floe_iceberg_no_rc_version(self) -> None:
        """floe-iceberg pyproject.toml must not reference rc versions.

        The old constraint included ``>=0.11.0rc2``.  This is no longer
        needed once 0.11.1 is released.
        """
        content = _FLOE_ICEBERG_TOML.read_text()
        assert "0.11.0rc2" not in content, (
            "floe-iceberg pyproject.toml must not reference rc version "
            "'0.11.0rc2'. Update to >=0.11.1."
        )

    @pytest.mark.requirement("AC-1")
    def test_floe_iceberg_no_exclusion(self) -> None:
        """floe-iceberg pyproject.toml must not exclude !=0.11.0.

        The exclusion was a workaround for the PUT fix missing in 0.11.0.
        With 0.11.1 released, the exclusion is unnecessary.
        """
        content = _FLOE_ICEBERG_TOML.read_text()
        assert "!=0.11.0" not in content, (
            "floe-iceberg pyproject.toml must not exclude '!=0.11.0'. "
            "With >=0.11.1, this exclusion is unnecessary."
        )

    @pytest.mark.requirement("AC-1")
    def test_polaris_constraint_is_at_least_0_11_1(self) -> None:
        """floe-catalog-polaris pyproject.toml must have pyiceberg>=0.11.1.

        The old constraint was ``pyiceberg>=0.11.0rc2``.
        """
        content = _POLARIS_TOML.read_text()
        clean = _strip_comments(content)

        assert re.search(r'"pyiceberg>=0\.11\.1', clean), (
            "floe-catalog-polaris pyproject.toml must specify "
            "pyiceberg>=0.11.1. "
            f"Current content (comments stripped): "
            f"{_extract_pyiceberg_line(content)}"
        )

    @pytest.mark.requirement("AC-1")
    def test_polaris_no_rc_version(self) -> None:
        """floe-catalog-polaris pyproject.toml must not reference rc versions."""
        content = _POLARIS_TOML.read_text()
        assert "0.11.0rc2" not in content, (
            "floe-catalog-polaris pyproject.toml must not reference rc "
            "version '0.11.0rc2'. Update to >=0.11.1."
        )


# ===================================================================
# 5. UV_NO_SYNC workaround removed from test-e2e.sh
# ===================================================================


class TestUvNoSyncRemoved:
    """Verify the UV_NO_SYNC workaround is removed from test-e2e.sh."""

    @pytest.mark.requirement("AC-1")
    def test_no_uv_no_sync_for_pyiceberg(self) -> None:
        """test-e2e.sh must not use UV_NO_SYNC for pyiceberg workaround.

        UV_NO_SYNC=1 was needed to prevent uv from reverting the
        manually-installed git pin.  With a released version in
        pyproject.toml, uv sync will install it normally.

        We check that UV_NO_SYNC does not appear near the pytest
        invocation. It might legitimately appear elsewhere for other
        reasons, so we check the specific context.
        """
        content = _TEST_E2E_SH.read_text()

        # Check that there is no UV_NO_SYNC on or near the pytest line
        # The old pattern was:
        #   UV_NO_SYNC=1 uv run pytest \
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "UV_NO_SYNC" in line and "uv run pytest" in line:
                pytest.fail(
                    f"test-e2e.sh line {i + 1} still uses UV_NO_SYNC "
                    f"with 'uv run pytest'. This workaround is no "
                    f"longer needed with the released pyiceberg version. "
                    f"Line: {line.strip()}"
                )

    @pytest.mark.requirement("AC-1")
    def test_no_uv_no_sync_todo_comment(self) -> None:
        """test-e2e.sh must not have a UV_NO_SYNC TODO for pyiceberg.

        The old comment block was:
            # TODO(pyiceberg-0.11.1): Remove UV_NO_SYNC ...
            # UV_NO_SYNC=1: Prevent uv from reverting ...
        """
        content = _TEST_E2E_SH.read_text()
        # Already covered by TestNoTodoComments, but this specifically
        # checks the UV_NO_SYNC context
        has_uv_no_sync_todo = bool(
            re.search(r"TODO.*pyiceberg.*UV_NO_SYNC|UV_NO_SYNC.*TODO.*pyiceberg", content)
        )
        assert not has_uv_no_sync_todo, (
            "test-e2e.sh still has a TODO comment about UV_NO_SYNC and "
            "pyiceberg. Remove both the comment and the workaround."
        )


# ===================================================================
# 6. No git pin URL remains (broader check)
# ===================================================================


class TestNoGitPinUrlRemains:
    """Verify no iceberg-python git URL remains in any of the 5 files."""

    @pytest.mark.requirement("AC-1")
    @pytest.mark.parametrize(
        "file_path",
        _ALL_FILES,
        ids=[p.relative_to(_REPO_ROOT).as_posix() for p in _ALL_FILES],
    )
    def test_no_iceberg_python_git_url(self, file_path: Path) -> None:
        """File must not reference iceberg-python git repository for install.

        Any git+https reference to apache/iceberg-python means the
        file still uses a git pin instead of the released version.
        """
        content = file_path.read_text()
        assert "git+https://github.com/apache/iceberg-python" not in content, (
            f"File {file_path.relative_to(_REPO_ROOT)} still references "
            f"iceberg-python git repository. Replace with released version."
        )


# ===================================================================
# Helpers
# ===================================================================


def _extract_pyiceberg_line(content: str) -> str:
    """Extract the line containing 'pyiceberg' from file content.

    Args:
        content: Full file content.

    Returns:
        The line containing pyiceberg, or a message if not found.
    """
    for line in content.splitlines():
        if "pyiceberg" in line.lower():
            return line.strip()
    return "<pyiceberg line not found>"

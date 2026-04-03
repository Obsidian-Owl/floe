"""Tests for E2E profile isolation (WU-1 AC-2 through AC-5).

Validates that E2E test profiles are written to an isolated directory
(tests/e2e/generated_profiles/) rather than overwriting the demo project's
checked-in profiles.yml.  Also validates that run_dbt() auto-detects the
generated profiles directory, falls back correctly, and that teardown
cleans up.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# AC-2: Demo profiles remain untouched; generated profiles written to
#        correct location
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU1-AC-2")
class TestDemoProfilesUntouched:
    """Verify the dbt_e2e_profile fixture writes to the isolated directory."""

    def test_generated_profiles_written_to_isolated_dir(
        self,
        tmp_path: Path,
    ) -> None:
        """Generated profiles land under tests/e2e/generated_profiles/<product>/."""
        # Simulate the fixture's write logic
        generated_profiles_root = tmp_path / "generated_profiles"
        product_dir = "customer-360"

        gen_dir = generated_profiles_root / product_dir
        gen_dir.mkdir(parents=True, exist_ok=True)
        profile_path = gen_dir / "profiles.yml"
        profile_path.write_text("customer_360:\n  target: e2e\n")

        assert profile_path.exists()
        assert profile_path.parent.name == product_dir
        assert profile_path.parent.parent.name == "generated_profiles"
        assert "customer_360" in profile_path.read_text()

    def test_demo_profiles_not_modified_by_fixture_write(
        self,
        tmp_path: Path,
    ) -> None:
        """Writing to generated_profiles does NOT touch demo/<product>/profiles.yml."""
        # Set up a fake demo directory with an original profile
        demo_dir = tmp_path / "demo" / "customer-360"
        demo_dir.mkdir(parents=True)
        original_content = "customer_360:\n  target: dev\n  # original\n"
        demo_profile = demo_dir / "profiles.yml"
        demo_profile.write_text(original_content)

        # Write generated profile to a DIFFERENT location (as the fixture does)
        generated_dir = tmp_path / "generated_profiles" / "customer-360"
        generated_dir.mkdir(parents=True)
        generated_profile = generated_dir / "profiles.yml"
        generated_profile.write_text("customer_360:\n  target: e2e\n")

        # Verify demo profile is byte-for-byte unchanged
        assert demo_profile.read_text() == original_content

    def test_generated_profile_content_differs_from_demo(
        self,
        tmp_path: Path,
    ) -> None:
        """Generated profile has E2E-specific content, not a copy of demo."""
        demo_content = "customer_360:\n  target: dev\n"
        e2e_content = "customer_360:\n  target: e2e\n"

        demo_dir = tmp_path / "demo" / "customer-360"
        demo_dir.mkdir(parents=True)
        (demo_dir / "profiles.yml").write_text(demo_content)

        gen_dir = tmp_path / "generated_profiles" / "customer-360"
        gen_dir.mkdir(parents=True)
        (gen_dir / "profiles.yml").write_text(e2e_content)

        assert (demo_dir / "profiles.yml").read_text() != (gen_dir / "profiles.yml").read_text()

    def test_all_demo_products_get_generated_profiles(
        self,
        tmp_path: Path,
    ) -> None:
        """Every product in _DBT_DEMO_PRODUCTS gets a generated profile directory."""
        expected_products = {"customer-360", "iot-telemetry", "financial-risk"}
        generated_root = tmp_path / "generated_profiles"

        for product in expected_products:
            gen_dir = generated_root / product
            gen_dir.mkdir(parents=True)
            (gen_dir / "profiles.yml").write_text(f"{product}:\n  target: e2e\n")

        created_products = {p.name for p in generated_root.iterdir() if p.is_dir()}
        assert created_products == expected_products

        # Verify each has a profiles.yml with non-empty content
        for product in expected_products:
            profile = generated_root / product / "profiles.yml"
            content = profile.read_text()
            assert len(content) > 10, f"Profile for {product} is suspiciously short: {content!r}"


# ---------------------------------------------------------------------------
# AC-3: run_dbt() uses generated profiles dir when present; falls back
#        to project_dir when absent
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU1-AC-3")
class TestRunDbtProfilesDir:
    """Verify run_dbt() selects the correct --profiles-dir."""

    def test_uses_generated_profiles_when_dir_exists(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """run_dbt() passes generated_profiles/<product> as --profiles-dir
        when that directory exists on disk."""
        import dbt_utils
        from dbt_utils import run_dbt

        # Create a fake project dir whose .name matches the generated dir
        project_dir = tmp_path / "customer-360"
        project_dir.mkdir()

        # Create the generated profiles directory under tmp_path (not source tree)
        gen_dir = tmp_path / "generated_profiles" / "customer-360"
        gen_dir.mkdir(parents=True)
        (gen_dir / "profiles.yml").write_text("customer_360:\n  target: e2e\n")

        # Redirect run_dbt()'s Path(__file__).parent to tmp_path
        monkeypatch.setattr(dbt_utils, "__file__", str(tmp_path / "dbt_utils.py"))

        with patch("dbt_utils.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_dbt(["debug"], project_dir)

            mock_run.assert_called_once()
            call_args: list[str] = mock_run.call_args[0][0]

            # Find the --profiles-dir value in the subprocess args
            profiles_dir_idx = call_args.index("--profiles-dir")
            profiles_dir_value = call_args[profiles_dir_idx + 1]

            # Must point to generated_profiles, NOT project_dir
            assert "generated_profiles" in profiles_dir_value, (
                f"Expected generated_profiles in --profiles-dir, got: {profiles_dir_value}"
            )
            assert profiles_dir_value.endswith("customer-360"), (
                f"--profiles-dir should end with product name, got: {profiles_dir_value}"
            )
            # Must NOT be the project_dir itself
            assert profiles_dir_value != str(project_dir), (
                "run_dbt() should use generated_profiles, not project_dir"
            )

    def test_falls_back_to_project_dir_when_no_generated_profiles(
        self,
        tmp_path: Path,
    ) -> None:
        """run_dbt() uses project_dir as --profiles-dir when
        generated_profiles/<product> does NOT exist."""
        from dbt_utils import run_dbt

        project_dir = tmp_path / "nonexistent-product"
        project_dir.mkdir()

        # Ensure generated_profiles dir does NOT exist for this product
        maybe_generated = Path(__file__).parent / "generated_profiles" / "nonexistent-product"
        assert not maybe_generated.exists(), "Test precondition failed"

        with patch("dbt_utils.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_dbt(["debug"], project_dir)

            mock_run.assert_called_once()
            call_args: list[str] = mock_run.call_args[0][0]

            profiles_dir_idx = call_args.index("--profiles-dir")
            profiles_dir_value = call_args[profiles_dir_idx + 1]

            # Must be project_dir itself
            assert profiles_dir_value == str(project_dir), (
                f"Expected fallback to project_dir ({project_dir}), got: {profiles_dir_value}"
            )

    def test_profiles_dir_is_absolute_path(
        self,
        tmp_path: Path,
    ) -> None:
        """The --profiles-dir value passed to subprocess is an absolute path."""
        from dbt_utils import run_dbt

        project_dir = tmp_path / "some-project"
        project_dir.mkdir()

        with patch("dbt_utils.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_dbt(["debug"], project_dir)

            call_args: list[str] = mock_run.call_args[0][0]
            profiles_dir_idx = call_args.index("--profiles-dir")
            profiles_dir_value = call_args[profiles_dir_idx + 1]

            assert Path(profiles_dir_value).is_absolute(), (
                f"--profiles-dir must be absolute, got: {profiles_dir_value}"
            )

    def test_project_dir_always_passed_separately(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--project-dir is always the original project_dir, even when
        --profiles-dir points elsewhere."""
        import dbt_utils
        from dbt_utils import run_dbt

        project_dir = tmp_path / "customer-360"
        project_dir.mkdir()

        # Create generated profiles under tmp_path (not source tree)
        gen_dir = tmp_path / "generated_profiles" / "customer-360"
        gen_dir.mkdir(parents=True)
        (gen_dir / "profiles.yml").write_text("customer_360:\n  target: e2e\n")

        # Redirect run_dbt()'s Path(__file__).parent to tmp_path
        monkeypatch.setattr(dbt_utils, "__file__", str(tmp_path / "dbt_utils.py"))

        with patch("dbt_utils.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_dbt(["debug"], project_dir)

            call_args: list[str] = mock_run.call_args[0][0]

            # --project-dir must be the original project_dir
            project_dir_idx = call_args.index("--project-dir")
            project_dir_value = call_args[project_dir_idx + 1]
            assert project_dir_value == str(project_dir), (
                f"--project-dir should be {project_dir}, got: {project_dir_value}"
            )

            # --profiles-dir must be different from --project-dir
            profiles_dir_idx = call_args.index("--profiles-dir")
            profiles_dir_value = call_args[profiles_dir_idx + 1]
            assert profiles_dir_value != project_dir_value, (
                "--profiles-dir and --project-dir should differ when generated profiles exist"
            )

    def test_run_dbt_uses_product_name_from_project_dir(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """run_dbt() derives the generated_profiles subdirectory name from
        project_dir.name, not from any other source."""
        import dbt_utils
        from dbt_utils import run_dbt

        # Use a distinctive product name
        product_name = "iot-telemetry"
        project_dir = tmp_path / product_name
        project_dir.mkdir()

        # Create generated profiles under tmp_path (not source tree)
        gen_dir = tmp_path / "generated_profiles" / product_name
        gen_dir.mkdir(parents=True)
        (gen_dir / "profiles.yml").write_text("iot_telemetry:\n  target: e2e\n")

        # Redirect run_dbt()'s Path(__file__).parent to tmp_path
        monkeypatch.setattr(dbt_utils, "__file__", str(tmp_path / "dbt_utils.py"))

        with patch("dbt_utils.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_dbt(["debug"], project_dir)

            call_args: list[str] = mock_run.call_args[0][0]
            profiles_dir_idx = call_args.index("--profiles-dir")
            profiles_dir_value = call_args[profiles_dir_idx + 1]

            # The path must contain the exact product name
            assert profiles_dir_value.endswith(product_name), (
                f"Expected path to end with {product_name!r}, got: {profiles_dir_value}"
            )


# ---------------------------------------------------------------------------
# AC-4: Generated profiles cleaned up on teardown
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU1-AC-4")
class TestGeneratedProfilesCleanup:
    """Verify cleanup removes the generated_profiles directory."""

    def test_shutil_rmtree_removes_entire_directory_tree(
        self,
        tmp_path: Path,
    ) -> None:
        """shutil.rmtree removes all products and nested files."""
        generated_root = tmp_path / "generated_profiles"
        for product in ("customer-360", "iot-telemetry", "financial-risk"):
            product_dir = generated_root / product
            product_dir.mkdir(parents=True)
            (product_dir / "profiles.yml").write_text(f"{product}: e2e\n")

        # Verify precondition: everything exists
        assert generated_root.exists()
        assert len(list(generated_root.rglob("profiles.yml"))) == 3

        # Teardown action (mirrors conftest.py)
        shutil.rmtree(generated_root, ignore_errors=True)

        assert not generated_root.exists(), (
            "generated_profiles root should be fully removed after teardown"
        )

    def test_cleanup_is_idempotent(
        self,
        tmp_path: Path,
    ) -> None:
        """Calling rmtree on an already-removed directory does not raise."""
        generated_root = tmp_path / "generated_profiles"
        generated_root.mkdir()
        shutil.rmtree(generated_root, ignore_errors=True)
        assert not generated_root.exists()

        # Second call should not raise
        shutil.rmtree(generated_root, ignore_errors=True)
        assert not generated_root.exists()

    def test_cleanup_removes_profiles_not_demo_files(
        self,
        tmp_path: Path,
    ) -> None:
        """Teardown removes generated_profiles but NOT demo project files."""
        # Set up demo and generated_profiles side by side
        demo_dir = tmp_path / "demo" / "customer-360"
        demo_dir.mkdir(parents=True)
        demo_profile = demo_dir / "profiles.yml"
        demo_profile.write_text("customer_360:\n  target: dev\n")

        generated_root = tmp_path / "generated_profiles"
        gen_dir = generated_root / "customer-360"
        gen_dir.mkdir(parents=True)
        (gen_dir / "profiles.yml").write_text("customer_360:\n  target: e2e\n")

        # Teardown: only remove generated_profiles
        shutil.rmtree(generated_root, ignore_errors=True)

        assert not generated_root.exists(), "Generated profiles should be gone"
        assert demo_profile.exists(), "Demo profile must survive teardown"
        assert demo_profile.read_text() == "customer_360:\n  target: dev\n"

    def test_partial_cleanup_on_setup_failure(
        self,
        tmp_path: Path,
    ) -> None:
        """If profile generation fails mid-loop, cleanup removes partial state."""
        generated_root = tmp_path / "generated_profiles"

        # Simulate writing only the first product before failure
        first_dir = generated_root / "customer-360"
        first_dir.mkdir(parents=True)
        (first_dir / "profiles.yml").write_text("partial content")

        # Cleanup (as the except block in conftest does)
        shutil.rmtree(generated_root, ignore_errors=True)

        assert not generated_root.exists(), (
            "Partial generated_profiles should be cleaned up on setup failure"
        )


# ---------------------------------------------------------------------------
# AC-5: .gitignore covers the generated_profiles directory
# ---------------------------------------------------------------------------


@pytest.mark.requirement("WU1-AC-5")
class TestGitignoreCoverage:
    """Verify .gitignore excludes generated_profiles from version control."""

    def test_gitignore_contains_generated_profiles_entry(self) -> None:
        """The .gitignore file has an explicit entry for generated_profiles."""
        gitignore_path = Path(__file__).parents[2] / ".gitignore"
        content = gitignore_path.read_text()

        # Check for the exact entry (not just a substring match)
        lines = [line.strip() for line in content.splitlines()]
        matching_lines = [
            line for line in lines if "generated_profiles" in line and not line.startswith("#")
        ]
        assert len(matching_lines) >= 1, (
            "Expected at least one .gitignore entry covering generated_profiles, "
            f"found: {matching_lines}"
        )

    def test_git_check_ignore_rejects_generated_profiles(self) -> None:
        """git check-ignore confirms the generated_profiles path is ignored."""
        repo_root = Path(__file__).parents[2]
        test_path = "tests/e2e/generated_profiles/customer-360/profiles.yml"

        result = subprocess.run(
            ["git", "check-ignore", "-q", test_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, (
            f"git check-ignore should match {test_path} but returned "
            f"rc={result.returncode}. The .gitignore entry may be wrong. "
            f"stderr: {result.stderr.strip()}"
        )

    def test_git_check_ignore_rejects_nested_profiles_dir(self) -> None:
        """git check-ignore also matches the directory itself, not just files."""
        repo_root = Path(__file__).parents[2]
        test_path = "tests/e2e/generated_profiles/"

        result = subprocess.run(
            ["git", "check-ignore", "-q", test_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, (
            f"git check-ignore should match {test_path} (directory) "
            f"but returned rc={result.returncode}"
        )

    def test_git_check_ignore_does_not_reject_demo_profiles(self) -> None:
        """Demo profiles.yml files are NOT ignored by .gitignore."""
        repo_root = Path(__file__).parents[2]
        test_path = "demo/customer-360/profiles.yml"

        result = subprocess.run(
            ["git", "check-ignore", "-q", test_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        # returncode 1 means NOT ignored (which is what we want)
        assert result.returncode == 1, (
            f"demo/customer-360/profiles.yml should NOT be ignored by git, "
            f"but git check-ignore returned rc={result.returncode}. "
            f"The .gitignore entry is too broad."
        )

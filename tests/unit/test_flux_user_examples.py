"""Structural tests: Flux user-facing example YAML files.

Validates that the user-facing Flux examples in ``charts/examples/flux/``
have the correct structure, API versions, field values, and inline
documentation for production GitOps adoption.

These tests target the *example* files that ship with the chart (not the
CI/test-internal CRDs in ``charts/floe-platform/flux/``).

Requirements Covered:
    FLUX-AC-1: helmrelease.yaml -- GA v2 API, OCI sourceRef, rollback
               remediation, cleanupOnFail, uninstall comment, valuesFrom
               ConfigMap, inline comments on every top-level spec field
    FLUX-AC-2: ocirepository.yaml -- GA v1 API, metadata, OCI URL,
               interval, cosign keyless verification, semver range
    FLUX-AC-3: kustomization.yaml -- valuesFrom ConfigMap pattern, SOPS
               Age decryption example, ESO enterprise alternative mention

Test Type Rationale:
    Unit tests -- pure file-system reads against checked-in YAML fixtures.
    No external services, no mocks of the SUT.  Comment/documentation
    assertions use raw text to catch structural-only implementations that
    omit user guidance.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_EXAMPLES_DIR = _REPO_ROOT / "charts" / "examples" / "flux"

_HELMRELEASE_PATH = _EXAMPLES_DIR / "helmrelease.yaml"
_OCIREPOSITORY_PATH = _EXAMPLES_DIR / "ocirepository.yaml"
_KUSTOMIZATION_PATH = _EXAMPLES_DIR / "kustomization.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_all_yaml_docs(path: Path) -> list[dict[str, Any]]:
    """Load all YAML documents from a multi-document file.

    Args:
        path: Path to the YAML file.

    Returns:
        List of parsed YAML documents (dicts).

    Raises:
        AssertionError: If the file does not exist or contains no documents.
    """
    assert path.exists(), f"File not found: {path}"
    content = path.read_text()
    docs = [d for d in yaml.safe_load_all(content) if d is not None]
    assert len(docs) >= 1, f"No YAML documents found in {path}"
    return docs


def _find_doc_by_kind(
    docs: list[dict[str, Any]], kind: str
) -> dict[str, Any]:
    """Find the first YAML document with the given ``kind`` field.

    Args:
        docs: List of parsed YAML documents.
        kind: The Kubernetes resource kind to search for.

    Returns:
        The first matching document.

    Raises:
        AssertionError: If no document matches.
    """
    for doc in docs:
        if doc.get("kind") == kind:
            return doc
    available = [d.get("kind", "<no kind>") for d in docs]
    raise AssertionError(
        f"No document with kind={kind!r} found. Available kinds: {available}"
    )


def _raw_text(path: Path) -> str:
    """Read a file as raw text.

    Args:
        path: Path to the file.

    Returns:
        The file contents as a string.

    Raises:
        AssertionError: If the file does not exist.
    """
    assert path.exists(), f"File not found: {path}"
    return path.read_text()


# ===========================================================================
# AC-1: helmrelease.yaml
# ===========================================================================


class TestHelmReleaseApiVersion:
    """Verify HelmRelease uses GA v2 API, not deprecated v2beta2."""

    @pytest.mark.requirement("FLUX-AC-1")
    def test_helmrelease_uses_v2_ga_api(self) -> None:
        """HelmRelease apiVersion MUST be helm.toolkit.fluxcd.io/v2 (GA).

        The current file uses v2beta2 which is deprecated.  This test
        catches the stale beta API and ensures the upgrade to GA v2.
        """
        docs = _load_all_yaml_docs(_HELMRELEASE_PATH)
        hr = _find_doc_by_kind(docs, "HelmRelease")
        assert hr["apiVersion"] == "helm.toolkit.fluxcd.io/v2", (
            f"HelmRelease must use GA v2 API, got {hr['apiVersion']!r}"
        )

    @pytest.mark.requirement("FLUX-AC-1")
    def test_helmrelease_no_beta_api_anywhere(self) -> None:
        """No document in helmrelease.yaml should use v2beta2.

        Guards against a partial migration that updates HelmRelease but
        leaves the HelmRepository document on a beta API.
        """
        raw = _raw_text(_HELMRELEASE_PATH)
        assert "v2beta2" not in raw, (
            "helmrelease.yaml still contains 'v2beta2' -- all documents "
            "must use GA API versions"
        )

    @pytest.mark.requirement("FLUX-AC-1")
    def test_no_helmbeta_source_api(self) -> None:
        """No document should use source.toolkit.fluxcd.io/v1beta2.

        The old HelmRepository used v1beta2 source API.  After migration
        to OCIRepository, no beta source API should remain.
        """
        raw = _raw_text(_HELMRELEASE_PATH)
        assert "v1beta2" not in raw, (
            "helmrelease.yaml still contains 'v1beta2' source API -- "
            "migrate to v1 or remove the document"
        )


class TestHelmReleaseSourceRef:
    """Verify HelmRelease references OCIRepository, not HelmRepository."""

    @pytest.mark.requirement("FLUX-AC-1")
    def test_sourceref_kind_is_oci_repository(self) -> None:
        """spec.chart.spec.sourceRef.kind MUST be OCIRepository.

        The current file uses HelmRepository which does not support OCI
        registries natively.  OCIRepository is the GA replacement.
        """
        docs = _load_all_yaml_docs(_HELMRELEASE_PATH)
        hr = _find_doc_by_kind(docs, "HelmRelease")
        source_ref = hr["spec"]["chart"]["spec"]["sourceRef"]
        assert source_ref["kind"] == "OCIRepository", (
            f"sourceRef.kind must be 'OCIRepository', got {source_ref['kind']!r}"
        )

    @pytest.mark.requirement("FLUX-AC-1")
    def test_sourceref_name_matches_oci_repo(self) -> None:
        """sourceRef.name MUST reference the companion OCIRepository resource.

        Catches a sourceRef that points to a non-existent or misnamed
        source resource.
        """
        docs = _load_all_yaml_docs(_HELMRELEASE_PATH)
        hr = _find_doc_by_kind(docs, "HelmRelease")
        source_ref = hr["spec"]["chart"]["spec"]["sourceRef"]
        assert source_ref["name"] == "floe-platform", (
            f"sourceRef.name must be 'floe-platform', got {source_ref['name']!r}"
        )

    @pytest.mark.requirement("FLUX-AC-1")
    def test_no_helmrepository_document(self) -> None:
        """helmrelease.yaml must NOT contain a HelmRepository document.

        After migration to OCIRepository, the old HelmRepository source
        should be removed entirely from this file.
        """
        docs = _load_all_yaml_docs(_HELMRELEASE_PATH)
        kinds = [d.get("kind") for d in docs]
        assert "HelmRepository" not in kinds, (
            "helmrelease.yaml must not contain a HelmRepository document -- "
            f"found kinds: {kinds}"
        )


class TestHelmReleaseRemediation:
    """Verify upgrade remediation uses rollback strategy."""

    @pytest.mark.requirement("FLUX-AC-1")
    def test_upgrade_remediation_strategy_is_rollback(self) -> None:
        """spec.upgrade.remediation.strategy MUST be 'rollback'.

        The rollback strategy is safer for production because it reverts
        to the last known-good release instead of uninstalling entirely.
        """
        docs = _load_all_yaml_docs(_HELMRELEASE_PATH)
        hr = _find_doc_by_kind(docs, "HelmRelease")
        remediation = hr["spec"]["upgrade"]["remediation"]
        assert remediation.get("strategy") == "rollback", (
            f"upgrade.remediation.strategy must be 'rollback', "
            f"got {remediation.get('strategy')!r}"
        )

    @pytest.mark.requirement("FLUX-AC-1")
    def test_upgrade_remediation_retries_is_3(self) -> None:
        """spec.upgrade.remediation.retries MUST be 3.

        Ensures the controller retries 3 times before triggering the
        remediation strategy.
        """
        docs = _load_all_yaml_docs(_HELMRELEASE_PATH)
        hr = _find_doc_by_kind(docs, "HelmRelease")
        remediation = hr["spec"]["upgrade"]["remediation"]
        assert remediation["retries"] == 3, (
            f"upgrade.remediation.retries must be 3, got {remediation['retries']}"
        )

    @pytest.mark.requirement("FLUX-AC-1")
    def test_upgrade_remediation_remediate_last_failure(self) -> None:
        """spec.upgrade.remediation.remediateLastFailure MUST be true.

        Without this, the last retry failure is not remediated, leaving
        the release in a broken state.
        """
        docs = _load_all_yaml_docs(_HELMRELEASE_PATH)
        hr = _find_doc_by_kind(docs, "HelmRelease")
        remediation = hr["spec"]["upgrade"]["remediation"]
        assert remediation.get("remediateLastFailure") is True, (
            f"upgrade.remediation.remediateLastFailure must be true, "
            f"got {remediation.get('remediateLastFailure')!r}"
        )

    @pytest.mark.requirement("FLUX-AC-1")
    def test_upgrade_cleanup_on_fail(self) -> None:
        """spec.upgrade.cleanupOnFail MUST be true.

        Ensures failed upgrade resources are cleaned up before
        remediation triggers.
        """
        docs = _load_all_yaml_docs(_HELMRELEASE_PATH)
        hr = _find_doc_by_kind(docs, "HelmRelease")
        assert hr["spec"]["upgrade"]["cleanupOnFail"] is True, (
            "spec.upgrade.cleanupOnFail must be true"
        )


class TestHelmReleaseUninstallComment:
    """Verify the file documents strategy: uninstall as a test-env option."""

    @pytest.mark.requirement("FLUX-AC-1")
    def test_uninstall_strategy_comment_present(self) -> None:
        """File MUST contain a comment mentioning 'strategy: uninstall'.

        Users need guidance that uninstall is an alternative for test
        environments.  This catches implementations that set rollback
        structurally but omit the documentation.
        """
        raw = _raw_text(_HELMRELEASE_PATH)
        # The comment must mention both the strategy name and the context
        assert "strategy: uninstall" in raw, (
            "helmrelease.yaml must contain a comment about "
            "'strategy: uninstall' for test environments"
        )

    @pytest.mark.requirement("FLUX-AC-1")
    def test_uninstall_comment_mentions_test_environments(self) -> None:
        """The uninstall-strategy comment must mention test environments.

        A bare mention of 'uninstall' is insufficient -- users need to
        know WHEN to use it.
        """
        raw = _raw_text(_HELMRELEASE_PATH)
        raw_lower = raw.lower()
        has_test_context = (
            "test" in raw_lower
            and "uninstall" in raw_lower
        )
        assert has_test_context, (
            "helmrelease.yaml must mention 'test' in context of uninstall "
            "strategy as guidance for non-production environments"
        )


class TestHelmReleaseValuesFrom:
    """Verify valuesFrom contains a ConfigMap example with instructions."""

    @pytest.mark.requirement("FLUX-AC-1")
    def test_values_from_configmap_example(self) -> None:
        """File MUST contain a valuesFrom ConfigMap example.

        This can be active or commented-out YAML, but the pattern must
        be present for users to copy.
        """
        raw = _raw_text(_HELMRELEASE_PATH)
        assert "valuesFrom" in raw, (
            "helmrelease.yaml must contain a 'valuesFrom' section"
        )
        assert "ConfigMap" in raw, (
            "helmrelease.yaml must contain a ConfigMap reference "
            "in the valuesFrom section"
        )

    @pytest.mark.requirement("FLUX-AC-1")
    def test_values_from_has_inline_instructions(self) -> None:
        """The valuesFrom section must have inline instructions.

        Bare YAML without explanation is insufficient for a user example.
        The comments must explain how to use valuesFrom.
        """
        raw = _raw_text(_HELMRELEASE_PATH)
        # Find the valuesFrom block and check for nearby comments
        lines = raw.splitlines()
        values_from_indices = [
            i for i, line in enumerate(lines)
            if "valuesFrom" in line
        ]
        assert len(values_from_indices) > 0, (
            "helmrelease.yaml must contain 'valuesFrom'"
        )
        # There must be a comment line near (within 5 lines of) valuesFrom
        found_instruction = False
        for idx in values_from_indices:
            start = max(0, idx - 3)
            end = min(len(lines), idx + 8)
            nearby_lines = lines[start:end]
            comment_lines = [
                line for line in nearby_lines
                if line.strip().startswith("#") and len(line.strip()) > 5
            ]
            if comment_lines:
                found_instruction = True
                break
        assert found_instruction, (
            "valuesFrom section must have inline comment instructions "
            "explaining how to use it"
        )


class TestHelmReleaseInlineComments:
    """Verify each top-level spec field has an inline comment."""

    @pytest.mark.requirement("FLUX-AC-1")
    def test_each_top_level_spec_field_has_comment(self) -> None:
        """Each direct child of spec: must have a comment on or above it.

        Required top-level spec fields: releaseName, targetNamespace,
        chart, interval, install, upgrade, rollback, uninstall, values,
        driftDetection.  Every one must have a human-readable comment
        explaining its purpose.

        This catches implementations that set the right structure but
        strip out all documentation, making the example useless to users.
        """
        raw = _raw_text(_HELMRELEASE_PATH)
        lines = raw.splitlines()

        # Find the HelmRelease spec block by locating 'kind: HelmRelease'
        # then the first 'spec:' after it
        hr_line_idx: int | None = None
        spec_line_idx: int | None = None
        for i, line in enumerate(lines):
            if "kind: HelmRelease" in line:
                hr_line_idx = i
            if hr_line_idx is not None and i > hr_line_idx:
                stripped = line.strip()
                if stripped == "spec:":
                    spec_line_idx = i
                    break

        assert spec_line_idx is not None, (
            "Could not find 'spec:' block after 'kind: HelmRelease'"
        )

        # Detect the indentation level of spec's children (spec_indent + 2)
        spec_indent = len(lines[spec_line_idx]) - len(lines[spec_line_idx].lstrip())
        child_indent = spec_indent + 2

        # Collect top-level spec keys
        top_level_keys: list[str] = []
        for i in range(spec_line_idx + 1, len(lines)):
            line = lines[i]
            if not line.strip():
                continue
            current_indent = len(line) - len(line.lstrip())
            # If we hit something at same or lesser indent, we left the spec block
            if current_indent <= spec_indent and line.strip() and not line.strip().startswith("#"):
                break
            if current_indent == child_indent and ":" in line and not line.strip().startswith("#"):
                key = line.strip().split(":")[0].strip()
                top_level_keys.append(key)

        assert len(top_level_keys) >= 5, (
            f"Expected at least 5 top-level spec fields, found {len(top_level_keys)}: "
            f"{top_level_keys}"
        )

        # For each top-level key, check that the line itself or the line
        # immediately above is a comment
        keys_without_comments: list[str] = []
        for i in range(spec_line_idx + 1, len(lines)):
            line = lines[i]
            current_indent = len(line) - len(line.lstrip())
            if current_indent == child_indent and ":" in line and not line.strip().startswith("#"):
                key = line.strip().split(":")[0].strip()
                if key in top_level_keys:
                    # Check line above for a comment
                    has_comment = False
                    # Check the line itself for inline comment
                    if "#" in line.split(":", 1)[-1]:
                        has_comment = True
                    # Check 1-3 lines above for a comment at the same or
                    # parent indent level
                    for offset in range(1, 4):
                        check_idx = i - offset
                        if check_idx < 0:
                            break
                        prev_line = lines[check_idx].strip()
                        if prev_line.startswith("#"):
                            has_comment = True
                            break
                        if prev_line and not prev_line.startswith("#"):
                            # Non-empty, non-comment line -- stop looking
                            break
                    if not has_comment:
                        keys_without_comments.append(key)

        assert len(keys_without_comments) == 0, (
            f"These top-level spec fields lack an inline or preceding comment: "
            f"{keys_without_comments}"
        )


# ===========================================================================
# AC-2: ocirepository.yaml
# ===========================================================================


class TestOciRepositoryFileExists:
    """Verify the ocirepository.yaml file exists."""

    @pytest.mark.requirement("FLUX-AC-2")
    def test_ocirepository_file_exists(self) -> None:
        """charts/examples/flux/ocirepository.yaml MUST exist.

        This is a new file that replaces the inline HelmRepository
        document.  The test fails until the file is created.
        """
        assert _OCIREPOSITORY_PATH.exists(), (
            f"ocirepository.yaml does not exist at {_OCIREPOSITORY_PATH}. "
            "This is a new file that must be created."
        )


class TestOciRepositoryApiVersion:
    """Verify OCIRepository uses GA v1 source API."""

    @pytest.mark.requirement("FLUX-AC-2")
    def test_api_version_is_source_v1(self) -> None:
        """apiVersion MUST be source.toolkit.fluxcd.io/v1.

        The GA API for source resources is v1, not v1beta2.
        """
        docs = _load_all_yaml_docs(_OCIREPOSITORY_PATH)
        oci = _find_doc_by_kind(docs, "OCIRepository")
        assert oci["apiVersion"] == "source.toolkit.fluxcd.io/v1", (
            f"OCIRepository apiVersion must be 'source.toolkit.fluxcd.io/v1', "
            f"got {oci['apiVersion']!r}"
        )


class TestOciRepositoryMetadata:
    """Verify OCIRepository metadata fields."""

    @pytest.mark.requirement("FLUX-AC-2")
    def test_metadata_name(self) -> None:
        """metadata.name MUST be 'floe-platform'.

        This name is referenced by the HelmRelease sourceRef.
        """
        docs = _load_all_yaml_docs(_OCIREPOSITORY_PATH)
        oci = _find_doc_by_kind(docs, "OCIRepository")
        assert oci["metadata"]["name"] == "floe-platform", (
            f"metadata.name must be 'floe-platform', "
            f"got {oci['metadata']['name']!r}"
        )

    @pytest.mark.requirement("FLUX-AC-2")
    def test_metadata_namespace(self) -> None:
        """metadata.namespace MUST be 'flux-system'.

        Flux source resources must reside in the flux-system namespace.
        """
        docs = _load_all_yaml_docs(_OCIREPOSITORY_PATH)
        oci = _find_doc_by_kind(docs, "OCIRepository")
        assert oci["metadata"]["namespace"] == "flux-system", (
            f"metadata.namespace must be 'flux-system', "
            f"got {oci['metadata']['namespace']!r}"
        )


class TestOciRepositorySpec:
    """Verify OCIRepository spec fields."""

    @pytest.mark.requirement("FLUX-AC-2")
    def test_spec_url(self) -> None:
        """spec.url MUST be oci://ghcr.io/floe-platform/charts/floe-platform.

        The URL must point to the OCI registry where the chart is published.
        """
        docs = _load_all_yaml_docs(_OCIREPOSITORY_PATH)
        oci = _find_doc_by_kind(docs, "OCIRepository")
        expected_url = "oci://ghcr.io/floe-platform/charts/floe-platform"
        assert oci["spec"]["url"] == expected_url, (
            f"spec.url must be {expected_url!r}, got {oci['spec']['url']!r}"
        )

    @pytest.mark.requirement("FLUX-AC-2")
    def test_spec_url_uses_oci_scheme(self) -> None:
        """spec.url MUST start with oci:// (not https://).

        Catches implementations that use a Helm HTTP URL instead of
        the OCI registry protocol.
        """
        docs = _load_all_yaml_docs(_OCIREPOSITORY_PATH)
        oci = _find_doc_by_kind(docs, "OCIRepository")
        url = oci["spec"]["url"]
        assert url.startswith("oci://"), (
            f"spec.url must use oci:// scheme, got {url!r}"
        )

    @pytest.mark.requirement("FLUX-AC-2")
    def test_spec_interval(self) -> None:
        """spec.interval MUST be '5m'.

        5-minute poll interval balances freshness against API rate limits.
        """
        docs = _load_all_yaml_docs(_OCIREPOSITORY_PATH)
        oci = _find_doc_by_kind(docs, "OCIRepository")
        assert oci["spec"]["interval"] == "5m", (
            f"spec.interval must be '5m', got {oci['spec']['interval']!r}"
        )


class TestOciRepositoryCosignVerification:
    """Verify cosign keyless verification is configured."""

    @pytest.mark.requirement("FLUX-AC-2")
    def test_verify_provider_is_cosign(self) -> None:
        """spec.verify.provider MUST be 'cosign'.

        Cosign verification ensures chart integrity from the OCI registry.
        """
        docs = _load_all_yaml_docs(_OCIREPOSITORY_PATH)
        oci = _find_doc_by_kind(docs, "OCIRepository")
        verify = oci["spec"].get("verify", {})
        assert verify.get("provider") == "cosign", (
            f"spec.verify.provider must be 'cosign', "
            f"got {verify.get('provider')!r}"
        )

    @pytest.mark.requirement("FLUX-AC-2")
    def test_verify_is_keyless(self) -> None:
        """Cosign verification must use keyless mode (no secretRef).

        Keyless verification with Fulcio/Rekor is the recommended
        approach for public OCI registries like GHCR.  A secretRef
        would indicate static-key verification which is harder to maintain.
        """
        docs = _load_all_yaml_docs(_OCIREPOSITORY_PATH)
        oci = _find_doc_by_kind(docs, "OCIRepository")
        verify = oci["spec"].get("verify", {})
        # Keyless means no secretRef is set
        assert "secretRef" not in verify, (
            "cosign verification should be keyless (no secretRef) -- "
            "keyless verification uses Fulcio/Rekor and is preferred for GHCR"
        )


class TestOciRepositorySemver:
    """Verify SemVer range with -0 suffix for pre-release inclusion."""

    @pytest.mark.requirement("FLUX-AC-2")
    def test_semver_range_present(self) -> None:
        """spec.ref.semver MUST contain '>=1.0.0-0'.

        The -0 suffix ensures pre-release versions (e.g., 1.0.0-rc.1)
        are included in the range, which is essential for development
        and staging environments.
        """
        docs = _load_all_yaml_docs(_OCIREPOSITORY_PATH)
        oci = _find_doc_by_kind(docs, "OCIRepository")
        ref = oci["spec"].get("ref", {})
        semver = ref.get("semver", "")
        assert ">=1.0.0-0" in semver, (
            f"spec.ref.semver must contain '>=1.0.0-0', got {semver!r}"
        )

    @pytest.mark.requirement("FLUX-AC-2")
    def test_semver_dash_zero_comment(self) -> None:
        """File must contain a comment explaining the -0 suffix.

        The -0 convention is non-obvious.  Without a comment, users will
        strip it, breaking pre-release resolution.
        """
        raw = _raw_text(_OCIREPOSITORY_PATH)
        raw_lower = raw.lower()
        # The comment must explain why -0 is used
        has_dash_zero_explanation = (
            "-0" in raw
            and (
                "pre-release" in raw_lower
                or "prerelease" in raw_lower
                or "pre release" in raw_lower
            )
        )
        assert has_dash_zero_explanation, (
            "ocirepository.yaml must contain a comment explaining the '-0' "
            "suffix in the semver range (it includes pre-release versions)"
        )


# ===========================================================================
# AC-3: kustomization.yaml
# ===========================================================================


class TestKustomizationValuesFrom:
    """Verify kustomization.yaml contains a valuesFrom ConfigMap pattern."""

    @pytest.mark.requirement("FLUX-AC-3")
    def test_values_from_configmap_pattern(self) -> None:
        """kustomization.yaml MUST contain a valuesFrom ConfigMap reference.

        This pattern allows users to externalize values for multi-env
        deployments.  Can be active or commented-out YAML.
        """
        raw = _raw_text(_KUSTOMIZATION_PATH)
        assert "valuesFrom" in raw, (
            "kustomization.yaml must contain a 'valuesFrom' pattern"
        )
        assert "ConfigMap" in raw, (
            "kustomization.yaml must reference a ConfigMap in the "
            "valuesFrom pattern"
        )

    @pytest.mark.requirement("FLUX-AC-3")
    def test_values_from_near_configmap(self) -> None:
        """valuesFrom and ConfigMap must appear in proximity.

        Catches files that mention ConfigMap in a totally different
        section (e.g., postBuild.substituteFrom) but lack a proper
        valuesFrom example.
        """
        raw = _raw_text(_KUSTOMIZATION_PATH)
        lines = raw.splitlines()
        values_from_lines = [
            i for i, line in enumerate(lines) if "valuesFrom" in line
        ]
        configmap_lines = [
            i for i, line in enumerate(lines) if "ConfigMap" in line
        ]

        # At least one ConfigMap must be within 10 lines of a valuesFrom
        found_proximity = False
        for vf_idx in values_from_lines:
            for cm_idx in configmap_lines:
                if abs(vf_idx - cm_idx) <= 10:
                    found_proximity = True
                    break
            if found_proximity:
                break

        assert found_proximity, (
            "A ConfigMap reference must appear within 10 lines of a "
            "'valuesFrom' entry in kustomization.yaml. Found valuesFrom "
            f"at lines {values_from_lines} and ConfigMap at lines "
            f"{configmap_lines}"
        )


class TestKustomizationSopsAge:
    """Verify SOPS decryption example uses Age, not GPG."""

    @pytest.mark.requirement("FLUX-AC-3")
    def test_sops_age_decryption_present(self) -> None:
        """SOPS decryption example MUST reference Age, not GPG.

        Age is the modern replacement for GPG in SOPS.  The example
        must guide users toward Age-based key management.
        Uses word-boundary matching to avoid false positives from
        words like 'management' or 'Usage' that contain 'age'.
        """
        raw = _raw_text(_KUSTOMIZATION_PATH)
        # Match "age" as a standalone word or as part of SOPS-specific terms
        # like "age-keygen", "sops-age", "Age key" -- but NOT "management"
        has_age_ref = bool(
            re.search(r"\bAge\b", raw)  # Capitalized proper noun
            or re.search(r"\bage-keygen\b", raw, re.IGNORECASE)
            or re.search(r"\bage key\b", raw, re.IGNORECASE)
            or re.search(r"sops.*age|age.*sops", raw, re.IGNORECASE)
            or re.search(r"\bage\.txt\b", raw, re.IGNORECASE)
            or re.search(r"\bage recipient\b", raw, re.IGNORECASE)
        )
        assert has_age_ref, (
            "kustomization.yaml SOPS decryption example must reference Age "
            "(not GPG) as the key management method. 'Age' must appear as "
            "a standalone word, not as a substring of other words."
        )

    @pytest.mark.requirement("FLUX-AC-3")
    def test_sops_not_gpg_default(self) -> None:
        """The SOPS example must NOT use GPG as the primary method.

        The current file references 'sops-gpg' which must be replaced
        with Age-based configuration.
        """
        raw = _raw_text(_KUSTOMIZATION_PATH)
        # The file currently has 'sops-gpg' -- this must be gone
        assert "sops-gpg" not in raw, (
            "kustomization.yaml must not reference 'sops-gpg' -- "
            "use Age-based SOPS decryption instead"
        )

    @pytest.mark.requirement("FLUX-AC-3")
    def test_sops_age_has_setup_instructions(self) -> None:
        """The SOPS Age example must include step-by-step setup instructions.

        A bare YAML block without explanation is insufficient.  Users need
        a numbered or bulleted procedure for generating Age keys and
        configuring SOPS.
        """
        raw = _raw_text(_KUSTOMIZATION_PATH)
        # Must reference Age as a proper noun/tool AND include setup steps
        has_age_ref = bool(
            re.search(r"\bAge\b", raw)
            or re.search(r"\bage-keygen\b", raw, re.IGNORECASE)
            or re.search(r"sops.*age|age.*sops", raw, re.IGNORECASE)
        )
        has_setup_steps = bool(
            re.search(r"age-keygen", raw, re.IGNORECASE)
            or re.search(r"generate.*key|key.*generat", raw, re.IGNORECASE)
            or re.search(r"step\s+\d|^\s*#\s*\d+\.", raw, re.MULTILINE)
        )
        assert has_age_ref and has_setup_steps, (
            "kustomization.yaml must include step-by-step setup instructions "
            "for SOPS Age decryption (mentioning Age as a tool and key "
            "generation steps)"
        )

    @pytest.mark.requirement("FLUX-AC-3")
    def test_sops_decryption_is_commented_out(self) -> None:
        """The SOPS Age decryption block must be commented-out YAML.

        It must not be active YAML since users need to configure
        their own Age keys first.  Check that the decryption block
        appears in comment form and references Age (not GPG).
        """
        raw = _raw_text(_KUSTOMIZATION_PATH)
        lines = raw.splitlines()

        # Find commented lines that mention both 'decryption' and 'age'
        # as a proper reference (not substring of 'management' etc.)
        commented_age_decryption = [
            line for line in lines
            if (
                line.strip().startswith("#")
                and "decryption" in line.lower()
                and bool(re.search(r"\bAge\b|\bage-keygen\b|\bage key\b", line))
            )
        ]
        # Also check for a commented secretRef that references an age key
        commented_age_secret = [
            line for line in lines
            if (
                line.strip().startswith("#")
                and bool(re.search(r"sops-age|age-key|age\.agekey", line, re.IGNORECASE))
            )
        ]
        total_age_decryption_comments = len(commented_age_decryption) + len(commented_age_secret)
        assert total_age_decryption_comments > 0, (
            "SOPS Age decryption example must appear as commented-out YAML "
            "with Age-specific references (not GPG). Found decryption "
            "comments but none reference Age."
        )


class TestKustomizationEsoMention:
    """Verify ESO (External Secrets Operator) mentioned as alternative."""

    @pytest.mark.requirement("FLUX-AC-3")
    def test_eso_mentioned_as_enterprise_alternative(self) -> None:
        """kustomization.yaml must mention ESO as an enterprise alternative.

        Users in enterprise environments often use External Secrets
        Operator instead of SOPS.  The example must acknowledge this.
        Uses word-boundary matching to avoid false positives from words
        like 'resources' that contain 'eso' as a substring.
        """
        raw = _raw_text(_KUSTOMIZATION_PATH)
        has_eso = bool(
            re.search(r"external secrets operator", raw, re.IGNORECASE)
            or re.search(r"external-secrets", raw, re.IGNORECASE)
            or re.search(r"\bESO\b", raw)  # uppercase acronym only
        )
        assert has_eso, (
            "kustomization.yaml must mention External Secrets Operator (ESO) "
            "as an enterprise alternative to SOPS"
        )

    @pytest.mark.requirement("FLUX-AC-3")
    def test_eso_in_comment_context(self) -> None:
        """ESO mention must be in a comment (guidance, not active config).

        ESO is documented as an alternative, not deployed by this file.
        Uses word-boundary matching to avoid false positives from words
        like 'resources' that contain 'eso' as a substring.
        """
        raw = _raw_text(_KUSTOMIZATION_PATH)
        lines = raw.splitlines()
        eso_lines = [
            line for line in lines
            if bool(
                re.search(r"external secrets", line, re.IGNORECASE)
                or re.search(r"external-secrets", line, re.IGNORECASE)
                or re.search(r"\bESO\b", line)  # uppercase acronym only
            )
        ]
        assert len(eso_lines) > 0, (
            "Must mention External Secrets Operator / ESO "
            "(as a standalone term, not as substring of 'resources')"
        )
        commented_eso = [
            line for line in eso_lines
            if line.strip().startswith("#")
        ]
        assert len(commented_eso) > 0, (
            "ESO mention must appear in a comment (guidance), "
            "not as active configuration"
        )

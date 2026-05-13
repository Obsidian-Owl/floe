from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

import yaml
from packaging.version import Version

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


SECRET_KEY_RE = re.compile(
    r"(secret|access_key|token|password|private_key)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
)
RELEASE_TAG_RE = re.compile(r"^v?(\d+\.\d+\.\d+)(?:-alpha\.(\d+))?$")
ALPHA_HELM_PUBLISH_CHART_PATHS = (
    "charts/floe-platform",
    "charts/floe-jobs",
)


class ReleaseManifestError(ValueError):
    """Raised when the release manifest is invalid."""


@dataclass(frozen=True)
class ReleaseInfo:
    train: str
    git_tag: str
    python_version: str
    helm_version: str


@dataclass(frozen=True)
class PackageEntry:
    path: str
    name: str
    evidence: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class PythonPackages:
    publish: tuple[PackageEntry, ...]
    exclude: tuple[PackageEntry, ...]


@dataclass(frozen=True)
class HelmInfo:
    alpha_policy: str
    charts: tuple[str, ...]


@dataclass(frozen=True)
class ValidationPolicy:
    require_current_main_ci: bool
    require_package_build_dry_run: bool
    require_full_devpod_e2e: bool
    require_aws_provider_live: bool
    allow_accepted_historical_evidence: bool


@dataclass(frozen=True)
class ReleaseManifest:
    release: ReleaseInfo
    python_packages: PythonPackages
    helm: HelmInfo
    validation: ValidationPolicy


@dataclass(frozen=True)
class ManifestValidationResult:
    git_tag: str
    python_version: str
    helm_version: str
    publish_count: int
    exclude_count: int
    publish_names: tuple[str, ...]


def normalize_tag_to_python_version(tag: str) -> str:
    match = RELEASE_TAG_RE.fullmatch(tag)
    if not match:
        raise ReleaseManifestError(f"unsupported release tag format: {tag}")
    version = f"{match.group(1)}a{match.group(2)}" if match.group(2) is not None else match.group(1)
    Version(version)
    return version


def normalize_tag_to_helm_version(tag: str) -> str:
    match = RELEASE_TAG_RE.fullmatch(tag)
    if not match:
        raise ReleaseManifestError(f"unsupported release tag format: {tag}")
    if match.group(2) is not None:
        return f"{match.group(1)}-alpha.{match.group(2)}"
    return match.group(1)


def load_release_manifest(path: Path) -> ReleaseManifest:
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    _reject_secret_like_keys(raw)
    data = _require_mapping(raw, "manifest")

    release = _require_mapping(data.get("release"), "release")
    python_packages = _require_mapping(data.get("python_packages"), "python_packages")
    helm = _require_mapping(data.get("helm"), "helm")
    validation = _require_mapping(data.get("validation"), "validation")

    return ReleaseManifest(
        release=ReleaseInfo(
            train=_require_str(release.get("train"), "release.train"),
            git_tag=_require_str(release.get("git_tag"), "release.git_tag"),
            python_version=_require_str(
                release.get("python_version"),
                "release.python_version",
            ),
            helm_version=_require_str(release.get("helm_version"), "release.helm_version"),
        ),
        python_packages=PythonPackages(
            publish=_load_package_entries(
                python_packages.get("publish"),
                "python_packages.publish",
                required_detail_field="evidence",
            ),
            exclude=_load_package_entries(
                python_packages.get("exclude"),
                "python_packages.exclude",
                required_detail_field="reason",
            ),
        ),
        helm=HelmInfo(
            alpha_policy=_require_str(helm.get("alpha_policy"), "helm.alpha_policy"),
            charts=tuple(
                _require_str(item, "helm.charts[]")
                for item in _require_list(helm.get("charts"), "helm.charts")
            ),
        ),
        validation=ValidationPolicy(
            require_current_main_ci=_require_bool(
                validation.get("require_current_main_ci"),
                "validation.require_current_main_ci",
            ),
            require_package_build_dry_run=_require_bool(
                validation.get("require_package_build_dry_run"),
                "validation.require_package_build_dry_run",
            ),
            require_full_devpod_e2e=_require_bool(
                validation.get("require_full_devpod_e2e"),
                "validation.require_full_devpod_e2e",
            ),
            require_aws_provider_live=_require_bool(
                validation.get("require_aws_provider_live"),
                "validation.require_aws_provider_live",
            ),
            allow_accepted_historical_evidence=_require_bool(
                validation.get("allow_accepted_historical_evidence"),
                "validation.allow_accepted_historical_evidence",
            ),
        ),
    )


def validate_release_manifest(
    manifest: ReleaseManifest,
    *,
    repo_root: Path,
    tag: str | None = None,
) -> ManifestValidationResult:
    if tag is not None and tag != manifest.release.git_tag:
        raise ReleaseManifestError(
            f"manifest git_tag does not match release tag: {manifest.release.git_tag} != {tag}",
        )

    expected_python_version = normalize_tag_to_python_version(
        tag or manifest.release.git_tag,
    )
    if manifest.release.python_version != expected_python_version:
        raise ReleaseManifestError(
            "manifest python_version does not match normalized git tag: "
            f"{manifest.release.python_version} != {expected_python_version}",
        )
    expected_helm_version = normalize_tag_to_helm_version(tag or manifest.release.git_tag)
    if manifest.release.helm_version != expected_helm_version:
        raise ReleaseManifestError(
            "manifest helm_version does not match normalized git tag: "
            f"{manifest.release.helm_version} != {expected_helm_version}",
        )
    if manifest.helm.alpha_policy != "publish":
        raise ReleaseManifestError(
            f"unsupported helm.alpha_policy for alpha release: {manifest.helm.alpha_policy}",
        )
    _validate_alpha_helm_publish_charts(manifest.helm.charts)

    Version(manifest.release.python_version)
    publish_names = tuple(pkg.name for pkg in manifest.python_packages.publish)
    excluded_names = tuple(pkg.name for pkg in manifest.python_packages.exclude)
    all_packages = (*manifest.python_packages.publish, *manifest.python_packages.exclude)
    _reject_duplicate_package_fields(all_packages)
    overlap = sorted(set(publish_names).intersection(excluded_names))
    if overlap:
        raise ReleaseManifestError(
            f"packages cannot be both published and excluded: {overlap}",
        )

    _validate_workspace_package_classification(repo_root, all_packages)

    for package in all_packages:
        project_path = repo_root / package.path
        pyproject_path = project_path / "pyproject.toml"
        if not pyproject_path.exists():
            raise ReleaseManifestError(
                f"package path missing pyproject.toml: {package.path}",
            )
        metadata = _read_project_metadata(pyproject_path)
        if metadata["name"] != package.name:
            raise ReleaseManifestError(
                f"package name mismatch for {package.path}: {metadata['name']} != {package.name}",
            )

    for package in manifest.python_packages.publish:
        metadata = _read_project_metadata(repo_root / package.path / "pyproject.toml")
        if metadata["version"] != manifest.release.python_version:
            raise ReleaseManifestError(
                f"package version mismatch for {package.name}: "
                f"{metadata['version']} != {manifest.release.python_version}",
            )

    # Task 1 validates declared Helm policy/version and chart presence; chart
    # metadata alignment belongs to the Helm policy task.
    for chart_path in manifest.helm.charts:
        if not (repo_root / chart_path / "Chart.yaml").exists():
            raise ReleaseManifestError(f"chart path missing Chart.yaml: {chart_path}")

    return ManifestValidationResult(
        git_tag=manifest.release.git_tag,
        python_version=manifest.release.python_version,
        helm_version=manifest.release.helm_version,
        publish_count=len(manifest.python_packages.publish),
        exclude_count=len(manifest.python_packages.exclude),
        publish_names=publish_names,
    )


def _validate_alpha_helm_publish_charts(chart_paths: tuple[str, ...]) -> None:
    expected_chart_paths = set(ALPHA_HELM_PUBLISH_CHART_PATHS)
    seen_chart_paths: set[str] = set()
    duplicate_chart_paths: set[str] = set()

    for chart_path in chart_paths:
        parsed_path = PurePosixPath(chart_path)
        if parsed_path.is_absolute():
            raise ReleaseManifestError(
                f"alpha Helm publish chart path must be relative: {chart_path}",
            )
        if ".." in parsed_path.parts:
            raise ReleaseManifestError(
                f"alpha Helm publish chart path must not traverse parents: {chart_path}",
            )
        if not parsed_path.parts or parsed_path.parts[0] != "charts":
            raise ReleaseManifestError(
                f"alpha Helm publish chart path must be under charts/: {chart_path}",
            )
        if chart_path not in ALPHA_HELM_PUBLISH_CHART_PATHS:
            raise ReleaseManifestError(
                f"alpha Helm publish chart path is not in the alpha allowlist: {chart_path}",
            )
        if chart_path in seen_chart_paths:
            duplicate_chart_paths.add(chart_path)
        seen_chart_paths.add(chart_path)

    if duplicate_chart_paths:
        raise ReleaseManifestError(
            f"duplicate alpha Helm publish chart path(s): {sorted(duplicate_chart_paths)}",
        )

    missing_chart_paths = sorted(expected_chart_paths - seen_chart_paths)
    if missing_chart_paths:
        raise ReleaseManifestError(
            f"missing alpha Helm publish chart path(s): {missing_chart_paths}",
        )


def _load_package_entries(
    value: Any,
    field_name: str,
    *,
    required_detail_field: str,
) -> tuple[PackageEntry, ...]:
    entries = []
    for index, item in enumerate(_require_list(value, field_name)):
        entry = _require_mapping(item, f"{field_name}[{index}]")
        detail = _require_non_empty_str(
            entry.get(required_detail_field),
            f"{field_name}[{index}].{required_detail_field}",
        )
        entries.append(
            PackageEntry(
                path=_require_str(entry.get("path"), f"{field_name}[{index}].path"),
                name=_require_str(entry.get("name"), f"{field_name}[{index}].name"),
                evidence=detail if required_detail_field == "evidence" else None,
                reason=detail if required_detail_field == "reason" else None,
            ),
        )
    return tuple(entries)


def _reject_duplicate_package_fields(packages: tuple[PackageEntry, ...]) -> None:
    _reject_duplicate_package_field(packages, field_name="name")
    _reject_duplicate_package_field(packages, field_name="path")


def _reject_duplicate_package_field(
    packages: tuple[PackageEntry, ...],
    *,
    field_name: str,
) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for package in packages:
        value = getattr(package, field_name)
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        raise ReleaseManifestError(
            f"duplicate package {field_name}: {sorted(duplicates)}",
        )


def _validate_workspace_package_classification(
    repo_root: Path,
    packages: tuple[PackageEntry, ...],
) -> None:
    classified_paths = {package.path for package in packages}
    workspace_paths = {
        pyproject.parent.relative_to(repo_root).as_posix()
        for pattern in ("packages/*/pyproject.toml", "plugins/*/pyproject.toml")
        for pyproject in repo_root.glob(pattern)
    }
    unclassified = sorted(workspace_paths - classified_paths)
    if unclassified:
        raise ReleaseManifestError(
            f"unclassified workspace package(s): {unclassified}",
        )


def _read_project_metadata(path: Path) -> dict[str, str]:
    with path.open("rb") as handle:
        project = _require_mapping(tomllib.load(handle).get("project"), "project")
    return {
        "name": _require_str(project.get("name"), "project.name"),
        "version": _require_str(project.get("version"), "project.version"),
    }


def _reject_secret_like_keys(value: Any, prefix: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            current = f"{prefix}.{key_text}" if prefix else key_text
            if SECRET_KEY_RE.search(key_text):
                raise ReleaseManifestError(f"manifest contains secret-like key: {current}")
            _reject_secret_like_keys(child, current)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_like_keys(child, f"{prefix}[{index}]")
    elif isinstance(value, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                location = prefix or "manifest"
                raise ReleaseManifestError(
                    f"manifest contains secret-like value: {location}",
                )


def _require_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReleaseManifestError(f"manifest field must be a mapping: {field_name}")
    return cast(dict[str, Any], value)


def _require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReleaseManifestError(f"manifest field must be a list: {field_name}")
    return value


def _require_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ReleaseManifestError(f"manifest field must be a string: {field_name}")
    return value


def _require_non_empty_str(value: Any, field_name: str) -> str:
    text = _require_str(value, field_name)
    if not text.strip():
        raise ReleaseManifestError(f"manifest field {field_name} must be non-empty")
    return text


def _require_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ReleaseManifestError(f"manifest field must be a boolean: {field_name}")
    return value

from __future__ import annotations

import argparse
import json
import re
import tomllib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^v?(?P<version>[0-9]+\.[0-9]+\.[0-9]+(?:[A-Za-z0-9.]+)?)$")


def project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    return str(data["project"]["version"])


def base_version(version: str) -> str:
    return version.split(".dev", 1)[0].split("+", 1)[0]


def plugin_versions() -> tuple[str, str]:
    portable = json.loads((ROOT / "plugin.json").read_text())
    compat = json.loads(
        (ROOT / ".codex-plugin" / "plugin.json").read_text()
    )
    return str(portable["version"]), str(compat["version"])


def validate_versions(tag: str | None = None) -> dict[str, str]:
    py_version = project_version()
    portable, compat = plugin_versions()
    if portable != compat:
        raise SystemExit(
            "portable and compatibility plugin versions differ"
        )
    if base_version(py_version) != portable:
        raise SystemExit(
            "Python project base version and plugin version differ: "
            f"{py_version!r} vs {portable!r}"
        )
    if tag:
        match = VERSION_RE.fullmatch(tag)
        if not match:
            raise SystemExit(f"release tag is not a version tag: {tag!r}")
        tagged = match.group("version")
        if tagged != py_version:
            raise SystemExit(
                "release tag must exactly match pyproject version: "
                f"{tagged!r} vs {py_version!r}"
            )
    return {
        "python_project": py_version,
        "portable_plugin": portable,
        "compat_plugin": compat,
    }


def validate_release_workflow() -> None:
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    required = (
        "id-token: write",
        "actions/attest@",
        "pypa/gh-action-pypi-publish@",
    )
    for marker in required:
        if marker not in text:
            raise SystemExit(
                f"release workflow missing required marker: {marker}"
            )
    forbidden = (
        "password:",
        "PYPI_API_TOKEN",
        "TWINE_PASSWORD",
    )
    for marker in forbidden:
        if marker in text:
            raise SystemExit(
                "release workflow contains long-lived credential surface: "
                f"{marker}"
            )


def validate_wheel(path: Path) -> dict[str, object]:
    required_suffixes = {
        "engine/resources/agents/scout.toml",
        "engine/resources/agents/builder.toml",
        "engine/resources/agents/debugger.toml",
        "engine/resources/agents/reviewer.toml",
        "engine/resources/agents/architect.toml",
        "engine/resources/agents/integrator.toml",
        "engine/resources/skill/SKILL.md",
        "engine/resources/skill/references/routing.md",
        "engine/resources/skill/references/context-firewall.md",
        "engine/resources/skill/references/caching.md",
        "engine/resources/skill/references/scheduling.md",
        "engine/resources/skill/references/verification.md",
        "engine/resources/skill/references/security.md",
    }
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
    missing = sorted(required_suffixes - names)
    if missing:
        raise SystemExit(
            "wheel is missing Cascade integration resources: "
            + ", ".join(missing)
        )
    return {
        "wheel": str(path),
        "entries": len(names),
        "required_resources": len(required_suffixes),
    }


def locate_wheel(directory: Path) -> Path:
    wheels = sorted(directory.glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit(
            f"expected exactly one wheel in {directory}, found {len(wheels)}"
        )
    return wheels[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag")
    parser.add_argument("--wheel-dir", type=Path)
    args = parser.parse_args(argv)

    report: dict[str, object] = {
        "versions": validate_versions(args.tag),
    }
    validate_release_workflow()
    report["release_workflow"] = "oidc+attestation"
    if args.wheel_dir:
        report["wheel"] = validate_wheel(
            locate_wheel(args.wheel_dir)
        )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

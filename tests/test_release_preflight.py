from pathlib import Path
import zipfile

import pytest

from scripts.release_preflight import (
    base_version,
    plugin_versions,
    project_version,
    validate_release_workflow,
    validate_versions,
    validate_wheel,
)


def test_project_base_version_matches_plugin_versions():
    portable, compat = plugin_versions()
    assert portable == compat
    assert base_version(project_version()) == portable


def test_release_workflow_uses_oidc_and_attestation():
    validate_release_workflow()


def test_tag_must_match_exact_python_project_version():
    version = project_version()
    assert validate_versions("v" + version)["python_project"] == version
    with pytest.raises(SystemExit):
        validate_versions("v0.0.0")


def test_wheel_validation_requires_packaged_resources(tmp_path: Path):
    wheel = tmp_path / "bad.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("engine/__init__.py", "")
    with pytest.raises(SystemExit):
        validate_wheel(wheel)

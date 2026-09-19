import json
from pathlib import Path

from engine.evaluation.models import load_cases
from engine.validation.discover import discover_validators


MANIFEST = Path("benchmarks/fixtures/monorepo_live.json")


def _materialize_case(tmp_path: Path, case_index: int) -> Path:
    data = json.loads(MANIFEST.read_text())
    case = data[case_index]
    for rel, text in case["files"].items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return tmp_path


def test_monorepo_manifest_has_read_and_bounded_write_cases():
    cases = load_cases(MANIFEST)
    assert len(cases) == 2

    read_case, write_case = cases
    assert read_case.write_paths == []
    assert read_case.answer_contains == ["packages/api/src/config.js"]

    assert write_case.write_paths == ["packages/core/value.txt"]
    assert write_case.acceptance
    assert "packages/web/value.txt" in write_case.files


def test_monorepo_fixture_selects_package_local_node_validators(
    tmp_path: Path,
    monkeypatch,
):
    root = _materialize_case(tmp_path, 1)
    monkeypatch.setattr(
        "engine.validation.discover.shutil.which",
        lambda name: f"/usr/bin/{name}" if name == "npm" else None,
    )

    specs = discover_validators(root)
    by_name = {spec.name: spec for spec in specs}

    assert by_name["packages/core:js-test"].cwd == "packages/core"
    assert by_name["packages/web:js-test"].cwd == "packages/web"
    assert by_name["packages/core:js-test"].command == (
        "npm",
        "run",
        "test",
        "--if-present",
    )
    assert by_name["packages/web:js-test"].command == (
        "npm",
        "run",
        "test",
        "--if-present",
    )


def test_monorepo_manifest_keeps_release_suite_count_unchanged():
    release_cases = load_cases("benchmarks/fixtures/live_tasks.json")
    monorepo_cases = load_cases(MANIFEST)

    assert len(release_cases) == 23
    assert {case.case_id for case in monorepo_cases}.isdisjoint(
        {case.case_id for case in release_cases}
    )

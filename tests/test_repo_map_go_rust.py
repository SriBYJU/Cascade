from pathlib import Path

from engine.context.repo_map import build_repo_map


def test_go_symbols_imports_and_local_package_edges(tmp_path: Path):
    (tmp_path / "go.mod").write_text(
        "module example.com/cascade-fixture\n\ngo 1.23\n"
    )
    auth = tmp_path / "auth"
    auth.mkdir()
    (auth / "session.go").write_text(
        "package auth\n\n"
        "type Session struct{}\n\n"
        "func RefreshSession() string { return \"ok\" }\n"
    )
    (tmp_path / "main.go").write_text(
        "package main\n\n"
        "import (\n"
        '    "fmt"\n'
        '    "example.com/cascade-fixture/auth"\n'
        ")\n\n"
        "func main() { fmt.Println(auth.RefreshSession()) }\n"
    )

    mapped = build_repo_map(tmp_path, use_cache=False)
    by_path = {file.path: file for file in mapped.files}

    assert {"Session", "RefreshSession"} <= set(
        by_path["auth/session.go"].symbols
    )
    assert "example.com/cascade-fixture/auth" in by_path["main.go"].imports
    assert "auth/session.go" in by_path["main.go"].references
    assert "main.go" in by_path["auth/session.go"].referenced_by


def test_rust_symbols_use_and_mod_edges(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    auth = src / "auth"
    auth.mkdir()
    (src / "main.rs").write_text(
        "mod auth;\n"
        "use crate::auth::session::Session;\n"
        "fn main() { let _ = Session::new(); }\n"
    )
    (src / "auth.rs").write_text(
        "pub mod session;\n"
    )
    (auth / "session.rs").write_text(
        "pub struct Session;\n"
        "impl Session { pub fn new() -> Self { Self } }\n"
    )

    mapped = build_repo_map(tmp_path, use_cache=False)
    by_path = {file.path: file for file in mapped.files}

    assert "main" in by_path["src/main.rs"].symbols
    assert "Session" in by_path["src/auth/session.rs"].symbols
    assert "src/auth.rs" in by_path["src/main.rs"].references
    assert (
        "src/auth/session.rs"
        in by_path["src/main.rs"].references
    )


def test_malformed_go_and_rust_source_fails_soft(tmp_path: Path):
    (tmp_path / "broken.go").write_text(
        'package x\nimport (\n "oops\n'
    )
    (tmp_path / "broken.rs").write_text(
        "pub fn ( this is invalid"
    )
    mapped = build_repo_map(tmp_path, use_cache=False)
    paths = {file.path for file in mapped.files}
    assert {"broken.go", "broken.rs"} <= paths

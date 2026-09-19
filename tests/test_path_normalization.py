from engine.schemas import normalize_repo_path


def test_normalize_repo_path_preserves_leading_dot_names():
    assert normalize_repo_path(".github/workflows/ci.yml") == (
        ".github/workflows/ci.yml"
    )
    assert normalize_repo_path(".env.example") == ".env.example"


def test_normalize_repo_path_removes_only_explicit_dot_slash():
    assert normalize_repo_path("./src/app.py") == "src/app.py"
    assert normalize_repo_path("././src/app.py") == "src/app.py"

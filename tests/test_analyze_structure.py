import json
import os
import tempfile

import pytest

from scripts.analyze_structure import detect_language, score_files, analyze_structure


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------

def test_detect_language_go():
    tree = [{"path": "go.mod"}, {"path": "main.go"}]
    assert detect_language(tree) == "go"


def test_detect_language_nodejs():
    tree = [{"path": "package.json"}, {"path": "index.js"}]
    assert detect_language(tree) == "nodejs"


def test_detect_language_python():
    tree = [{"path": "requirements.txt"}, {"path": "app.py"}]
    assert detect_language(tree) == "python"


def test_detect_language_java():
    tree = [{"path": "pom.xml"}]
    assert detect_language(tree) == "java"


def test_detect_language_rust():
    tree = [{"path": "Cargo.toml"}]
    assert detect_language(tree) == "rust"


def test_detect_language_unknown():
    tree = [{"path": "README.md"}]
    assert detect_language(tree) == "unknown"


# ---------------------------------------------------------------------------
# score_files
# ---------------------------------------------------------------------------

def test_score_files_go_project():
    tree = [
        {"path": "go.mod", "size": 100},
        {"path": "main.go", "size": 200},
        {"path": "controller/relay.go", "size": 500},
        {"path": "model/user.go", "size": 300},
        {"path": "README.md", "size": 50},
        {"path": "Dockerfile", "size": 80},
        {"path": "static/image.png", "size": 10000},
    ]
    scored = score_files(tree, "go")
    paths = [s["path"] for s in scored]

    # main.go should be highest priority
    assert scored[0]["path"] == "main.go"
    assert scored[0]["priority"] == 95

    # controller/relay.go should be high
    assert "controller/relay.go" in paths[:3]

    # README and Dockerfile should be in top results
    assert "README.md" in paths[:6]
    assert "Dockerfile" in paths[:6]

    # Binary/static files should be low
    assert scored[-1]["path"] == "static/image.png"


# ---------------------------------------------------------------------------
# analyze_structure (integration)
# ---------------------------------------------------------------------------

def test_analyze_structure_output_format():
    tree_data = {
        "repo_url": "https://github.com/test/repo",
        "platform": "github",
        "owner": "test",
        "repo": "repo",
        "branch": "main",
        "files": [
            {"path": "go.mod", "size": 100},
            {"path": "main.go", "size": 200},
            {"path": "controller/api.go", "size": 500},
            {"path": "README.md", "size": 50},
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(tree_data, f)
        temp_path = f.name

    out_path = temp_path + ".out.json"

    try:
        analyze_structure(temp_path, max_files=10, output=out_path)

        with open(out_path, "r") as f:
            result = json.load(f)

        assert result["detected_language"] == "go"
        assert len(result["core_files"]) == 4
        assert result["core_files"][0]["path"] == "main.go"
        assert all("priority" in f for f in result["core_files"])
    finally:
        os.unlink(temp_path)
        if os.path.exists(out_path):
            os.unlink(out_path)

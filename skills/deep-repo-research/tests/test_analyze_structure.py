import json
import os
import tempfile

import pytest

from scripts.analyze_structure import (
    detect_language,
    score_files,
    analyze_structure,
    parse_tech_stack,
    build_architecture,
    build_deployment,
    build_files_analyzed,
    build_overview,
    build_summary,
)


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
# analyze_structure (integration) - validates output matches template expectations
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

        # Language detection
        assert result["detected_language"] == "go"
        assert result["tech_stack"]["language"] == "Go"

        # Core files still present (backward compat)
        assert len(result["core_files"]) == 4
        assert result["core_files"][0]["path"] == "main.go"
        assert all("priority" in f for f in result["core_files"])

        # Template-required fields
        assert result["repo_name"] == "repo"
        assert result["repo_url"] == "https://github.com/test/repo"
        assert result["branch"] == "main"
        assert "generated_at" in result
        assert isinstance(result["tech_stack"], dict)
        assert "overview" in result
        assert "architecture" in result
        assert "components" in result["architecture"]
        assert "data_flow" in result["architecture"]
        assert "files_analyzed" in result
        assert len(result["files_analyzed"]) == 4
        assert "deployment" in result
        assert "summary" in result

        # files_analyzed entries have template-required keys
        for fa in result["files_analyzed"]:
            assert "path" in fa
            assert "language" in fa
            assert "analysis" in fa
            assert "code_snippet" in fa
    finally:
        os.unlink(temp_path)
        if os.path.exists(out_path):
            os.unlink(out_path)


def test_analyze_structure_produces_renderable_report():
    """End-to-end: analyze_structure output must be consumable by generate_report."""
    from scripts.generate_report import load_template, render_report

    tree_data = {
        "repo_url": "https://github.com/test/repo",
        "platform": "github",
        "owner": "test",
        "repo": "repo",
        "branch": "main",
        "files": [
            {"path": "package.json", "size": 100},
            {"path": "index.js", "size": 200},
            {"path": "routes/api.js", "size": 500},
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
            data = json.load(f)

        # All four templates must render without error
        for style in ["overview", "architecture", "deployment", "full"]:
            template = load_template(style)
            report = render_report(data, template)
            assert len(report) > 100
            assert data["repo_name"] in report
    finally:
        os.unlink(temp_path)
        if os.path.exists(out_path):
            os.unlink(out_path)


# ---------------------------------------------------------------------------
# Tech stack parsing
# ---------------------------------------------------------------------------

def test_parse_tech_stack_nodejs_with_package_json(tmp_path):
    pkg = {
        "dependencies": {"express": "^4.18.0", "mongoose": "^7.0.0"},
        "scripts": {"build": "webpack"}
    }
    pkg_path = tmp_path / "package.json"
    pkg_path.write_text(json.dumps(pkg))

    tree = [{"path": "package.json"}]
    stack = parse_tech_stack("nodejs", tree, str(tmp_path))

    assert stack["language"] == "Node.js"
    assert stack["framework"] == "Express.js"
    assert stack["database"] == "MongoDB"
    assert stack["build_tool"] == "npm/webpack"


def test_parse_tech_stack_go_with_go_mod(tmp_path):
    go_mod = tmp_path / "go.mod"
    go_mod.write_text("module example.com/app\n\ngo 1.21\n")

    tree = [{"path": "go.mod"}]
    stack = parse_tech_stack("go", tree, str(tmp_path))

    assert stack["language"] == "Go"
    assert stack["build_tool"] == "Go Modules"


# ---------------------------------------------------------------------------
# Architecture building
# ---------------------------------------------------------------------------

def test_build_architecture_basic():
    core_files = [
        {"path": "main.go", "type": "entry", "reason": "Entry point"},
        {"path": "controller/api.go", "type": "route", "reason": "Routes"},
    ]
    arch = build_architecture("go", core_files, [])

    assert "Go" in arch["description"]
    assert len(arch["components"]) == 2
    assert arch["components"][0]["name"] == "入口"
    assert "入口" in arch["data_flow"]


# ---------------------------------------------------------------------------
# Deployment building
# ---------------------------------------------------------------------------

def test_build_deployment_with_docker():
    core_files = [
        {"path": "Dockerfile", "type": "deploy", "reason": "Docker"},
        {"path": "main.go", "type": "entry", "reason": "Entry"},
    ]
    deploy = build_deployment(core_files, [])

    assert "Docker" in deploy["description"]
    assert "docker build" in deploy["docker_command"]


# ---------------------------------------------------------------------------
# Files analyzed building
# ---------------------------------------------------------------------------

def test_build_files_analyzed_basic():
    core_files = [
        {"path": "main.go", "type": "entry", "reason": "Entry", "size": 200},
    ]
    files = build_files_analyzed(core_files, "go")

    assert len(files) == 1
    assert files[0]["path"] == "main.go"
    assert files[0]["language"] == "go"
    assert files[0]["analysis"] == "Entry"
    assert files[0]["code_snippet"] == ""


def test_build_files_analyzed_with_contents(tmp_path):
    src = tmp_path / "main.go"
    src.write_text("package main\n\nfunc main() {\n\tprintln(\"hello\")\n}\n")

    core_files = [
        {"path": "main.go", "type": "entry", "reason": "Entry", "size": 200},
    ]
    files = build_files_analyzed(core_files, "go", str(tmp_path))

    assert files[0]["code_snippet"] != ""
    assert "package main" in files[0]["code_snippet"]
    assert "行代码)" in files[0]["analysis"]

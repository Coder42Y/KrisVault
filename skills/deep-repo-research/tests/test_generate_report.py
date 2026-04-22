import json
import os
import tempfile

import pytest
from jinja2 import Template

from scripts.generate_report import render_report, load_template, generate_report


# ---------------------------------------------------------------------------
# render_report
# ---------------------------------------------------------------------------

def test_render_report_basic():
    data = {
        "repo_name": "test-repo",
        "repo_url": "https://github.com/test/repo",
        "branch": "main",
        "generated_at": "2026-04-21",
        "tech_stack": {"language": "Go", "framework": "Gin"},
        "overview": "A test project.",
        "architecture": {"description": "Simple MVC."},
        "files_analyzed": [],
        "deployment": {"description": "Docker."},
        "summary": "Good project.",
    }
    template_content = "# {{ repo_name }}\n\n{{ overview }}"
    template = Template(template_content)
    result = render_report(data, template)
    assert "# test-repo" in result
    assert "A test project." in result


# ---------------------------------------------------------------------------
# load_template
# ---------------------------------------------------------------------------

def test_user_template_override(tmp_path):
    # Create user override directory
    user_dir = tmp_path / "user_templates"
    user_dir.mkdir(parents=True)
    (user_dir / "overview.md.j2").write_text("USER OVERRIDE: {{ repo_name }}")

    # Test loading from specific directory
    template = load_template("overview", template_dir=str(user_dir))
    result = template.render(repo_name="test")
    assert result == "USER OVERRIDE: test"


# ---------------------------------------------------------------------------
# generate_report (end-to-end)
# ---------------------------------------------------------------------------

def test_generate_report_e2e(tmp_path):
    data = {
        "repo_name": "my-project",
        "repo_url": "https://github.com/user/repo",
        "branch": "main",
        "generated_at": "2026-04-21",
        "tech_stack": {"language": "Python", "framework": "Flask"},
        "overview": "A Flask app.",
        "architecture": {"description": "Simple.", "components": [], "data_flow": ""},
        "files_analyzed": [],
        "deployment": {"description": "Docker.", "env_vars": [], "docker_command": "", "config_example": ""},
        "summary": "Works well.",
    }

    data_path = tmp_path / "analysis.json"
    with open(data_path, "w") as f:
        json.dump(data, f)

    # Need a template directory
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "full.md.j2").write_text("# {{ repo_name }}\n\n{{ overview }}")

    output_path = tmp_path / "report.md"
    generate_report(str(data_path), style="full", output=str(output_path), template_dir=str(template_dir))

    content = output_path.read_text()
    assert "# my-project" in content
    assert "A Flask app." in content


# ---------------------------------------------------------------------------
# all built-in templates render
# ---------------------------------------------------------------------------

def test_all_templates_render():
    data = {
        "repo_name": "test",
        "repo_url": "https://github.com/test/repo",
        "branch": "main",
        "generated_at": "2026-04-21",
        "tech_stack": {"language": "Go", "framework": "Gin", "database": "SQLite", "build_tool": "Go Modules"},
        "overview": "Test overview.",
        "architecture": {
            "description": "MVC pattern.",
            "components": [{"name": "Router", "path": "router.go", "description": "Routes requests."}],
            "data_flow": "Request -> Router -> Controller -> Model -> DB"
        },
        "files_analyzed": [
            {"path": "main.go", "language": "go", "analysis": "Entry point.", "code_snippet": "func main() {}"}
        ],
        "deployment": {
            "description": "Docker.",
            "env_vars": [{"name": "PORT", "description": "Server port", "default": "8080"}],
            "docker_command": "docker build -t app .",
            "config_example": "port: 8080"
        },
        "summary": "Good project."
    }

    for style in ["overview", "architecture", "deployment", "full"]:
        template = load_template(style)
        result = render_report(data, template)
        assert f"# {data['repo_name']}" in result or data['repo_name'] in result
        assert len(result) > 100  # Should produce meaningful content

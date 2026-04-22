"""Generate Markdown report from analysis data using Jinja2 templates."""
import argparse
import json
import os
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, Template


def get_template_dirs() -> list:
    """Return list of template directories to search.

    Priority:
    1. User overrides: ~/.deep-repo-research/templates/
    2. Built-in: <script_dir>/../templates/
    """
    dirs = []
    user_dir = Path.home() / ".deep-repo-research" / "templates"
    if user_dir.exists():
        dirs.append(str(user_dir))

    builtin_dir = Path(__file__).parent.parent / "templates"
    dirs.append(str(builtin_dir))
    return dirs


def load_template(style: str, template_dir: str = None) -> Template:
    """Load a Jinja2 template by style name."""
    template_name = f"{style}.md.j2"

    if template_dir:
        dirs = [template_dir]
    else:
        dirs = get_template_dirs()

    env = Environment(loader=FileSystemLoader(dirs), trim_blocks=True, lstrip_blocks=True)
    return env.get_template(template_name)


def render_report(data: dict, template: Template) -> str:
    """Render the template with analysis data."""
    return template.render(**data)


def generate_report(data_json: str, style: str = "full", output: str = None, template_dir: str = None):
    """Main entry point."""
    with open(data_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    template = load_template(style, template_dir)
    report = render_report(data, template)

    output_path = output or f"report_{style}.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Generated {style} report: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Markdown report from analysis data")
    parser.add_argument("data_json", help="JSON file containing analysis results")
    parser.add_argument("--style", default="full", choices=["overview", "architecture", "deployment", "full"], help="Report style")
    parser.add_argument("--output", help="Output Markdown file path")
    parser.add_argument("--template-dir", help="Custom template directory")
    args = parser.parse_args()
    generate_report(args.data_json, args.style, args.output, args.template_dir)

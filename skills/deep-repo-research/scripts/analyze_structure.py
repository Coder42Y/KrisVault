"""Analyze repository structure and identify core source files."""
import argparse
import json
import sys
from pathlib import Path


LANGUAGE_INDICATORS = {
    "go": ["go.mod", "go.sum", "main.go"],
    "nodejs": ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"],
    "python": ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"],
    "java": ["pom.xml", "build.gradle", "gradlew"],
    "rust": ["Cargo.toml", "Cargo.lock"],
    "ruby": ["Gemfile", "config.ru"],
}

FILE_PATTERNS = {
    "go": {
        "entry": ["main.go", "cmd/*/main.go"],
        "route": ["controller/", "handler/", "router/", "api/"],
        "model": ["model/", "models/", "entity/", "domain/"],
        "service": ["service/", "services/", "biz/", "usecase/"],
        "config": ["config/", "conf/", "settings/"],
        "middleware": ["middleware/", "middlewares/"],
    },
    "nodejs": {
        "entry": ["index.js", "server.js", "app.js", "main.js"],
        "route": ["routes/", "router/", "controllers/"],
        "model": ["models/", "schemas/", "entities/"],
        "service": ["services/", "business/", "usecases/"],
        "config": ["config/", "configs/"],
        "middleware": ["middleware/", "middlewares/"],
    },
    "python": {
        "entry": ["main.py", "app.py", "manage.py", "wsgi.py", "asgi.py"],
        "route": ["routes/", "views/", "urls.py", "blueprints/"],
        "model": ["models/", "models.py", "db/"],
        "service": ["services/", "tasks/", "celery/"],
        "config": ["config/", "settings/", "configs/"],
        "middleware": ["middleware/", "middlewares/"],
    },
    "java": {
        "entry": ["*Application.java", "*Main.java"],
        "route": ["controller/", "web/", "rest/"],
        "model": ["model/", "entity/", "domain/", "dto/"],
        "service": ["service/", "services/", "business/"],
        "config": ["config/", "configuration/"],
        "middleware": ["interceptor/", "filter/"],
    },
    "rust": {
        "entry": ["main.rs", "lib.rs"],
        "route": ["routes/", "handlers/", "controllers/"],
        "model": ["models/", "entities/", "schema/"],
        "service": ["services/", "usecases/", "logic/"],
        "config": ["config/", "settings/"],
        "middleware": ["middleware/"],
    },
    "ruby": {
        "entry": ["config.ru", "app.rb"],
        "route": ["controllers/", "routes/"],
        "model": ["models/"],
        "service": ["services/", "workers/"],
        "config": ["config/", "initializers/"],
        "middleware": ["middleware/"],
    },
}

DEPLOY_PATTERNS = [
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Makefile",
    "deploy/",
    "deployment/",
    "helm/",
    "k8s/",
    "kubernetes/",
    "terraform/",
    ".github/workflows/",
    ".gitlab-ci.yml",
]

README_PATTERNS = ["README.md", "README.rst", "README.txt"]


def detect_language(tree: list) -> str:
    """Detect primary language from file indicators."""
    paths = {item.get("path", "") for item in tree}
    for lang, indicators in LANGUAGE_INDICATORS.items():
        if any(ind in paths for ind in indicators):
            return lang
    # Fallback: check file extensions
    exts = {}
    for item in tree:
        path = item.get("path", "")
        ext = Path(path).suffix.lstrip(".")
        if ext:
            exts[ext] = exts.get(ext, 0) + 1
    # Simple fallback ranking
    ext_priority = {"go": 1, "js": 2, "ts": 2, "py": 3, "java": 4, "rs": 5, "rb": 6}
    for ext, priority in ext_priority.items():
        if ext in exts and exts[ext] > 2:
            mapping = {"go": "go", "js": "nodejs", "ts": "nodejs", "py": "python", "java": "java", "rs": "rust", "rb": "ruby"}
            return mapping.get(ext, "unknown")
    return "unknown"


def match_pattern(path: str, pattern: str) -> bool:
    """Check if path matches a pattern (supports * wildcard and directory prefix)."""
    if pattern.endswith("/"):
        return path.startswith(pattern) or ("/" + pattern) in path
    if "*" in pattern:
        import fnmatch
        return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(Path(path).name, pattern)
    return path == pattern or Path(path).name == pattern


def score_file(path: str, language: str) -> tuple:
    """Score a single file. Returns (priority, file_type, reason)."""
    filename = Path(path).name
    ext = Path(path).suffix.lower()

    # Check deployment patterns
    for pattern in DEPLOY_PATTERNS:
        if match_pattern(path, pattern):
            return (80, "deploy", f"Matches deployment pattern: {pattern}")

    # Check README
    for pattern in README_PATTERNS:
        if match_pattern(path, pattern):
            return (85, "doc", "README file")

    # Check dependency/config files
    if filename in ("go.mod", "package.json", "requirements.txt", "pyproject.toml",
                    "Cargo.toml", "pom.xml", "build.gradle", "Gemfile"):
        return (90, "config", f"Dependency/config file: {filename}")

    # Language-specific patterns
    patterns = FILE_PATTERNS.get(language, {})
    priority_map = {"entry": 95, "route": 90, "model": 85, "service": 80, "config": 75, "middleware": 70}

    for file_type, type_patterns in patterns.items():
        for pattern in type_patterns:
            if match_pattern(path, pattern):
                priority = priority_map.get(file_type, 50)
                return (priority, file_type, f"{language} project, matches {file_type} pattern: {pattern}")

    # Generic source file boost
    if ext in (".go", ".js", ".ts", ".py", ".java", ".rs", ".rb"):
        return (30, "source", f"{language} source file")

    return (10, "other", "Other file")


def score_files(tree: list, language: str) -> list:
    """Score all files in the tree."""
    scored = []
    for item in tree:
        path = item.get("path", "")
        if not path:
            continue
        priority, file_type, reason = score_file(path, language)
        scored.append({
            "path": path,
            "type": file_type,
            "priority": priority,
            "reason": reason,
            "size": item.get("size", 0),
        })
    # Sort by priority descending
    scored.sort(key=lambda x: x["priority"], reverse=True)
    return scored


def analyze_structure(repo_tree_json: str, max_files: int = 15, output: str = None):
    """Main entry point."""
    with open(repo_tree_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    tree = data.get("files", data.get("tree", []))
    language = detect_language(tree)
    scored = score_files(tree, language)

    result = {
        "repo_url": data.get("repo_url", ""),
        "platform": data.get("platform", ""),
        "owner": data.get("owner", ""),
        "repo": data.get("repo", ""),
        "branch": data.get("branch", ""),
        "detected_language": language,
        "max_files": max_files,
        "core_files": scored[:max_files],
    }

    output_path = output or "core_files.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Detected language: {language}")
    print(f"Identified {len(result['core_files'])} core files (out of {len(tree)} total)")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze repository structure and identify core files")
    parser.add_argument("repo_tree_json", help="JSON file from fetch_repo.py --list-only")
    parser.add_argument("--max-files", type=int, default=15, help="Maximum files to return")
    parser.add_argument("--output", help="Output JSON file path")
    args = parser.parse_args()
    analyze_structure(args.repo_tree_json, args.max_files, args.output)

"""Analyze repository structure and identify core source files."""
import argparse
import json
import sys
from datetime import datetime
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


# ---------------------------------------------------------------------------
# New: build report fields from analysis
# ---------------------------------------------------------------------------

LANGUAGE_DISPLAY = {
    "go": "Go",
    "nodejs": "Node.js",
    "python": "Python",
    "java": "Java",
    "rust": "Rust",
    "ruby": "Ruby",
    "unknown": "Unknown",
}


def _read_file_text(contents_dir: str, path: str, max_chars: int = 8000) -> str:
    """Read text content of a file from contents_dir."""
    if not contents_dir:
        return ""
    full_path = Path(contents_dir) / path
    if not full_path.exists():
        return ""
    try:
        text = full_path.read_text(encoding="utf-8", errors="ignore")
        return text[:max_chars]
    except Exception:
        return ""


def _extract_code_snippet(content: str, max_lines: int = 30) -> str:
    """Extract first N non-empty lines as code snippet."""
    lines = content.splitlines()
    # Skip shebang and common header comments if possible
    start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("//") and not stripped.startswith("/*") and not stripped.startswith("*"):
            start = i
            break
    selected = lines[start:start + max_lines]
    return "\n".join(selected)


def parse_tech_stack(language: str, tree: list, contents_dir: str = None) -> dict:
    """Parse tech stack from dependency files."""
    stack = {
        "language": LANGUAGE_DISPLAY.get(language, language),
        "framework": "未明确",
        "database": "未明确",
        "build_tool": "未明确",
    }

    paths = {item.get("path", ""): item for item in tree}

    # Try to read package.json
    if "package.json" in paths and contents_dir:
        content = _read_file_text(contents_dir, "package.json")
        try:
            pkg = json.loads(content)
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

            # Detect framework
            fw_map = {
                "express": "Express.js",
                "koa": "Koa",
                "fastify": "Fastify",
                "nestjs": "NestJS",
                "next": "Next.js",
                "react": "React",
                "vue": "Vue.js",
                "angular": "Angular",
                "svelte": "Svelte",
                "hapi": "Hapi",
            }
            for dep, fw_name in fw_map.items():
                if dep in deps:
                    stack["framework"] = fw_name
                    break

            # Detect database
            db_map = {
                "mongoose": "MongoDB",
                "mongodb": "MongoDB",
                "sequelize": "SQL (via Sequelize)",
                "typeorm": "SQL (via TypeORM)",
                "prisma": "SQL (via Prisma)",
                "redis": "Redis",
                "ioredis": "Redis",
                "pg": "PostgreSQL",
                "mysql2": "MySQL",
                "sqlite3": "SQLite",
            }
            for dep, db_name in db_map.items():
                if dep in deps:
                    stack["database"] = db_name
                    break

            # Detect build tool
            scripts = pkg.get("scripts", {})
            if "build" in scripts or "webpack" in deps:
                stack["build_tool"] = "npm/webpack"
            elif "vite" in deps:
                stack["build_tool"] = "Vite"
            else:
                stack["build_tool"] = "npm"
        except Exception:
            pass

    # Try go.mod
    elif "go.mod" in paths and contents_dir:
        content = _read_file_text(contents_dir, "go.mod")
        stack["build_tool"] = "Go Modules"
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("go "):
                stack["framework"] = f"Go {line[3:].strip()}"
                break

    # Try requirements.txt or pyproject.toml
    elif ("requirements.txt" in paths or "pyproject.toml" in paths) and contents_dir:
        stack["build_tool"] = "pip"
        if "pyproject.toml" in paths:
            content = _read_file_text(contents_dir, "pyproject.toml")
            if "poetry" in content:
                stack["build_tool"] = "Poetry"
            elif "hatch" in content:
                stack["build_tool"] = "Hatch"
        # Try to detect framework from requirements
        req_path = "requirements.txt" if "requirements.txt" in paths else None
        if req_path:
            content = _read_file_text(contents_dir, req_path)
            fw_map = {
                "django": "Django",
                "flask": "Flask",
                "fastapi": "FastAPI",
                "tornado": "Tornado",
                "bottle": "Bottle",
            }
            for dep, fw_name in fw_map.items():
                if dep in content.lower():
                    stack["framework"] = fw_name
                    break
            db_map = {
                "psycopg": "PostgreSQL",
                "pymongo": "MongoDB",
                "sqlalchemy": "SQL (via SQLAlchemy)",
                "redis": "Redis",
                "pymysql": "MySQL",
            }
            for dep, db_name in db_map.items():
                if dep in content.lower():
                    stack["database"] = db_name
                    break

    # Try Cargo.toml
    elif "Cargo.toml" in paths and contents_dir:
        stack["build_tool"] = "Cargo"
        content = _read_file_text(contents_dir, "Cargo.toml")
        fw_map = {
            "actix": "Actix-web",
            "rocket": "Rocket",
            "axum": "Axum",
            "warp": "Warp",
            "tide": "Tide",
        }
        for dep, fw_name in fw_map.items():
            if dep in content.lower():
                stack["framework"] = fw_name
                break

    # Try pom.xml / build.gradle
    elif ("pom.xml" in paths or "build.gradle" in paths) and contents_dir:
        stack["build_tool"] = "Maven" if "pom.xml" in paths else "Gradle"

    return stack


def build_architecture(language: str, core_files: list, tree: list) -> dict:
    """Build architecture description from file structure."""
    components = []
    type_names = {
        "entry": "入口",
        "route": "路由/API",
        "model": "数据模型",
        "service": "业务逻辑",
        "config": "配置",
        "middleware": "中间件",
        "deploy": "部署",
        "doc": "文档",
        "source": "源码",
    }

    seen_types = set()
    for f in core_files[:10]:
        ft = f["type"]
        if ft in seen_types:
            continue
        seen_types.add(ft)
        components.append({
            "name": type_names.get(ft, ft),
            "path": f["path"],
            "description": f["reason"],
        })

    desc = f"{LANGUAGE_DISPLAY.get(language, language)} 项目，"
    if components:
        desc += f"包含 {len(components)} 个核心模块。"
    else:
        desc += "项目结构较为简单。"

    # Build a simple data flow description
    flow_parts = []
    if any(c["name"] == "入口" for c in components):
        flow_parts.append("入口启动服务")
    if any(c["name"] == "路由/API" for c in components):
        flow_parts.append("路由接收请求")
    if any(c["name"] == "业务逻辑" for c in components):
        flow_parts.append("业务层处理逻辑")
    if any(c["name"] == "数据模型" for c in components):
        flow_parts.append("模型层操作数据")
    if any(c["name"] == "中间件" for c in components):
        flow_parts.append("中间件处理横切关注点")

    if flow_parts:
        data_flow = " → ".join(flow_parts)
    else:
        data_flow = "标准请求处理流程"

    return {
        "description": desc,
        "components": components,
        "data_flow": data_flow,
    }


def build_deployment(core_files: list, tree: list, contents_dir: str = None) -> dict:
    """Build deployment info from deploy files."""
    deploy = {
        "description": "未检测到明确的部署文档",
        "env_vars": [],
        "docker_command": "",
        "config_example": "",
    }

    has_docker = any(f["path"] in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml") for f in core_files)
    has_makefile = any(f["path"] == "Makefile" for f in core_files)
    has_ci = any(f["path"].startswith(".github/workflows/") or f["path"] == ".gitlab-ci.yml" for f in core_files)

    parts = []
    if has_docker:
        parts.append("Docker")
    if has_makefile:
        parts.append("Makefile")
    if has_ci:
        parts.append("CI/CD")

    if parts:
        deploy["description"] = f"支持 {' / '.join(parts)} 部署方式"

    seen_env_names = set()

    if has_docker:
        deploy["docker_command"] = "docker build -t app .\ndocker run -p 8080:8080 app"
        deploy["env_vars"].append({"name": "PORT", "description": "服务端口", "default": "8080"})
        seen_env_names.add("PORT")

    # Try to extract more env vars from Dockerfile or docker-compose
    if contents_dir:
        for path in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml"):
            content = _read_file_text(contents_dir, path, max_chars=2000)
            if content:
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith("ENV "):
                        parts = line[4:].split("=", 1)
                        if parts:
                            name = parts[0].strip()
                            default = parts[1].strip() if len(parts) > 1 else ""
                            if name not in seen_env_names:
                                deploy["env_vars"].append({
                                    "name": name,
                                    "description": "环境变量",
                                    "default": default,
                                })
                                seen_env_names.add(name)
                    elif line.startswith("EXPOSE "):
                        port = line[7:].strip()
                        if "PORT" not in seen_env_names:
                            deploy["env_vars"].append({
                                "name": "PORT",
                                "description": "服务端口",
                                "default": port,
                            })
                            seen_env_names.add("PORT")
                break

    return deploy


def build_files_analyzed(core_files: list, language: str, contents_dir: str = None) -> list:
    """Convert core_files to files_analyzed format."""
    files_analyzed = []
    ext_map = {
        "go": "go", "nodejs": "javascript", "python": "python",
        "java": "java", "rust": "rust", "ruby": "ruby", "unknown": "text",
    }
    lang = ext_map.get(language, language)

    for f in core_files:
        entry = {
            "path": f["path"],
            "language": lang,
            "analysis": f["reason"],
            "code_snippet": "",
        }
        if contents_dir:
            content = _read_file_text(contents_dir, f["path"])
            if content:
                entry["code_snippet"] = _extract_code_snippet(content)
                # Add a brief analysis based on content length
                lines = content.count("\n")
                entry["analysis"] = f"{f['reason']} ({lines} 行代码)"
        files_analyzed.append(entry)

    return files_analyzed


def build_overview(language: str, tech_stack: dict, total_files: int) -> str:
    """Build project overview text."""
    lang = LANGUAGE_DISPLAY.get(language, language)
    framework = tech_stack.get("framework", "未明确")
    fw_text = f"，使用 {framework} 框架" if framework != "未明确" else ""
    return f"一个 {lang} 项目{fw_text}，共 {total_files} 个文件。项目结构清晰，核心模块包括入口、路由、业务逻辑和数据模型等。"


def build_summary(language: str, tech_stack: dict, core_files_count: int) -> str:
    """Build summary text."""
    lang = LANGUAGE_DISPLAY.get(language, language)
    return f"该项目是一个结构良好的 {lang} 项目，识别出 {core_files_count} 个核心文件。建议进一步查看入口文件和路由定义以理解系统全貌。"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyze_structure(repo_tree_json: str, max_files: int = 15, output: str = None, contents_dir: str = None):
    """Main entry point."""
    with open(repo_tree_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    tree = data.get("files", data.get("tree", []))
    language = detect_language(tree)
    scored = score_files(tree, language)
    selected = scored[:max_files]

    # Build all report fields
    tech_stack = parse_tech_stack(language, tree, contents_dir)
    architecture = build_architecture(language, selected, tree)
    deployment = build_deployment(selected, tree, contents_dir)
    files_analyzed = build_files_analyzed(selected, language, contents_dir)
    overview = build_overview(language, tech_stack, len(tree))
    summary = build_summary(language, tech_stack, len(selected))

    result = {
        # Template-required fields
        "repo_name": data.get("repo", "unknown"),
        "repo_url": data.get("repo_url", ""),
        "branch": data.get("branch", ""),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tech_stack": tech_stack,
        "overview": overview,
        "architecture": architecture,
        "files_analyzed": files_analyzed,
        "deployment": deployment,
        "summary": summary,
        # Backward-compatible fields
        "platform": data.get("platform", ""),
        "owner": data.get("owner", ""),
        "repo": data.get("repo", ""),
        "detected_language": language,
        "max_files": max_files,
        "core_files": selected,
    }

    output_path = output or "analysis_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Detected language: {language}")
    print(f"Identified {len(result['core_files'])} core files (out of {len(tree)} total)")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze repository structure and identify core files")
    parser.add_argument("repo_tree_json", help="JSON file from fetch_repo.py --list-only")
    parser.add_argument("--max-files", type=int, default=15, help="Maximum files to return")
    parser.add_argument("--output", help="Output JSON file path")
    parser.add_argument("--contents-dir", help="Directory containing downloaded file contents")
    args = parser.parse_args()
    analyze_structure(args.repo_tree_json, args.max_files, args.output, args.contents_dir)

# deep-repo-research

一个 Claude Code Skill，用于自动调研 GitHub/GitLab 仓库并生成结构化 Markdown 报告。

## 功能

- 自动获取仓库文件列表，识别核心源码文件
- 支持 Go / Node.js / Python / Java / Rust / Ruby 项目
- 生成四种报告风格：概览、架构分析、部署指南、完整报告
- 支持 GitHub 和 GitLab（含私有仓库）

## 安装

```bash
git clone https://github.com/Coder42Y/deep-repo-research.git
cd deep-repo-research
pip install -r requirements.txt
```

链接到 Claude Code skills 目录：

```bash
ln -s $(pwd) ~/.claude/skills/deep-repo-research
```

## 使用

在 Claude Code 对话中：

```
/github-research https://github.com/octocat/Hello-World --style full
```

### 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `repo-url` | 仓库地址（GitHub 或 GitLab） | 必填 |
| `--style` | 报告风格：`overview`, `architecture`, `deployment`, `full` | `full` |
| `--auto` | 跳过文件列表确认，自动执行 | 否 |
| `--max-files` | 最多分析文件数 | 15 |

### 私有仓库

```bash
# GitHub
export GITHUB_TOKEN=ghp_xxx
/github-research https://github.com/yourcompany/private-repo

# GitLab
export GITLAB_TOKEN=glpat-xxx
/github-research https://gitlab.com/yourcompany/private-repo
```

## 自定义模板

在 `~/.deep-repo-research/templates/` 下创建同名模板文件即可覆盖默认模板：

```bash
mkdir -p ~/.deep-repo-research/templates
cp deep-repo-research/templates/full.md.j2 ~/.deep-repo-research/templates/
# 编辑自定义模板
```

## 项目结构

```
deep-repo-research/
├── SKILL.md              # Claude 读取的 skill 定义
├── scripts/
│   ├── fetch_repo.py     # 下载仓库文件
│   ├── analyze_structure.py  # 识别核心文件
│   └── generate_report.py    # 生成 Markdown 报告
└── templates/
    ├── overview.md.j2
    ├── architecture.md.j2
    ├── deployment.md.j2
    └── full.md.j2
```

## 开发

```bash
# 运行测试
pytest tests/ -v

# 手动测试 fetch
python scripts/fetch_repo.py https://github.com/octocat/Hello-World --list-only

# 手动测试分析
python scripts/fetch_repo.py https://github.com/octocat/Hello-World --list-only > tree.json
python scripts/analyze_structure.py tree.json --max-files 10

# 手动测试报告生成
# 先创建 analysis_result.json，然后：
python scripts/generate_report.py analysis_result.json --style full
```

## License

MIT

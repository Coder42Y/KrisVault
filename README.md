<div align="center">

<h1>🎯 <code>PainHub</code></h1>

<p>
  <b>为 Claude Code、OpenClaw 及更多 AI 工具打造的开源技能集合</b><br>
  <em>An open-source skill collection for Claude Code, OpenClaw &amp; more AI tools</em>
</p>

<p>
  <a href="#-简体中文"><kbd>🀄&nbsp;&nbsp;简体中文</kbd></a>
  &nbsp;&nbsp;
  <a href="#-english"><kbd>🇬🇧&nbsp;&nbsp;English</kbd></a>
</p>

<br>

</div>

---

<a id="简体中文"></a>

<h2>🀄 简体中文</h2>

### 简介

**PainHub** 是一个开源技能（Skill）集合仓库，兼容 [Claude Code](https://claude.ai/code)、**OpenClaw** 及各类支持技能扩展的 AI 开发工具。每个技能都是独立的模块，可单独安装到对应的 AI 环境中。

### 技能列表

| 技能 | 描述 | 版本 |
|------|------|------|
| [🎯 daily-pulse](./skills/daily-pulse/) | 每日热点推送 + 按需查询，结构化预抓取 + Agent 评分排版 | `v3.0.0` |
| [🔍 deep-repo-research](./skills/deep-repo-research/) | 自动调研 GitHub/GitLab 仓库并生成结构化 Markdown 报告。支持 Go / Node.js / Python / Java / Rust / Ruby 项目，四种报告风格，含私有仓库支持 | `v0.1.0` |

### 快速开始

```bash
git clone https://github.com/Coder42Y/PainHub.git
cd PainHub
```

进入你想使用的技能目录，按该技能的 README 安装即可。

### 设计规范

所有 Skill README 遵循统一的设计规范，见 [`DESIGN.md`](DESIGN.md)。

### 贡献指南

1. 每个技能放在 `skills/<skill-name>/` 目录下
2. 包含 `SKILL.md`（Claude 读取的技能定义）和 `README.md`（用户文档）
3. 提供完整的测试和安装说明

### 隐私声明

本仓库公开的代码和文档均经过清理，不含个人身份信息、API key / token / 密码、私有配置。个人隐私文件通过 `.gitignore` 排除。

### 许可证

[MIT](./LICENSE)

---

<a id="english"></a>

<h2>🇬🇧 English</h2>

### About

**PainHub** is an open-source skill collection compatible with [Claude Code](https://claude.ai/code), **OpenClaw**, and other AI tools that support skill extensions. Each skill is a standalone module that can be individually installed.

### Skills

| Skill | Description | Version |
|-------|-------------|---------|
| [🎯 daily-pulse](./skills/daily-pulse/) | Daily hot topics push + on-demand query, structured pre-fetching + Agent scoring | `v3.0.0` |
| [🔍 deep-repo-research](./skills/deep-repo-research/) | Research GitHub/GitLab repos and generate structured Markdown reports. Supports Go / Node.js / Python / Java / Rust / Ruby, four report styles, with private repo support | `v0.1.0` |

### Quick Start

```bash
git clone https://github.com/Coder42Y/PainHub.git
cd PainHub
```

Navigate to any skill directory and follow its README for installation.

### Design Guidelines

All skill READMEs follow a unified design system. See [`DESIGN.md`](DESIGN.md).

### Contributing

1. Place each skill in `skills/<skill-name>/`
2. Include `SKILL.md` (Claude skill definition) and `README.md` (user docs)
3. Provide complete tests and installation instructions

### Privacy

All published code and docs are sanitized. No personal info, API keys, tokens, or private configs are included. Personal files are excluded via `.gitignore`.

### License

[MIT](./LICENSE)

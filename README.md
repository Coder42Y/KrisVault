# PainHub

> OpenClaw Skills Collection — 结构化、低成本的 Agent 能力扩展

| | |
|:---|:---|
| **仓库** | `Coder42Y/PainHub` |
| **最近更新** | `2026-04-22` |

**一句话：**一组为 OpenClaw 设计的声明式 Skill，把原本由 LLM 完成的重复性工作（搜索、评分、格式化）下沉到结构化脚本，Agent 只做决策和摘要。

---

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/Coder42Y/PainHub.git

# 2. 安装单个 skill（以 daily-pulse 为例）
cp -r PainHub/skills/daily-pulse ~/.openclaw/workspace/skills/

# 3. 触发
"推热点"
```

---

## Skills

| Skill | 描述 | 状态 | 路径 |
|-------|------|------|------|
| 🎯 **daily-pulse** | 每日热点推送 + 按需查询，结构化预抓取 + 热度评分 | `stable` | [`skills/daily-pulse/`](skills/daily-pulse/) |

---

## 设计规范

所有 Skill README 遵循统一的头部设计规范，见 [`DESIGN.md`](DESIGN.md)。

核心原则：
- 首屏高密度信息（版本、状态、兼容性、更新时间）
- 一句话价值主张，站在用户角度
- 快速开始 ≤ 3 步
- 中英混排自然，不花哨

---

## 仓库结构

```
PainHub/
├── README.md              # 本文档
├── DESIGN.md              # Skill README 设计规范
├── .gitignore             # 全局忽略规则（隐私文件 + OS 文件）
└── skills/
    └── daily-pulse/       # 每日热点推送
        ├── SKILL.md
        ├── README.md
        └── scripts/
```

---

## 隐私声明

本仓库公开的代码和文档均经过清理，不含：
- 个人身份信息
- API key / token / 密码
- 私有配置（cron 任务、memory 记录等）

个人隐私文件通过 `.gitignore` 排除，保存在本地分支 `backup/personal-state`，永不推送。

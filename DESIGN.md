# OpenClaw Skills README Design System

> 本规范约束 `workspace/skills/<skill-name>/README.md` 的头部设计。
> 所有 skill README 的开头必须遵循此模板，保持品牌一致性。

---

## 设计原则

1. **一眼识别** — 从任意 skill 的 README 能立刻认出这是 kris 的 OpenClaw 技能库
2. **信息密度高** — 首屏包含：它是啥、状态如何、怎么用、关键数据
3. **不花哨** — 不用 ASCII art、不用 badge 泛滥、不用复杂排版
4. **中英文混排自然** — 标题/关键标签用中文，技术细节用英文

---

## 头部模板（必须）

```markdown
# 🎯 SkillName

> <one-line description in Chinese>

| | |
|:---|:---|
| **版本** | `vX.Y.Z` |
| **状态** | `stable` / `beta` / `wip` |
| **OpenClaw** | `>= 0.x.x` |
| **最近更新** | `YYYY-MM-DD` |

**一句话：**<一句话说明这个 skill 解决什么问题，适合什么场景>

---
```

### 字段说明

| 字段 | 规则 |
|------|------|
| `🎯` | emoji 标识符，每个 skill 有专属 emoji，体现领域特征 |
| `SkillName` | 英文 skill key（如 `hot-topics`、`zhihu-notes`），不加空格 |
| `版本` | 语义化版本，与 SKILL.md frontmatter 的 version 保持一致 |
| `状态` | 三选一：`stable`（稳定可用）、`beta`（可用但边缘未打磨）、`wip`（开发中） |
| `OpenClaw` | 最低兼容版本，不写 `latest` |
| `最近更新` | 最后一次有意义改动的日期 |
| `一句话` | 不超过 80 字，站在用户角度写价值，不写技术细节 |

---

## 快速开始块（必须）

紧跟头部之后，三段式：

```markdown
## 快速开始

```bash
# 1. 安装/激活
<one command to get it running>

# 2. 触发
<example trigger phrase>

# 3. 配置文件（如有）
<path to config file>
```
```

规则：
- 安装命令 ≤ 2 行
- 触发词必须是从用户口中说出来的自然语言，不是技术命令
- 配置文件路径用 `~` 简写，不要写绝对路径

---

## 特性亮点（可选但推荐）

用 bullet list，每项格式：

```markdown
- **特性名** — 一句话说明，附 emoji
```

不超过 5 项。不要写"简单易用"这种废话。

---

## 风格细节

### Emoji 使用

- 头部：领域 emoji 1 个（如 `🎯` `🤖` `📱`）
- 特性列表：每行 1 个相关 emoji
- 禁止：连续 3 个以上 emoji、用 emoji 替代标点、不同 section 风格不一致

### 分隔线

- 头部和正文之间用 `---`
- 大章节之间用 `---` 或二级标题
- 不要用 `***` 或 `<hr>`

### 代码块

- bash 命令用 ```` ```bash ````
- JSON 配置用 ```` ```json ````
- 输出示例用 ```` ```markdown ````

### 中英文排版

- 中文和英文/数字之间留空格（如 `OpenClaw v3`）
- 代码、路径、版本号不翻译，保持英文
- 标点用中文全角（，。：；）

---

## 示例：hot-topics

```markdown
# 🎯 hot-topics

> 每日热点推送 + 按需查询，结构化预抓取 + Agent 评分排版

| | |
|:---|:---|
| **版本** | `v3.0.0` |
| **状态** | `stable` |
| **OpenClaw** | `>= 0.5.0` |
| **最近更新** | `2026-04-21` |

**一句话：**让 Agent 用 5 秒完成全网热点抓取，再用 LLM 做热度评分和一句话摘要，替代过去 3 分钟、44K tokens 的纯 LLM 搜索模式。

---
```

---

## 禁忌

- ❌ 不用 shields.io badge
- ❌ 不用 "Star ⭐ this repo" 呼吁
- ❌ 不用 ASCII logo / banner 图
- ❌ 不用表格做版本对比（Changelog 另放）
- ❌ 不用 "Table of Contents" 自动目录（GitHub 自带）

---

*最后更新：2026-04-21*

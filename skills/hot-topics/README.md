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

## 快速开始

```bash
# 1. 安装
# 将本目录复制到 OpenClaw skills 目录
cp -r hot-topics ~/.openclaw/workspace/skills/

# 2. 触发（直接跟 Agent 说）
"推热点"
"给我看看 AI"
"GitHub 热门"

# 3. 配置文件
~/.openclaw/cron/hot-topics-prefs.json
```

---

## 为什么做这个

v2 版本是纯 LLM 驱动：Agent 自己决定搜索什么、用什么工具、怎么合并结果。每次推送要调 25 次工具、加载 44K tokens、耗时 183 秒，成本高、不可预测、对弱模型不友好。

v3 把**搜索和评分**从 LLM 手里拿回来，写成零依赖 Node.js 脚本。LLM 只做它擅长的事：生成摘要和排版。

---

## 特性

- **⚡ 5 秒预抓取** — `fetch.js` 并行拉取所有源，纯 Node.js 内置模块，零外部依赖
- **📊 结构化评分** — `source_weight × time_decay × social_bonus × (1 + ai_semantic_bonus)`，按热度取 Top N
- **🔥 热点新闻宁缺毋滥** — `min_score = 2.5`，不够格就显示「今日无重大热点」，绝不凑数
- **⭐ GitHub 日增速排序** — 追踪每日新增 stars，不是总星数，发现真正在爆发的项目
- **🎙️ 按需查询** — "给我看看 AI"、"CS2 赛程"、"开源趋势"，实时触发指定板块

---

## 架构

```
用户 / Cron ──▶ fetch.js ──▶ /tmp/hot-topics-raw.json ──▶ Agent ──▶ 推送
               (Node.js)        (结构化 JSON)           (评分+摘要)
```

**三层分工：**

| 层 | 职责 | 耗时 |
|---|------|------|
| 预抓取层 `fetch.js` | 并行 HTTP 请求、RSS 解析、JSON 结构化 | ~5-10s |
| 评分层 Agent | 读取 JSON、计算热度分、排序过滤 | ~1-2s |
| 生成层 LLM | 每板块生成一句话摘要、按模板排版 | ~10-20s |

**总计：~20-40s**（vs v2 的 183s）

---

## 热度评分公式

```
score = source_weight × time_decay × social_bonus × (1 + ai_semantic_bonus)
```

| 因子 | 说明 |
|------|------|
| `source_weight` | 来源可信度权重。HN 1.2-1.5，RSS 源按权威度 1.0-1.5，默认 1.0 |
| `time_decay` | 时效衰减。24h 内 = 1.0，24-48h = 0.7，48-72h = 0.4，>72h = 0.1 |
| `social_bonus` | HN upvotes ≥ 100 = +0.5，≥ 50 = +0.3，< 50 = 0 |
| `ai_semantic_bonus` | LLM 判断是否为重大突破/事件，硬上限 0.5，宁缺毋滥 |

Agent 按 `score` 降序排列，取每个板块的 `target_count` 条。`hot-news` 板块额外要求 `min_score >= 2.5`。

---

## 配置

编辑 `~/.openclaw/cron/hot-topics-prefs.json`：

```json
{
  "version": 3,
  "push_time": "9:30",
  "freshness": "48h",

  "preset_topics": {
    "hot-news": {
      "enabled": true,
      "target_count": 3,
      "min_score": 2.5,
      "sources": [
        {"name": "HN front page", "weight": 1.5, "api": "hn_algolia", "tag": "front_page"}
      ]
    },
    "ai": {
      "enabled": true,
      "target_count": 8,
      "sources": [
        {"name": "HN AI", "weight": 1.2, "api": "hn_algolia", "query": "artificial intelligence"},
        {"name": "TechCrunch AI", "weight": 1.2, "rss": "https://techcrunch.com/category/artificial-intelligence/feed/"}
      ]
    },
    "finance": {
      "enabled": true,
      "target_count": 6,
      "sources": [
        {"name": "HN finance", "weight": 1.2, "api": "hn_algolia", "query": "finance"}
      ]
    },
    "esports": {
      "enabled": true,
      "target_count": 5,
      "sources": [
        {"name": "HN gaming", "weight": 1.0, "api": "hn_algolia", "query": "gaming"}
      ]
    },
    "football": {
      "enabled": true,
      "target_count": 5,
      "focus_clubs": ["巴萨", "迈阿密国际"],
      "sources": [
        {"name": "BBC Sport", "weight": 1.1, "rss": "http://feeds.bbci.co.uk/sport/football/rss.xml"}
      ]
    },
    "github": {
      "enabled": true,
      "target_count": 4,
      "sources": [
        {"name": "GitHub Trending API", "weight": 1.0, "api": "github_search", "exclude_orgs": ["microsoft", "google", "meta"]}
      ]
    },
    "tech": {
      "enabled": true,
      "target_count": 6,
      "sources": [
        {"name": "HN tech", "weight": 1.2, "api": "hn_algolia", "query": "technology"}
      ]
    }
  },

  "custom_topics": [],

  "global": {
    "max_parallel_requests": 8,
    "request_timeout_ms": 15000,
    "cache_ttl_hours": 24,
    "ai_semantic_bonus_max": 0.5
  }
}
```

### Source 类型

| 类型 | 字段 | 说明 |
|------|------|------|
| RSS | `rss` | 任何标准 RSS feed，正则解析 |
| HN Algolia | `api: "hn_algolia"` + `tag` 或 `query` | `tag` 用于官方标签，`query` 用于关键词搜索 |
| GitHub Search | `api: "github_search"` | 搜索近 2 天创建的仓库，按 stars 排序，支持 `exclude_orgs` |
| 通用 JSON | `url` | 直接 GET，取 `.hits` 或 `.items` |

### 自定义板块

在 `custom_topics` 追加：

```json
{
  "name": "SpaceX",
  "keywords": ["SpaceX", "Starship"],
  "target_count": 3,
  "sources": [{"name": "HN", "api": "hn_algolia", "query": "SpaceX"}]
}
```

---

## 触发词

### 定时推送

Cron 每天 9:30 自动执行。payload：`请执行每日热点推送`。

### 一键催推（全量）

```
推热点
立即推送
我要看热点
今日热点
热点日报
```

### 按需查询（指定板块）

| 你说 | Agent 返回 |
|------|-----------|
| "给我看看 AI" / "AI 简讯" | `ai` 板块 |
| "查一下财经" / "股市动态" | `finance` 板块 |
| "GitHub 热门" / "开源趋势" | `github` 板块 |
| "CS2 赛程" / "电竞赛果" | `esports` 板块 |
| "AI 和财经简讯" | `ai` + `finance` 两个板块 |

---

## 性能对比

| 指标 | v2 (LLM 全驱动) | v3 (预抓取 + LLM 摘要) |
|------|----------------|----------------------|
| 单次推送耗时 | 183s | ~20-40s |
| 输入 tokens | 44,140 | ~2,000-4,000 |
| 工具调用次数 | 25 次 | 2 次（exec fetch.js + read JSON）|
| 对弱模型兼容性 | 差（全靠 LLM 判断） | 好（结构化评分已做） |
| 可扩展性 | 难（改 prompt） | 易（改 JSON 配置） |

---

## 文件结构

```
hot-topics/
├── SKILL.md              # Agent 指令（核心，YAML frontmatter + Markdown 正文）
├── README.md             # 本文档
├── scripts/
│   ├── fetch.js          # 预抓取脚本：并行 HTTP、RSS 解析、GitHub/HN API
│   ├── cache.js          # 缓存读写：GitHub stars 历史、原子写入、路径安全
│   └── test.js           # 自动化测试：57 项断言
├── docs/
│   └── superpowers/
│       ├── specs/        # v3 设计文档
│       └── plans/        # 实现计划
└── ARCHITECTURE.md       # 深度调研报告（v2 工作方式分析）
```

---

## 要求

- **OpenClaw** `>= 0.5.0`（支持 Skill 系统 + Cron + isolated session）
- **Node.js** `>= 18`（仅使用内置 `https` / `http` / `fs`，零外部依赖）

---

## 测试

```bash
cd ~/.openclaw/workspace/skills/hot-topics/scripts
node test.js
```

覆盖：cache 读写与安全、RSS 解析、v3 配置格式、fetch.js 端到端、SKILL.md 指令完整性。57 项断言，全部通过。

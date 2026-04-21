# Hot-Topics Skill for OpenClaw

每日热点推送 + 按需查询的 OpenClaw Skill。结构化预抓取 + Agent 评分排版，低成本、高质量、可扩展。

---

## 功能

- **7 个预设板块**：热点新闻、AI、财经、电竞、足球、GitHub 趋势、科技数码
- **用户自定义板块**：声明式配置，自动扩展
- **按需查询**：实时触发指定板块，支持模糊匹配和多板块组合
- **热度评分**：来源权重 × 时效衰减 × 社交信号 × AI 语义加成
- **GitHub 日增速排序**：追踪开源项目每日新增 stars，而非总星数
- **零依赖预抓取**：纯 Node.js 内置模块，~5-10 秒完成全量抓取

---

## 安装

```bash
# 1. 将本目录复制到 OpenClaw skills 目录
cp -r hot-topics ~/.openclaw/workspace/skills/

# 2. 初始化配置文件（首次运行会自动创建）
node ~/.openclaw/workspace/skills/hot-topics/scripts/fetch.js
```

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
    }
  },
  "custom_topics": [],
  "global": {
    "max_parallel_requests": 8,
    "request_timeout_ms": 15000,
    "ai_semantic_bonus_max": 0.5
  }
}
```

### 配置字段说明

| 字段 | 说明 |
|------|------|
| `version` | 配置版本，必须为 `3` |
| `push_time` | 定时推送时间（HH:mm） |
| `freshness` | 内容时效过滤：`24h` 或 `48h` |
| `preset_topics` | 预设板块配置 |
| `custom_topics` | 用户自定义板块数组 |
| `global` | 全局设置：并行数、超时、AI 语义加成上限 |

### Source 类型

| 类型 | 字段 | 示例 |
|------|------|------|
| RSS | `rss` | `"rss": "https://example.com/feed.xml"` |
| HN Algolia | `api: "hn_algolia"` + `tag` 或 `query` | `"tag": "front_page"` / `"query": "AI"` |
| GitHub Search | `api: "github_search"` | `"exclude_orgs": ["microsoft"]` |
| 通用 JSON | `url` | `"url": "https://api.example.com/news"` |

---

## 使用

### 定时推送

设置 Cron job，每天自动执行：

```json
{
  "schedule": {"kind": "cron", "expr": "30 9 * * *", "tz": "Asia/Shanghai"},
  "sessionTarget": "isolated",
  "payload": {"kind": "agentTurn", "message": "请执行每日热点推送"}
}
```

### 按需查询触发词

| 触发词 | 行为 |
|--------|------|
| `推热点` / `今日热点` | 立即执行全量推送 |
| `给我看看AI` / `AI简讯` | 只返回 AI 板块 |
| `GitHub热门` / `开源趋势` | 只返回 GitHub 板块 |
| `AI和财经简讯` | 返回 AI + 财经 两个板块 |
| `CS2赛程` / `足球赛果` | 返回电竞 / 足球板块 |

---

## 架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Cron / 用户    │────▶│  fetch.js       │────▶│  /tmp/hot-topics│
│   触发          │     │  (Node.js 零依赖)│     │  -raw.json      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │  Agent (OpenClaw)│
                                               │  - 读取 JSON      │
                                               │  - 热度评分排序   │
                                               │  - LLM 生成摘要   │
                                               │  - Markdown 输出  │
                                               └─────────────────┘
```

- **预抓取层**：`fetch.js` 并行抓取所有数据源，输出结构化 JSON
- **评分层**：Agent 按公式计算热度，过滤、排序
- **生成层**：LLM 为每条内容生成一句话摘要，按模板排版

### 热度评分公式

```
score = source_weight × time_decay × social_bonus × (1 + ai_semantic_bonus)
```

- `source_weight`：来源可信度权重（Bloomberg 1.5、Reuters 1.4、HN 1.2 等）
- `time_decay`：时效衰减（24h 内 1.0、24-48h 0.7、48-72h 0.4、>72h 0.1）
- `social_bonus`：HN upvotes ≥100 +0.5、≥50 +0.3
- `ai_semantic_bonus`：LLM 判断重大事件，硬上限 0.5

---

## 要求

- OpenClaw (支持 Skill 系统和 Cron)
- Node.js ≥ 18（仅使用内置 `https` / `http` / `fs` 模块，零外部依赖）

---

## 文件结构

```
hot-topics/
├── SKILL.md              # Agent 指令（核心）
├── README.md             # 本文档
├── scripts/
│   ├── fetch.js          # 预抓取脚本
│   └── cache.js          # 缓存读写工具
├── docs/
│   └── superpowers/
│       ├── specs/        # 设计文档
│       └── plans/        # 实现计划
└── ARCHITECTURE.md       # 深度调研报告
```

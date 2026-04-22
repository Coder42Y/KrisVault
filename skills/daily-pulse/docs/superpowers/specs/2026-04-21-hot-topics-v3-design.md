# Hot-Topics Skill v3 设计方案

> 日期：2026-04-21
> 状态：已确认，待实现

---

## 1. 设计目标

将 hot-topics 从"纯 LLM 驱动的信息聚合器"升级为**结构化、低成本、高质量、可扩展**的热点推送系统。

### 核心指标

| 指标 | 当前 (v2) | 目标 (v3) |
|------|----------|----------|
| 单次推送耗时 | 183s | ≤ 60s |
| 输入 tokens | 44K | ≤ 12K |
| 板块数量 | 4（固定） | 7+（可扩展） |
| 内容质量 | LLM 全判断 | 结构化评分 + AI 辅助 |
| 用户自定义 | 不支持 | 声明式配置 |
| 按需查询 | 不支持 | 支持 |

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│  配置层: hot-topics-prefs.json (v3)                          │
│  ├─ preset_topics: 7 个预设板块（结构化配置）                 │
│  │   ├─ hot-news: 宁缺毋滥, min_score=2.5                   │
│  │   ├─ ai, finance, esports, football, github              │
│  │   └─ 每个板块: sources + weights + target_count          │
│  ├─ custom_topics: 声明式自定义板块                           │
│  └─ global: 并行数、超时、缓存策略                            │
├─────────────────────────────────────────────────────────────┤
│  预抓取层: scripts/fetch.js                                  │
│  ├─ 零依赖 Node.js 脚本                                      │
│  ├─ 并行抓取所有板块                                         │
│  └─ 输出结构化 JSON → /tmp/hot-topics-raw.json               │
├─────────────────────────────────────────────────────────────┤
│  Agent 层: 热度评分 + 摘要 + 排版                            │
│  ├─ 热度 = 来源权重 × 时效衰减 × 社交信号 × AI语义(上限0.5)  │
│  ├─ 按热度排序，取 top N                                     │
│  ├─ LLM 生成一句话摘要                                       │
│  └─ 按模板输出 Markdown                                      │
├─────────────────────────────────────────────────────────────┤
│  触发层                                                      │
│  ├─ 定时: Cron → isolated session → 推送微信/QQ             │
│  └─ 按需: 用户消息 → current session → 直接回复             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 配置格式 (v3)

### 3.1 预设板块

| 板块 key | 说明 | 特殊规则 |
|----------|------|---------|
| `hot-news` | 跨领域爆点 | 宁缺毋滥，min_score=2.5，不足显示"今日无重大热点" |
| `ai` | AI/ML 新闻 | Wired, TechCrunch, ArXiv（每周限2条） |
| `finance` | 财经 | Bloomberg, Reuters, WSJ |
| `esports` | 电竞 | LoL + CS2 子板块，按赛事日历动态调整 |
| `football` | 足球 | 按 focus_clubs 优先展示 |
| `github` | 开源热门 | GitHub Trending + HN Show HN，按日增速排序 |
| `tech` | 科技数码 | 手机、硬件、互联网 |

### 3.2 热度评分公式

```
score = source_weight × time_decay × social_bonus × (1 + ai_semantic_bonus)

source_weight: Bloomberg 1.5, Reuters 1.4, Wired 1.2, 通用 1.0
time_decay:    48h 内 = 1.0, 48-72h = 0.5, >72h = 过滤
social_bonus:  HN 前10页 +1.0, Reddit r/tech 热门 +0.8, 无数据 +0
ai_semantic:   LLM 判断重大事件 +0.5（硬上限，不能更高）
```

### 3.3 配置示例

```json
{
  "version": 3,
  "updated_at": "2026-04-21T12:00:00+08:00",
  "push_time": "9:30",
  "freshness": "48h",
  
  "preset_topics": {
    "hot-news": {
      "enabled": true,
      "target_count": 3,
      "min_score": 2.5,
      "sources": [
        {"name": "HN front page", "weight": 1.5, "url": "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=10"},
        {"name": "Reddit r/all", "weight": 1.2, "url": "..."},
        {"name": "Google News trending", "weight": 1.0, "url": "..."}
      ]
    },
    "ai": {
      "enabled": true,
      "target_count": 8,
      "sources": [
        {"name": "Wired AI", "weight": 1.3, "rss": "https://www.wired.com/feed/tag/ai/latest/rss"},
        {"name": "TechCrunch AI", "weight": 1.2, "rss": "https://techcrunch.com/category/artificial-intelligence/feed/"},
        {"name": "ArXiv AI", "weight": 0.8, "rss": "...", "weekly_limit": 2}
      ]
    },
    "finance": {
      "enabled": true,
      "target_count": 6,
      "sources": [
        {"name": "Bloomberg", "weight": 1.5, "rss": "https://feeds.bloomberg.com/markets/news.rss"},
        {"name": "Reuters", "weight": 1.4, "rss": "..."}
      ]
    },
    "esports": {
      "enabled": true,
      "target_count": 5,
      "sub_sections": {
        "lol": {"sources": [...], "keywords": ["MSI", "Worlds"]},
        "cs2": {"sources": [...], "focus_teams": ["Falcons", "Vitality"]}
      }
    },
    "football": {
      "enabled": true,
      "target_count": 5,
      "focus_clubs": ["巴萨", "迈阿密国际"],
      "leagues": ["欧冠", "五大联赛"]
    },
    "github": {
      "enabled": true,
      "target_count": 4,
      "sources": [
        {"name": "GitHub Trending API", "weight": 1.0, "api": "github_search", "exclude_orgs": ["microsoft", "google", "facebook"]},
        {"name": "HN Show HN", "weight": 1.2, "api": "hn_algolia", "tag": "show_hn"}
      ],
      "sort_by": "stars_daily_growth"
    }
  },
  
  "custom_topics": [
    {
      "name": "SpaceX",
      "keywords": ["SpaceX", "Starship", "Falcon", "Elon Musk 航天"],
      "target_count": 3,
      "sources": ["google_news", "reddit"]
    }
  ],
  
  "global": {
    "max_parallel_requests": 8,
    "request_timeout_ms": 15000,
    "cache_ttl_hours": 24,
    "ai_semantic_bonus_max": 0.5
  }
}
```

---

## 4. 预抓取脚本 (scripts/fetch.js)

### 4.1 设计原则

- **零依赖**：只用 Node.js 内置 `https`/`http` 模块
- **并行抓取**：`Promise.all` 同时请求所有数据源
- **内容清洗**：正则提取 RSS 字段，去掉 HTML 噪音
- **容错**：单个源失败不影响整体，记录到 `errors`

### 4.2 输入输出

**输入**：读取 `~/.openclaw/cron/hot-topics-prefs.json`

**输出**：`/tmp/hot-topics-raw.json`

```json
{
  "fetchedAt": "2026-04-21T09:30:05+08:00",
  "results": {
    "ai": [
      {"title": "...", "url": "...", "source": "Wired", "date": "2026-04-20", "raw_text": "..."}
    ],
    "github": [
      {"full_name": "tw93/Kami", "stars": 355, "language": "HTML", "description": "..."}
    ]
  },
  "errors": {
    "ai": ["Wired RSS timeout after 10s"]
  }
}
```

### 4.3 性能预期

- 并行 8 个请求 → 总等待时间 ≈ 最慢请求的耗时（~5-10s）
- 清洗 + 结构化 → ~1-2s
- **总计：~5-10s**

---

## 5. Agent 执行流程

### 5.1 定时推送（Cron）

```
1. Cron 触发 → 创建 isolated session
2. Agent 执行: exec "node ~/.openclaw/workspace/skills/hot-topics/scripts/fetch.js"
3. Agent 读取: read /tmp/hot-topics-raw.json
4. Agent 计算热度分 → 排序 → 取 top N
5. LLM 生成一句话摘要（每板块）
6. 按模板输出 Markdown
7. 自动推送到微信/QQ（delivery: announce）
```

### 5.2 按需查询（用户实时请求）

```
1. 用户发送: "今晚CS2赛程" / "给我看看GitHub热门" / "AI和财经简讯"
2. Agent 在当前 session 执行
3. 匹配板块 → 执行 fetch.js（指定板块）
4. 读取结果 → 热度排序 → 摘要 → 直接回复
```

**触发词规则**：
- `板块名 + 最新/动态/赛程/赛果/简讯` → 匹配对应板块
- `给我/查/看看 + 板块名` → 匹配对应板块
- 多板块组合 → 一次返回多个板块

---

## 6. 修改文件清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `SKILL.md` | 重写 | 并行抓取指令、热度评分规则、按需查询触发词、输出模板 |
| `scripts/fetch.js` | 新增 | 预抓取脚本（零依赖 Node.js） |
| `hot-topics-prefs.json` | 升级 v3 | 预设板块结构化 + 自定义板块 + 全局配置 |
| `README.md` | 新增 | 对外发布的 skill 说明文档 |

---

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| fetch.js 运行环境不确定 | 只用 node 内置模块，零依赖 |
| RSS 格式不规则 | 正则失败时 fallback 到 raw text 提取 |
| Agent 不按指令并行 | SKILL.md 明确标注"必须一次性并行调用" |
| GitHub API 限流 | 未认证 10 req/min，每天只查一次足够 |
| LLM 幻觉（热度判断虚高） | AI 语义加成硬上限 0.5，来源权重才是主力 |

---

*设计确认后进入 implementation 阶段*

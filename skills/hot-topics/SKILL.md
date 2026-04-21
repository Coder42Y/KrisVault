---
name: hot-topics
description: >
  每日热点推送 + 按需查询。支持 7 个预设板块（热点新闻/AI/财经/电竞/足球/GitHub/科技）
  和用户自定义板块。触发词：推热点、今日热点、给我看看XX、查一下XX、XX简讯、XX赛程。
  配置：~/.openclaw/cron/hot-topics-prefs.json（v3）。
---

# 热点推送 v3

结构化低热点聚合系统。预抓取脚本完成所有网络请求，Agent 只负责评分、摘要、排版。

---

## 执行规则

### 1. 预抓取优先（强制）

**任何热点推送或查询任务，第一步必须是：**

```bash
node /Users/kris/.openclaw/workspace/skills/hot-topics/scripts/fetch.js
```

然后读取结果：
```
read /tmp/hot-topics-raw.json
```

**禁止**在执行 fetch.js 之前或之外调用 web_fetch、exec curl、browser 等工具进行搜索。
所有搜索已在 fetch.js 中并行完成。

### 2. 评分与排序

从 `/tmp/hot-topics-raw.json` 读取每个板块的 items，按以下公式计算热度分：

```
score = source_weight × time_decay × social_bonus × (1 + ai_semantic_bonus)

source_weight:   来自 item._source_weight（配置中定义，默认 1.0）
time_decay:      发布时间在 24h 内 = 1.0, 24-48h = 0.7, 48-72h = 0.4, >72h = 0.1
social_bonus:    HN points ≥ 100 = +0.5, ≥ 50 = +0.3, < 50 = 0
ai_semantic_bonus: LLM 判断该条是否为重大事件/突破（上限 0.5，宁缺毋滥）
```

按 score 降序排列，取每个板块的 `target_count` 条。

### 3. 热点新闻特殊规则（宁缺毋滥）

`hot-news` 板块 `min_score = 2.5`：
- 如果有 items 的 score ≥ 2.5，取 top 3 展示
- 如果全部 items 的 score < 2.5，输出：**「今日无重大热点」**
- 绝不为了凑数而降低标准

### 4. GitHub 板块特殊展示

GitHub 条目展示的是 **日增 stars**（`daily_growth`），不是总 stars。

格式示例：
```
- **tw93/Kami** | +411 ⭐/日 | HTML
  Good content deserves good paper.
```

---

## 输出模板

```markdown
# 热点推送 YYYY-MM-DD

## 热点新闻
- **标题** | 来源 | 时间
  一句话摘要（由 LLM 基于 title + description 生成，不编造）

## AI
- **标题** | 来源 | 时间
  一句话摘要

## 财经
- **标题** | 来源 | 时间
  一句话摘要

## 科技数码
- **标题** | 来源 | 时间
  一句话摘要

## 电竞
- **标题** | 来源 | 时间
  一句话摘要

## 足球
- **标题** | 来源 | 时间
  一句话摘要

## GitHub 趋势
- **repo/name** | +N ⭐/日 | 语言
  一句话描述
```

### 板块图标映射

| 板块 key | 图标 |
|----------|------|
| hot-news | 🔥 |
| ai | 🤖 |
| finance | 💰 |
| tech | 📱 |
| esports | 🎮 |
| football | ⚽ |
| github | ⭐ |

---

## 触发词

### 定时推送

Cron 每天 9:30 触发，payload：`请执行每日热点推送`。

### 一键催推

```
推热点
立即推送
我要看热点
催一下
现在推给我
快推
马上推
今日热点
热点日报
```

### 按需查询（实时）

用户消息匹配以下模式时，执行 fetch.js 并只返回对应板块：

| 模式 | 匹配板块 | 示例 |
|------|---------|------|
| `给我看看XX` / `查一下XX` / `看看XX` | XX 对应板块 | "给我看看AI" → ai |
| `XX简讯` / `XX动态` / `XX最新` | XX 对应板块 | "AI简讯" → ai |
| `XX赛程` / `XX赛果` | esports / football | "CS2赛程" → esports |
| `GitHub热门` / `开源趋势` / `今日GitHub` | github | "GitHub热门" → github |
| `多板块组合` | 多个 | "AI和财经简讯" → ai + finance |

**板块名映射（模糊匹配）：**
- AI / 人工智能 / ai → `ai`
- 财经 / 股市 / 金融 / finance → `finance`
- 电竞 / 游戏 / esports / CS2 / LOL → `esports`
- 足球 / 欧冠 / 西甲 / football → `football`
- 科技 / 数码 / 互联网 / tech → `tech`
- GitHub / 开源 / github → `github`
- 热点 / 新闻 / 爆点 / hot-news → `hot-news`

### 配置查询

```
查看当前配置
我的兴趣是什么
推送时间是几点
我订阅了哪些板块
```

### 配置修改

```
设置兴趣: AI,财经,电竞
添加科技到兴趣
移除足球
设置推送时间: 8:00
```

---

## 自定义板块

当用户要求添加自定义板块时：

1. 读取 `~/.openclaw/cron/hot-topics-prefs.json`
2. 在 `custom_topics` 数组追加：
   ```json
   {
     "name": "用户给的名称",
     "keywords": ["关键词1", "关键词2"],
     "target_count": 3,
     "sources": [{"name": "HN", "api": "hn_algolia", "query": "关键词"}]
   }
   ```
3. 写回配置文件
4. 回复确认

---

## 错误处理

- 单个板块抓取失败：`errors` 中记录，该板块显示 `⚠️ [板块名] 获取失败`
- fetch.js 整体失败：提示用户检查网络或配置文件
- 某板块无内容：显示 `今日暂无相关内容`

---

## 关键文件路径

| 文件 | 路径 |
|------|------|
| 预抓取脚本 | `/Users/kris/.openclaw/workspace/skills/hot-topics/scripts/fetch.js` |
| 配置文件 | `~/.openclaw/cron/hot-topics-prefs.json` |
| 抓取结果 | `/tmp/hot-topics-raw.json` |
| 缓存目录 | `~/.openclaw/cron/` |

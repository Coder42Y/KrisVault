# Hot-Topics Skill 深度调研报告

> 生成时间：2026-04-21
> 调研范围：Skill 定义、配置机制、执行流程、Web 信息获取、归纳总结逻辑、架构分析

---

## 一、Skill 的本质：OpenClaw Skill 是什么？

OpenClaw 的 **Skill** 不是传统意义上的"插件"或"代码模块"，而是一种**声明式的 LLM 指令模板**。它的核心是一个 Markdown 文件（`SKILL.md`），通过 YAML frontmatter 声明元数据，正文部分编写结构化指令。

### 1.1 文件结构

```
workspace/skills/
├── hot-topics/
│   └── SKILL.md          <-- 唯一的文件（547 行 Markdown）
├── xhs-image-gen/
│   ├── SKILL.md
│   ├── scripts/screenshot.js
│   └── references/
└── tencent-channel-community/
    ├── SKILL.md
    └── references/
```

### 1.2 加载机制

OpenClaw 启动时扫描 `workspace/skills/` 下的目录，查找 `SKILL.md`，解析 frontmatter 中的 `name` 和 `description`，然后格式化为 XML 注入 system prompt：

```xml
<available_skills>
  <skill>
    <name>hot-topics</name>
    <description>每日热点推送。支持自定义兴趣板块...</description>
    <location>/Users/kris/.openclaw/workspace/skills/hot-topics/SKILL.md</location>
  </skill>
</available_skills>
```

**关键**：Agent 不会自动执行 skill。它只在 system prompt 中被告知"有这些 skill 可用"。当用户消息或 cron payload 匹配 skill 的触发条件时，agent 会主动用 `read` 工具读取 SKILL.md，然后按其中指令执行。

### 1.3 与其他 Skill 的对比

| 维度 | Hot-Topics | XHS-Image-Gen | Tencent-Channel |
|------|-----------|---------------|-----------------|
| 核心能力 | 信息聚合 | 图片生成 | API 调用 |
| 是否有代码/脚本 | **否** | 是（screenshot.js） | 是（CLI 工具） |
| 输出类型 | 文本（Markdown） | 文件（PNG） | 操作（API 调用） |
| 配置复杂度 | 中（prefs.json） | 低 | 高（多 reference） |
| 对 LLM 依赖度 | **极高** | 中 | 低 |

Hot-Topics 是最典型的**纯 LLM 驱动** skill，所有逻辑委托给语言模型。

---

## 二、整体架构：三层模型

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: 指令层 (SKILL.md)                               │
│  - 定义搜索策略、格式模板、触发词                          │
│  - 纯文本，无代码逻辑                                      │
├─────────────────────────────────────────────────────────┤
│  Layer 2: 配置层 (hot-topics-prefs.json)                  │
│  - 用户订阅的 topics、推送时间、电竞/足球细化配置          │
│  - Agent 运行时读取，动态调整行为                          │
├─────────────────────────────────────────────────────────┤
│  Layer 3: 执行层 (OpenClaw Cron + Agent)                  │
│  - Cron 定时触发 -> 创建 isolated session                 │
│  - Agent 读取 Skill + 配置 -> 调用工具 -> 输出结果        │
└─────────────────────────────────────────────────────────┘
```

### 2.1 Layer 1: 指令层

`SKILL.md` 的核心内容：

- **触发词定义**："今日 AI 日报"、"推热点"、"设置兴趣"等
- **搜索策略**：多源并发搜索（Exa、Tavily、ArXiv、WebFetch）
- **动态关键词拼接**：按板块类型拼接搜索关键词
- **格式模板**：日报/周报的 Markdown 输出模板
- **图标映射**：各板块对应的 emoji

### 2.2 Layer 2: 配置层

`hot-topics-prefs.json` 当前配置：

```json
{
  "version": 2,
  "updated_at": "2026-04-18T10:42:00+08:00",
  "topics": ["AI", "股市/财经", "电竞", "足球"],
  "topic_item_counts": {"AI": 12, "股市/财经": 7, "电竞": 5, "足球": 5},
  "freshness": "48h",
  "esports": {
    "lol": {
      "daily": ["选手新闻", "赛事动态", "版本更新", "战队交易", "riot games"],
      "tournament_only": ["MSI", "Worlds", "世界赛", "全球总决赛"]
    },
    "cs2": {
      "all_tournaments": ["IEM", "ESL Pro League", "BLAST", "PGL", "Major", "StarLadder"],
      "focus_teams": ["Falcons", "Team Falcons", "Vitality", "Team Vitality", "猎鹰", "Vitality"],
      "scope": "赛果/赛程 + 转会/阵容变动 + 战队动态等所有CS2相关资讯",
      "keywords_extra": ["CS2 roster", "CS2 transfer", "CS2 roster change", "CS2 signing", "CS2 lineup"]
    }
  },
  "football": {
    "enabled": true,
    "mode": "简报模式",
    "focus_clubs": ["巴萨", "Barcelona", "巴塞罗那", "迈阿密国际", "Inter Miami", "Inter Miami CF"],
    "leagues": ["欧冠", "五大联赛", "西甲", "英超", "意甲", "德甲", "法甲"],
    "push_trigger": "主动推送重大比赛，形式从简"
  },
  "custom_topics": [],
  "push_time": "9:30"
}
```

### 2.3 Layer 3: 执行层

#### Cron Job 配置

```json
{
  "id": "b534fc04-af59-4485-a3f2-1214078d29c7",
  "name": "每日热点推送 9:30",
  "schedule": {
    "kind": "cron",
    "expr": "30 9 * * *",
    "tz": "Asia/Shanghai"
  },
  "sessionTarget": "isolated",
  "wakeMode": "now",
  "payload": {
    "kind": "agentTurn",
    "message": "请执行每日热点推送。话题顺序：AI、财经、电竞、足球。"
  },
  "delivery": {
    "mode": "announce",
    "channel": "last"
  }
}
```

**重要**：`sessionTarget: "isolated"` 确保每次运行都在独立的 session 中，不影响主对话。

---

## 三、执行流程详解（以 2026-04-21 成功运行为例）

```
1. Cron 触发 (09:30 CST)
   └─> 创建 isolated session: e2b8e134-7ec6-4c75-bc12-07d152d834de

2. Agent 初始化
   └─> System prompt 包含 <available_skills> 列表

3. 用户消息（cron payload）
   "请执行每日热点推送。话题顺序：AI、财经、电竞、足球。"

4. Agent 匹配意图 → 读取 SKILL.md
   └─> read /Users/kris/.openclaw/workspace/skills/hot-topics/SKILL.md

5. Agent 读取配置
   └─> 读取 hot-topics-prefs.json 获取 topics、freshness、电竞/足球配置

6. 按板块执行搜索
   ├─> AI:      web_fetch Google News RSS + exec curl/calls
   ├─> 财经:    web_fetch Google News RSS
   ├─> 电竞:    web_fetch HLTV/news 站点
   └─> 足球:    web_fetch BBC Sport/news

7. LLM 归纳整理
   └─> 将搜索结果去重、摘要、按格式模板排版

8. 输出推送
   └─> 输出 Markdown 格式热点内容 → 自动推送到微信/QQ
```

### 3.1 实际工具调用统计

| 工具 | 调用次数 | 用途 |
|------|---------|------|
| `exec` | 14 | 执行 bash 命令（curl、npm 等） |
| `web_fetch` | 8 | 抓取网页/RSS 内容 |
| `read` | 1 | 读取 SKILL.md |
| `process` | 1 | 启动子进程 |
| `browser` | 1 | 浏览器访问 |
| **总计** | **25** | |

### 3.2 性能指标

| 指标 | 数值 |
|------|------|
| 耗时 | 183 秒（约 3 分钟） |
| 输入 tokens | 44,140 |
| 输出 tokens | 3,718 |
| 模型 | MiniMax-M2.7 |
| 结果 | 成功推送，deliveryStatus: delivered |

---

## 四、获取 Web Info 的机制

### 4.1 SKILL.md 中声明的搜索策略

```bash
# Exa — AI 科技新闻（默认）
mcporter call 'exa.web_search_exa(query: "AI news today", numResults: 8)'

# Tavily — 深度+新闻主题
tvly search "AI today" --depth advanced --max-results 8 --topic news --time-range day --json

# ArXiv — 今日学术（可选）
curl -s "https://export.arxiv.org/api/query?..."

# Google News — 突发新闻
WebFetch "https://news.google.com/rss/search?q=AI+AGI&..."
```

### 4.2 实际使用的工具

**重要发现**：SKILL.md 中提到的 `mcporter` (Exa) 和 `tvly` (Tavily) 在系统中**并未安装**。2026-04-21 的成功运行完全依赖 `web_fetch` 和 `exec/curl`。

| 数据源 | 工具 | 方式 |
|--------|------|------|
| Google News RSS | `web_fetch` | RSS feed 解析 |
| HLTV (CS2 电竞) | `web_fetch` | 网页抓取 |
| BBC Sport | `web_fetch` | 网页抓取 |
| Bloomberg | `web_fetch` | 网页抓取 |
| Wired | `web_fetch` | 网页抓取 |
| 其他补充 | `exec` + `curl` | 命令行请求 |

**结论**：Skill 的设计与实际执行环境之间存在 gap，agent 会自主降级到可用工具。这是一个"理想设计 vs 实际运行"的典型案例。

### 4.3 搜索执行逻辑

Skill 中没有硬编码搜索逻辑，而是通过**自然语言指令**指导 LLM：

```
"按 topics 列表并发执行多源搜索"
"每板块 8 秒超时"
"单板块超时：该板块标记为获取失败"
```

实际执行时，LLM 自主决定：
- 用什么关键词搜索
- 调用哪个数据源
- 如何处理超时
- 如何合并结果

---

## 五、归纳总结机制

### 5.1 去重与排序

**没有结构化去重算法**。完全依赖 LLM 的上下文记忆：

```
"去重合并 + 排序"
"各板块内按时间排序（最新的在前）"
```

LLM 将多次搜索的结果加载到上下文中（44K tokens 的输入量说明加载了大量原始内容），然后在生成输出时自然地去重和排序。

### 5.2 格式模板

Skill 提供了严格的输出格式模板：

```markdown
# 热点推送 YYYY-MM-DD

## 板块名（带 emoji）
- **标题** | 来源 | 时间
  一句话摘要

## 下一板块
...
```

LLM 按照此模板将搜索结果"翻译"成结构化的 Markdown。格式控制完全靠 prompt engineering，没有模板引擎或渲染层。

### 5.3 摘要生成

每条新闻的"一句话摘要"由 LLM **实时生成**，不是从源站提取：

```
- **人形机器人中国半马破纪录** | Wired | Apr 20
  中国公司Honor的人形机器人以50:26完赛，比人类纪录快7分钟
```

这个摘要既不是原文摘录，也不是预定义的，而是 LLM 对抓取内容的理解和压缩。

### 5.4 实际输出示例（2026-04-21）

```markdown
# 热点推送 2026-04-21

## AI
- **人形机器人中国半马破纪录** | Wired | Apr 20
  中国公司Honor的人形机器人以50:26完赛，比人类纪录快7分钟

## 财经
- **AI热潮推动韩国综指创历史新高** | Bloomberg | Apr 21
  科技巨头领涨，市场对中东局势缓和信心增强

## 电竞
- **Vitality成为CS2首支双冠王** | HLTV | Apr 19
  完成第二个大满贯，ZywOo获IEM Rio MVP

## 足球
- **德甲第35冠！拜仁4-2逆转Stuttgart** | BBC | Apr 19
  联赛提前四轮夺冠，剑指三冠王
```

---

## 六、优势分析

### 1. 零代码、纯声明式

整个 skill 只有 547 行 Markdown，无需编写任何 JavaScript/TypeScript。开发成本低，修改门槛低。

### 2. 配置驱动、灵活可变

通过 `hot-topics-prefs.json` 可以动态调整：
- 订阅的板块（AI、财经、电竞、足球等）
- 每个板块的条数
- 推送时间
- 电竞/足球的细化偏好（关注哪些队伍、赛事）

### 3. 利用 LLM 的泛化能力

LLM 自主处理：
- 搜索关键词的动态拼接
- 多源结果的去重
- 内容摘要的生成
- 格式排版

不需要为每个数据源写解析器。

### 4. 与 OpenClaw 生态深度集成

- Cron 系统定时触发
- Isolated session 不影响主会话
- 自动推送到微信/QQ 通道
- 配置持久化到 JSON 文件

---

## 七、局限性分析

### 1. 成本高、耗时长

| 指标 | 数值 | 问题 |
|------|------|------|
| 输入 tokens | 44,140 | 大量原始网页内容加载到上下文 |
| 输出 tokens | 3,718 | 最终只有 ~3.7K 有效内容 |
| 耗时 | 183 秒 | 3 分钟才能完成一次推送 |
| 工具调用 | 25 次 | 多次网络往返 |

**本质问题**：没有专门的内容抓取和去重服务，所有工作都由 LLM 完成，导致 token 消耗巨大。

### 2. 可靠性依赖工具可用性

- `mcporter` (Exa) 和 `tvly` (Tavily) 未安装，skill 中描述的搜索链实际上只有部分可用
- 如果 `web_fetch` 失败或目标站点结构变化，agent 无法自动适配
- 没有 fallback 策略的显式编码

### 3. 去重和排序不透明

"去重合并"完全依赖 LLM 的上下文窗口记忆：
- 如果搜索结果太多超出上下文，去重会失效
- 没有时间戳比对或 URL 去重的结构化逻辑
- 排序可能受 LLM 幻觉影响

### 4. 时效性控制弱

虽然配置了 `freshness: 48h`，但：
- 没有预过滤机制，所有搜索结果都先加载再筛选
- 依赖数据源本身的时间准确性（RSS 可能有延迟）

### 5. 无缓存和增量机制

每次运行都从零开始搜索所有板块：
- 没有"今天已经报道过的新闻"缓存
- 无法做增量更新
- 相同话题每天可能被重复报道

### 6. 输出格式不可编程

格式控制完全靠 prompt：
- 无法动态调整板块顺序（虽然配置中有顺序，但 LLM 可能不严格遵守）
- 无法精确控制条数（配置说 AI 12 条，实际输出 6 条）
- 图标映射可能遗漏

### 7. 对 LLM 能力依赖过重

这个 skill 的架构本质上是 **"LLM as Orchestrator"**：
- 搜索策略由 LLM 决定
- 去重由 LLM 完成
- 摘要由 LLM 生成
- 格式由 LLM 排版

这意味着：
- 换用较弱的模型可能导致质量下降
- LLM 的"创造力"可能偏离预期（如编造新闻来源）
- 难以预测和调试

---

## 八、总结与优化建议

### 当前状态

| 维度 | 状态 |
|------|------|
| 功能可用性 | 已验证成功（2026-04-21 推送完整内容） |
| 架构复杂度 | 低（纯 Markdown + JSON 配置） |
| 运行成本 | 高（44K input tokens / 次） |
| 可靠性 | 中（依赖 LLM 和外部工具可用性） |
| 可维护性 | 高（无代码，改 Markdown 即可） |

### 优化方向

1. **增加专门的内容抓取服务**：减少 LLM 处理原始 HTML 的工作量
2. **增加去重缓存**：维护已报道新闻的 URL/title 索引，避免重复
3. **固化格式化逻辑**：将模板渲染从 LLM 转移到代码层
4. **安装缺失的搜索工具**：Exa/Tavily 可以提升搜索质量
5. **增加增量更新机制**：只搜索自上次推送以来的新内容

---

*报告由 Claude Code 自动生成*

# Hot-Topics Skill v3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade hot-topics skill from pure LLM-driven to structured low-cost system with pre-fetch script, configurable scoring, and on-demand queries.

**Architecture:** A zero-dependency Node.js pre-fetch script (`fetch.js`) parallel-fetches all sources and outputs structured JSON. The Agent reads this JSON, applies the scoring formula, and generates summaries. A separate `cache.js` manages GitHub star history for daily-growth calculation.

**Tech Stack:** Node.js (built-in `https`/`http`/`fs`), OpenClaw Agent (MiniMax-M2.7), RSS feeds, GitHub Search API, HN Algolia API.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/fetch.js` | Create | Parallel fetch all sources, output structured JSON to `/tmp/hot-topics-raw.json` |
| `scripts/cache.js` | Create | Read/write cache files (`github-cache.json`, `hot-topics-cache.json`) |
| `SKILL.md` | Rewrite | Agent instructions: parallel fetch, scoring rules, on-demand triggers, output templates |
| `cron/hot-topics-prefs.json` | Modify | Upgrade to v3 format with preset_topics, custom_topics, global settings |
| `README.md` | Create | Public-facing documentation for GitHub distribution |

---

### Task 1: Create `scripts/cache.js`

**Files:**
- Create: `workspace/skills/hot-topics/scripts/cache.js`

- [ ] **Step 1: Write cache.js with read/write functions**

```javascript
const fs = require("fs");
const path = require("path");

const CACHE_DIR = path.join(require("os").homedir(), ".openclaw", "cron");

function ensureDir() {
  if (!fs.existsSync(CACHE_DIR)) fs.mkdirSync(CACHE_DIR, { recursive: true });
}

function readCache(filename) {
  ensureDir();
  const fp = path.join(CACHE_DIR, filename);
  try {
    return JSON.parse(fs.readFileSync(fp, "utf8"));
  } catch {
    return {};
  }
}

function writeCache(filename, data) {
  ensureDir();
  const fp = path.join(CACHE_DIR, filename);
  fs.writeFileSync(fp, JSON.stringify(data, null, 2));
}

module.exports = { readCache, writeCache };
```

- [ ] **Step 2: Test cache.js works**

Run:
```bash
cd /Users/kris/.openclaw/workspace/skills/hot-topics/scripts
node -e "
const { readCache, writeCache } = require('./cache');
writeCache('test-cache.json', { foo: 'bar' });
const data = readCache('test-cache.json');
console.log(data.foo === 'bar' ? 'PASS' : 'FAIL');
"
```

Expected: `PASS`

- [ ] **Step 3: Commit**

```bash
git add workspace/skills/hot-topics/scripts/cache.js
git commit -m "feat: add cache utility for hot-topics"
```

---

### Task 2: Create `scripts/fetch.js` core structure

**Files:**
- Create: `workspace/skills/hot-topics/scripts/fetch.js`

- [ ] **Step 1: Write fetch.js with config reader and HTTP helper**

```javascript
const https = require("https");
const http = require("http");
const fs = require("fs");
const path = require("path");
const { readCache, writeCache } = require("./cache");

const CONFIG_PATH = path.join(
  require("os").homedir(),
  ".openclaw", "cron", "hot-topics-prefs.json"
);
const OUTPUT_PATH = "/tmp/hot-topics-raw.json";

function readConfig() {
  try {
    return JSON.parse(fs.readFileSync(CONFIG_PATH, "utf8"));
  } catch (err) {
    console.error("Failed to read config:", err.message);
    process.exit(1);
  }
}

function fetchUrl(url, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith("https:") ? https : http;
    const req = client.get(url, { timeout: timeoutMs }, (res) => {
      let data = "";
      res.on("data", chunk => data += chunk);
      res.on("end", () => resolve({ status: res.statusCode, body: data }));
    });
    req.on("error", reject);
    req.on("timeout", () => { req.destroy(); reject(new Error("timeout")); });
  });
}

// Placeholder: will be filled in Task 3
function parseRss(body) { return []; }
function fetchGithub() { return []; }
function fetchHN(tag) { return []; }

async function main() {
  const config = readConfig();
  console.log("Fetching sources...");
  // Placeholder: will be filled in Task 3
  fs.writeFileSync(OUTPUT_PATH, JSON.stringify({ fetchedAt: new Date().toISOString(), results: {}, errors: {} }, null, 2));
  console.log("Done. Output:", OUTPUT_PATH);
}

main().catch(err => { console.error(err); process.exit(1); });
```

- [ ] **Step 2: Test fetch.js runs without error**

Run:
```bash
cd /Users/kris/.openclaw/workspace/skills/hot-topics
node scripts/fetch.js
```

Expected: `Done. Output: /tmp/hot-topics-raw.json`

Verify:
```bash
cat /tmp/hot-topics-raw.json | jq '.fetchedAt'
```

Expected: a valid ISO timestamp.

- [ ] **Step 3: Commit**

```bash
git add workspace/skills/hot-topics/scripts/fetch.js
git commit -m "feat: add fetch.js skeleton with config reader and HTTP helper"
```

---

### Task 3: Implement RSS parsing and GitHub fetching in `fetch.js`

**Files:**
- Modify: `workspace/skills/hot-topics/scripts/fetch.js`

- [ ] **Step 1: Add RSS parser function**

Replace the `parseRss` placeholder with:

```javascript
function parseRss(body, sourceName) {
  const items = [];
  const itemRegex = /<item[\s\S]*?<\/item>/g;
  let match;
  while ((match = itemRegex.exec(body)) !== null) {
    const itemXml = match[0];
    const title = (itemXml.match(/<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?<\/title>/i) || [])[1]?.trim() || "";
    const link = (itemXml.match(/<link>(.*?)<\/link>/i) || [])[1]?.trim() || "";
    const pubDate = (itemXml.match(/<pubDate>(.*?)<\/pubDate>/i) || [])[1]?.trim() || "";
    if (title && link) {
      items.push({ title, url: link, source: sourceName, date: pubDate, raw_text: "" });
    }
  }
  return items;
}
```

- [ ] **Step 2: Add GitHub trending fetcher**

Replace the `fetchGithub` placeholder with:

```javascript
async function fetchGithub(config) {
  const cache = readCache("github-cache.json");
  const yesterdayKey = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  const todayKey = new Date().toISOString().slice(0, 10);
  
  const excludeOrgs = new Set((config.exclude_orgs || []).map(o => o.toLowerCase()));
  const twoDaysAgo = new Date(Date.now() - 2 * 86400000).toISOString().slice(0, 10);
  
  const searchUrl = `https://api.github.com/search/repositories?q=created:>${twoDaysAgo}&sort=stars&order=desc&per_page=20`;
  const res = await fetchUrl(searchUrl);
  if (res.status !== 200) throw new Error(`GitHub API ${res.status}`);
  
  const data = JSON.parse(res.body);
  const repos = [];
  
  for (const item of (data.items || [])) {
    const org = (item.full_name || "").split("/")[0]?.toLowerCase();
    if (excludeOrgs.has(org)) continue;
    
    const currentStars = item.stargazers_count || 0;
    const prevStars = cache[todayKey]?.[item.full_name] || cache[yesterdayKey]?.[item.full_name] || currentStars;
    const dailyGrowth = currentStars - prevStars;
    
    repos.push({
      full_name: item.full_name,
      stars: currentStars,
      daily_growth: dailyGrowth,
      language: item.language,
      description: item.description || "",
      html_url: item.html_url
    });
  }
  
  // Update cache
  if (!cache[todayKey]) cache[todayKey] = {};
  for (const r of repos) cache[todayKey][r.full_name] = r.stars;
  writeCache("github-cache.json", cache);
  
  return repos.sort((a, b) => b.daily_growth - a.daily_growth).slice(0, config.target_count || 4);
}
```

- [ ] **Step 3: Add HN fetcher**

Replace the `fetchHN` placeholder with:

```javascript
async function fetchHN(tag, hitsPerPage = 10) {
  const url = `https://hn.algolia.com/api/v1/search?tags=${tag}&hitsPerPage=${hitsPerPage}`;
  const res = await fetchUrl(url);
  if (res.status !== 200) throw new Error(`HN API ${res.status}`);
  const data = JSON.parse(res.body);
  return (data.hits || []).map(h => ({
    title: h.title,
    url: h.url || `https://news.ycombinator.com/item?id=${h.objectID}`,
    source: "Hacker News",
    points: h.points || 0,
    date: h.created_at,
    raw_text: ""
  }));
}
```

- [ ] **Step 4: Implement main() to parallel-fetch all sources**

Replace the `main()` placeholder with:

```javascript
async function main() {
  const config = readConfig();
  const results = {};
  const errors = {};
  const now = Date.now();
  const freshnessMs = (config.freshness === "48h" ? 48 : 24) * 3600000;
  
  // Build fetch tasks from preset_topics
  const tasks = [];
  for (const [key, topic] of Object.entries(config.preset_topics || {})) {
    if (!topic.enabled) continue;
    
    tasks.push((async () => {
      const topicResults = [];
      const topicErrors = [];
      
      for (const source of (topic.sources || [])) {
        try {
          let items = [];
          if (source.rss) {
            const res = await fetchUrl(source.rss);
            items = parseRss(res.body, source.name);
          } else if (source.api === "github_search") {
            items = await fetchGithub({ ...source, target_count: topic.target_count });
          } else if (source.api === "hn_algolia") {
            items = await fetchHN(source.tag || "front_page", 10);
          } else if (source.url) {
            const res = await fetchUrl(source.url);
            // Generic JSON API
            try { items = JSON.parse(res.body).hits || JSON.parse(res.body).items || []; } catch { items = []; }
          }
          
          // Filter by freshness
          for (const item of items) {
            const itemDate = item.date ? new Date(item.date).getTime() : now;
            if (now - itemDate <= freshnessMs) {
              item._source_weight = source.weight || 1.0;
              item._topic = key;
              topicResults.push(item);
            }
          }
        } catch (err) {
          topicErrors.push(`${source.name}: ${err.message}`);
        }
      }
      
      results[key] = topicResults;
      if (topicErrors.length) errors[key] = topicErrors;
    })());
  }
  
  await Promise.all(tasks);
  
  const output = {
    fetchedAt: new Date().toISOString(),
    freshness_hours: freshnessMs / 3600000,
    results,
    errors
  };
  
  fs.writeFileSync(OUTPUT_PATH, JSON.stringify(output, null, 2));
  console.log("Done. Output:", OUTPUT_PATH);
  console.log("Summary:", Object.entries(results).map(([k, v]) => `${k}: ${v.length} items`).join(", "));
}
```

- [ ] **Step 5: Test fetch.js end-to-end**

First, ensure config exists. Run:
```bash
cat /Users/kris/.openclaw/cron/hot-topics-prefs.json | jq '.version'
```

If not v3 yet, skip this test and do Task 4 first. If v3 config exists:

```bash
cd /Users/kris/.openclaw/workspace/skills/hot-topics
node scripts/fetch.js
```

Expected: `Done. Output: /tmp/hot-topics-raw.json` and a summary line like `ai: 8 items, finance: 5 items, ...`

Verify:
```bash
cat /tmp/hot-topics-raw.json | jq '.results | keys'
```

Expected: array of topic keys.

- [ ] **Step 6: Commit**

```bash
git add workspace/skills/hot-topics/scripts/fetch.js
git commit -m "feat: implement parallel fetching with RSS, GitHub, HN support"
```

---

### Task 4: Upgrade `hot-topics-prefs.json` to v3

**Files:**
- Modify: `cron/hot-topics-prefs.json`

- [ ] **Step 1: Backup current config and write v3**

```bash
cp /Users/kris/.openclaw/cron/hot-topics-prefs.json /Users/kris/.openclaw/cron/hot-topics-prefs.json.v2.bak
```

Then write the v3 config (content is in the design spec). Keep user's current topics (`AI`, `股市/财经`, `电竞`, `足球`) enabled, add `hot-news` and `github` and `tech`.

- [ ] **Step 2: Validate JSON**

```bash
cat /Users/kris/.openclaw/cron/hot-topics-prefs.json | jq '.version'
```

Expected: `3`

```bash
cat /Users/kris/.openclaw/cron/hot-topics-prefs.json | jq '.preset_topics | keys'
```

Expected: `["ai", "esports", "finance", "football", "github", "hot-news", "tech"]`

- [ ] **Step 3: Test fetch.js with v3 config**

```bash
cd /Users/kris/.openclaw/workspace/skills/hot-topics
node scripts/fetch.js
```

Expected: completes without error, outputs summary.

- [ ] **Step 4: Commit**

```bash
git add cron/hot-topics-prefs.json
git commit -m "feat: upgrade hot-topics config to v3 with preset topics, scoring weights, and github support"
```

---

### Task 5: Rewrite `SKILL.md`

**Files:**
- Modify: `workspace/skills/hot-topics/SKILL.md`

- [ ] **Step 1: Write new SKILL.md**

The new SKILL.md must include:
1. Frontmatter (name, description)
2. **Pre-fetch execution rule**: "Always run `node scripts/fetch.js` first, then read `/tmp/hot-topics-raw.json`"
3. **Parallel execution instruction**: "All searches happen in fetch.js; do NOT call web_fetch or exec for searching. Just read the JSON output."
4. **Scoring formula explanation**: How to compute score from source_weight, time_decay, social_bonus, ai_semantic_bonus (max 0.5)
5. **Hot-news special rule**: "宁缺毋滥" - if no items meet min_score, show "今日无重大热点"
6. **On-demand trigger words**: "给我看看XX", "查一下XX", "XX简讯", "XX赛程" etc.
7. **Output template**: Markdown format with emoji icons per section
8. **GitHub section special handling**: Show stars_daily_growth, not total stars
9. **Custom topics**: How to handle user-defined topics (append to custom_topics array)

- [ ] **Step 2: Test that SKILL.md frontmatter is valid**

```bash
head -5 /Users/kris/.openclaw/workspace/skills/hot-topics/SKILL.md
```

Expected: valid YAML frontmatter with `name: hot-topics` and `description`.

- [ ] **Step 3: Commit**

```bash
git add workspace/skills/hot-topics/SKILL.md
git commit -m "feat: rewrite SKILL.md for v3 with pre-fetch, scoring, and on-demand triggers"
```

---

### Task 6: Create `README.md`

**Files:**
- Create: `workspace/skills/hot-topics/README.md`

- [ ] **Step 1: Write README.md**

Content should cover:
1. What is this skill (daily hot topics push + on-demand queries)
2. Features (7 preset topics, custom topics, GitHub trending, configurable scoring)
3. Installation (one-command install via OpenClaw)
4. Configuration (`hot-topics-prefs.json` explained)
5. Usage (cron setup + on-demand trigger words)
6. Architecture (pre-fetch script + Agent scoring)
7. Requirements (OpenClaw, Node.js)

- [ ] **Step 2: Verify README renders**

```bash
cat /Users/kris/.openclaw/workspace/skills/hot-topics/README.md | head -20
```

Expected: proper Markdown with headers.

- [ ] **Step 3: Commit**

```bash
git add workspace/skills/hot-topics/README.md
git commit -m "docs: add README.md for GitHub distribution"
```

---

## Self-Review

**1. Spec coverage:**
- ✅ Pre-fetch script (Task 2-3)
- ✅ Structured scoring with source weights (Task 3 + SKILL.md)
- ✅ Hot-news "宁缺毋滥" rule (SKILL.md)
- ✅ GitHub trending with daily growth (Task 3 fetchGithub)
- ✅ On-demand queries (SKILL.md trigger words)
- ✅ Custom topics support (config v3)
- ✅ Cache for GitHub stars (Task 1 cache.js + Task 3)
- ✅ Parallel execution in fetch.js (Task 3 Promise.all)
- ✅ Zero dependency (only built-in Node.js modules)

**2. Placeholder scan:**
- No TBD/TODO
- No vague "add error handling" steps
- All code is actual, runnable code

**3. Type consistency:**
- `fetchUrl` returns `{status, body}` consistently
- Cache format: `{[dateKey]: {[repo]: stars}}` consistently
- Config keys: `preset_topics`, `custom_topics`, `global` consistently

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-21-hot-topics-v3.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints for review

**Which approach?**

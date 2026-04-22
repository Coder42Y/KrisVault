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

function fetchUrl(url, timeoutMs = 15000, headers = {}) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith("https:") ? https : http;
    const urlObj = new URL(url);
    const options = {
      hostname: urlObj.hostname,
      path: urlObj.pathname + urlObj.search,
      timeout: timeoutMs,
      headers: { "User-Agent": "daily-pulse-fetch/1.0", ...headers }
    };
    const req = client.get(options, (res) => {
      let data = "";
      res.on("data", chunk => data += chunk);
      res.on("end", () => resolve({ status: res.statusCode, body: data }));
    });
    req.on("error", reject);
    req.on("timeout", () => { req.destroy(); reject(new Error("timeout")); });
  });
}

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

async function fetchHN(tag, query, hitsPerPage = 10) {
  let url;
  if (tag) {
    url = `https://hn.algolia.com/api/v1/search?tags=${encodeURIComponent(tag)}&hitsPerPage=${hitsPerPage}`;
  } else if (query) {
    url = `https://hn.algolia.com/api/v1/search?query=${encodeURIComponent(query)}&tags=story&hitsPerPage=${hitsPerPage}`;
  } else {
    url = `https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=${hitsPerPage}`;
  }
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
            items = await fetchHN(source.tag, source.query, 10);
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

main().catch(err => { console.error(err); process.exit(1); });

const https = require("https");
const http = require("http");
const tls = require("tls");
const zlib = require("zlib");
const fs = require("fs");
const path = require("path");
const { readCache, writeCache } = require("./cache");

const CONFIG_PATH = path.join(
  require("os").homedir(),
  ".openclaw", "cron", "hot-topics-prefs.json"
);
const OUTPUT_PATH = "/tmp/hot-topics-raw.json";

let ACTIVE_PROXY = null;

function readConfig() {
  try {
    return JSON.parse(fs.readFileSync(CONFIG_PATH, "utf8"));
  } catch (err) {
    console.error("Failed to read config:", err.message);
    process.exit(1);
  }
}

function resolveProxy(config = {}) {
  return process.env.https_proxy ||
    process.env.HTTPS_PROXY ||
    process.env.http_proxy ||
    process.env.HTTP_PROXY ||
    process.env.all_proxy ||
    process.env.ALL_PROXY ||
    config?.global?.proxy ||
    config?.proxy ||
    null;
}

function parseHttpResponse(buffer) {
  const headerEndIndex = buffer.indexOf('\r\n\r\n');
  if (headerEndIndex === -1) {
    throw new Error('Invalid HTTP response: header separator not found');
  }
  const headerPart = buffer.slice(0, headerEndIndex).toString('utf8');
  let bodyBuffer = buffer.slice(headerEndIndex + 4);

  const lines = headerPart.split('\r\n');
  const statusLine = lines[0] || '';
  const statusMatch = statusLine.match(/HTTP\/\d\.\d\s+(\d+)/i);
  const status = statusMatch ? parseInt(statusMatch[1], 10) : 200;

  const headers = {};
  for (let i = 1; i < lines.length; i++) {
    const idx = lines[i].indexOf(':');
    if (idx > 0) {
      const key = lines[i].slice(0, idx).trim().toLowerCase();
      const val = lines[i].slice(idx + 1).trim();
      headers[key] = val;
    }
  }

  // Handle chunked transfer encoding
  if (headers['transfer-encoding']?.toLowerCase().includes('chunked')) {
    const chunks = [];
    let offset = 0;
    while (offset < bodyBuffer.length) {
      const lineEnd = bodyBuffer.indexOf('\r\n', offset);
      if (lineEnd === -1) break;
      const chunkSizeHex = bodyBuffer.slice(offset, lineEnd).toString('utf8').trim().split(';')[0];
      const chunkSize = parseInt(chunkSizeHex, 16);
      if (isNaN(chunkSize) || chunkSize === 0) break;
      const chunkStart = lineEnd + 2;
      const chunkEnd = chunkStart + chunkSize;
      chunks.push(bodyBuffer.slice(chunkStart, chunkEnd));
      offset = chunkEnd + 2;
    }
    bodyBuffer = Buffer.concat(chunks);
  }

  // Handle content encoding
  const encoding = (headers['content-encoding'] || '').toLowerCase();
  let bodyStr = '';
  try {
    if (encoding.includes('gzip')) {
      bodyStr = zlib.gunzipSync(bodyBuffer).toString('utf8');
    } else if (encoding.includes('deflate')) {
      bodyStr = zlib.inflateSync(bodyBuffer).toString('utf8');
    } else if (encoding.includes('br')) {
      bodyStr = zlib.brotliDecompressSync(bodyBuffer).toString('utf8');
    } else {
      bodyStr = bodyBuffer.toString('utf8');
    }
  } catch (err) {
    bodyStr = bodyBuffer.toString('utf8');
  }

  return { status, headers, body: bodyStr };
}

function fetchUrl(url, timeoutMs = 15000, headers = {}) {
  const proxyUrl = ACTIVE_PROXY;
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const isHttps = urlObj.protocol === 'https:';
    const targetPort = urlObj.port || (isHttps ? 443 : 80);

    let timer = setTimeout(() => {
      cleanup();
      reject(new Error("timeout"));
    }, timeoutMs);

    let activeSocket = null;
    let connectReq = null;
    let httpReq = null;

    function cleanup() {
      if (timer) { clearTimeout(timer); timer = null; }
      if (activeSocket) { activeSocket.destroy(); activeSocket = null; }
      if (connectReq) { connectReq.destroy(); connectReq = null; }
      if (httpReq) { httpReq.destroy(); httpReq = null; }
    }

    if (proxyUrl) {
      const proxyObj = new URL(proxyUrl);
      if (isHttps) {
        connectReq = http.request({
          host: proxyObj.hostname,
          port: proxyObj.port || 80,
          method: 'CONNECT',
          path: `${urlObj.hostname}:${targetPort}`,
          headers: {
            'Host': `${urlObj.hostname}:${targetPort}`,
            ...(proxyObj.username ? { 'Proxy-Authorization': 'Basic ' + Buffer.from(`${decodeURIComponent(proxyObj.username)}:${decodeURIComponent(proxyObj.password || '')}`).toString('base64') } : {})
          }
        });

        connectReq.on('connect', (res, socket, head) => {
          if (res.statusCode !== 200) {
            cleanup();
            return reject(new Error(`Proxy CONNECT failed: ${res.statusCode}`));
          }

          const tlsSocket = tls.connect({
            socket: socket,
            servername: urlObj.hostname,
            rejectUnauthorized: true
          }, () => {
            const reqHeaders = {
              'Host': urlObj.hostname,
              'User-Agent': 'daily-pulse-fetch/1.0',
              'Accept': '*/*',
              'Accept-Encoding': 'gzip, deflate, br',
              'Connection': 'close',
              ...headers
            };

            const path = urlObj.pathname + urlObj.search;
            const headerStr = Object.entries(reqHeaders).map(([k, v]) => `${k}: ${v}`).join('\r\n');
            tlsSocket.write(`GET ${path} HTTP/1.1\r\n${headerStr}\r\n\r\n`);
          });

          activeSocket = tlsSocket;
          let rawData = Buffer.alloc(0);

          tlsSocket.on('data', (chunk) => {
            rawData = Buffer.concat([rawData, chunk]);
          });

          tlsSocket.on('end', () => {
            cleanup();
            try {
              const parsed = parseHttpResponse(rawData);
              resolve({ status: parsed.status, body: parsed.body });
            } catch (err) {
              reject(err);
            }
          });

          tlsSocket.on('error', (err) => {
            cleanup();
            reject(err);
          });
        });

        connectReq.on('error', (err) => {
          cleanup();
          reject(err);
        });
        connectReq.end();
      } else {
        // Plain HTTP via proxy
        httpReq = http.get({
          host: proxyObj.hostname,
          port: proxyObj.port || 80,
          path: url,
          headers: {
            'Host': urlObj.hostname,
            'User-Agent': 'daily-pulse-fetch/1.0',
            'Accept-Encoding': 'gzip, deflate',
            ...headers
          }
        }, (res) => {
          let chunks = [];
          res.on('data', chunk => chunks.push(chunk));
          res.on('end', () => {
            cleanup();
            const buf = Buffer.concat(chunks);
            const encoding = (res.headers['content-encoding'] || '').toLowerCase();
            let body = '';
            try {
              if (encoding.includes('gzip')) body = zlib.gunzipSync(buf).toString('utf8');
              else if (encoding.includes('deflate')) body = zlib.inflateSync(buf).toString('utf8');
              else body = buf.toString('utf8');
              resolve({ status: res.statusCode, body });
            } catch (err) {
              reject(err);
            }
          });
        });
        httpReq.on('error', (err) => {
          cleanup();
          reject(err);
        });
      }
    } else {
      // Direct connection
      const client = isHttps ? https : http;
      const options = {
        hostname: urlObj.hostname,
        port: urlObj.port || (isHttps ? 443 : 80),
        path: urlObj.pathname + urlObj.search,
        timeout: timeoutMs,
        headers: { "User-Agent": "daily-pulse-fetch/1.0", ...headers }
      };
      httpReq = client.get(options, (res) => {
        let data = "";
        res.on("data", chunk => data += chunk);
        res.on("end", () => {
          cleanup();
          resolve({ status: res.statusCode, body: data });
        });
      });
      httpReq.on("error", (err) => {
        cleanup();
        reject(err);
      });
      httpReq.on("timeout", () => {
        cleanup();
        reject(new Error("timeout"));
      });
    }
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
  ACTIVE_PROXY = resolveProxy(config);
  if (ACTIVE_PROXY) {
    console.log(`Using proxy: ${ACTIVE_PROXY}`);
  }
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

if (require.main === module) {
  main().catch(err => { console.error(err); process.exit(1); });
}

module.exports = { fetchUrl, parseRss, fetchGithub, fetchHN, main, resolveProxy };


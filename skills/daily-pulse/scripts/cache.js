const fs = require("fs");
const path = require("path");
const os = require("os");

const CACHE_DIR = path.join(os.homedir(), ".openclaw", "cron");

function ensureDir() {
  if (!fs.existsSync(CACHE_DIR)) fs.mkdirSync(CACHE_DIR, { recursive: true });
}

function resolveSafe(filename) {
  if (typeof filename !== "string") {
    throw new TypeError("filename must be a string");
  }
  if (filename.includes("/") || filename.includes("\\") || filename === ".." || filename.startsWith(".")) {
    throw new Error("Invalid cache filename: path separators and hidden files are not allowed");
  }
  const fp = path.resolve(CACHE_DIR, filename);
  if (!fp.startsWith(CACHE_DIR + path.sep)) {
    throw new Error("Invalid cache filename: path traversal detected");
  }
  return fp;
}

function readCache(filename) {
  ensureDir();
  const fp = resolveSafe(filename);
  try {
    return JSON.parse(fs.readFileSync(fp, "utf8"));
  } catch (err) {
    if (err.code === "ENOENT") return {};
    throw err;
  }
}

function writeCache(filename, data) {
  ensureDir();
  const fp = resolveSafe(filename);
  const tmpFp = fp + ".tmp";
  fs.writeFileSync(tmpFp, JSON.stringify(data, null, 2));
  fs.renameSync(tmpFp, fp);
}

module.exports = { readCache, writeCache };

const http = require("http");
const https = require("https");
const { spawn } = require("child_process");
const { URL } = require("url");
const fs = require("fs");
const pathModule = require("path");
const { randomUUID } = require("crypto");

const PROXY_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  Accept: "*/*",
  "Accept-Language": "en-US,en;q=0.9",
  Referer: "https://www.erome.com/",
  Origin: "https://www.erome.com",
};

const PROXY_AGENT = new https.Agent({ keepAlive: true, maxSockets: 32 });

function streamProxy(req, res, targetUrlString, options = {}) {
  let target;
  try {
    target = new URL(targetUrlString);
  } catch {
    sendJson(res, 400, { ok: false, error: "Invalid proxy url." });
    return;
  }
  if (!/^https?:$/.test(target.protocol) || !/erome\.com$/i.test(target.hostname)) {
    sendJson(res, 400, { ok: false, error: "Only erome.com hosts are proxied." });
    return;
  }

  const headers = { ...PROXY_HEADERS };
  if (req.headers["range"]) headers["Range"] = req.headers["range"];
  if (req.headers["if-none-match"]) headers["If-None-Match"] = req.headers["if-none-match"];
  if (req.headers["if-modified-since"]) headers["If-Modified-Since"] = req.headers["if-modified-since"];

  const lib = target.protocol === "http:" ? http : https;
  const upstream = lib.request(
    {
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port || (target.protocol === "https:" ? 443 : 80),
      path: target.pathname + target.search,
      method: "GET",
      headers,
      agent: target.protocol === "https:" ? PROXY_AGENT : undefined,
    },
    (upRes) => {
      const passHeaders = {
        "Access-Control-Allow-Origin": "*",
        "Accept-Ranges": upRes.headers["accept-ranges"] || "bytes",
        "Cache-Control": "public, max-age=3600",
      };
      if (upRes.headers["content-type"]) passHeaders["Content-Type"] = upRes.headers["content-type"];
      if (upRes.headers["content-length"]) passHeaders["Content-Length"] = upRes.headers["content-length"];
      if (upRes.headers["content-range"]) passHeaders["Content-Range"] = upRes.headers["content-range"];
      if (upRes.headers["etag"]) passHeaders["ETag"] = upRes.headers["etag"];
      if (upRes.headers["last-modified"]) passHeaders["Last-Modified"] = upRes.headers["last-modified"];

      if (options.download) {
        const name = options.filename || decodeURIComponent(target.pathname.split("/").pop() || "file");
        passHeaders["Content-Disposition"] = `attachment; filename="${name.replace(/"/g, "")}"`;
      }

      res.writeHead(upRes.statusCode || 200, passHeaders);
      upRes.pipe(res);
    }
  );

  upstream.on("error", (err) => {
    if (!res.headersSent) sendJson(res, 502, { ok: false, error: "Proxy upstream error: " + err.message });
    else res.destroy();
  });
  req.on("close", () => upstream.destroy());
  upstream.end();
}

const HOST = process.env.HOST || "127.0.0.1";
const PORT = Number(process.env.PORT || 3000);
const PYTHON_BIN = process.env.PYTHON_BIN || "python";
const UI_PATH = pathModule.join(__dirname, "ui.html");
const APP_ROOT = pathModule.join(__dirname, "app");
const APP_INDEX_PATH = pathModule.join(APP_ROOT, "index.html");
const WATCHER_GUI_DIST_ROOT = pathModule.join(__dirname, "erome-watcher", "gui", "dist");
const WATCHER_GUI_ASSETS_ROOT = pathModule.join(WATCHER_GUI_DIST_ROOT, "assets");
const WATCHER_GUI_INDEX_PATH = pathModule.join(WATCHER_GUI_DIST_ROOT, "index.html");
const STATE_PATH = pathModule.join(__dirname, "state.json");
const DOWNLOAD_JOB_EVENT_LIMIT = 80;
const DOWNLOAD_JOB_LIMIT = 100;
const downloadJobs = new Map();

const DEFAULT_STATE = {
  settings: {
    download_directory: "Downloads",
    media_type: "all",
    skip_downloaded: true,
    overwrite: false,
    max_workers: 4,
    form_values: {},
  },
  downloaded: {
    media: {},
    albums: {},
  },
};

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
};

function sendJson(res, statusCode, payload) {
  res.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  });
  res.end(JSON.stringify(payload));
}

function sendHtml(res, statusCode, html) {
  res.writeHead(statusCode, {
    "Content-Type": "text/html; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
  });
  res.end(html);
}

function getUiHtml() {
  try {
    return fs.readFileSync(UI_PATH, "utf8");
  } catch {
    return "<!doctype html><html><body><h1>ui.html missing</h1></body></html>";
  }
}

function normalizeState(rawState = {}) {
  return {
    settings: { ...DEFAULT_STATE.settings, ...(rawState.settings || {}) },
    downloaded: {
      media: { ...((rawState.downloaded && rawState.downloaded.media) || {}) },
      albums: { ...((rawState.downloaded && rawState.downloaded.albums) || {}) },
    },
  };
}

function readState() {
  try {
    return normalizeState(JSON.parse(fs.readFileSync(STATE_PATH, "utf8")));
  } catch {
    return normalizeState();
  }
}

function writeState(state) {
  const normalized = normalizeState(state);
  fs.writeFileSync(STATE_PATH, JSON.stringify(normalized, null, 2));
  return normalized;
}

function publicDownloadJob(job) {
  return {
    id: job.id,
    kind: job.kind,
    status: job.status,
    created_at: job.created_at,
    updated_at: job.updated_at,
    percent: job.percent,
    completed: job.completed,
    total: job.total,
    attempts: job.attempts,
    retry_count: job.retry_count,
    last_error: job.last_error,
    current: job.current,
    error: job.error,
    result: job.result,
    events: job.events,
  };
}

function rememberDownloadEvent(job, event) {
  job.events.push({ at: new Date().toISOString(), ...event });
  if (job.events.length > DOWNLOAD_JOB_EVENT_LIMIT) {
    job.events.splice(0, job.events.length - DOWNLOAD_JOB_EVENT_LIMIT);
  }
}

function pruneDownloadJobs() {
  if (downloadJobs.size <= DOWNLOAD_JOB_LIMIT) return;
  const removable = Array.from(downloadJobs.values())
    .filter((job) => ["done", "error"].includes(job.status))
    .sort((left, right) => String(left.updated_at).localeCompare(String(right.updated_at)));
  while (downloadJobs.size > DOWNLOAD_JOB_LIMIT && removable.length) {
    downloadJobs.delete(removable.shift().id);
  }
}

function createCompletedDownloadJob(kind, result) {
  const now = new Date().toISOString();
  const itemCount = Array.isArray(result) ? result.length : result ? 1 : 0;
  const job = {
    id: randomUUID(),
    kind,
    status: "done",
    created_at: now,
    updated_at: now,
    percent: 100,
    completed: itemCount,
    total: itemCount,
    attempts: 0,
    retry_count: 0,
    last_error: "",
    current: null,
    error: null,
    result,
    events: [],
  };
  rememberDownloadEvent(job, {
    event: "item_done",
    status: Array.isArray(result) ? "done" : result?.status || "done",
    completed: itemCount,
    total: itemCount,
    percent: 100,
  });
  downloadJobs.set(job.id, job);
  pruneDownloadJobs();
  return job;
}

function handleDownloadJobMessage(job, message) {
  job.updated_at = new Date().toISOString();
  if (message && message.progress) {
    const progress = message.progress;
    job.status = progress.event === "retry" ? "retrying" : "running";
    job.percent = Number.isFinite(Number(progress.percent)) ? Number(progress.percent) : job.percent;
    job.completed = Number.isFinite(Number(progress.completed)) ? Number(progress.completed) : job.completed;
    job.total = Number.isFinite(Number(progress.total)) ? Number(progress.total) : job.total;
    job.attempts = Math.max(job.attempts || 0, Number(progress.attempts || 0));
    job.current = {
      event: progress.event,
      type: progress.type || "media",
      url: progress.url || "",
      filename: progress.filename || "",
      path: progress.path || "",
      status: progress.status || "",
      attempts: progress.attempts || 0,
    };
    if (progress.error) {
      job.last_error = progress.error;
    }
    if (progress.event === "retry") {
      job.retry_count += 1;
    }
    rememberDownloadEvent(job, progress);
    return;
  }

  if (message && message.ok === true) {
    const results = message.data;
    const resultCount = Array.isArray(results) ? results.length : results ? 1 : 0;
    job.status = "done";
    job.percent = 100;
    job.completed = job.total || resultCount;
    job.total = job.total || resultCount;
    job.result = results;
    job.error = null;
    rememberDownloadEvent(job, {
      event: "job_done",
      status: "done",
      completed: job.completed,
      total: job.total,
      percent: 100,
    });
    return;
  }

  if (message && message.error) {
    job.status = "error";
    job.error = message.error;
    job.last_error = message.error;
    rememberDownloadEvent(job, { event: "job_error", status: "error", error: message.error });
  }
}

function parseDownloadJobLine(job, line) {
  const trimmed = line.trim();
  if (!trimmed) return;
  try {
    handleDownloadJobMessage(job, JSON.parse(trimmed));
  } catch (error) {
    job.updated_at = new Date().toISOString();
    job.last_error = `Could not parse progress: ${trimmed.slice(0, 160)}`;
    rememberDownloadEvent(job, { event: "parse_error", status: "error", error: error.message || String(error) });
  }
}

function startBridgeDownloadJob(kind, method, payload, finalize) {
  const now = new Date().toISOString();
  const job = {
    id: randomUUID(),
    kind,
    status: "running",
    created_at: now,
    updated_at: now,
    percent: 0,
    completed: 0,
    total: 0,
    attempts: 0,
    retry_count: 0,
    last_error: "",
    current: null,
    error: null,
    result: null,
    events: [],
    stderr: "",
  };
  downloadJobs.set(job.id, job);
  pruneDownloadJobs();
  rememberDownloadEvent(job, { event: "job_start", status: "running", percent: 0 });

  const child = spawn(PYTHON_BIN, ["api_bridge.py", method], {
    cwd: __dirname,
    stdio: ["pipe", "pipe", "pipe"],
  });
  job.pid = child.pid;

  let stdoutBuffer = "";
  const drainStdout = (force = false) => {
    let newlineIndex = stdoutBuffer.indexOf("\n");
    while (newlineIndex >= 0) {
      const line = stdoutBuffer.slice(0, newlineIndex);
      stdoutBuffer = stdoutBuffer.slice(newlineIndex + 1);
      parseDownloadJobLine(job, line);
      newlineIndex = stdoutBuffer.indexOf("\n");
    }
    if (force && stdoutBuffer.trim()) {
      parseDownloadJobLine(job, stdoutBuffer);
      stdoutBuffer = "";
    }
  };

  child.stdout.on("data", (chunk) => {
    stdoutBuffer += chunk.toString("utf8");
    drainStdout(false);
  });

  child.stderr.on("data", (chunk) => {
    job.stderr = `${job.stderr}${chunk.toString("utf8")}`.slice(-4000);
  });

  child.on("error", (error) => {
    job.updated_at = new Date().toISOString();
    job.status = "error";
    job.error = error.message || String(error);
    job.last_error = job.error;
    rememberDownloadEvent(job, { event: "job_error", status: "error", error: job.error });
  });

  child.on("close", (code) => {
    drainStdout(true);
    job.updated_at = new Date().toISOString();
    if (code !== 0 && job.status !== "done") {
      job.status = "error";
      job.error = job.error || job.last_error || job.stderr.trim() || `Bridge process exited with code ${code}.`;
      job.last_error = job.error;
      rememberDownloadEvent(job, { event: "job_error", status: "error", error: job.error });
      return;
    }
    if (code === 0 && job.status !== "done") {
      job.status = "error";
      job.error = job.error || job.last_error || "Bridge exited without a final download result.";
      job.last_error = job.error;
      rememberDownloadEvent(job, { event: "job_error", status: "error", error: job.error });
      return;
    }
    if (job.status === "done" && typeof finalize === "function") {
      try {
        finalize(job.result);
      } catch (error) {
        job.state_error = error.message || String(error);
        rememberDownloadEvent(job, { event: "state_error", status: "warning", error: job.state_error });
      }
    }
  });

  child.stdin.write(JSON.stringify(payload));
  child.stdin.end();
  return job;
}

function finalizeDownloadedResults(results, albumPath) {
  const state = readState();
  recordDownloadResults(state, results || [], albumPath || "");
  writeState(state);
}

function startAlbumDownloadJob(body) {
  const state = readState();
  const directory = body.directory || state.settings.download_directory || "Downloads";
  const overwrite = body.overwrite === true;
  const skipDownloaded = body.skip_downloaded !== false && state.settings.skip_downloaded !== false;
  const mediaType = body.media_type || state.settings.media_type || "all";
  const maxWorkers = getInt(body.max_workers, state.settings.max_workers || 4);
  const sourcePath = body.path || body.url || body.album_url || "";
  const albumPath = albumPathFromValue(sourcePath);
  state.settings = {
    ...state.settings,
    download_directory: directory,
    media_type: mediaType,
    skip_downloaded: skipDownloaded,
    overwrite,
    max_workers: maxWorkers,
  };
  writeState(state);

  return startBridgeDownloadJob(
    "album",
    "download_album_progress",
    {
      path: sourcePath,
      directory,
      include_photos: body.include_photos !== false && mediaType !== "video",
      include_videos: body.include_videos !== false && mediaType !== "photo",
      overwrite,
      max_workers: maxWorkers,
      skip_urls: skipDownloaded ? Object.keys(state.downloaded.media) : [],
      retry_delay: Number.isFinite(Number(body.retry_delay)) ? Number(body.retry_delay) : 0.5,
    },
    (results) => finalizeDownloadedResults(results, albumPath)
  );
}

function startMediaDownloadJob(body) {
  const state = readState();
  const mediaUrl = normalizeMediaUrl(body.url || "");
  const directory = body.directory || state.settings.download_directory || "Downloads";
  const overwrite = body.overwrite === true;
  const skipDownloaded = body.skip_downloaded !== false && state.settings.skip_downloaded !== false;
  const albumPath = albumPathFromValue(body.album || body.album_url || "");
  state.settings = {
    ...state.settings,
    download_directory: directory,
    skip_downloaded: skipDownloaded,
    overwrite,
  };
  writeState(state);

  if (skipDownloaded && state.downloaded.media[mediaUrl]) {
    return createCompletedDownloadJob("media", { ...state.downloaded.media[mediaUrl], status: "skipped_downloaded" });
  }

  return startBridgeDownloadJob(
    "media",
    "download_media_progress",
    {
      url: mediaUrl,
      directory,
      filename: body.filename || "",
      overwrite,
      retry_delay: Number.isFinite(Number(body.retry_delay)) ? Number(body.retry_delay) : 0.5,
    },
    (result) => finalizeDownloadedResults(result, albumPath)
  );
}

function getDownloadJob(pathname) {
  if (pathname === "/api/download/jobs") return { mode: "list" };
  if (pathname.startsWith("/api/download/jobs/")) {
    return { mode: "item", id: decodeURIComponent(pathname.slice("/api/download/jobs/".length)) };
  }
  return null;
}

function getWatcherDownloadJobPath(watcherPath) {
  if (watcherPath === "/download/jobs") return { mode: "list" };
  if (watcherPath.startsWith("/download/jobs/")) {
    return { mode: "item", id: decodeURIComponent(watcherPath.slice("/download/jobs/".length)) };
  }
  return null;
}

function normalizeMediaUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  try {
    return new URL(raw.startsWith("//") ? `https:${raw}` : raw).href;
  } catch {
    return raw;
  }
}

function albumPathFromValue(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  try {
    const parsed = new URL(raw);
    const parts = parsed.pathname.split("/").filter(Boolean);
    const albumIndex = parts.indexOf("a");
    if (albumIndex >= 0 && parts[albumIndex + 1]) return parts[albumIndex + 1];
  } catch {
    // Treat as slug/path below.
  }
  return raw.replace(/^\/+|\/+$/g, "").split("/").pop() || raw;
}

function recordDownloadResults(state, results, albumPath = "") {
  const items = Array.isArray(results) ? results : [results];
  const now = new Date().toISOString();
  for (const item of items) {
    if (!item || !item.url) continue;
    const status = item.status || "downloaded";
    if (!["downloaded", "skipped"].includes(status)) continue;
    const url = normalizeMediaUrl(item.url);
    state.downloaded.media[url] = {
      url,
      type: item.type || "media",
      filename: item.filename || "",
      path: item.path || "",
      album: albumPath || "",
      status,
      downloaded_at: now,
    };
  }
  if (albumPath) {
    state.downloaded.albums[albumPath] = {
      path: albumPath,
      media_count: items.filter((item) => item && ["downloaded", "skipped", "skipped_downloaded"].includes(item.status)).length,
      downloaded_at: now,
    };
  }
}

function getAppHtml() {
  try {
    return fs.readFileSync(APP_INDEX_PATH, "utf8");
  } catch {
    return getUiHtml();
  }
}

function tryServeAppStatic(req, res, pathname) {
  if (req.method !== "GET") return false;
  if (!pathname.startsWith("/app/")) return false;

  const relative = pathname.slice("/app/".length);
  const safePath = pathModule.normalize(relative).replace(/^([.][./\\])+/, "");
  const filePath = pathModule.join(APP_ROOT, safePath);

  if (!filePath.startsWith(APP_ROOT)) {
    sendJson(res, 403, { ok: false, error: "Forbidden path." });
    return true;
  }

  let stat;
  try {
    stat = fs.statSync(filePath);
  } catch {
    sendJson(res, 404, { ok: false, error: "Static file not found." });
    return true;
  }

  if (!stat.isFile()) {
    sendJson(res, 404, { ok: false, error: "Static file not found." });
    return true;
  }

  const ext = pathModule.extname(filePath).toLowerCase();
  const contentType = MIME_TYPES[ext] || "application/octet-stream";

  res.writeHead(200, {
    "Content-Type": contentType,
    "Cache-Control": "public, max-age=3600",
    "Access-Control-Allow-Origin": "*",
  });

  fs.createReadStream(filePath).pipe(res);
  return true;
}

function serveStaticFromRoot(res, root, relativePath) {
  const safePath = pathModule.normalize(relativePath).replace(/^([.][./\\])+/, "");
  const filePath = pathModule.join(root, safePath);

  if (!filePath.startsWith(root)) {
    sendJson(res, 403, { ok: false, error: "Forbidden path." });
    return true;
  }

  let stat;
  try {
    stat = fs.statSync(filePath);
  } catch {
    sendJson(res, 404, { ok: false, error: "Static file not found." });
    return true;
  }

  if (!stat.isFile()) {
    sendJson(res, 404, { ok: false, error: "Static file not found." });
    return true;
  }

  const ext = pathModule.extname(filePath).toLowerCase();
  const contentType = MIME_TYPES[ext] || "application/octet-stream";
  res.writeHead(200, {
    "Content-Type": contentType,
    "Cache-Control": "public, max-age=3600",
    "Access-Control-Allow-Origin": "*",
  });
  fs.createReadStream(filePath).pipe(res);
  return true;
}

function tryServeWatcherStatic(req, res, pathname) {
  if (req.method !== "GET") return false;

  if (pathname.startsWith("/assets/")) {
    return serveStaticFromRoot(res, WATCHER_GUI_ASSETS_ROOT, pathname.slice("/assets/".length));
  }

  if (pathname.startsWith("/watcher/assets/")) {
    return serveStaticFromRoot(res, WATCHER_GUI_ASSETS_ROOT, pathname.slice("/watcher/assets/".length));
  }

  if (pathname === "/watcher" || pathname === "/watcher/" || pathname.startsWith("/watcher/")) {
    if (fs.existsSync(WATCHER_GUI_INDEX_PATH)) {
      sendHtml(res, 200, fs.readFileSync(WATCHER_GUI_INDEX_PATH, "utf8"));
      return true;
    }

    sendHtml(
      res,
      200,
      "<!doctype html><html><body><h1>Erome Watcher dashboard not built</h1><p>Run <code>cd erome-watcher/gui && npm run build</code>, then reload this page.</p></body></html>"
    );
    return true;
  }

  return false;
}

function parseBody(req) {
  return new Promise((resolve, reject) => {
    let raw = "";
    req.on("data", (chunk) => {
      raw += chunk;
      if (raw.length > 2_000_000) {
        reject(new Error("Request body too large."));
        req.destroy();
      }
    });
    req.on("end", () => {
      if (!raw.trim()) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(raw));
      } catch {
        reject(new Error("Invalid JSON body."));
      }
    });
    req.on("error", reject);
  });
}

function callBridge(method, payload = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(PYTHON_BIN, ["api_bridge.py", method], {
      cwd: __dirname,
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString("utf8");
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString("utf8");
    });

    child.on("error", (error) => {
      reject(error);
    });

    child.on("close", (code) => {
      let parsed;
      try {
        parsed = stdout ? JSON.parse(stdout) : null;
      } catch {
        parsed = null;
      }

      if (code !== 0) {
        const errMessage =
          parsed?.error || stderr.trim() || `Bridge process exited with code ${code}.`;
        reject(new Error(errMessage));
        return;
      }

      if (!parsed || parsed.ok !== true) {
        reject(new Error(parsed?.error || "Bridge returned an invalid payload."));
        return;
      }

      resolve(parsed.data);
    });

    child.stdin.write(JSON.stringify(payload));
    child.stdin.end();
  });
}

function getBool(value, fallback = false) {
  if (value === null || value === undefined || value === "") return fallback;
  return ["1", "true", "yes", "on"].includes(String(value).toLowerCase());
}

function getInt(value, fallback) {
  if (value === null || value === undefined || value === "") return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.trunc(parsed) : fallback;
}

function getAlbumQueryOptions(url) {
  return {
    sort_by: url.searchParams.get("sort") || url.searchParams.get("sort_by") || "default",
    sort_dir: url.searchParams.get("dir") || url.searchParams.get("sort_dir") || "desc",
    hidden_only:
      getBool(url.searchParams.get("hidden"), false) || getBool(url.searchParams.get("hidden_only"), false),
  };
}

function normalizeWatcherPath(value) {
  const normalized = String(value || "/").replace(/\/+/g, "/");
  return normalized || "/";
}

function getWatcherPath(pathname) {
  if (pathname === "/api/watcher") return "/";
  if (pathname.startsWith("/api/watcher/")) return normalizeWatcherPath(pathname.slice("/api/watcher".length));
  return null;
}

function getWatcherProfileRoute(watcherPath) {
  const parts = watcherPath.split("/").filter(Boolean).map((part) => decodeURIComponent(part));
  if (parts[0] !== "profile" || !parts[1]) return null;
  return { username: parts[1], action: parts[2] || "snapshot" };
}

const server = http.createServer(async (req, res) => {
  if (!req.url || !req.method) {
    sendJson(res, 400, { ok: false, error: "Invalid request." });
    return;
  }

  if (req.method === "OPTIONS") {
    res.writeHead(204, {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    });
    res.end();
    return;
  }

  const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);
  const path = url.pathname;

  try {
    if (tryServeAppStatic(req, res, path)) {
      return;
    }

    if (tryServeWatcherStatic(req, res, path)) {
      return;
    }

    const watcherPath = getWatcherPath(path);
    if (watcherPath !== null) {
      const watcherDownloadJobPath = getWatcherDownloadJobPath(watcherPath);
      if (req.method === "GET" && watcherDownloadJobPath?.mode === "list") {
        sendJson(res, 200, { ok: true, data: Array.from(downloadJobs.values()).map(publicDownloadJob) });
        return;
      }
      if (req.method === "GET" && watcherDownloadJobPath?.mode === "item") {
        const job = downloadJobs.get(watcherDownloadJobPath.id);
        if (!job) {
          sendJson(res, 404, { ok: false, error: "Download job not found." });
          return;
        }
        sendJson(res, 200, { ok: true, data: publicDownloadJob(job) });
        return;
      }
      if (req.method === "POST" && watcherPath === "/download/jobs") {
        const body = await parseBody(req);
        const job = startAlbumDownloadJob(body);
        sendJson(res, 202, { ok: true, data: publicDownloadJob(job) });
        return;
      }

      if (req.method === "GET" && (watcherPath === "/" || watcherPath === "/health")) {
        const data = await callBridge("watcher_health", {});
        sendJson(res, 200, data);
        return;
      }

      if (req.method === "GET" && watcherPath === "/search/live") {
        const data = await callBridge("watcher_search_live", {
          query: url.searchParams.get("query") || url.searchParams.get("keyword") || "",
          page: getInt(url.searchParams.get("page"), 1),
        });
        sendJson(res, 200, data);
        return;
      }

      if (req.method === "GET" && watcherPath === "/search") {
        const data = await callBridge("watcher_search", {
          query: url.searchParams.get("query") || url.searchParams.get("keyword") || "",
          username: url.searchParams.get("username") || "",
          limit: getInt(url.searchParams.get("limit"), 20),
          sort_by: url.searchParams.get("sort_by") || "relevance",
          source: url.searchParams.get("source") || "",
          min_views: url.searchParams.get("min_views") || "",
        });
        sendJson(res, 200, data);
        return;
      }

      if (req.method === "GET" && watcherPath === "/album") {
        const data = await callBridge("watcher_album", { url: url.searchParams.get("url") || "" });
        sendJson(res, 200, data);
        return;
      }

      if (req.method === "POST" && watcherPath === "/download") {
        const body = await parseBody(req);
        const data = await callBridge("watcher_download_album", body);
        sendJson(res, 200, data);
        return;
      }

      if (req.method === "GET" && watcherPath === "/index/stats") {
        const data = await callBridge("watcher_index_stats", {});
        sendJson(res, 200, data);
        return;
      }

      if (req.method === "POST" && watcherPath === "/index/profile") {
        const body = await parseBody(req);
        const data = await callBridge("watcher_index_profile", body);
        sendJson(res, 200, data);
        return;
      }

      if (req.method === "POST" && watcherPath === "/index/explore") {
        const body = await parseBody(req);
        const data = await callBridge("watcher_index_explore", body);
        sendJson(res, 200, data);
        return;
      }

      if (req.method === "POST" && watcherPath === "/index/rebuild") {
        const body = await parseBody(req);
        const data = await callBridge("watcher_index_rebuild", body);
        sendJson(res, 200, data);
        return;
      }

      if (req.method === "POST" && watcherPath === "/watch") {
        const body = await parseBody(req);
        const data = await callBridge("watcher_watch", body);
        sendJson(res, 200, data);
        return;
      }

      if (req.method === "POST" && watcherPath === "/watch/alert") {
        const body = await parseBody(req);
        const data = await callBridge("watcher_watch_alert", body);
        sendJson(res, 200, data);
        return;
      }

      if (req.method === "GET" && watcherPath === "/profile") {
        const data = await callBridge("watcher_profile", { username: url.searchParams.get("username") || url.searchParams.get("profile") || "" });
        sendJson(res, 200, data);
        return;
      }

      const profileRoute = getWatcherProfileRoute(watcherPath);
      if (req.method === "GET" && profileRoute) {
        if (profileRoute.action === "snapshot") {
          const data = await callBridge("watcher_profile", { username: profileRoute.username });
          sendJson(res, 200, data);
          return;
        }
        if (profileRoute.action === "diff") {
          const data = await callBridge("watcher_profile_diff", { username: profileRoute.username });
          sendJson(res, 200, data);
          return;
        }
        if (profileRoute.action === "history") {
          const data = await callBridge("watcher_profile_history", {
            username: profileRoute.username,
            limit: getInt(url.searchParams.get("limit"), 20),
          });
          sendJson(res, 200, data);
          return;
        }
      }

      sendJson(res, 404, { ok: false, error: "Watcher route not found." });
      return;
    }

    if (req.method === "GET" && path === "/") {
      sendHtml(res, 200, getUiHtml());
      return;
    }

    if (req.method === "GET" && path === "/health") {
      sendJson(res, 200, { ok: true, service: "EroTok bridge", version: "1.0.0" });
      return;
    }

    if (req.method === "GET" && path === "/api/diagnostics") {
      const data = await callBridge("diagnostics", {});
      sendJson(res, 200, { ok: true, data });
      return;
    }

    if (req.method === "GET" && path === "/api/state") {
      sendJson(res, 200, { ok: true, data: readState() });
      return;
    }

    if (req.method === "GET" && path === "/api/settings") {
      sendJson(res, 200, { ok: true, data: readState().settings });
      return;
    }

    if (req.method === "POST" && path === "/api/settings") {
      const body = await parseBody(req);
      const state = readState();
      state.settings = { ...state.settings, ...body };
      sendJson(res, 200, { ok: true, data: writeState(state).settings });
      return;
    }

    if (req.method === "GET" && path === "/api/downloaded") {
      sendJson(res, 200, { ok: true, data: readState().downloaded });
      return;
    }

    if (req.method === "GET" && path === "/api/search") {
      const data = await callBridge("search", {
        keyword: url.searchParams.get("keyword") || "",
        page: getInt(url.searchParams.get("page"), 1),
        limit: getInt(url.searchParams.get("limit"), 1),
        ...getAlbumQueryOptions(url),
      });
      sendJson(res, 200, { ok: true, data });
      return;
    }

    if (req.method === "GET" && path === "/api/hidden-search") {
      const data = await callBridge("search", {
        keyword: url.searchParams.get("keyword") || "hidden",
        page: getInt(url.searchParams.get("page"), 1),
        limit: getInt(url.searchParams.get("limit"), 1),
        ...getAlbumQueryOptions(url),
        hidden_only: true,
      });
      sendJson(res, 200, { ok: true, data });
      return;
    }

    if (req.method === "GET" && path === "/api/explore") {
      const data = await callBridge("explore", {
        page: getInt(url.searchParams.get("page"), 1),
        limit: getInt(url.searchParams.get("limit"), 1),
        new: getBool(url.searchParams.get("new"), false),
        ...getAlbumQueryOptions(url),
      });
      sendJson(res, 200, { ok: true, data });
      return;
    }

    if (req.method === "GET" && path === "/api/version") {
      const data = await callBridge("version", {
        version: url.searchParams.get("version") || "all",
      });
      sendJson(res, 200, { ok: true, data });
      return;
    }

    if (req.method === "GET" && path === "/api/profile/reposts") {
      const data = await callBridge("profile_reposts", {
        profile: url.searchParams.get("profile") || "",
        page: getInt(url.searchParams.get("page"), 1),
        limit: getInt(url.searchParams.get("limit"), 1),
        ...getAlbumQueryOptions(url),
        content: "reposts",
      });
      sendJson(res, 200, { ok: true, data });
      return;
    }

    if (req.method === "GET" && path === "/api/profile") {
      const data = await callBridge("profile", {
        profile: url.searchParams.get("profile") || "",
        page: getInt(url.searchParams.get("page"), 1),
        limit: getInt(url.searchParams.get("limit"), 1),
        ...getAlbumQueryOptions(url),
        content: url.searchParams.get("content") || url.searchParams.get("tab") || "albums",
      });
      sendJson(res, 200, { ok: true, data });
      return;
    }

    if (req.method === "GET" && path === "/api/album/content") {
      const albumPath = url.searchParams.get("path") || "";
      const data = await callBridge("album_content", { path: albumPath });
      sendJson(res, 200, { ok: true, data });
      return;
    }

    if (req.method === "GET" && path === "/api/album/info") {
      const albumPath = url.searchParams.get("path") || "";
      const data = await callBridge("album_info", { path: albumPath });
      sendJson(res, 200, { ok: true, data });
      return;
    }

    if (req.method === "GET" && path === "/api/album/metadata") {
      const albumPath = url.searchParams.get("path") || "";
      const data = await callBridge("album_metadata", { path: albumPath });
      sendJson(res, 200, { ok: true, data });
      return;
    }

    if (req.method === "GET" && (path === "/proxy" || path === "/media")) {
      const target = url.searchParams.get("url") || "";
      const download = getBool(url.searchParams.get("download"), false);
      const filename = url.searchParams.get("filename") || "";
      streamProxy(req, res, target, { download, filename });
      return;
    }

    if (req.method === "GET" && path === "/api/content") {
      const mediaUrl = url.searchParams.get("url") || "";
      const maxVideoBytes = getInt(url.searchParams.get("maxVideoBytes"), 0);
      const data = await callBridge("content", {
        url: mediaUrl,
        max_video_bytes: maxVideoBytes,
      });

      const asBinary = getBool(url.searchParams.get("binary"), true);
      if (asBinary) {
        const buffer = Buffer.from(data.bytes_base64, "base64");
        res.writeHead(200, {
          "Content-Type": data.content_type || "application/octet-stream",
          "Content-Length": buffer.length,
          "Access-Control-Allow-Origin": "*",
        });
        res.end(buffer);
      } else {
        sendJson(res, 200, { ok: true, data });
      }
      return;
    }

    if (req.method === "POST" && path === "/api/download") {
      const body = await parseBody(req);
      const state = readState();
      const directory = body.directory || state.settings.download_directory || "Downloads";
      const overwrite = body.overwrite === true;
      const skipDownloaded = body.skip_downloaded !== false && state.settings.skip_downloaded !== false;
      const mediaType = body.media_type || state.settings.media_type || "all";
      state.settings = {
        ...state.settings,
        download_directory: directory,
        media_type: mediaType,
        skip_downloaded: skipDownloaded,
        overwrite,
        max_workers: getInt(body.max_workers, state.settings.max_workers || 4),
      };
      const albumPath = albumPathFromValue(body.path || "");
      const data = await callBridge("download_album", {
        path: body.path || "",
        directory,
        include_photos: body.include_photos !== false && mediaType !== "video",
        include_videos: body.include_videos !== false && mediaType !== "photo",
        overwrite,
        max_workers: state.settings.max_workers,
        skip_urls: skipDownloaded ? Object.keys(state.downloaded.media) : [],
        retry_until_done: body.retry_until_done === true,
        retry_delay: Number.isFinite(Number(body.retry_delay)) ? Number(body.retry_delay) : 0.5,
      });
      recordDownloadResults(state, data, albumPath);
      writeState(state);
      sendJson(res, 200, { ok: true, data });
      return;
    }

    const downloadJobPath = getDownloadJob(path);
    if (req.method === "GET" && downloadJobPath?.mode === "list") {
      sendJson(res, 200, { ok: true, data: Array.from(downloadJobs.values()).map(publicDownloadJob) });
      return;
    }
    if (req.method === "GET" && downloadJobPath?.mode === "item") {
      const job = downloadJobs.get(downloadJobPath.id);
      if (!job) {
        sendJson(res, 404, { ok: false, error: "Download job not found." });
        return;
      }
      sendJson(res, 200, { ok: true, data: publicDownloadJob(job) });
      return;
    }
    if (req.method === "POST" && path === "/api/download/jobs") {
      const body = await parseBody(req);
      const job = startAlbumDownloadJob(body);
      sendJson(res, 202, { ok: true, data: publicDownloadJob(job) });
      return;
    }

    if (req.method === "POST" && path === "/api/download/media/jobs") {
      const body = await parseBody(req);
      const job = startMediaDownloadJob(body);
      sendJson(res, 202, { ok: true, data: publicDownloadJob(job) });
      return;
    }

    if (req.method === "POST" && path === "/api/download/media") {
      const body = await parseBody(req);
      const state = readState();
      const mediaUrl = normalizeMediaUrl(body.url || "");
      const directory = body.directory || state.settings.download_directory || "Downloads";
      const overwrite = body.overwrite === true;
      const skipDownloaded = body.skip_downloaded !== false && state.settings.skip_downloaded !== false;
      state.settings = {
        ...state.settings,
        download_directory: directory,
        skip_downloaded: skipDownloaded,
        overwrite,
      };
      if (skipDownloaded && state.downloaded.media[mediaUrl]) {
        writeState(state);
        sendJson(res, 200, { ok: true, data: { ...state.downloaded.media[mediaUrl], status: "skipped_downloaded" } });
        return;
      }
      const data = await callBridge("download_media", {
        url: mediaUrl,
        directory,
        filename: body.filename || "",
        overwrite,
        retry_until_done: body.retry_until_done === true,
        retry_delay: Number.isFinite(Number(body.retry_delay)) ? Number(body.retry_delay) : 0.5,
      });
      recordDownloadResults(state, data, albumPathFromValue(body.album || ""));
      writeState(state);
      sendJson(res, 200, { ok: true, data });
      return;
    }

    sendJson(res, 404, {
      ok: false,
      error: "Route not found.",
      routes: [
        "GET /health",
        "GET /api/diagnostics",
        "GET /api/state",
        "GET /api/settings",
        "POST /api/settings",
        "GET /api/downloaded",
        "GET /api/search?keyword=&page=1&limit=1",
        "GET /api/hidden-search?keyword=&page=1&limit=1",
        "GET /api/explore?page=1&limit=1&new=false",
        "GET /api/version?version=all",
        "GET /api/profile?profile=<username>&page=1&limit=1",
        "GET /api/profile/reposts?profile=<username>&page=1&limit=1",
        "GET /api/album/content?path=RHoERFQP",
        "GET /api/album/info?path=RHoERFQP",
        "GET /api/album/metadata?path=RHoERFQP",
        "GET /api/content?url=<media-url>&maxVideoBytes=0&binary=true",
        "POST /api/download",
        "POST /api/download/jobs",
        "GET /api/download/jobs",
        "GET /api/download/jobs/<id>",
        "POST /api/download/media",
        "POST /api/download/media/jobs",
        "GET /watcher",
        "GET /api/watcher/health",
        "GET /api/watcher/profile/<username>",
        "GET /api/watcher/profile/<username>/diff",
        "GET /api/watcher/profile/<username>/history?limit=20",
        "POST /api/watcher/watch",
        "POST /api/watcher/watch/alert",
        "GET /api/watcher/album?url=https://www.erome.com/a/...",
        "POST /api/watcher/download",
        "POST /api/watcher/download/jobs",
        "GET /api/watcher/download/jobs/<id>",
        "GET /api/watcher/index/stats",
        "POST /api/watcher/index/profile",
        "POST /api/watcher/index/explore",
        "POST /api/watcher/index/rebuild",
        "GET /api/watcher/search?query=&limit=20",
        "GET /api/watcher/search/live?query=&page=1",
      ],
    });
  } catch (error) {
    sendJson(res, 500, { ok: false, error: error.message || String(error) });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`EroTok server listening on http://${HOST}:${PORT}`);
});

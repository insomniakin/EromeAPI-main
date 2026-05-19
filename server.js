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
const REDDIT_USER_AGENT = "EroTok/1.0 local feed bridge";

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
  albums: {
    seen: {},
    skipped: {},
    saved: {},
  },
  reddit: {
    client_id: "",
    client_secret: "",
    redirect_uri: "",
    oauth_state: "",
    auth: null,
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
    albums: {
      seen: { ...((rawState.albums && rawState.albums.seen) || {}) },
      skipped: { ...((rawState.albums && rawState.albums.skipped) || {}) },
      saved: { ...((rawState.albums && rawState.albums.saved) || {}) },
    },
    reddit: {
      client_id: String((rawState.reddit && rawState.reddit.client_id) || ""),
      client_secret: String((rawState.reddit && rawState.reddit.client_secret) || ""),
      redirect_uri: String((rawState.reddit && rawState.reddit.redirect_uri) || ""),
      oauth_state: String((rawState.reddit && rawState.reddit.oauth_state) || ""),
      auth: rawState.reddit && rawState.reddit.auth ? { ...rawState.reddit.auth } : null,
    },
  };
}

function publicRedditStatus(redditState = {}) {
  const auth = redditState.auth || null;
  return {
    configured: !!redditState.client_id,
    client_id: redditState.client_id || "",
    has_client_secret: !!redditState.client_secret,
    redirect_uri: redditState.redirect_uri || "",
    connected: !!(auth && auth.refresh_token),
    username: auth && auth.username ? auth.username : "",
    scope: auth && auth.scope ? auth.scope : "",
    expires_at: auth && auth.expires_at ? auth.expires_at : 0,
  };
}

function sanitizeState(state) {
  const normalized = normalizeState(state);
  return {
    ...normalized,
    reddit: publicRedditStatus(normalized.reddit),
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

function normalizeAlbumKey(value) {
  const path = albumPathFromValue(value);
  if (path) return path;
  const raw = String(value || "").trim();
  if (!raw) return "";
  try {
    return new URL(raw.startsWith("//") ? `https:${raw}` : raw).href;
  } catch {
    return raw;
  }
}

function albumRecordFromBody(body = {}) {
  const url = String(body.url || body.album_url || body.path || "").trim();
  const key = normalizeAlbumKey(url || body.key || body.title || "");
  if (!key) {
    throw new Error("Album history actions require an album url, path, key, or title.");
  }
  return {
    key,
    url,
    title: String(body.title || ""),
    thumb: String(body.thumb || body.thumbnail || ""),
    source: String(body.source || "erome"),
    updated_at: new Date().toISOString(),
  };
}

function recordAlbumState(state, body = {}) {
  const action = String(body.action || body.state || "seen").toLowerCase();
  const actionMap = {
    seen: ["seen", true],
    skipped: ["skipped", true],
    saved: ["saved", true],
    unsee: ["seen", false],
    unseen: ["seen", false],
    unskip: ["skipped", false],
    unskipped: ["skipped", false],
    unsave: ["saved", false],
    unsaved: ["saved", false],
  };
  const target = actionMap[action];
  if (!target) {
    throw new Error("Album history action should be seen, skipped, saved, unsee, unskip, or unsave.");
  }
  const [bucket, shouldSet] = target;
  const record = albumRecordFromBody(body);
  state.albums = state.albums || { seen: {}, skipped: {}, saved: {} };
  state.albums[bucket] = state.albums[bucket] || {};
  if (shouldSet) {
    state.albums[bucket][record.key] = record;
  } else {
    delete state.albums[bucket][record.key];
  }
  return { bucket, action, record, albums: state.albums };
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

function clampInt(value, fallback, min, max) {
  const parsed = getInt(value, fallback);
  return Math.max(min, Math.min(max, parsed));
}

function sendRedirect(res, target) {
  res.writeHead(302, {
    Location: target,
    "Access-Control-Allow-Origin": "*",
  });
  res.end();
}

function sendPlainHtml(res, statusCode, title, message) {
  sendHtml(
    res,
    statusCode,
    `<!doctype html><html><head><meta charset="utf-8"><title>${title}</title></head><body style="font-family:Segoe UI,Arial,sans-serif;background:#0b1220;color:#e5e7eb;padding:24px"><h1>${title}</h1><p>${message}</p><p>You can close this tab and return to EroTok.</p></body></html>`
  );
}

function requestOrigin(req) {
  const host = req.headers.host || `${HOST}:${PORT}`;
  return `http://${host}`;
}

function redditRedirectUri(req) {
  return new URL("/api/reddit/callback", requestOrigin(req)).href;
}

function formEncode(data) {
  return new URLSearchParams(data).toString();
}

function httpsJsonRequest(targetUrl, options = {}) {
  return new Promise((resolve, reject) => {
    const target = new URL(targetUrl);
    const body = options.body || null;
    const headers = { ...(options.headers || {}) };
    if (body && !headers["Content-Length"]) headers["Content-Length"] = Buffer.byteLength(body);
    const request = https.request(
      {
        protocol: target.protocol,
        hostname: target.hostname,
        port: target.port || 443,
        path: target.pathname + target.search,
        method: options.method || "GET",
        headers,
      },
      (response) => {
        let raw = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => { raw += chunk; });
        response.on("end", () => {
          let data = null;
          try {
            data = raw ? JSON.parse(raw) : null;
          } catch {
            data = { raw };
          }
          resolve({ statusCode: response.statusCode || 0, data, raw });
        });
      }
    );
    request.on("error", reject);
    if (body) request.write(body);
    request.end();
  });
}

function redditBasicAuth(clientId, clientSecret = "") {
  return `Basic ${Buffer.from(`${clientId}:${clientSecret}`).toString("base64")}`;
}

async function exchangeRedditCode(clientId, clientSecret, code, redirectUri) {
  const body = formEncode({ grant_type: "authorization_code", code, redirect_uri: redirectUri });
  const response = await httpsJsonRequest("https://www.reddit.com/api/v1/access_token", {
    method: "POST",
    headers: {
      Authorization: redditBasicAuth(clientId, clientSecret),
      "Content-Type": "application/x-www-form-urlencoded",
      "User-Agent": REDDIT_USER_AGENT,
    },
    body,
  });
  if (response.statusCode < 200 || response.statusCode > 299 || !response.data || response.data.error) {
    throw new Error(response.data?.error_description || response.data?.error || `Reddit token exchange failed with ${response.statusCode}.`);
  }
  return response.data;
}

async function refreshRedditToken(state) {
  const reddit = state.reddit || {};
  const auth = reddit.auth || {};
  if (!reddit.client_id || !auth.refresh_token) {
    throw new Error("Reddit login required.");
  }
  if (auth.access_token && Number(auth.expires_at || 0) > Date.now() + 60_000) {
    return auth.access_token;
  }
  const response = await httpsJsonRequest("https://www.reddit.com/api/v1/access_token", {
    method: "POST",
    headers: {
      Authorization: redditBasicAuth(reddit.client_id, reddit.client_secret),
      "Content-Type": "application/x-www-form-urlencoded",
      "User-Agent": REDDIT_USER_AGENT,
    },
    body: formEncode({ grant_type: "refresh_token", refresh_token: auth.refresh_token }),
  });
  if (response.statusCode < 200 || response.statusCode > 299 || !response.data || response.data.error) {
    throw new Error(response.data?.error_description || response.data?.error || `Reddit token refresh failed with ${response.statusCode}.`);
  }
  auth.access_token = response.data.access_token;
  auth.expires_at = Date.now() + Math.max(60, Number(response.data.expires_in || 3600)) * 1000;
  auth.scope = response.data.scope || auth.scope || "";
  state.reddit.auth = auth;
  writeState(state);
  return auth.access_token;
}

async function redditApiRequest(state, apiPath) {
  const accessToken = await refreshRedditToken(state);
  const response = await httpsJsonRequest(`https://oauth.reddit.com${apiPath}`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "User-Agent": REDDIT_USER_AGENT,
    },
  });
  if (response.statusCode < 200 || response.statusCode > 299) {
    throw new Error(response.data?.message || response.data?.error || `Reddit API failed with ${response.statusCode}.`);
  }
  return response.data;
}

function decodeRedditUrl(value) {
  return String(value || "").replace(/&amp;/g, "&");
}

function firstHttpThumbnail(data = {}) {
  const thumbnail = decodeRedditUrl(data.thumbnail || "");
  if (/^https?:\/\//i.test(thumbnail)) return thumbnail;
  const image = data.preview && data.preview.images && data.preview.images[0];
  return image && image.source ? decodeRedditUrl(image.source.url || "") : "";
}

function redditImageFromPost(data = {}) {
  const direct = decodeRedditUrl(data.url_overridden_by_dest || data.url || "");
  if (/\.(jpe?g|png|gif|webp)(\?|$)/i.test(direct)) return direct;
  const image = data.preview && data.preview.images && data.preview.images[0];
  return image && image.source ? decodeRedditUrl(image.source.url || "") : "";
}

function redditVideoFromPost(data = {}) {
  const video = data.secure_media?.reddit_video || data.media?.reddit_video || data.preview?.reddit_video_preview;
  return video && video.fallback_url ? decodeRedditUrl(video.fallback_url) : "";
}

function redditGalleryImage(data = {}) {
  const metadata = data.media_metadata || {};
  for (const item of Object.values(metadata)) {
    if (item && item.status === "valid" && item.s && item.s.u) return decodeRedditUrl(item.s.u);
  }
  return "";
}

function normalizeRedditPost(post) {
  const data = post && post.data ? post.data : post;
  if (!data || data.stickied) return null;
  const permalink = data.permalink ? `https://www.reddit.com${data.permalink}` : decodeRedditUrl(data.url || "");
  const sourceUrl = decodeRedditUrl(data.url_overridden_by_dest || data.url || permalink);
  const thumb = firstHttpThumbnail(data);
  const videoUrl = redditVideoFromPost(data);
  const imageUrl = videoUrl ? "" : (redditImageFromPost(data) || redditGalleryImage(data));
  const mediaUrl = videoUrl || imageUrl;
  if (!mediaUrl) return null;
  const type = videoUrl ? "video" : "photo";
  return {
    source: "reddit",
    id: data.name || data.id || permalink,
    album: {
      source: "reddit",
      id: data.name || data.id || permalink,
      title: data.title || "Reddit post",
      url: permalink,
      source_url: sourceUrl,
      thumb,
      subreddit: data.subreddit_name_prefixed || (data.subreddit ? `r/${data.subreddit}` : ""),
      username: data.author ? `u/${data.author}` : "",
      is_nsfw: !!data.over_18,
    },
    media: {
      source: "reddit",
      type,
      url: mediaUrl,
      thumb_url: thumb,
      permalink,
      source_url: sourceUrl,
    },
  };
}

function normalizeRedditSearchQuery(value) {
  return String(value || "")
    .replace(/(^|\s)#(?=\S)/g, "$1")
    .replace(/[,;\n\r]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function redditFeedPathFromQuery(url) {
  const params = new URLSearchParams({
    limit: String(clampInt(url.searchParams.get("limit"), 12, 1, 50)),
    raw_json: "1",
  });
  const after = url.searchParams.get("after") || "";
  if (after) params.set("after", after);
  const kind = String(url.searchParams.get("kind") || "home").toLowerCase();
  if (kind === "subreddit") {
    const names = String(url.searchParams.get("subreddit") || "")
      .split(/[,+\s]+/)
      .map((name) => name.trim().replace(/^r\//i, ""))
      .filter(Boolean)
      .slice(0, 8);
    if (!names.length) throw new Error("Enter at least one subreddit for Reddit subreddit feed.");
    return `/r/${names.map(encodeURIComponent).join("+")}/hot?${params.toString()}`;
  }
  if (kind === "search") {
    const query = String(url.searchParams.get("query") || "").trim();
    if (!normalizeRedditSearchQuery(query)) throw new Error("Enter a Reddit search query.");
    params.set("q", normalizeRedditSearchQuery(query));
    params.set("sort", url.searchParams.get("sort") || "hot");
    params.set("t", url.searchParams.get("time") || "week");
    const subreddit = String(url.searchParams.get("subreddit") || "").trim().replace(/^r\//i, "");
    if (subreddit) return `/r/${encodeURIComponent(subreddit)}/search?restrict_sr=1&${params.toString()}`;
    return `/search?restrict_sr=0&${params.toString()}`;
  }
  if (kind === "new") return `/new?${params.toString()}`;
  if (kind === "hot") return `/hot?${params.toString()}`;
  return `/best?${params.toString()}`;
}

function getAlbumQueryOptions(url) {
  return {
    sort_by: url.searchParams.get("sort") || url.searchParams.get("sort_by") || "default",
    sort_dir: url.searchParams.get("dir") || url.searchParams.get("sort_dir") || "desc",
    hidden_only:
      getBool(url.searchParams.get("hidden"), false) || getBool(url.searchParams.get("hidden_only"), false),
    match_mode: url.searchParams.get("match_mode") || url.searchParams.get("mode") || "site",
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
      sendJson(res, 200, { ok: true, data: sanitizeState(readState()) });
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

    if (req.method === "GET" && path === "/api/reddit/status") {
      const state = readState();
      state.reddit.redirect_uri = redditRedirectUri(req);
      writeState(state);
      sendJson(res, 200, { ok: true, data: publicRedditStatus(state.reddit) });
      return;
    }

    if (req.method === "POST" && path === "/api/reddit/config") {
      const body = await parseBody(req);
      const state = readState();
      const clientId = String(body.client_id || body.clientId || "").trim();
      const clientSecret = String(body.client_secret || body.clientSecret || "").trim();
      if (!clientId) throw new Error("Reddit client ID is required.");
      const previousClientId = state.reddit.client_id;
      state.reddit.client_id = clientId;
      if (clientSecret) {
        state.reddit.client_secret = clientSecret;
      } else if (clientId !== previousClientId) {
        state.reddit.client_secret = "";
      }
      state.reddit.redirect_uri = redditRedirectUri(req);
      writeState(state);
      sendJson(res, 200, { ok: true, data: publicRedditStatus(state.reddit) });
      return;
    }

    if (req.method === "GET" && path === "/api/reddit/login") {
      const state = readState();
      const queryClientId = String(url.searchParams.get("client_id") || "").trim();
      if (queryClientId) state.reddit.client_id = queryClientId;
      if (!state.reddit.client_id) {
        sendPlainHtml(res, 400, "Reddit client ID required", "Enter a Reddit app client ID in EroTok before connecting Reddit.");
        return;
      }
      state.reddit.redirect_uri = redditRedirectUri(req);
      state.reddit.oauth_state = randomUUID();
      writeState(state);
      const authUrl = new URL("https://www.reddit.com/api/v1/authorize");
      authUrl.searchParams.set("client_id", state.reddit.client_id);
      authUrl.searchParams.set("response_type", "code");
      authUrl.searchParams.set("state", state.reddit.oauth_state);
      authUrl.searchParams.set("redirect_uri", state.reddit.redirect_uri);
      authUrl.searchParams.set("duration", "permanent");
      authUrl.searchParams.set("scope", "identity read mysubreddits history");
      sendRedirect(res, authUrl.href);
      return;
    }

    if (req.method === "GET" && path === "/api/reddit/callback") {
      const state = readState();
      const expectedState = state.reddit.oauth_state || "";
      const returnedState = url.searchParams.get("state") || "";
      const error = url.searchParams.get("error") || "";
      if (error) {
        sendPlainHtml(res, 400, "Reddit connection cancelled", `Reddit returned: ${error}`);
        return;
      }
      if (!expectedState || returnedState !== expectedState) {
        sendPlainHtml(res, 400, "Reddit state mismatch", "The Reddit OAuth state did not match. Start the connection again from EroTok.");
        return;
      }
      const code = url.searchParams.get("code") || "";
      if (!code) {
        sendPlainHtml(res, 400, "Reddit code missing", "Reddit did not return an OAuth code.");
        return;
      }
      try {
        const token = await exchangeRedditCode(state.reddit.client_id, state.reddit.client_secret, code, state.reddit.redirect_uri || redditRedirectUri(req));
        state.reddit.oauth_state = "";
        state.reddit.auth = {
          access_token: token.access_token,
          refresh_token: token.refresh_token,
          scope: token.scope || "",
          token_type: token.token_type || "bearer",
          expires_at: Date.now() + Math.max(60, Number(token.expires_in || 3600)) * 1000,
          username: "",
        };
        const me = await redditApiRequest(state, "/api/v1/me");
        state.reddit.auth.username = me && me.name ? me.name : "";
        writeState(state);
        sendPlainHtml(res, 200, "Reddit connected", `Connected ${state.reddit.auth.username || "your Reddit account"} to EroTok.`);
        return;
      } catch (callbackError) {
        sendPlainHtml(res, 500, "Reddit connection failed", String(callbackError.message || callbackError));
        return;
      }
    }

    if (req.method === "POST" && path === "/api/reddit/disconnect") {
      const state = readState();
      state.reddit.auth = null;
      state.reddit.oauth_state = "";
      writeState(state);
      sendJson(res, 200, { ok: true, data: publicRedditStatus(state.reddit) });
      return;
    }

    if (req.method === "GET" && path === "/api/reddit/feed") {
      const state = readState();
      if (!state.reddit.client_id) {
        sendJson(res, 400, { ok: false, error: "Reddit client ID required.", code: "reddit_not_configured" });
        return;
      }
      if (!state.reddit.auth || !state.reddit.auth.refresh_token) {
        sendJson(res, 401, { ok: false, error: "Reddit login required.", code: "reddit_login_required" });
        return;
      }
      let feedPath;
      try {
        feedPath = redditFeedPathFromQuery(url);
      } catch (feedError) {
        sendJson(res, 400, { ok: false, error: feedError.message || String(feedError) });
        return;
      }
      const listing = await redditApiRequest(state, feedPath);
      const children = Array.isArray(listing?.data?.children) ? listing.data.children : [];
      const items = children.map(normalizeRedditPost).filter(Boolean);
      sendJson(res, 200, {
        ok: true,
        data: {
          source: "reddit",
          authenticated: true,
          items,
          after: listing?.data?.after || "",
        },
      });
      return;
    }

    if (req.method === "GET" && path === "/api/albums/history") {
      sendJson(res, 200, { ok: true, data: readState().albums });
      return;
    }

    if (req.method === "POST" && path === "/api/albums/mark") {
      const body = await parseBody(req);
      const state = readState();
      const data = recordAlbumState(state, body);
      writeState(state);
      sendJson(res, 200, { ok: true, data });
      return;
    }

    if (req.method === "POST" && path === "/api/albums/clear-history") {
      const body = await parseBody(req);
      const state = readState();
      const bucket = String(body.bucket || "all").toLowerCase();
      if (bucket === "all") {
        state.albums = { seen: {}, skipped: {}, saved: {} };
      } else if (["seen", "skipped", "saved"].includes(bucket)) {
        state.albums[bucket] = {};
      } else {
        throw new Error("Album history bucket should be all, seen, skipped, or saved.");
      }
      sendJson(res, 200, { ok: true, data: writeState(state).albums });
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
        "GET /api/reddit/status",
        "POST /api/reddit/config",
        "GET /api/reddit/login",
        "GET /api/reddit/callback",
        "POST /api/reddit/disconnect",
        "GET /api/reddit/feed?kind=home&limit=12",
        "GET /api/albums/history",
        "POST /api/albums/mark",
        "POST /api/albums/clear-history",
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

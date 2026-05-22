# EroTok / EromeAPI

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Node](https://img.shields.io/badge/Node.js-local%20bridge-339933?style=for-the-badge&logo=node.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-optional%20APIs-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![UI](https://img.shields.io/badge/UI-EroTok%20Control%20Panel-22D3EE?style=for-the-badge)
![Scope](https://img.shields.io/badge/scope-public%20pages%20only-818CF8?style=for-the-badge)

EroTok is a local-first toolkit for exploring, previewing, indexing, watching, and archiving public media-gallery pages that you are allowed to access. The main app combines a Python scraping/API layer, a Node.js bridge server, a single-file browser control panel, local download jobs, album search history, Reddit and Twitter/X feed providers, watcher utilities, userscripts, and an optional generic FastAPI media-gallery scaffold.

The project is built for personal archiving, creator backups, public-page monitoring, local search, and automation. It does not log in to Erome, bypass access controls, generate fake engagement, upload files, edit posts, or interact with private account features.

## Responsible Use

Use this project only for public content that you own, created, or have permission to archive. Do not use it to bypass access controls, scrape private or restricted content, rehost other people's media, evade platform rules, or download content where you do not have rights.

This repository is public-page and local-first by design:

- No Erome login automation
- No private account access
- No upload, edit, comment, vote, or fake engagement actions
- No server-side public media hosting
- No payment, subscription, or paywall bypassing
- Reddit and Twitter/X support is read-only feed discovery

## What Is Included

| Area | Files | What It Does |
| --- | --- | --- |
| Root control panel | `server.js`, `ui.html`, `api.py`, `api_bridge.py` | Browser UI plus local JSON API for search, feeds, previews, downloads, state, and diagnostics |
| Erome/XXXErome API wrapper | `api.py` | Public explore, keyword search, hashtag matching, profile albums/reposts, album media, metadata, direct content, and downloads |
| Feed history | `server.js`, `ui.html`, `state.json` | Persistent seen, skipped, and saved album buckets with hide filters and clear buttons |
| Reddit feed | `server.js`, `ui.html` | Local OAuth, token refresh, home/hot/new/subreddit/search feed normalization, and mixed-feed rendering |
| Twitter/X feed | `server.js`, `ui.html` | Anonymous public-page attempt plus optional X API bearer-token mode |
| Watcher | `erome-watcher/`, `watcher_*.py`, `erome_mcp_server.py` | Public profile snapshots, diffs, alerts, SQLite history, local search index, REST API, MCP tools, and GUI |
| Userscripts | `userscript/erotok.user.js`, `userscript/profile-video-only.user.js` | Browser-side helper panels that delegate heavy work to the local app or filter profile cards |
| Generic API scaffold | `media-gallery-api-structure/` | FastAPI architecture spike for normalized gallery/profile/media adapters |
| Planning docs | `docs/superpowers/plans/`, `docs/superpowers/specs/` | Implementation plans and design notes for feed/search/player slices |

## Requirements

- Python 3.10 or newer
- Node.js 18 or newer
- A modern browser
- Optional: Reddit app client ID for Reddit feeds
- Optional: X API bearer token for reliable Twitter/X feeds
- Optional: Tampermonkey or Violentmonkey for userscripts

Install Python dependencies from the repository root:

```bash
python -m pip install -r requirements.txt
```

Recommended isolated setup:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Quick Start

Start the main local bridge from the project root, the folder that contains `server.js`:

```bash
node server.js
```

Open the control panel:

```text
http://127.0.0.1:3000/
```

Health check:

```text
http://127.0.0.1:3000/health
```

If the Node bridge cannot find the Python environment you installed dependencies into, set `PYTHON_BIN` before starting it:

```bash
PYTHON_BIN=.venv/bin/python node server.js
```

PowerShell equivalent:

```powershell
$env:PYTHON_BIN=".\.venv\Scripts\python.exe"
node server.js
```

Use a different host or port when needed:

```bash
HOST=127.0.0.1 PORT=3006 node server.js
```

PowerShell equivalent:

```powershell
$env:HOST="127.0.0.1"
$env:PORT="3006"
node server.js
```

## How Everything Fits Together

EroTok runs as a local app with a small set of cooperating pieces:

1. Your browser opens the UI from `http://127.0.0.1:3000/`.
2. `server.js` serves the UI, receives browser actions, stores local state, runs download jobs, proxies safe media requests, and exposes JSON endpoints.
3. For Erome and XXXErome page work, `server.js` calls `api_bridge.py` as a short-lived Python process.
4. `api_bridge.py` reads JSON from stdin, calls the correct `Api` method in `api.py`, then prints JSON back to Node.
5. `api.py` requests public pages, parses album/profile/search/media data, and downloads media when asked.
6. `state.json` stores local settings, form values, download history, album history, and Reddit OAuth metadata.
7. Optional subsystems add more surfaces: Reddit and Twitter/X feeds in `server.js`, watcher APIs under `erome-watcher/`, userscripts under `userscript/`, and the generic FastAPI scaffold under `media-gallery-api-structure/`.

Nothing has to be deployed to a public server. The normal workflow is local browser -> local Node bridge -> local Python API -> public pages you are allowed to access.

## First Run Checklist

Use this checklist when setting up a fresh copy:

1. Clone or open the repository.
2. Install Python dependencies with `python -m pip install -r requirements.txt`.
3. Start the local bridge with `node server.js`.
4. Open `http://127.0.0.1:3000/`.
5. Click `Health` or open `http://127.0.0.1:3000/health` to confirm the Node bridge is alive.
6. Click `Run Connectivity Diagnostics` to check public Erome reachability from your machine.
7. Set `Download Folder` if you want media saved somewhere other than `Downloads/`.
8. Choose `All`, `Photo`, or `Video` in the result tools to control previews and downloads.
9. Start with `Explore`, `Search`, or a known public profile before connecting optional Reddit or Twitter/X feeds.
10. Keep `state.json` private; it is ignored by git because it can contain local paths and OAuth metadata.

## Main Control Panel

The root page served from `ui.html` is the primary app. It exposes tabs for feed browsing, search, explore, profile lookup, version switching, album lookup, media preview, downloads, and diagnostics.

Common controls:

- Layout: auto, desktop, or phone-style view
- Hide terms: exclude visible albums by words, usernames, or hashtags
- Hide seen, skipped, or saved albums
- Clear seen, skipped, or saved history buckets
- Hashtag chips: combine typed and suggested hashtags
- Persisted form values in local `state.json`
- Watcher shortcut at `/watcher`

The app stores local UI settings, download history, album history, and Reddit connection metadata in `state.json`. That file is intentionally ignored by git because it can contain local paths and tokens.

### Main Control Panel Workflow

1. Start `node server.js` and open the root URL.
2. Use the global toolbar to set layout, hide filters, history filters, and hashtag chips.
3. Use the left tabs to choose a feature: Feed, Search, Explore, Profile, Version, Album, Media, Download, or Diagnostics.
4. Run an action. The raw JSON response appears in the output panel so you can inspect exactly what the backend returned.
5. When results include albums or media, the preview area renders cards and playable media using the same result data.
6. Use result tools to change download folder, media type, sort order, hidden-only behavior, preview, profile feed, or download actions.
7. Use `Copy JSON` when you want to reuse a response in tests, scripts, notes, or another tool.

The UI is intentionally both visual and inspectable. You can browse with the cards, but the underlying JSON stays visible so automation and debugging are easier.

## Feed Modes

Open the Feed tab and choose a feed network:

- `Erome only`: load public Erome or XXXErome albums through the Python API
- `XXXErome only`: force the XXXErome public site for Erome-style sources
- `Reddit only`: load normalized Reddit media posts from the connected Reddit account
- `Twitter/X only`: load Twitter/X media from anonymous public pages or X API v2
- `All`: combine Erome, Reddit, and Twitter/X batches while isolating provider errors

For Erome-style feeds, choose a source:

- `Explore`: public explore pages
- `Explore (New)`: public new explore pages
- `Search keyword`: keyword and hashtag search
- `Profile uploads`: public uploads for a username or profile URL
- `Profile reposts`: public reposts for a username or profile URL

Useful feed options:

- `Keyword match mode`: all keywords, any keyword, exact phrase, only this combo, or site default
- `Show`: all media, videos only, or photos only
- `Albums per batch`: how many album cards to fetch per feed page
- `Max items per album`: cap rendered media from each album
- `Auto-load ahead`: continue loading while scrolling
- `Fullscreen feed`: expand the feed surface
- `Start videos muted`: initial mute preference
- `Min video length`: skip short videos when duration metadata is available

Feed cards support open-source, seen, skip, save, download, and media preview actions. Videos use the custom YouTube-style local player with timeline, volume, speed, picture-in-picture, and fullscreen controls.

### Feed Step-By-Step

1. Choose `Feed` from the tab row.
2. Pick a network: Erome, XXXErome, Reddit, Twitter/X, or All.
3. If the network includes Erome-style sources, pick the source: Explore, Explore New, Search keyword, Profile uploads, or Profile reposts.
4. Enter search text, hashtags, or a profile username/URL depending on the chosen source.
5. Choose a keyword match mode when searching.
6. Pick `All`, `Videos only`, or `Photos only` in `Show`.
7. Set batch size and max items per album.
8. Enable or disable auto-load ahead depending on whether you want continuous scrolling.
9. Click `Start Feed`.
10. Scroll through the rendered feed cards.
11. Use card actions to open the source, preview media, save, skip, mark seen, or download.
12. Click `Reset` when changing major source settings so pagination and provider cursors start cleanly.

### How Feed Loading Works

For Erome-style feeds, the browser asks `server.js` for `/api/explore`, `/api/search`, `/api/profile`, or `/api/profile/reposts`. Node forwards those calls to `api_bridge.py`, which calls `api.py` and returns normalized album objects.

For Reddit feeds, Node talks to Reddit OAuth endpoints and normalizes media posts into the same feed-card shape used by Erome results. For Twitter/X feeds, Node either uses X API v2 when a bearer token is configured, or tries public X pages and reports a graceful unavailable response when X only returns its JavaScript shell.

The `All` feed mode requests more than one provider and merges what succeeds. A failure from Reddit or Twitter/X does not have to break Erome results, and an unavailable provider is shown as status text instead of crashing the feed.

### Feed Card Actions

- `Open`: opens the original album or provider source.
- `Seen`: records the album in the local seen bucket.
- `Skip`: records the album in the local skipped bucket and moves on.
- `Save`: records the album in the local saved bucket.
- `Download`: starts an asynchronous local album or media download job.
- Media controls: play, pause, seek, change volume, change speed, use picture-in-picture, or fullscreen.

History filters use the local album buckets. If `Hide skipped` is on, skipped cards disappear from future feed rendering until you clear or unskip them.

## Search Modes

The Search tab and feed search source both call the same backend search behavior through `match_mode`:

| Mode | Meaning |
| --- | --- |
| `site` | Use the site's broad search behavior, with extra hashtag filtering when hashtags are present |
| `all` | All plain keyword terms must match searchable album text |
| `any` | At least one plain keyword term must match |
| `exact` | The plain phrase must appear as written after normalization |
| `combo` | Plain terms and requested hashtags must match the same enriched album metadata |

Hashtag input supports simple tags, multi-word tags, commas, semicolons, and separate `#` markers:

```text
#redhair #outdoor
#alternative girl, #egirl
travel; beach; #cosplay
```

Selected hashtag chips are combined with typed search terms. When hashtag precision is needed, the backend enriches candidate albums with detail metadata before filtering.

### Search Step-By-Step

1. Open the Search tab for direct JSON search, or choose `Search keyword` in the Feed tab for card-based browsing.
2. Choose the site: Erome, XXXErome, or auto/default depending on the control.
3. Enter words, phrases, hashtags, or a combination.
4. Add hashtag chips when you want reusable tags across feed/search actions.
5. Choose `site`, `all`, `any`, `exact`, or `combo`.
6. Set page and limit for direct Search tab calls.
7. Click `Run Search` or `Start Feed`.
8. Inspect JSON output or browse rendered cards.
9. If results feel too broad, switch from `site` or `any` to `all`, `exact`, or `combo`.
10. If results feel too narrow, remove hide terms, clear history filters, reduce hashtags, or use `site` mode.

### How Matching Works

`site` mode uses the public site's own search endpoint first. When hashtags are present, EroTok can enrich returned albums with detail metadata and filter by real tags. `all`, `any`, `exact`, and `combo` run local matching against normalized album title, username, URL, tags, description, and metadata that the parser can see.

`combo` is the strictest mixed mode. It requires plain terms and requested hashtags to match the enriched album metadata, which is useful when a word appears in titles but you only want albums with the actual tag.

## Album History

Album history is local and stored in `state.json` under three buckets:

- `seen`: albums you already watched or marked seen
- `skipped`: albums you intentionally skipped
- `saved`: albums you want to keep visible as saved items

Use these from the UI or API:

```text
GET  /api/albums/history
POST /api/albums/mark
POST /api/albums/clear-history
```

Example mark request:

```json
{
  "album": { "url": "https://www.erome.com/a/RHoERFQP", "title": "Example" },
  "bucket": "seen",
  "marked": true
}
```

Clear one bucket or all buckets:

```json
{ "bucket": "seen" }
```

```json
{ "bucket": "all" }
```

### Album History Step-By-Step

1. Browse feed cards or preview results.
2. Mark albums as seen when you have already watched them.
3. Mark albums as skipped when you do not want them shown again in the current browsing style.
4. Mark albums as saved when you want to keep a local reminder.
5. Use `Hide seen`, `Hide skipped`, and `Hide saved` to decide which buckets are filtered out of the visible feed.
6. Use `Clear seen`, `Clear skipped`, or `Clear saved` when you want that bucket reset.
7. Use `/api/albums/history` to inspect the stored buckets from automation.

Album history is not the same as download history. Album history controls browsing visibility. Download history controls whether known downloaded media URLs are skipped during future download jobs.

## Downloads

The Download tab and feed buttons use local download endpoints. Downloads are written under the configured directory, defaulting to `Downloads/`, which is ignored by git.

Settings:

- `download_directory`: target folder
- `media_type`: all, photo, or video
- `skip_downloaded`: skip media URLs already recorded in local state
- `overwrite`: overwrite existing files when true
- `max_workers`: Python download worker count for album downloads

Synchronous endpoints:

```text
POST /api/download
POST /api/download/media
```

Asynchronous job endpoints used by the UI:

```text
POST /api/download/jobs
POST /api/download/media/jobs
GET  /api/download/jobs
GET  /api/download/jobs/<job-id>
```

Example album job body:

```json
{
  "path": "https://www.erome.com/a/RHoERFQP",
  "directory": "Downloads",
  "media_type": "all",
  "overwrite": false,
  "skip_downloaded": true,
  "max_workers": 4
}
```

Example single-media body:

```json
{
  "url": "https://example.com/media.mp4",
  "directory": "Downloads",
  "filename": "optional-name.mp4",
  "overwrite": false
}
```

### Download Step-By-Step From The UI

1. Set `Download Folder` in result tools or `Directory` in the Download tab.
2. Choose the media type: all, photo, or video.
3. Leave `Overwrite` false for normal archiving, or set it true when you want to force a fresh write.
4. For an album, enter an album slug or URL in the Download tab and click `Run Download`.
5. From a feed card, click the album download action to download that card's album.
6. From a previewed media item, click the single-media download action to save just that file.
7. Watch the status line for job progress, retry messages, item counts, and final state.
8. Inspect active jobs through the JSON output or `GET /api/download/jobs`.
9. If a media type filter returns no files, the UI can retry with photos plus videos for album downloads.
10. If a previous file is incomplete or stale, turn on `Overwrite` once to force a real replacement.

### How Download Jobs Work

The UI uses asynchronous job endpoints so the browser does not freeze while files are being written. Node creates a job record, starts `api_bridge.py`, and listens for newline-delimited progress events. Python reports `item_start`, `item_progress`, `retry`, and `item_done` events. Node stores the latest event list in memory so `/api/download/jobs/<job-id>` can show live progress.

Album downloads use `download_album_progress`; single-media downloads use `download_media_progress`. Both retry transient failures. Media is written through temporary `.part` files and moved into place only after the stream completes, so a failed stream should not leave a final filename that gets mistaken for a completed download.

Download history records successful media URLs in `state.json`. When `skip_downloaded` is true, future album downloads send known successful URLs to Python as `skip_urls`. Stale skipped or failed items are not treated as successful downloads. `overwrite` bypasses skip history for that request.

### Download Output Layout

Album files are saved under a readable folder name based on title, album slug, and username:

```text
Downloads/<Album Title> (<slug>) [<username>]/<Album Title> (1).jpg
Downloads/<Album Title> (<slug>) [<username>]/<Album Title> (2).mp4
```

Single-media downloads save directly under the chosen directory unless you provide a filename.

## Reddit Feed Setup

Reddit support is optional and read-only. It uses Reddit OAuth and stores tokens locally in `state.json`; `/api/state` redacts token values before returning state to the browser.

1. Create a Reddit app at `https://www.reddit.com/prefs/apps`.
2. Use an installed app client ID, or a web app client ID plus secret.
3. Start EroTok with `node server.js`.
4. Open `http://127.0.0.1:3000/`.
5. In the Feed tab, copy the displayed redirect URI.
6. Add that exact redirect URI to your Reddit app.
7. Enter the client ID, optionally enter the client secret, then click `Connect Reddit`.
8. Approve Reddit access in the opened tab.
9. Return to EroTok and click `Refresh Reddit`.

Reddit feed options:

- Home / best
- Home / hot
- Home / new
- Subreddit(s), including multiple names separated by spaces, commas, or plus signs
- Search, optionally restricted to a subreddit
- Sort options for search: hot, new, top, relevance
- Items per batch from 1 to 50

Reddit API routes:

```text
GET  /api/reddit/status
POST /api/reddit/config
GET  /api/reddit/login
GET  /api/reddit/callback
POST /api/reddit/disconnect
GET  /api/reddit/feed?kind=home|hot|new|subreddit|search&limit=12
```

### How Reddit Feeds Work

1. The browser saves your Reddit app client settings through `/api/reddit/config`.
2. `Connect Reddit` opens `/api/reddit/login`, which redirects to Reddit OAuth.
3. Reddit redirects back to `/api/reddit/callback` with an authorization code.
4. Node exchanges that code for access and refresh tokens.
5. Tokens are stored locally in `state.json`; `/api/state` and `/api/reddit/status` only return redacted status to the browser.
6. Feed requests refresh the access token when needed.
7. Reddit listing responses are normalized into EroTok feed items with album-like metadata and direct media URLs when available.

Use `Disconnect` to clear the stored Reddit auth from local state.

## Twitter/X Feed Setup

Twitter/X support works in two tiers:

1. With no token, EroTok tries anonymous public X pages for profile media or search pages. Public X often returns only the JavaScript app shell, so this can return a handled unavailable message with no items.
2. With an official X API bearer token, EroTok uses X API v2 for recent search or profile timeline media when your X API plan allows those endpoints.

Create and manage X API apps at:

```text
https://developer.x.com
```

Start with either bearer-token environment variable:

```bash
X_BEARER_TOKEN=your-x-api-bearer-token node server.js
```

```bash
TWITTER_BEARER_TOKEN=your-x-api-bearer-token node server.js
```

PowerShell equivalent:

```powershell
$env:X_BEARER_TOKEN="your-x-api-bearer-token"
node server.js
```

Optional X API base override:

```bash
X_API_BASE=https://api.twitter.com/2 node server.js
```

Twitter/X route:

```text
GET /api/twitter/feed?profile=@username&limit=12&after=<token>
GET /api/twitter/feed?query=has:media&limit=12&after=<token>
```

The route always returns JSON. API failures and anonymous app-shell failures are reported as provider-unavailable responses instead of crashing the server.

### How Twitter/X Feeds Work

1. If `X_BEARER_TOKEN` or `TWITTER_BEARER_TOKEN` is set, Node uses X API v2.
2. For profile mode, Node resolves the username to a user ID and requests recent tweets with media expansions.
3. For search mode, Node sends a recent-search query and adds `has:media` when needed.
4. X API media expansions are normalized into feed cards with media URLs, thumbnails, source links, and usernames.
5. If no bearer token is set, Node tries the public `x.com` profile/media or search page.
6. If public X returns only its app shell, the response is still `ok: true`, but the feed data is marked unavailable with a message.

Twitter/X support is best treated as optional. X API access depends on your token, plan, rate limits, and endpoint permissions.

## Node API Reference

The local bridge exposes JSON routes for the UI, userscripts, and automation:

```text
GET  /health
GET  /api/diagnostics
GET  /api/state
GET  /api/settings
POST /api/settings
GET  /api/downloaded
GET  /api/albums/history
POST /api/albums/mark
POST /api/albums/clear-history
GET  /api/search?keyword=&match_mode=all&page=1&limit=1&site=https://www.erome.com
GET  /api/hidden-search?keyword=&match_mode=all&page=1&limit=1
GET  /api/explore?page=1&limit=1&new=false
GET  /api/version?version=all
GET  /api/profile?profile=<username>&page=1&limit=1&content=albums|reposts
GET  /api/profile/reposts?profile=<username>&page=1&limit=1
GET  /api/album/content?path=RHoERFQP
GET  /api/album/info?path=RHoERFQP
GET  /api/album/metadata?path=RHoERFQP
GET  /api/content?url=<media-url>&maxVideoBytes=0&binary=true
GET  /proxy?url=<erome-media-url>
GET  /media?url=<erome-media-url>
POST /api/download
POST /api/download/jobs
GET  /api/download/jobs
GET  /api/download/jobs/<id>
POST /api/download/media
POST /api/download/media/jobs
GET  /api/reddit/status
POST /api/reddit/config
GET  /api/reddit/login
GET  /api/reddit/callback
POST /api/reddit/disconnect
GET  /api/reddit/feed?kind=home&limit=12
GET  /api/twitter/feed?query=has:media&limit=12
```

All JSON responses use an `ok` field. Successful bridge responses generally return data under `data`; errors return `ok: false` and an `error` message.

### Node API Usage Pattern

1. Start `node server.js`.
2. Call `GET /health` to confirm the server is up.
3. Use `GET` routes for read-only lookups and previews.
4. Use `POST` routes for settings, history marks, downloads, and watcher actions that create work.
5. For long downloads, prefer `/api/download/jobs` over synchronous `/api/download`.
6. Poll `/api/download/jobs/<id>` until `status` is `done` or `error`.
7. Treat `ok: false` as a request-level failure, and provider-specific `unavailable` messages as handled provider limitations.

The Node API is useful for userscripts, local automation, browser bookmarks, curl scripts, and any tool that can send HTTP requests to localhost.

## Python API Usage

Use `api.py` directly when you want Python automation without the Node bridge:

```python
from api import Api

api = Api()

albums = api.get_all_album_data(
    "#alternative girl, #egirl",
    page=1,
    limit=2,
    match_mode="combo",
    site_base="https://www.erome.com",
)

explore = api.get_explore(page=1, limit=2, new=False)
profile = api.get_profile_info("username", page=1, limit=0, content="albums")
reposts = api.get_profile_reposts("username", page=1, limit=2)
album = api.get_album_info("https://www.erome.com/a/RHoERFQP")
metadata = api.get_album_metadata("RHoERFQP")
content = api.get_album_content("RHoERFQP")

downloaded = api.download_album(
    "RHoERFQP",
    directory="Downloads",
    include_photos=True,
    include_videos=True,
    overwrite=False,
    max_workers=4,
)
```

Important public methods:

- `get_all_album_data(keyword, page, limit, sort_by, sort_dir, hidden_only, match_mode, site_base)`
- `get_explore(page, limit, new, sort_by, sort_dir, hidden_only, site_base)`
- `get_profile_info(profile, page, limit, sort_by, sort_dir, hidden_only, content, site_base)`
- `get_profile_reposts(profile, page, limit, sort_by, sort_dir, hidden_only, site_base)`
- `get_album_content(path)`
- `get_album_info(path)`
- `get_album_metadata(path)`
- `get_content(url, max_video_bytes=0)`
- `download_album(path, directory, include_photos, include_videos, overwrite, max_workers, skip_urls, retry_until_done, retry_delay)`
- `download_media(url, directory, filename, overwrite, retry_until_done, retry_delay)`

### Python API Step-By-Step

1. Import `Api` from `api.py`.
2. Create one `Api()` instance per script or workflow.
3. Use `get_explore`, `get_all_album_data`, or `get_profile_info` to discover public albums.
4. Use `get_album_info` when you need title, username, slug, and ordered media URLs.
5. Use `get_album_metadata` when you need counts, tags, likes, views, and durations where the public page exposes them.
6. Use `get_content` for direct media bytes.
7. Use `download_album` for full album archiving.
8. Use `download_media` for one media URL.
9. Pass a `progress_callback` when you want progress events in your own script.
10. Use `retry_until_done=True` only when you intentionally want a download to keep retrying until it succeeds or the process is stopped.

The Python layer validates input types, normalizes supported Erome/XXXErome and Reddit media URLs, sanitizes filenames, writes safe sequential album filenames, and closes streamed HTTP responses after each media request.

## API Bridge Usage

`api_bridge.py` is a JSON-over-stdin wrapper used by `server.js`. You can also call it directly:

```bash
echo '{"keyword":"#redhair","page":1,"limit":1,"match_mode":"all"}' | python api_bridge.py search
```

Methods accepted by the bridge:

```text
search
explore
album_content
album_info
album_metadata
profile
profile_reposts
version
download_album
download_album_progress
download_media
download_media_progress
content
diagnostics
watcher_*
```

Progress methods print newline-delimited `{"progress": ...}` events before the final JSON result.

### Bridge Message Shape

Normal bridge calls receive one JSON object on stdin and print one JSON object on stdout:

```json
{ "ok": true, "data": [] }
```

Progress bridge calls print progress lines first, then a final result:

```json
{ "progress": { "event": "item_start", "percent": 0 } }
{ "progress": { "event": "item_progress", "percent": 45 } }
{ "ok": true, "data": [] }
```

This is why `server.js` can show live download progress while still treating the final line as the completed job result.

## Watcher Tools

Watcher features operate on public pages that you explicitly inspect or index. They store snapshots and search metadata locally in SQLite.

### Integrated Watcher Through Node

Start the main bridge:

```bash
node server.js
```

Open:

```text
http://127.0.0.1:3000/watcher
```

If the packaged watcher dashboard is missing, build it:

```bash
cd erome-watcher/gui
npm install
npm run build
cd ../..
node server.js
```

Integrated watcher routes:

```text
GET  /api/watcher/health
GET  /api/watcher/profile/<username>
GET  /api/watcher/profile/<username>/diff
GET  /api/watcher/profile/<username>/history?limit=20
POST /api/watcher/watch
POST /api/watcher/watch/alert
GET  /api/watcher/album?url=https://www.erome.com/a/...
POST /api/watcher/download
POST /api/watcher/download/jobs
GET  /api/watcher/download/jobs/<id>
GET  /api/watcher/index/stats
POST /api/watcher/index/profile
POST /api/watcher/index/explore
POST /api/watcher/index/rebuild
GET  /api/watcher/search?query=&limit=20
GET  /api/watcher/search/live?query=&page=1
```

### Standalone Watcher API

From the repository root:

```bash
python watcher_api_server.py
```

Default URL:

```text
http://127.0.0.1:8011/
```

From the standalone watcher package:

```bash
cd erome-watcher
python -m pip install -r requirements.txt
uvicorn api_server:app --host 127.0.0.1 --port 8011
```

Standalone routes include:

```text
GET  /health
GET  /profile/{username}
GET  /profile/{username}/diff
GET  /profile/{username}/history
POST /watch
POST /watch/alert
GET  /album?url=https://www.erome.com/a/...
GET  /index/stats
POST /index/profile
POST /index/explore
POST /index/rebuild
GET  /search?query=...&limit=20
GET  /search/live?query=...&page=1
```

### CLI, MCP, and Hermes Helpers

Run a profile check from the root project:

```bash
python watch_profile.py SOME_USERNAME --format summary
python watch_profile.py SOME_USERNAME --format telegram
python watch_profile.py SOME_USERNAME --format discord
```

Run the MCP server:

```bash
python erome_mcp_server.py
```

Post an alert payload to a Hermes webhook:

```bash
python post_alert_to_hermes.py YOUR_WEBHOOK_URL SOME_USERNAME
```

The `erome-watcher/examples/` folder contains sample MCP config, webhook config, and cron prompt files.

### Watcher Step-By-Step

1. Start either the integrated Node bridge or the standalone watcher API.
2. Fetch a public profile snapshot with `/api/watcher/profile/<username>` or `/profile/{username}`.
3. Run a diff with `/diff` to compare the newest public snapshot with stored history.
4. Use `/watch` to update stored state for a profile.
5. Use `/watch/alert` when you want a formatted alert payload for new or changed public albums.
6. Use `/index/profile`, `/index/explore`, or `/index/rebuild` to populate the local search index.
7. Use `/search` for indexed local search and `/search/live` for live public search.
8. Use watcher download routes when you want watcher-driven downloads to reuse the same main API downloader.

The watcher is for repeated public-page monitoring. It is separate from album history: watcher state tracks snapshots and index data, while the root UI album history tracks seen, skipped, and saved browsing buckets.

## Userscripts

Install userscripts with Tampermonkey, Violentmonkey, or another compatible manager.

### EroTok Mini

File:

```text
userscript/erotok.user.js
```

Required flow:

```bash
git clone https://github.com/insomniakin/EromeAPI-main.git
cd EromeAPI-main
python -m pip install -r requirements.txt
node server.js
```

Then browse to a public `https://www.erome.com/*` page. The panel appears in the lower-right corner and talks to `http://127.0.0.1:3000`.

What it can do:

- Search public albums through the local bridge
- Load Explore results
- Load the current public profile
- Download the current public album through the local bridge
- Use suggested hashtag chips and multi-word hashtag parsing
- Apply hide-term filtering to displayed results
- Persist mini-panel settings with userscript storage
- Open the full local app

For a listing-ready description, screenshots, QR details, and install text, use `SLEAZYFORK_README.md`.

### Profile Videos Only

File:

```text
userscript/profile-video-only.user.js
```

This script adds a small toolbar on Erome and XXXErome profile/post pages. It can toggle visible cards to likely video posts only, refresh the scan, and persist the toggle in browser local storage. It does not call the local bridge and does not download media.

### Userscript Step-By-Step

1. Install Tampermonkey, Violentmonkey, or a compatible userscript manager.
2. Install the desired script from `userscript/`.
3. Start `node server.js` if the script needs the local bridge.
4. Open a public supported page in your browser.
5. Use the injected panel or toolbar on that page.
6. For EroTok Mini, keep the local app running because search, explore, profile, and download actions call `http://127.0.0.1:3000`.
7. For Profile Videos Only, no local server is needed because filtering runs entirely in the page.

Userscripts are convenience layers. The actual heavy work still belongs to the local Node/Python app unless the script explicitly says it is page-only.

## Generic Media Gallery API Scaffold

`media-gallery-api-structure/` is a separate FastAPI scaffold for a generic public media-gallery API. It is an architecture spike, not a site-specific scraper.

Run it:

```bash
cd media-gallery-api-structure
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn api_server:app --reload --port 8015
```

PowerShell activation:

```powershell
cd media-gallery-api-structure
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn api_server:app --reload --port 8015
```

Open:

```text
http://127.0.0.1:8015/docs
```

Endpoints:

```text
GET /health
GET /sources
GET /resolve?url=...
GET /profile?url=...
GET /gallery?url=...
```

Important files:

- `media_gallery_api/models/schemas.py`: normalized response models
- `media_gallery_api/core/interfaces.py`: adapter contracts
- `media_gallery_api/core/service.py`: orchestration layer
- `media_gallery_api/adapters/base.py`: shared adapter helpers
- `media_gallery_api/adapters/example_public_gallery.py`: safe example adapter stub
- `API_DESIGN.md`: endpoint and response-envelope design

Add site-specific parsing only by creating a new adapter under `media_gallery_api/adapters/` and keeping raw selectors isolated there.

### Scaffold Step-By-Step

1. Start the scaffold API on a separate port such as `8015`.
2. Open `/docs` to inspect the generated FastAPI documentation.
3. Call `/sources` to list available adapter IDs.
4. Call `/resolve?url=...` to see which adapter can handle a URL.
5. Call `/profile?url=...` or `/gallery?url=...` to receive normalized response envelopes.
6. Add new adapters by implementing the shared interfaces in `media_gallery_api/core/interfaces.py`.
7. Keep parser-specific selectors inside the adapter so the service and response models stay reusable.

This scaffold is useful when you want to experiment with a cleaner multi-source API shape without changing the root EroTok app.

## Screenshots And Assets

Screenshots used by the README and listing docs live under `docs/screenshots/`:

```text
docs/screenshots/erotok-control-panel.png
docs/screenshots/erotok-controls.png
```

The root UI can display the optional support QR asset:

```text
app/assets/cashapp-qr.jpg
```

## Development Docs

Implementation plans and design specs live under `docs/superpowers/`:

```text
docs/superpowers/plans/2026-05-18-search-history-feed.md
docs/superpowers/plans/2026-05-18-reddit-feed-integration.md
docs/superpowers/plans/2026-05-20-root-video-player-twitter-access.md
docs/superpowers/plans/2026-05-20-twitter-x-all-feed.md
docs/superpowers/specs/2026-05-18-reddit-custom-feeds-design.md
docs/superpowers/specs/2026-05-20-root-video-player-twitter-access-design.md
docs/superpowers/specs/2026-05-20-twitter-x-all-feed-design.md
```

These docs are useful for future feature work, but they are not required to run the app.

## Testing And Verification

Run the pytest suite:

```bash
python -m pytest -q
```

Run through unittest discovery:

```bash
python -m unittest discover -s tests -v
```

Syntax checks:

```bash
python -m py_compile api.py api_bridge.py watcher_api_server.py watcher_bridge.py watcher_runtime.py
node --check server.js
```

FastAPI scaffold smoke test:

```bash
cd media-gallery-api-structure
python -m py_compile api_server.py media_gallery_api/adapters/base.py media_gallery_api/adapters/example_public_gallery.py media_gallery_api/core/interfaces.py media_gallery_api/core/service.py media_gallery_api/models/schemas.py
```

Runtime smoke checks after starting `node server.js`:

```text
GET http://127.0.0.1:3000/health
GET http://127.0.0.1:3000/api/state
GET http://127.0.0.1:3000/api/reddit/status
GET http://127.0.0.1:3000/api/twitter/feed?query=has%3Amedia&limit=1
```

## Project Structure

```text
api.py                         Python public-page API wrapper
api_bridge.py                  JSON bridge used by the Node server
server.js                      Local Node server, GUI host, proxy, jobs, Reddit/Twitter, watcher routes
ui.html                        EroTok browser control panel
app/                           Static assets served by the Node bridge
userscript/                    Tampermonkey/Violentmonkey helper scripts
erome-watcher/                 Watcher package, REST API, MCP server, examples, and GUI source
media-gallery-api-structure/   Generic FastAPI media-gallery API scaffold
docs/screenshots/              README and listing screenshots
docs/superpowers/              Plans and design specs
tests/                         Python pytest/unittest coverage
SLEAZYFORK_README.md           Listing-ready userscript copy
```

## Public Repository Safety

The `.gitignore` excludes local runtime files and downloaded media:

- `Downloads/` and `downloads/`
- `state.json`
- SQLite databases and `erome-watcher/state/`
- Python caches and virtual environments
- Node `node_modules/`
- local output files such as `output.txt`, `results.txt`, and test output files
- captured third-party album HTML fixtures such as `erome_album.html`

Before publishing, check:

```bash
git status --short
```

Make sure no private media, credentials, local state, cookies, OAuth tokens, bearer tokens, personal downloads, or captured third-party pages are staged.

## Troubleshooting

If `node server.js` starts but API calls fail with missing Python packages, set `PYTHON_BIN` to the Python executable inside your virtual environment and restart the server.

If a Reddit connection fails, refresh `/api/reddit/status`, confirm the redirect URI in the UI exactly matches the Reddit app settings, then reconnect.

If Twitter/X returns no items, check the route response message. Anonymous public pages often return an app shell with no media URLs; reliable results usually require an X API bearer token and plan access to the requested endpoints.

If profile or search results are empty, try the other public site option (`https://www.erome.com` or `https://xxxerome.com`), reduce filters, clear seen/skipped history, and verify the source page is public in a browser.

If downloads skip something you expected to retry, turn on `Overwrite` for that run or remove the existing file from the target folder. Successful downloads are remembered by URL; incomplete `.part` files are temporary and can be safely removed if a process is interrupted.

If the feed hides too much, clear hide terms and turn off `Hide seen`, `Hide skipped`, and `Hide saved` while testing. History filters are local convenience filters, not provider-side filters.

If the watcher dashboard says it is not built, run `cd erome-watcher/gui && npm install && npm run build`, then restart or reload the Node server.

## License

See `LICENSE`.

## Disclaimer

This is an unofficial local tool for public pages. Erome, Reddit, and X/Twitter can change their public HTML, APIs, rate limits, and access rules at any time. Use responsibly, respect creator rights, and follow all applicable laws and platform terms.

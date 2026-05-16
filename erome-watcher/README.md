# Erome Watcher

This project scaffolds all three paths discussed:
- a custom MCP server for Hermes
- a custom REST API with FastAPI
- a polling watcher script suitable for Hermes cron or external automation

Important:
- This is a scraper-based watcher, not an official Erome API.
- Site HTML can change and break selectors.
- Use responsibly, respect rate limits, and review site terms before production use.
- The search/index features in this project operate on public content you explicitly crawl or index; they do not bypass private, hidden, or access-controlled content.

## Files

- `erome_watcher/client.py` — fetch and parse profile/album pages
- `erome_watcher/models.py` — normalized data models
- `erome_watcher/diffing.py` — snapshot diff logic
- `erome_watcher/state.py` — compatibility wrapper around state storage
- `erome_watcher/sqlite_state.py` — SQLite-backed history and snapshot store
- `erome_watcher/alerts.py` — Telegram/Discord-ready alert text formatting
- `erome_mcp_server.py` — MCP server exposing Hermes-callable tools
- `api_server.py` — FastAPI REST service
- `watch_profile.py` — simple CLI polling helper
- `post_alert_to_hermes.py` — pushes formatted alert payloads to Hermes webhooks
- `gui/` — React + Tailwind control-room UI for local search, indexing, and watcher actions
- `examples/` — Hermes config snippets and automation examples

## Install

```bash
cd /home/insomniakin/.hermes/hermes-agent/spikes/erome-watcher
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Quick usage

### 1. Test profile watcher from CLI

```bash
python3 watch_profile.py SOME_USERNAME
python3 watch_profile.py SOME_USERNAME --format telegram
python3 watch_profile.py SOME_USERNAME --format discord
```

This stores history in:
- `state/erome_state.sqlite3`

### 2. Run the REST API

```bash
uvicorn api_server:app --host 127.0.0.1 --port 8011
```

### 2b. Run the React + Tailwind GUI

```bash
cd gui
npm install
npm run dev
```

Then open the local Vite URL shown in the terminal (default: `http://127.0.0.1:4174`).
The GUI defaults to API base `http://127.0.0.1:8011`, but you can change it from the header input.

### 2c. Package the GUI into the FastAPI server

```bash
cd gui
npm run build
cd ..
uvicorn api_server:app --host 127.0.0.1 --port 8011
```

After building, FastAPI serves the packaged dashboard directly at:
- `http://127.0.0.1:8011/`

Endpoints:
- `GET /health`
- `GET /profile/{username}`
- `GET /profile/{username}/diff`
- `GET /profile/{username}/history`
- `POST /watch` with JSON `{ "username": "...", "persist": true }`
- `POST /watch/alert` with JSON `{ "username": "...", "persist": true }`
- `GET /album?url=https://www.erome.com/a/...`
- `GET /index/stats`
- `POST /index/profile` with JSON `{ "username": "..." }`
- `POST /index/explore` with JSON `{ "page": 1, "persist_snapshot": true }`
- `POST /index/rebuild` with JSON `{ "usernames": ["..."] }` or `{}`
- `GET /search?query=...&limit=20`
- `GET /search?username=USERNAME&query=...`
- `GET /search?query=...&sort_by=relevance|recent|views|title&source=profile|explore|search&min_views=3000`
- `GET /search/live?query=...&page=1`

### 3. Run the MCP server directly

```bash
python3 erome_mcp_server.py
```

Exposed tools:
- `get_profile_snapshot(username)`
- `get_album_snapshot(album_url)`
- `diff_profile(username, persist=True)`
- `format_profile_alert(username, persist=True)`
- `get_profile_history(username, limit=20)`

## Hermes integration

### A. Native MCP

Add the contents of `examples/hermes-config.mcp.yaml` into `~/.hermes/config.yaml`, adjusting the absolute path.

Then restart Hermes. The MCP tools should appear with names like:
- `mcp_erome_watcher_get_profile_snapshot`
- `mcp_erome_watcher_get_album_snapshot`
- `mcp_erome_watcher_diff_profile`
- `mcp_erome_watcher_format_profile_alert`
- `mcp_erome_watcher_get_profile_history`

### B. Hermes cron polling

Once MCP is configured, create a cron job that periodically checks watched users.

See:
- `examples/cron-prompt.txt`

Suggested behavior:
- call `mcp_erome_watcher_format_profile_alert`
- if counts changed, emit `telegram_text` or `discord_text`
- if no changes, stay quiet or send a short no-change note

### C. External webhook path

If you want your own external service to decide when something changed, run `api_server.py` and have your service POST to Hermes webhooks.

Hermes webhook setup references:
- `examples/hermes-config.webhook.yaml`
- `examples/webhook-subscribe.sh`

Example flow:
1. run `api_server.py`
2. create a Hermes webhook subscription
3. run:

```bash
python3 post_alert_to_hermes.py YOUR_WEBHOOK_URL SOME_USERNAME
```

That script:
- asks the watcher API for `/watch/alert`
- posts the resulting payload to the Hermes webhook

## Recommended architecture

For Hermes-first use:
- run `erome_mcp_server.py`
- configure it in Hermes MCP
- use Hermes cron for polling and alerts

For general API use outside Hermes too:
- run `api_server.py`
- optionally add Hermes webhooks on top
- use `/index/*` to build a local searchable index from known public profiles or explore pages
- use `/search` for fast local search over indexed public metadata
- use `/search/live` sparingly because repeated live scraping can trigger rate limits
- use `gui/` for an operator-friendly control room over search, indexing, and watcher actions
- packaged mode serves the compiled GUI directly from FastAPI on port 8011 after `npm run build`

## Notes about parser assumptions

Light live inspection showed:
- `/explore` contains album cards with classes like `album`, `album-link`, `album-title`, `album-user`
- profile pages can be addressed as `/{username}?t=posts`
- album pages are under `/a/<id>`
- album pages may contain many `img[src]` items and not always explicit `video source[src]`

The parser now prefers:
- `a.album-link[href]` and `a[href*="/a/"]` for profile album extraction
- `.album-title`, `.album-user`, `.album-bottom-views` where present
- media URLs from `video`, `source`, `img`, and direct media-like links

You should still test against your target usernames/albums and tune selectors if needed.

## Next practical steps

1. Install requirements
2. Run `python3 watch_profile.py SOME_USERNAME --format summary`
3. Inspect `state/erome_state.sqlite3`
4. Run the API or MCP server
5. Wire Hermes MCP and cron
6. Add your real delivery target (Telegram/Discord/webhook)

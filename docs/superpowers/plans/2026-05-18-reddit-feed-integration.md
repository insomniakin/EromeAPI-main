# Reddit Feed Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add authenticated Reddit as an optional feed provider inside the existing EroTok local app while preserving the current Erome-only workflow.

**Architecture:** Keep EroTok's Node/Python bridge as the main app. Add local Reddit OAuth and Reddit feed endpoints to `server.js`, transform Reddit listing posts into the same `{ album, media }` shape used by the vertical feed, and extend `ui.html` with Erome/Reddit/Both source controls. Store Reddit tokens locally in `state.json`, but never expose tokens through `/api/state` or UI status responses.

**Tech Stack:** Node.js built-in `http`/`https`, Reddit OAuth, existing static `ui.html`, Python unittest source checks.

---

### Task 1: Add Reddit State And OAuth Routes

**Files:**
- Modify: `server.js`
- Test: `tests/test_watcher_gui_source.py`

- [ ] Add failing source checks for `reddit: {`, `sanitizeState`, `/api/reddit/login`, `/api/reddit/callback`, `/api/reddit/status`, and `/api/reddit/disconnect`.
- [ ] Run `python -m unittest tests.test_watcher_gui_source.WatcherGuiSourceTests.test_server_has_reddit_oauth_routes -v`; expect failure because routes are missing.
- [ ] Extend `DEFAULT_STATE` with `reddit: { client_id: "", auth: null, oauth_state: "" }`.
- [ ] Add `sanitizeState(state)` that removes `state.reddit.auth.access_token`, `refresh_token`, and `oauth_state` before `/api/state` returns data.
- [ ] Add local OAuth endpoints:
  - `GET /api/reddit/status`
  - `POST /api/reddit/config`
  - `GET /api/reddit/login`
  - `GET /api/reddit/callback`
  - `POST /api/reddit/disconnect`
- [ ] Exchange OAuth code using Reddit installed-app auth with the configured client ID and blank secret.

### Task 2: Add Reddit Feed Endpoint

**Files:**
- Modify: `server.js`
- Test: `tests/test_watcher_gui_source.py`

- [ ] Add failing source checks for `normalizeRedditPost`, `/api/reddit/feed`, `oauth.reddit.com`, and `reddit_video`.
- [ ] Run the focused source test and confirm it fails.
- [ ] Implement token refresh before Reddit API requests.
- [ ] Implement `normalizeRedditPost(post)` returning `{ source: "reddit", album, media }` for Reddit-hosted images and videos.
- [ ] Implement `GET /api/reddit/feed?kind=home|subreddit|search&subreddit=&query=&after=&limit=`.
- [ ] Return `{ items, after, authenticated }` without leaking tokens.

### Task 3: Extend The EroTok Feed UI

**Files:**
- Modify: `ui.html`
- Test: `tests/test_watcher_gui_source.py`

- [ ] Add failing source checks for `feedNetwork`, `redditConnect`, `redditDisconnect`, `fetchRedditFeedBatch`, `appendRedditFeedItems`, and `appendMixedFeedItems`.
- [ ] Run the focused source test and confirm it fails.
- [ ] Add a compact Reddit account panel with client ID input, connect/disconnect buttons, and status text.
- [ ] Add feed network selector: `Erome only`, `Reddit only`, `Both`.
- [ ] Add Reddit feed controls: kind, subreddit, query, and items per batch.
- [ ] Keep Erome source controls intact and default to `Erome only`.
- [ ] Add frontend functions to call `/api/reddit/status`, `/api/reddit/config`, `/api/reddit/login`, `/api/reddit/disconnect`, and `/api/reddit/feed`.
- [ ] Render Reddit items using the same vertical feed surface with Reddit-safe actions: open source, seen, skip, save.

### Task 4: Verify And Run

**Files:**
- Modify: none unless verification finds defects.

- [ ] Run `python -m unittest discover -s tests -v`; expect all tests passing.
- [ ] Run `node --check server.js`; expect no syntax errors.
- [ ] Start the worktree server on port `3006` with `PORT=3006 node server.js`.
- [ ] Smoke `GET /health`, `GET /api/reddit/status`, and root HTML checks for new controls.
- [ ] Confirm existing Erome `match_mode=all` search still returns handled JSON.

---

Self-review: This plan covers Reddit OAuth, token redaction, Reddit-only and mixed feed modes, Scrolller-inspired source controls, tests, and local server verification. It deliberately excludes Reddit password capture, browser-cookie reuse, Devvit replacement, and Erome login automation.
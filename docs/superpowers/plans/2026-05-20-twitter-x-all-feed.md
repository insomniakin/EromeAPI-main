# Twitter/X And All Feed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `Twitter/X only` and `All` feed modes, where `All` combines Erome, Reddit, and Twitter/X while tolerating optional provider availability.

**Architecture:** Keep the current root `server.js` and `ui.html` architecture. Add a Twitter/X provider route returning normalized feed items, then wire the UI network selector and mixed-feed loader to use Erome, Reddit, and Twitter/X batches together.

**Tech Stack:** Node `http` server, browser JavaScript in `ui.html`, Python `pytest` source/contract tests.

---

### Task 1: Contract Tests

**Files:**
- Modify: `tests/test_watcher_gui_source.py`

- [ ] Add a failing source test for the Twitter/X and All UI/provider contract:

```python
def test_root_feed_has_twitter_and_all_network_modes(self):
    source = Path("ui.html").read_text(encoding="utf-8")
    server = Path("server.js").read_text(encoding="utf-8")

    self.assertIn('value="twitter"', source)
    self.assertIn('Twitter/X only', source)
    self.assertIn('value="all"', source)
    self.assertIn('>All<', source)
    self.assertIn("function fetchTwitterFeedBatch", source)
    self.assertIn("function appendExternalFeedItems", source)
    self.assertIn("network === 'all'", source)
    self.assertIn("fetchTwitterFeedBatch()", source)
    self.assertIn('path === "/api/twitter/feed"', server)
    self.assertIn('function normalizeTwitterPost', server)
```

- [ ] Run `python -m pytest tests/test_watcher_gui_source.py -q` and confirm the new test fails because Twitter/X is not implemented yet.

### Task 2: Server Twitter/X Provider

**Files:**
- Modify: `server.js`

- [ ] Add `TWITTER_USER_AGENT`, URL decode helpers, `normalizeTwitterPost`, and `twitterPublicFeedFromQuery` near the Reddit feed helpers.
- [ ] Implement `GET /api/twitter/feed` so it returns `{ ok: true, data: { source: "twitter", authenticated: false, unavailable, items, after: "" } }`.
- [ ] In anonymous mode, fetch a public `x.com/search` or profile page and extract representative media URLs when available.
- [ ] If public access fails or no parseable media exists, return a handled empty result with `unavailable: true` and a message instead of throwing.

### Task 3: UI Feed Wiring

**Files:**
- Modify: `ui.html`

- [ ] Add `Twitter/X only` and `All` to the feed network selector.
- [ ] Preserve saved legacy `both` values by treating them like `all` in JavaScript.
- [ ] Add Twitter/X query and item-count controls to persisted `FORM_SETTING_IDS`.
- [ ] Add `fetchTwitterFeedBatch()` and a shared `appendExternalFeedItems()` used by Reddit and Twitter/X.
- [ ] Update `loadMoreFeed()` so `twitter` fetches Twitter/X only and `all` fetches Erome, Reddit, and Twitter/X in parallel.
- [ ] Isolate Reddit/Twitter provider errors in `all` mode so successful providers still render.
- [ ] Update empty-state text to mention Twitter/X unavailable or filtered states.

### Task 4: Verification

**Files:**
- No additional file edits.

- [ ] Run `python -m pytest tests/test_watcher_gui_source.py -q` and confirm the focused tests pass.
- [ ] Run `python -m pytest -q` and confirm the full suite passes.
- [ ] Restart the local server and verify `/health` responds.
- [ ] Verify `/api/twitter/feed` returns handled JSON, not a crash.
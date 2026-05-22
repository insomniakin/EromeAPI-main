# Search History Feed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore accurate keyword/hashtag search modes and add persistent seen/skipped/saved album controls without changing the stable running checkout.

**Architecture:** Keep the root Node bridge and single-file `ui.html` structure. Add search-mode semantics in the Python API so CLI, Node routes, and UI share one behavior. Store album history in `state.json` through new Node state endpoints, and let the UI filter/mark albums using those endpoints.

**Tech Stack:** Python `unittest`, BeautifulSoup scraping layer, Node `http` bridge, local JSON state, browser JavaScript in `ui.html`.

---

### Task 1: Search Mode Backend

**Files:**
- Modify: `api.py`
- Modify: `api_bridge.py`
- Test: `tests/test_api.py`

- [ ] Add failing tests for `match_mode="exact"`, `match_mode="any"`, `match_mode="all"`, and `match_mode="combo"` using fake search/detail HTML.
- [ ] Run `python -m unittest tests.test_api.ApiTests.test_search_match_modes_filter_plain_keywords -v` and confirm it fails because `match_mode` is not accepted.
- [ ] Add parsing helpers in `Api` for plain keyword terms, album searchable text, hashtag metadata matching, and mode filtering.
- [ ] Extend `Api.get_all_album_data(..., match_mode="all")` and pass `match_mode` through `api_bridge.py`.
- [ ] Run `python -m unittest tests.test_api.ApiTests.test_search_match_modes_filter_plain_keywords tests.test_api.ApiTests.test_combo_match_requires_only_requested_metadata_tags -v` and confirm both pass.

### Task 2: State Endpoints For Album History

**Files:**
- Modify: `server.js`
- Test: `tests/test_watcher_gui_source.py`

- [ ] Add failing source tests proving `seen_albums`, `skipped_albums`, `/api/albums/mark`, and `/api/albums/clear-history` exist.
- [ ] Extend `DEFAULT_STATE` and `normalizeState` with `albums.seen`, `albums.skipped`, and `albums.saved` maps.
- [ ] Add `normalizeAlbumKey`, `recordAlbumState`, and JSON endpoints to mark, unmark, and clear album history.
- [ ] Run `python -m unittest tests.test_watcher_gui_source.WatcherGuiSourceTests.test_root_ui_has_persistent_album_history_controls -v` and confirm it passes.

### Task 3: Root UI Search And History Controls

**Files:**
- Modify: `ui.html`
- Test: `tests/test_watcher_gui_source.py`

- [ ] Add failing source tests for `searchMatchMode`, `hideSeenAlbums`, `hideSkippedAlbums`, `markAlbumState`, and history buttons.
- [ ] Add UI controls for search mode and feed/result history filters.
- [ ] Add album history state loading, marking, unmarking, and client-side filtering.
- [ ] Add `Seen`, `Skip`, and `Save` actions to album cards and feed items.
- [ ] Run the focused GUI source tests and full `python -m unittest discover -s tests -v`.

### Task 4: Runtime Verification

**Files:**
- No committed file edits beyond Tasks 1-3.

- [ ] Start the worktree server on `127.0.0.1:3006`.
- [ ] Verify `GET /health` returns ok.
- [ ] Verify root HTML contains `Exact phrase`, `Any keyword`, `All keywords`, `Only this combo`, `Hide seen`, and `Hide skipped`.
- [ ] Verify `/api/search?keyword=%23redhair&match_mode=all&page=1&limit=1` returns JSON or a handled error, not a server crash.
- [ ] Keep the original `3005` server untouched until the updated port is verified.

### Deferred Slice: Login And Reddit Feed

This first plan intentionally does not implement Reddit/OAuth or Erome authenticated feed. After search/history is verified, create a separate plan for OAuth/token storage, Reddit API integration, optional Erome session mode, and the combined feed data model.

# Erome Watcher Search + GUI Upgrade Plan

> For Hermes: implement this plan directly in the erome-watcher project with small verified steps.

Goal: upgrade the current Erome watcher into a stronger local-search product with FTS5 ranking, richer GUI controls, a details drawer, and FastAPI-served static frontend assets from port 8011.

Architecture: keep the existing Python FastAPI + SQLite + React/Tailwind split, but upgrade SQLite from a plain indexed table search to a hybrid album_index + FTS5 mirror. The backend remains the source of truth; the React app becomes a compiled static frontend served by FastAPI in production while remaining runnable through Vite in development.

Tech stack: FastAPI, SQLite/FTS5, Python stdlib sqlite3, React 18, Vite, Tailwind v4.

---

## Task 1: Inspect and lock the current backend/frontend contract

Objective: confirm the current schema, search response shape, and GUI assumptions before changing ranking or packaging.

Files:
- Read: `spikes/erome-watcher/erome_watcher/sqlite_state.py`
- Read: `spikes/erome-watcher/api_server.py`
- Read: `spikes/erome-watcher/gui/src/App.tsx`

Steps:
1. Read the current album index schema and search helpers.
2. Read the `/search`, `/health`, `/index/*`, `/watch/alert` API routes.
3. Read the GUI search result rendering and identify fields already consumed.
4. Preserve backward compatibility where cheap: keep `results`, `score`, `matched_terms`, and `index_stats` in the JSON response.

Verification:
- Current API routes and frontend fields are documented in working memory for implementation.

## Task 2: Add FTS5 mirror tables and sync helpers

Objective: create a robust full-text layer without discarding the existing album_index source table.

Files:
- Modify: `spikes/erome-watcher/erome_watcher/sqlite_state.py`

Steps:
1. In `get_conn()`, create an FTS5 virtual table such as `album_index_fts` with columns:
   - `album_id UNINDEXED`
   - `username`
   - `title`
   - `search_blob`
2. Add helper(s) to repopulate/update FTS rows whenever `album_index` changes.
3. Ensure `index_profile_snapshot()` deletes and replaces both `album_index` rows and corresponding `album_index_fts` rows for a username.
4. Ensure `rebuild_album_index()` also rebuilds the FTS mirror.

Implementation notes:
- Prefer explicit sync writes over fragile triggers.
- Keep `album_index` as the canonical structured row store.
- Use `INSERT OR REPLACE` semantics where possible.

Verification:
- `python3 -m py_compile spikes/erome-watcher/erome_watcher/sqlite_state.py`
- quick sqlite smoke check to ensure `album_index_fts` exists and can be queried with `MATCH`.

## Task 3: Implement FTS-backed search with ranking/fallback filters

Objective: replace the current naive contains-all-terms scan with FTS5 ranking plus useful sorting metadata.

Files:
- Modify: `spikes/erome-watcher/erome_watcher/sqlite_state.py`
- Modify: `spikes/erome-watcher/erome_watcher/models.py`

Steps:
1. Add helper for parsing `views_text` into a sortable numeric estimate, e.g.:
   - `3K` -> `3000`
   - `4,7K` -> `4700`
   - unknown -> `None`
2. Extend the search result payload to include fields such as:
   - `views_estimate`
   - `rank`
   - maybe `sort_value` if useful internally
3. Rewrite `search_albums()` to:
   - use `MATCH` against `album_index_fts` when query is non-empty
   - join back to `album_index`
   - compute a score from bm25 plus exact-title/prefix/username boosts
   - preserve empty-query behavior by returning recent indexed rows
4. Add optional search arguments to the Python function:
   - `sort_by` (`relevance`, `recent`, `views`, `title`)
   - `source`
   - `min_views`
5. Keep the return structure compatible with existing API consumers while adding the richer fields.

Verification:
- run a direct Python smoke test against the live DB for queries like `blowjob`, `goth`, and empty query.
- confirm results are returned in sane order.

## Task 4: Expand the FastAPI `/search` contract and add static frontend serving

Objective: expose richer query controls and serve the built frontend from FastAPI on port 8011.

Files:
- Modify: `spikes/erome-watcher/api_server.py`

Steps:
1. Extend `/search` query parameters to support:
   - `sort_by`
   - `source`
   - `min_views`
2. Pass those through to `search_albums()`.
3. Keep CORS enabled for dev mode.
4. Add static serving for the built GUI, preferably:
   - serve `/assets/*` from `gui/dist/assets`
   - serve `/` and unknown non-API paths to `gui/dist/index.html`
5. Ensure API routes still take precedence over the SPA catch-all.

Implementation notes:
- Use `fastapi.staticfiles.StaticFiles` and an HTML fallback route.
- Guard static serving so it works when `gui/dist` exists; otherwise return a helpful message or keep API-only behavior.

Verification:
- `python3 -m py_compile spikes/erome-watcher/api_server.py`
- `curl http://127.0.0.1:8011/health`
- `curl 'http://127.0.0.1:8011/search?query=blowjob&sort_by=relevance'`
- `curl http://127.0.0.1:8011/` after frontend build should return HTML, not 404.

## Task 5: Upgrade the React GUI with filters, sorts, and richer summary panels

Objective: make the frontend feel like a serious operator dashboard instead of a basic control surface.

Files:
- Modify: `spikes/erome-watcher/gui/src/App.tsx`
- Modify: `spikes/erome-watcher/gui/src/index.css`

Steps:
1. Add search controls for:
   - sort mode
   - source filter
   - min views
2. Add richer summary cards, for example:
   - top result score
   - top result views estimate
   - active query/filter summary
   - selected profile status
3. Add visual sort/filter chips and better empty/loading states.
4. Keep the current dark premium styling language intact.

Verification:
- `cd spikes/erome-watcher/gui && npm run build`
- browser test confirms controls render and search still works.

## Task 6: Add a details drawer for result inspection

Objective: let the operator inspect one result deeply without leaving the dashboard.

Files:
- Modify: `spikes/erome-watcher/gui/src/App.tsx`

Steps:
1. Add a selected-result state.
2. Open a side drawer/modal when the user clicks a result card or explicit "Inspect" button.
3. Show in the drawer:
   - title
   - username
   - album URL
   - profile URL
   - thumbnail
   - source
   - views text / views estimate
   - indexed timestamp
   - snapshot timestamp
   - matched terms
4. Add quick actions to open album/profile in new tabs.

Verification:
- browser interaction test confirms the drawer opens, populates, and closes correctly.

## Task 7: Build the frontend and verify the FastAPI-served packaged app on 8011

Objective: prove the packaged app works from the single production port.

Files:
- Uses built artifacts under: `spikes/erome-watcher/gui/dist`

Steps:
1. Run `npm run build` in `gui/`.
2. Restart the FastAPI server on 8011.
3. Open `http://127.0.0.1:8011/` in the browser.
4. Verify:
   - app shell loads from FastAPI
   - stats populate
   - search with filters works
   - drawer works
   - API routes still respond directly

Verification commands:
- `curl http://127.0.0.1:8011/health`
- `curl http://127.0.0.1:8011/ | head`
- browser check of `/`
- browser check of a filtered search

## Task 8: Update docs

Objective: document both dev mode and packaged mode clearly.

Files:
- Modify: `spikes/erome-watcher/README.md`

Steps:
1. Add the new `/search` parameters.
2. Document FTS5-backed local search.
3. Document dev GUI mode on Vite.
4. Document packaged mode served by FastAPI from 8011 after `npm run build`.

Verification:
- README shows both workflows and current commands are accurate.

---

Execution order:
1. backend schema + FTS
2. backend API route upgrade
3. frontend controls + drawer
4. packaged static serving
5. end-to-end verification
6. docs

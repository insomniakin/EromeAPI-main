# Reddit Custom Feeds Design

## Context

EroTok already has a local Node bridge, single-file root UI, Reddit OAuth, Reddit feed fetching, token refresh, Reddit media normalization, and Reddit-only or mixed Erome/Reddit feed rendering. The missing feature is support for Reddit account custom feeds, also known as multireddits or multis.

Reddit custom feeds are owned by a Reddit account and exposed through the Reddit API under `/api/multi/*`. The current OAuth scope includes `read` and `mysubreddits`, which is enough for read-only custom feed discovery and feed use. This feature should remain read-only: it will not create, edit, delete, subscribe, vote, comment, or otherwise mutate Reddit account state.

## Goal

Let a connected Reddit account choose one of its Reddit custom feeds and browse that feed inside EroTok's existing vertical feed surface. Reddit custom feed items should behave like current Reddit feed items: they should normalize into the existing `{ source, album, media }` shape, respect pagination, and keep the existing local seen, skipped, saved, open-source, and download actions.

## Architecture

The root `server.js` remains the only Reddit bridge. It will gain a small set of helpers for Reddit multi metadata and multi listing paths, then expose one new discovery endpoint and extend the existing feed endpoint.

New backend route:

- `GET /api/reddit/custom-feeds`

This route requires the same local Reddit configuration and login checks as `/api/reddit/feed`. It calls Reddit's `GET /api/multi/mine?expand_srs=true`, normalizes the response, and returns safe public metadata only:

- `path`: Reddit multi path, such as `/user/example/m/myfeed`
- `name`: stable multi name or slug
- `display_name`: human-readable name
- `visibility`: Reddit visibility value when present
- `subreddits`: subreddit names included in the custom feed

The route must not return access tokens, refresh tokens, OAuth state, client secret, or raw Reddit payloads that could contain unnecessary account details.

Existing backend route extension:

- `GET /api/reddit/feed?kind=custom&multi_path=/user/example/m/myfeed&after=&limit=`

When `kind=custom`, `redditFeedPathFromQuery()` will validate and encode the selected `multi_path`, append the same listing parameters used by other Reddit feeds, and fetch posts from the selected multi. Returned posts continue through `normalizeRedditPost()` and the response shape remains `{ items, after, authenticated }`.

## UI Design

The Feed tab keeps the existing Reddit account panel and feed controls. The `Reddit feed` select gains a `Custom feed` option. A compact custom-feed row appears near the Reddit feed controls with:

- a `Refresh custom feeds` button
- a `Reddit custom feed` select populated from `/api/reddit/custom-feeds`
- status text for loading, empty results, or API errors

The UI stores the selected custom feed path in existing form settings so a reload can restore the choice without storing secrets. When the user chooses `Custom feed` and starts the vertical feed, `fetchRedditFeedBatch()` sends `kind=custom` and `multi_path=<selected path>` to `/api/reddit/feed`.

If the user has not connected Reddit, the existing connect flow remains the required path. If no custom feeds exist, the UI should say so and keep the feed from starting until another Reddit feed kind is selected.

## Data Flow

1. User connects Reddit through the existing OAuth flow.
2. UI calls `/api/reddit/custom-feeds` when the user refreshes custom feeds or selects the custom-feed mode.
3. Server refreshes the token if needed, calls Reddit's multi endpoint, and returns normalized safe feed metadata.
4. UI lets the user select a custom feed path.
5. Vertical feed calls `/api/reddit/feed?kind=custom&multi_path=...`.
6. Server fetches the Reddit listing, normalizes media posts, and returns feed items plus `after` cursor.
7. UI appends the returned items through the existing Reddit feed renderer.

## Error Handling

Backend errors should return JSON with existing conventions:

- `reddit_not_configured` when no client ID is stored
- `reddit_login_required` when no refresh token is available
- a 400 error when `kind=custom` has no valid `multi_path`
- a Reddit API error message when Reddit rejects the multi request

Frontend errors should be visible in the existing status area and the custom-feed status text. A failed custom-feed load must not erase the current selected feed until a successful response replaces it.

## Testing

Use the existing Python source-check test style in `tests/test_watcher_gui_source.py` for this slice. Add tests before implementation that assert the presence of:

- `/api/reddit/custom-feeds`
- `normalizeRedditCustomFeed`
- `redditCustomFeedPathFromQuery` or equivalent helper
- `kind === "custom"` handling in the Reddit feed path builder
- UI IDs for custom feed select, refresh button, and status text
- frontend functions such as `loadRedditCustomFeeds` and custom feed request parameters

After implementation, run:

- `python -m unittest tests.test_watcher_gui_source.WatcherGuiSourceTests -v`
- `python -m unittest discover -s tests -v`
- `node --check server.js`

Runtime smoke checks should verify `/health`, `/api/reddit/status`, and root HTML. Live custom-feed API verification requires a connected Reddit account with at least one custom feed.

## Out Of Scope

This feature will not add Reddit multi creation, editing, deletion, subreddit management, voting, commenting, saving to Reddit, browser-cookie reuse, password handling, or automated account actions. Local EroTok save/seen/skip behavior remains separate from Reddit account state.

## Acceptance Criteria

- A connected Reddit user can load a list of their Reddit custom feeds.
- The Feed tab can select one custom feed and browse its media posts.
- Custom feed posts render in the same vertical feed surface as existing Reddit posts.
- Feed pagination uses Reddit's `after` cursor and continues to work across batches.
- No Reddit token, OAuth state, client secret, or raw sensitive auth data is exposed through UI state or API responses.
- Existing Erome-only, Reddit home, subreddit, search, and mixed-feed behavior continues to work.
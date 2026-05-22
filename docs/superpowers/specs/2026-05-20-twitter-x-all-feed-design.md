# Twitter/X And All Feed Design

## Goal

Add Twitter/X as a feed provider and add an `All` feed option that combines Erome, Reddit, and Twitter/X in the existing feed view.

## Approved Product Behavior

- Add `Twitter/X only` to the feed network selector.
- Add `All` to the feed network selector.
- `All` means Erome + Reddit + Twitter/X.
- Twitter/X should appear in the feed whether the user is logged in or not.
- Anonymous Twitter/X mode should try supported public/search-style results.
- Logged-in Twitter/X mode can enhance the same provider later without requiring a separate feed UI.
- Existing Reddit behavior should stay intact.
- Existing Erome behavior should stay intact.

## Architecture

Keep the current single Node server plus root `ui.html` feed architecture. Add Twitter/X as another provider rather than creating a separate page or feed renderer.

Server additions:

- Add a `GET /api/twitter/feed` route.
- Normalize Twitter/X results into the same feed item shape used by Reddit-style items.
- Return handled JSON errors when Twitter/X public access is unavailable or blocked.

UI additions:

- Add `twitter` and `all` values to `feedNetwork`.
- Rename the visible `Both` option to `All` while preserving legacy compatibility for saved `both` values.
- Add `fetchTwitterFeedBatch()`.
- Update `loadMoreFeed()` so `twitter` loads only Twitter/X and `all` loads Erome, Reddit, and Twitter/X.
- Keep using the existing feed card renderer where possible.

## Data Flow

Twitter/X only:

1. User selects `Twitter/X only`.
2. `loadMoreFeed()` calls `fetchTwitterFeedBatch()`.
3. The browser requests `/api/twitter/feed` with query/sort/batch inputs.
4. The server returns normalized Twitter/X items.
5. The UI appends items through the shared feed renderer.

All:

1. User selects `All`.
2. `loadMoreFeed()` fetches Erome, Reddit, and Twitter/X batches in parallel.
3. Provider failures are isolated when possible.
4. Successful provider results render together in the existing feed.
5. Empty/error text identifies which provider had no items or was unavailable.

## Login And Anonymous Behavior

The first implementation should not require Twitter/X login. It should expose Twitter/X as a provider and support public results when available.

If logged-in Twitter/X support is added, it should reuse the same route and normalized feed item contract. Credentials or session data must not be hardcoded into source files.

## Error Handling

- `Twitter/X only` can show a Twitter/X-specific empty or blocked message.
- `All` should not fail the whole feed because Reddit or Twitter/X is unavailable.
- If Reddit is disconnected, `All` should still show Erome and Twitter/X results.
- If Twitter/X public access fails, `All` should still show Erome and Reddit results.
- Empty states should distinguish no results from provider unavailable.

## Tests

Use test-first implementation.

Source/contract tests:

- UI contains `Twitter/X only`.
- UI contains `All`.
- UI includes `twitter` and `all` feed network values.
- UI includes `fetchTwitterFeedBatch()`.
- UI all-mode path fetches Erome, Reddit, and Twitter/X.
- Server includes `path === "/api/twitter/feed"`.

Behavior tests:

- Twitter/X normalizer converts representative public item data into the shared feed item shape.
- All-mode merge tolerates provider failures and keeps successful providers visible.
- Saved legacy `both` settings still behave like all-compatible mixed mode.

## Out Of Scope For First Slice

- Full Twitter/X OAuth flow.
- Hardcoded user credentials or cookies.
- A separate Twitter/X page.
- Live-network-dependent tests.
- Rewriting the existing Erome or Reddit provider architecture.

## Open Implementation Detail

Twitter/X public access can change or be blocked. The first implementation should treat public fetch failures as handled provider unavailability, not as a server crash.
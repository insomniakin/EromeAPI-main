# Root Video Player And Twitter Access Design

## Goal

Use the YouTube-style player already present in the watcher GUI for root-site feed and preview videos, and make Twitter/X feed limitations clear when anonymous public X pages do not expose media.

## Approved Behavior

- Replace root-site native feed/preview video controls with a YouTube-style player.
- Keep existing lazy loading, scroll autoplay, mute preference, min-duration filtering, downloads, and album actions.
- Do not copy external repository code; port the existing local player behavior from the repo.
- Keep Twitter/X anonymous-first, but explain that public X search/profile pages can return only a JavaScript app shell with no parseable media.
- Tell users that a real Twitter/X feed requires official API/session support when anonymous public parsing is unavailable.

## Scope

- Modify `ui.html` and source tests.
- Improve `server.js` Twitter/X unavailable message.
- Keep tests live-network independent.
- Do not implement full X OAuth/API credentials in this slice.
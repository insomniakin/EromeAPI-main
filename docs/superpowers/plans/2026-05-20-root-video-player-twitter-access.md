# Root Video Player And Twitter Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace root-site native video controls with a YouTube-style player and make Twitter/X anonymous feed limitations clear.

**Architecture:** Port the existing local watcher player behavior into root `ui.html` with focused helper functions and CSS. Keep Twitter/X route anonymous-first but return actionable unavailable messages when X serves only an app shell.

**Tech Stack:** Root `ui.html`, Node `server.js`, Python source tests.

---

### Task 1: Root Player Contract Test

**Files:**
- Modify: `tests/test_watcher_gui_source.py`

- [x] Add a failing source test that checks root `ui.html` contains `function createVideoPlayerClone`, `yt-clone-player`, timeline controls, volume controls, fullscreen controls, and no `video.controls = true` in `makeFeedItem`.
- [x] Run the focused test and confirm it fails.

### Task 2: Root Player Implementation

**Files:**
- Modify: `ui.html`

- [x] Add root CSS for `.yt-clone-player` controls adapted to the feed container.
- [x] Add helper functions for formatting time, clamping, seeking, control visibility, mute/volume, speed, picture-in-picture, and fullscreen.
- [x] Replace native video creation in `makeFeedItem` with `createVideoPlayerClone` while preserving existing video event behavior.

### Task 3: Twitter/X Explanation

**Files:**
- Modify: `server.js`
- Modify: `ui.html`
- Modify: `tests/test_watcher_gui_source.py`

- [x] Add test expectations for an actionable Twitter/X app-shell message.
- [x] Update server unavailable messages to explain that anonymous X returns an app shell without media URLs and API/session support is required.
- [x] Add a short UI note near Twitter/X controls.

### Task 4: Verification

**Files:**
- No additional edits.

- [x] Run focused source tests.
- [x] Run `python -m pytest -q`.
- [x] Run `node --check server.js`.
- [x] Restart the local server and verify `/health` and `/api/twitter/feed` return handled JSON.
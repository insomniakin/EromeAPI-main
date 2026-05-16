# GitHub Launch Notes

![Launch](https://img.shields.io/badge/launch-ready-22D3EE?style=for-the-badge)
![Local First](https://img.shields.io/badge/local--first-yes-34D399?style=for-the-badge)
![Public Pages](https://img.shields.io/badge/public%20pages-only-818CF8?style=for-the-badge)

These notes are written for the public GitHub release of EroTok / EromeAPI.

## What This Project Is

EroTok is a local control panel and Python/Node toolkit for working with public Erome pages. It helps users preview public albums, search with keywords and hashtags, download media they are allowed to archive, watch public profiles, and run local automation through simple API routes.

## What Makes It Useful

- Local browser GUI with no cloud service required
- Public album search and explore helpers
- Multi-word hashtag search with chip controls
- Hide-term filtering for feed and result cleanup
- TikTok-style vertical preview feed
- Per-job download progress with stable UI layout
- Public profile watcher snapshots and diffs
- SQLite-backed local watcher search index
- Node API bridge for scripts and tools
- Tampermonkey/Violentmonkey userscript mini panel that links back to the full GitHub version
- Optional MCP and Hermes helper entrypoints

## Public Release Positioning

Use the wording below when describing the repo publicly:

> A local-first public-page toolkit for previewing, indexing, watching, and archiving Erome albums that you own or have permission to download.

Avoid describing it as an unlimited downloader or a tool for collecting third-party content. The public repo should stay clear that it is for responsible, permission-based use.

## Safety Notes For GitHub

Before pushing, confirm these files are not staged:

- Downloaded media folders
- SQLite state files
- `state.json`
- local output logs
- private config
- tokens, cookies, credentials, or webhook URLs

Use:

```bash
git status --short
```

The `.gitignore` has been updated to exclude common local/runtime files.

## Suggested Repository Description

```text
Local-first EroTok GUI and Python/Node toolkit for public Erome search, preview, watching, and permission-based archiving.
```

## Suggested GitHub Topics

```text
erome, local-first, python, nodejs, scraper, media-archive, watcher, sqlite, gui, automation, public-pages
```

## Quick Demo Flow

1. Run `pip install -r requirements.txt`.
2. Run `node server.js` from the project root.
3. Open `http://127.0.0.1:3000/`.
4. Try Search with `#alternative girl, #egirl`.
5. Open Feed mode and preview public album media.
6. Use Watcher routes for public profile snapshots and local search.

## Release Checklist

- [x] README rewritten for GitHub
- [x] Runtime/download files ignored
- [x] QR support image added as a local asset
- [x] README screenshots captured and embedded
- [x] Userscript mini panel added
- [x] Tests passing locally
- [x] Python syntax checked
- [x] Node syntax checked
- [ ] Public GitHub remote created
- [ ] First push completed
- [ ] Repository description and topics added on GitHub

## Verification Used Before Publishing

```bash
python -m unittest discover -s tests
python -m py_compile api.py api_bridge.py
node --check server.js
```

Expected result at the time of writing:

```text
36 tests passing
```

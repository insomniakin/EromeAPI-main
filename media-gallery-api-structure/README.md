# Media Gallery API Structure

This spike is a generic API scaffold for a public media-gallery website.

It does NOT implement scraping for any particular site.
Instead, it gives you a clean architecture you can adapt to a lawful/public target yourself.

## Goal

Provide a "bad ass" API shape that can:
- inspect a gallery/profile/album URL
- normalize metadata
- classify media as image/video
- expose a stable JSON API
- optionally cache results
- support later adapters for specific sites

## Suggested stack

- Python 3.11+
- FastAPI
- Pydantic
- httpx
- BeautifulSoup / lxml
- SQLite for cache/index/history

## Project layout

- `api_server.py` — FastAPI entrypoint
- `media_gallery_api/models/schemas.py` — response/request models
- `media_gallery_api/core/service.py` — orchestration layer
- `media_gallery_api/core/interfaces.py` — adapter contracts
- `media_gallery_api/adapters/base.py` — shared adapter helpers
- `media_gallery_api/adapters/example_public_gallery.py` — example adapter stub
- `API_DESIGN.md` — endpoint design and behavior
- `requirements.txt` — optional dependencies

## Run

```bash
cd /home/insomniakin/.hermes/hermes-agent/spikes/media-gallery-api-structure
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api_server:app --reload --port 8015
```

## Notes

- Adapters should only target content you are authorized to access.
- Keep site-specific parsing isolated under `media_gallery_api/adapters/`.
- The API contract should stay stable even when adapters change.

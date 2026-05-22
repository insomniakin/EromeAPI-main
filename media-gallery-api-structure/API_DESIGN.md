# API Design

## Core idea

Separate the system into 4 layers:

1. Transport/API layer
- FastAPI endpoints
- input validation
- response shaping

2. Service layer
- resolves which adapter to use
- orchestrates gallery/profile/media extraction
- applies caching / dedupe / pagination normalization

3. Adapter layer
- one adapter per site type
- parses HTML/API responses into normalized models
- never leaks raw site-specific structure outside the adapter

4. Storage layer (optional later)
- SQLite/Postgres for cache/history/index

## Normalized resource types

- Source
  - site name
  - adapter name
  - supported capabilities

- Profile
  - handle / username
  - display name
  - avatar
  - bio
  - gallery count

- Gallery
  - id
  - source_url
  - title
  - owner
  - tags
  - created_at
  - stats
  - media_count
  - cover_url

- MediaItem
  - id
  - gallery_id
  - media_type: image | video
  - direct_url
  - thumbnail_url
  - width
  - height
  - duration_seconds
  - mime_type
  - sort_index

## Proposed endpoints

### GET /health
Returns service health.

### GET /sources
Lists installed adapters and capabilities.

Response example:
```json
{
  "sources": [
    {
      "key": "example_public_gallery",
      "display_name": "Example Public Gallery",
      "capabilities": ["profile", "gallery", "media"]
    }
  ]
}
```

### GET /resolve?url=...
Figures out what kind of URL it is and which adapter can handle it.

### GET /profile?url=...
Returns normalized profile metadata and linked galleries.

### GET /gallery?url=...
Returns normalized gallery metadata plus media inventory.

### GET /media?url=...
Directly resolves a media page or gallery into image/video items.

### POST /extract
Body-driven endpoint.

Request example:
```json
{
  "url": "https://example.com/gallery/123",
  "include_media": true,
  "include_profile": false,
  "limit": 50
}
```

### GET /search
Optional future endpoint backed by local index.

### GET /cache/stats
Optional future endpoint for cache metrics.

## Recommended response envelopes

Use a stable top-level envelope:

```json
{
  "ok": true,
  "source": "example_public_gallery",
  "kind": "gallery",
  "data": { ... },
  "warnings": [],
  "fetched_at": "2026-05-20T22:00:00Z"
}
```

## Suggested capability model

- `profile`
- `gallery`
- `media`
- `pagination`
- `search`
- `video`
- `images`

## Error model

```json
{
  "ok": false,
  "error": {
    "code": "UNSUPPORTED_URL",
    "message": "No adapter matched the provided URL"
  }
}
```

## Why this structure is good

- site-specific parsing stays isolated
- API remains consistent even if selectors change
- easy to add caching and search later
- easy to add a UI later
- easy to support image-only, video-only, or mixed galleries

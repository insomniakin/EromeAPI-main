from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api import Api
from erome_watcher.alerts import format_alert
from erome_watcher.client import EromeClient
from erome_watcher.sqlite_state import (
    diff_snapshots,
    history as snapshot_history,
    index_profile_snapshot,
    index_stats,
    load_latest_snapshot,
    rebuild_album_index,
    save_snapshot,
    search_albums,
)
from erome_watcher.state import diff_and_update

VALID_SORTS = {'relevance', 'recent', 'views', 'title'}
APP_ROOT = Path(__file__).resolve().parent
GUI_DIST_DIR = APP_ROOT / 'gui' / 'dist'
GUI_DIST_ASSETS = GUI_DIST_DIR / 'assets'
GUI_DIST_INDEX = GUI_DIST_DIR / 'index.html'

app = FastAPI(title='Erome Watcher API', version='0.4.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)
client = EromeClient()
STATE_DIR = Path(os.getenv('EROME_STATE_DIR', APP_ROOT / 'state'))
DB_PATH = STATE_DIR / 'erome_state.sqlite3'
PUBLIC_ONLY_NOTE = (
    'Search covers indexed public content only. It does not discover private, hidden, or access-controlled content.'
)


class WatchRequest(BaseModel):
    username: str
    persist: bool = True


class ProfileIndexRequest(BaseModel):
    username: str
    enrich_albums: bool = False
    max_enrich: int = 24


class DownloadAlbumRequest(BaseModel):
    url: str
    directory: str = 'Downloads'
    include_photos: bool = True
    include_videos: bool = True
    overwrite: bool = False
    max_workers: int = 4


class ExploreIndexRequest(BaseModel):
    page: int = 1
    persist_snapshot: bool = True


class RebuildIndexRequest(BaseModel):
    usernames: list[str] | None = None


def _normalize_sort(sort_by: str | None) -> str:
    if sort_by in VALID_SORTS:
        return sort_by
    return 'relevance'


def _spa_available() -> bool:
    return GUI_DIST_INDEX.exists()


def _serve_spa_index() -> Response:
    if _spa_available():
        return FileResponse(GUI_DIST_INDEX)
    return HTMLResponse(
        '<h1>Erome Watcher API</h1><p>GUI bundle not found. Run <code>cd gui && npm run build</code> to package the frontend.</p>',
        status_code=200,
    )


@app.get('/health')
def health() -> dict:
    return {
        'status': 'ok',
        'version': app.version,
        'index_stats': index_stats(DB_PATH),
        'gui_packaged': _spa_available(),
    }


@app.get('/profile/{username}')
def profile(username: str) -> dict:
    snapshot = client.get_profile_snapshot(username)
    return snapshot.model_dump()


@app.get('/profile/{username}/diff')
def profile_diff(username: str) -> dict:
    previous = load_latest_snapshot(username, DB_PATH)
    current = client.get_profile_snapshot(username)
    if previous is None:
        return {
            'username': username,
            'message': 'No previous snapshot stored yet',
            'current': current.model_dump(),
        }
    return diff_snapshots(previous, current).model_dump()


@app.get('/profile/{username}/history')
def profile_history(username: str, limit: int = 20) -> dict:
    return {'username': username, 'history': snapshot_history(username, limit=limit, db_path=DB_PATH)}


@app.post('/watch')
def watch(request: WatchRequest) -> dict:
    try:
        snapshot = client.get_profile_snapshot(request.username)
        if request.persist:
            return diff_and_update(snapshot, STATE_DIR).model_dump()
        previous = load_latest_snapshot(request.username, DB_PATH)
        if previous is None:
            return {
                'username': request.username,
                'message': 'No previous snapshot stored yet',
                'current': snapshot.model_dump(),
            }
        return diff_snapshots(previous, snapshot).model_dump()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.post('/watch/alert')
def watch_alert(request: WatchRequest) -> dict:
    try:
        snapshot = client.get_profile_snapshot(request.username)
        previous = load_latest_snapshot(request.username, DB_PATH)
        diff = diff_and_update(snapshot, STATE_DIR) if request.persist else (
            diff_snapshots(previous, snapshot) if previous else None
        )
        if diff is None:
            return {'username': request.username, 'message': 'No previous snapshot stored yet'}
        return format_alert(diff).model_dump()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.get('/album')
def album(url: str) -> dict:
    try:
        return client.get_album_snapshot(url).model_dump()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.post('/download')
def download_album(request: DownloadAlbumRequest) -> dict:
    try:
        results = Api().download_album(
            path=request.url,
            directory=request.directory,
            include_photos=request.include_photos,
            include_videos=request.include_videos,
            overwrite=request.overwrite,
            max_workers=max(1, min(16, request.max_workers)),
        )
        return {'album_url': request.url, 'count': len(results), 'downloaded': results}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.get('/index/stats')
def get_index_stats() -> dict:
    stats = index_stats(DB_PATH)
    stats['note'] = PUBLIC_ONLY_NOTE
    return stats


@app.post('/index/profile')
def index_profile(request: ProfileIndexRequest) -> dict:
    try:
        snapshot = client.get_profile_snapshot(
            request.username,
            enrich_albums=request.enrich_albums,
            max_enrich=max(1, min(100, request.max_enrich)),
        )
        save_snapshot(snapshot, DB_PATH)
        indexing = index_profile_snapshot(snapshot, DB_PATH)
        return {
            'mode': 'profile',
            'snapshot': snapshot.model_dump(),
            'indexing': indexing,
            'index_stats': index_stats(DB_PATH),
            'note': PUBLIC_ONLY_NOTE,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.post('/index/explore')
def index_explore(request: ExploreIndexRequest) -> dict:
    try:
        snapshot = client.get_explore_snapshot(page=request.page)
        if request.persist_snapshot:
            save_snapshot(snapshot, DB_PATH)
        indexing = index_profile_snapshot(snapshot, DB_PATH)
        return {
            'mode': 'explore',
            'snapshot': snapshot.model_dump(),
            'indexing': indexing,
            'index_stats': index_stats(DB_PATH),
            'note': PUBLIC_ONLY_NOTE,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.post('/index/rebuild')
def rebuild_index(request: RebuildIndexRequest) -> dict:
    try:
        result = rebuild_album_index(usernames=request.usernames, db_path=DB_PATH)
        return {
            'rebuild': result,
            'index_stats': index_stats(DB_PATH),
            'note': PUBLIC_ONLY_NOTE,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.get('/search')
def search(
    query: str = Query('', description='Case-insensitive query over locally indexed public album metadata.'),
    username: str | None = Query(None, description='Optional username filter.'),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query('relevance', description='Sort mode: relevance, recent, views, or title.'),
    source: str | None = Query(None, description='Optional source filter such as profile or explore.'),
    min_views: int | None = Query(None, ge=0, description='Minimum parsed views estimate for indexed results.'),
) -> dict:
    try:
        normalized_sort = _normalize_sort(sort_by)
        normalized_source = source.strip() if source else None
        results = search_albums(
            query=query,
            username=username,
            limit=limit,
            sort_by=normalized_sort,
            source=normalized_source,
            min_views=min_views,
            db_path=DB_PATH,
        )
        return {
            'query': query,
            'username': username,
            'limit': limit,
            'sort_by': normalized_sort,
            'source': normalized_source,
            'min_views': min_views,
            'total_returned': len(results),
            'index_stats': index_stats(DB_PATH),
            'results': results,
            'note': PUBLIC_ONLY_NOTE,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get('/search/live')
def search_live(
    query: str = Query(..., min_length=1, description='Live public-site query, subject to rate limits.'),
    page: int = Query(1, ge=1, le=50),
) -> dict:
    try:
        snapshot = client.search_public(query=query, page=page)
        return {
            'query': query,
            'page': page,
            'snapshot': snapshot.model_dump(),
            'note': PUBLIC_ONLY_NOTE,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


if GUI_DIST_ASSETS.exists():
    app.mount('/assets', StaticFiles(directory=GUI_DIST_ASSETS), name='gui-assets')


@app.get('/', include_in_schema=False, response_model=None)
def serve_root() -> Response:
    return _serve_spa_index()


@app.get('/{full_path:path}', include_in_schema=False, response_model=None)
def serve_spa(full_path: str) -> Response:
    candidate = GUI_DIST_DIR / full_path
    if candidate.exists() and candidate.is_file():
        return FileResponse(candidate)
    if '.' in full_path:
        raise HTTPException(status_code=404, detail='Not found')
    return _serve_spa_index()

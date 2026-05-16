from __future__ import annotations

from typing import Any, Dict, Optional

from api import Api
from watcher_runtime import WATCHER_GUI_DIST, WATCHER_ROOT, ensure_watcher_path


ensure_watcher_path()

from erome_watcher.alerts import format_alert  # noqa: E402
from erome_watcher.client import EromeClient  # noqa: E402
from erome_watcher.sqlite_state import (  # noqa: E402
    diff_snapshots,
    history as snapshot_history,
    index_profile_snapshot,
    index_stats,
    load_latest_snapshot,
    rebuild_album_index,
    save_snapshot,
    search_albums,
)
from erome_watcher.state import diff_and_update  # noqa: E402


PUBLIC_ONLY_NOTE = (
    "Search covers indexed public content only. It does not discover private, hidden, or access-controlled content."
)
VALID_SORTS = {"relevance", "recent", "views", "title"}
STATE_DIR = WATCHER_ROOT / "state"
DB_PATH = STATE_DIR / "erome_state.sqlite3"

client = EromeClient()


def _bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _int(value: Any, default: int, minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_text(payload: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        text = _optional_text(payload.get(key))
        if text:
            return text
    raise ValueError(f"Missing required field: {' or '.join(keys)}")


def _normalize_sort(sort_by: Any) -> str:
    sort = str(sort_by or "relevance").strip().lower()
    return sort if sort in VALID_SORTS else "relevance"


def _watcher_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "version": "0.4.0",
        "index_stats": index_stats(DB_PATH),
        "gui_packaged": (WATCHER_GUI_DIST / "index.html").exists(),
        "note": PUBLIC_ONLY_NOTE,
    }


def _profile(username: str) -> Dict[str, Any]:
    return client.get_profile_snapshot(username).model_dump()


def _profile_diff(username: str) -> Dict[str, Any]:
    previous = load_latest_snapshot(username, DB_PATH)
    current = client.get_profile_snapshot(username)
    if previous is None:
        return {
            "username": username,
            "message": "No previous snapshot stored yet",
            "current": current.model_dump(),
        }
    return diff_snapshots(previous, current).model_dump()


def _watch(username: str, persist: bool) -> Dict[str, Any]:
    snapshot = client.get_profile_snapshot(username)
    if persist:
        return diff_and_update(snapshot, STATE_DIR).model_dump()

    previous = load_latest_snapshot(username, DB_PATH)
    if previous is None:
        return {
            "username": username,
            "message": "No previous snapshot stored yet",
            "current": snapshot.model_dump(),
        }
    return diff_snapshots(previous, snapshot).model_dump()


def _watch_alert(username: str, persist: bool) -> Dict[str, Any]:
    snapshot = client.get_profile_snapshot(username)
    previous = load_latest_snapshot(username, DB_PATH)
    if persist:
        diff = diff_and_update(snapshot, STATE_DIR)
    elif previous is None:
        return {"username": username, "message": "No previous snapshot stored yet"}
    else:
        diff = diff_snapshots(previous, snapshot)
    return format_alert(diff).model_dump()


def _search(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query", payload.get("keyword", "")))
    username = _optional_text(payload.get("username"))
    source = _optional_text(payload.get("source"))
    min_views = payload.get("min_views")
    min_views_value = None if min_views in (None, "") else _int(min_views, 0, minimum=0)
    limit = _int(payload.get("limit"), 20, minimum=1, maximum=100)
    sort_by = _normalize_sort(payload.get("sort_by"))

    results = search_albums(
        query=query,
        username=username,
        limit=limit,
        sort_by=sort_by,
        source=source,
        min_views=min_views_value,
        db_path=DB_PATH,
    )
    return {
        "query": query,
        "username": username,
        "limit": limit,
        "sort_by": sort_by,
        "source": source,
        "min_views": min_views_value,
        "total_returned": len(results),
        "index_stats": index_stats(DB_PATH),
        "results": results,
        "note": PUBLIC_ONLY_NOTE,
    }


def _download_album(payload: Dict[str, Any]) -> Dict[str, Any]:
    album_url = _required_text(payload, "url", "album_url", "path")
    results = Api().download_album(
        path=album_url,
        directory=str(payload.get("directory", "Downloads")),
        include_photos=_bool(payload.get("include_photos"), True),
        include_videos=_bool(payload.get("include_videos"), True),
        overwrite=_bool(payload.get("overwrite"), False),
        max_workers=_int(payload.get("max_workers"), 4, minimum=1, maximum=16),
    )
    return {"album_url": album_url, "count": len(results), "downloaded": results}


def handle_watcher_method(method: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    payload = payload or {}
    normalized = method.removeprefix("watcher_")

    if normalized == "health":
        return _watcher_health()
    if normalized == "profile":
        return _profile(_required_text(payload, "username", "profile"))
    if normalized == "profile_diff":
        return _profile_diff(_required_text(payload, "username", "profile"))
    if normalized == "profile_history":
        username = _required_text(payload, "username", "profile")
        limit = _int(payload.get("limit"), 20, minimum=1, maximum=100)
        return {"username": username, "history": snapshot_history(username, limit=limit, db_path=DB_PATH)}
    if normalized == "watch":
        return _watch(_required_text(payload, "username", "profile"), _bool(payload.get("persist"), True))
    if normalized == "watch_alert":
        return _watch_alert(_required_text(payload, "username", "profile"), _bool(payload.get("persist"), True))
    if normalized == "album":
        return client.get_album_snapshot(_required_text(payload, "url", "album_url")).model_dump()
    if normalized == "download_album":
        return _download_album(payload)
    if normalized == "index_stats":
        stats = index_stats(DB_PATH)
        stats["note"] = PUBLIC_ONLY_NOTE
        return stats
    if normalized == "index_profile":
        snapshot = client.get_profile_snapshot(
            _required_text(payload, "username", "profile"),
            enrich_albums=_bool(payload.get("enrich_albums", payload.get("enrich")), False),
            max_enrich=_int(payload.get("max_enrich"), 24, minimum=1, maximum=100),
        )
        save_snapshot(snapshot, DB_PATH)
        indexing = index_profile_snapshot(snapshot, DB_PATH)
        return {
            "mode": "profile",
            "snapshot": snapshot.model_dump(),
            "indexing": indexing,
            "index_stats": index_stats(DB_PATH),
            "note": PUBLIC_ONLY_NOTE,
        }
    if normalized == "index_explore":
        snapshot = client.get_explore_snapshot(page=_int(payload.get("page"), 1, minimum=1, maximum=50))
        if _bool(payload.get("persist_snapshot"), True):
            save_snapshot(snapshot, DB_PATH)
        indexing = index_profile_snapshot(snapshot, DB_PATH)
        return {
            "mode": "explore",
            "snapshot": snapshot.model_dump(),
            "indexing": indexing,
            "index_stats": index_stats(DB_PATH),
            "note": PUBLIC_ONLY_NOTE,
        }
    if normalized == "index_rebuild":
        usernames = payload.get("usernames") if isinstance(payload.get("usernames"), list) else None
        result = rebuild_album_index(usernames=usernames, db_path=DB_PATH)
        return {"rebuild": result, "index_stats": index_stats(DB_PATH), "note": PUBLIC_ONLY_NOTE}
    if normalized == "search":
        return _search(payload)
    if normalized == "search_live":
        snapshot = client.search_public(
            query=_required_text(payload, "query", "keyword"),
            page=_int(payload.get("page"), 1, minimum=1, maximum=50),
        )
        return {"query": payload.get("query", payload.get("keyword", "")), "page": _int(payload.get("page"), 1), "snapshot": snapshot.model_dump(), "note": PUBLIC_ONLY_NOTE}

    raise ValueError(f"Unknown watcher method: {method}")
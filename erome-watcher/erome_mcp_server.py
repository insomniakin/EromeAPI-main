from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from erome_watcher.alerts import format_alert
from erome_watcher.client import EromeClient
from erome_watcher.models import ProfileDiff
from erome_watcher.sqlite_state import history as snapshot_history
from erome_watcher.sqlite_state import load_latest_snapshot, diff_snapshots
from erome_watcher.state import diff_and_update

mcp = FastMCP('erome-watcher')
client = EromeClient()
STATE_DIR = Path(__file__).resolve().parent / 'state'


@mcp.tool()
def get_profile_snapshot(username: str) -> dict:
    """Fetch a normalized snapshot of an Erome profile/albums page."""
    return client.get_profile_snapshot(username).model_dump()


@mcp.tool()
def get_album_snapshot(album_url: str) -> dict:
    """Fetch album details and media URLs from an Erome album URL."""
    return client.get_album_snapshot(album_url).model_dump()


@mcp.tool()
def diff_profile(username: str, persist: bool = True) -> dict:
    """Compare the current profile snapshot to the last stored snapshot."""
    current = client.get_profile_snapshot(username)
    if persist:
        return diff_and_update(current, STATE_DIR).model_dump()
    previous = load_latest_snapshot(username)
    if previous is None:
        return {
            'username': username,
            'message': 'No stored snapshot exists yet',
            'current': current.model_dump(),
        }
    return diff_snapshots(previous, current).model_dump()


@mcp.tool()
def format_profile_alert(username: str, persist: bool = True) -> dict:
    """Get Telegram/Discord-ready text for profile changes."""
    diff = diff_profile(username, persist=persist)
    if 'new_albums' not in diff:
        return diff
    return format_alert(ProfileDiff.model_validate(diff)).model_dump()


@mcp.tool()
def get_profile_history(username: str, limit: int = 20) -> dict:
    """Return recent stored snapshot history for a watched profile."""
    return {'username': username, 'history': snapshot_history(username, limit=limit)}


if __name__ == '__main__':
    mcp.run()

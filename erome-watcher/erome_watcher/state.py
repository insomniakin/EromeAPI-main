from __future__ import annotations

from pathlib import Path
from typing import Optional

from .models import ProfileDiff, ProfileSnapshot
from .sqlite_state import diff_and_update as sqlite_diff_and_update
from .sqlite_state import load_latest_snapshot as sqlite_load_latest_snapshot
from .sqlite_state import save_snapshot as sqlite_save_snapshot


DEFAULT_STATE_DIR = Path(__file__).resolve().parents[1] / 'state'
DEFAULT_JSON_STATE_DIR = DEFAULT_STATE_DIR / 'json'
DEFAULT_DB_PATH = DEFAULT_STATE_DIR / 'erome_state.sqlite3'


def _resolve_root(state_dir: Optional[Path] = None) -> Path:
    return Path(state_dir) if state_dir is not None else DEFAULT_STATE_DIR


def _resolve_json_root(state_dir: Optional[Path] = None) -> Path:
    root = _resolve_root(state_dir)
    return root / 'json'


def _resolve_db_path(state_dir: Optional[Path] = None) -> Path:
    root = _resolve_root(state_dir)
    return root / 'erome_state.sqlite3'


def state_path(username: str, state_dir: Optional[Path] = None) -> Path:
    root = _resolve_json_root(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root / f'{username}.json'


def load_snapshot(username: str, state_dir: Optional[Path] = None) -> Optional[ProfileSnapshot]:
    path = state_path(username, state_dir)
    if not path.exists():
        return None
    return ProfileSnapshot.model_validate_json(path.read_text())


def save_snapshot(snapshot: ProfileSnapshot, state_dir: Optional[Path] = None) -> Path:
    path = state_path(snapshot.username, state_dir)
    path.write_text(snapshot.model_dump_json(indent=2))
    return path


def diff_and_update(current: ProfileSnapshot, state_dir: Optional[Path] = None) -> ProfileDiff:
    return sqlite_diff_and_update(current, _resolve_db_path(state_dir))


def load_latest_snapshot(username: str, state_dir: Optional[Path] = None) -> Optional[ProfileSnapshot]:
    return sqlite_load_latest_snapshot(username, _resolve_db_path(state_dir))


def save_snapshot_sqlite(snapshot: ProfileSnapshot, state_dir: Optional[Path] = None) -> Path:
    return sqlite_save_snapshot(snapshot, _resolve_db_path(state_dir))

from __future__ import annotations

import runpy
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent
WATCHER_ROOT = APP_ROOT / "erome-watcher"
WATCHER_GUI_DIST = WATCHER_ROOT / "gui" / "dist"


def ensure_watcher_path() -> Path:
    if not WATCHER_ROOT.exists():
        raise RuntimeError(f"Watcher folder not found: {WATCHER_ROOT}")
    watcher_path = str(WATCHER_ROOT)
    if watcher_path not in sys.path:
        sys.path.insert(0, watcher_path)
    return WATCHER_ROOT


def run_watcher_script(script_name: str) -> None:
    watcher_root = ensure_watcher_path()
    script_path = watcher_root / script_name
    if not script_path.exists():
        raise RuntimeError(f"Watcher script not found: {script_path}")
    runpy.run_path(str(script_path), run_name="__main__")
from __future__ import annotations

import os

from watcher_runtime import ensure_watcher_path


ensure_watcher_path()

from api_server import app  # noqa: E402


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8011")))
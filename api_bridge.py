import base64
import json
import mimetypes
import sys
import threading
from typing import Any, Dict

import requests
from api import Api


def read_payload() -> Dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Payload must be a JSON object.")
    return data


def write_result(result: Dict[str, Any], exit_code: int = 0) -> None:
    sys.stdout.write(json.dumps(result, ensure_ascii=True))
    sys.exit(exit_code)


progress_lock = threading.Lock()


def write_progress(progress: Dict[str, Any]) -> None:
    with progress_lock:
        sys.stdout.write(json.dumps({"progress": progress}, ensure_ascii=True) + "\n")
        sys.stdout.flush()


def main() -> None:
    if len(sys.argv) < 2:
        write_result({"ok": False, "error": "Missing method argument."}, 1)

    method = sys.argv[1]
    payload = read_payload()

    try:
        if method.startswith("watcher_"):
            from watcher_bridge import handle_watcher_method

            result = handle_watcher_method(method, payload)
            write_result({"ok": True, "data": result})

        api = Api()

        if method == "search":
            result = api.get_all_album_data(
                payload.get("keyword", ""),
                int(payload.get("page", 1)),
                int(payload.get("limit", 1)),
                str(payload.get("sort_by", "default")),
                str(payload.get("sort_dir", "desc")),
                bool(payload.get("hidden_only", False)),
                str(payload.get("match_mode", "site")),
                str(payload.get("site_base", "")),
            )
            write_result({"ok": True, "data": result})

        if method == "explore":
            result = api.get_explore(
                int(payload.get("page", 1)),
                int(payload.get("limit", 1)),
                bool(payload.get("new", False)),
                str(payload.get("sort_by", "default")),
                str(payload.get("sort_dir", "desc")),
                bool(payload.get("hidden_only", False)),
                str(payload.get("site_base", "")),
            )
            write_result({"ok": True, "data": result})

        if method == "album_content":
            result = api.get_album_content(str(payload.get("path", "")))
            write_result({"ok": True, "data": result})

        if method == "album_info":
            result = api.get_album_info(str(payload.get("path", "")))
            write_result({"ok": True, "data": result})

        if method == "album_metadata":
            result = api.get_album_metadata(str(payload.get("path", "")))
            write_result({"ok": True, "data": result})

        if method == "profile":
            result = api.get_profile_info(
                str(payload.get("profile", "")),
                int(payload.get("page", 1)),
                int(payload.get("limit", 1)),
                str(payload.get("sort_by", "default")),
                str(payload.get("sort_dir", "desc")),
                bool(payload.get("hidden_only", False)),
                str(payload.get("content", "albums")),
                str(payload.get("site_base", "")),
            )
            write_result({"ok": True, "data": result})

        if method == "profile_reposts":
            result = api.get_profile_reposts(
                str(payload.get("profile", "")),
                int(payload.get("page", 1)),
                int(payload.get("limit", 1)),
                str(payload.get("sort_by", "default")),
                str(payload.get("sort_dir", "desc")),
                bool(payload.get("hidden_only", False)),
                str(payload.get("site_base", "")),
            )
            write_result({"ok": True, "data": result})

        if method == "version":
            version = str(payload.get("version", "all"))
            result = api.change_version_content(version)
            write_result({"ok": True, "data": {"version": version, "changed": result}})

        if method == "download_album":
            result = api.download_album(
                path=str(payload.get("path", "")),
                directory=str(payload.get("directory", "Downloads")),
                include_photos=bool(payload.get("include_photos", True)),
                include_videos=bool(payload.get("include_videos", True)),
                overwrite=bool(payload.get("overwrite", False)),
                max_workers=int(payload.get("max_workers", 4)),
                skip_urls=payload.get("skip_urls") if isinstance(payload.get("skip_urls"), list) else None,
                retry_until_done=bool(payload.get("retry_until_done", False)),
                retry_delay=float(payload.get("retry_delay", 0.5)),
            )
            write_result({"ok": True, "data": result})

        if method == "download_album_progress":
            result = api.download_album(
                path=str(payload.get("path", payload.get("url", ""))),
                directory=str(payload.get("directory", "Downloads")),
                include_photos=bool(payload.get("include_photos", True)),
                include_videos=bool(payload.get("include_videos", True)),
                overwrite=bool(payload.get("overwrite", False)),
                max_workers=int(payload.get("max_workers", 4)),
                skip_urls=payload.get("skip_urls") if isinstance(payload.get("skip_urls"), list) else None,
                retry_until_done=True,
                retry_delay=float(payload.get("retry_delay", 0.5)),
                progress_callback=write_progress,
            )
            write_result({"ok": True, "data": result})

        if method == "download_media":
            result = api.download_media(
                url=str(payload.get("url", "")),
                directory=str(payload.get("directory", "Downloads")),
                filename=str(payload.get("filename", "")),
                overwrite=bool(payload.get("overwrite", False)),
                retry_until_done=bool(payload.get("retry_until_done", False)),
                retry_delay=float(payload.get("retry_delay", 0.5)),
            )
            write_result({"ok": True, "data": result})

        if method == "download_media_progress":
            result = api.download_media(
                url=str(payload.get("url", "")),
                directory=str(payload.get("directory", "Downloads")),
                filename=str(payload.get("filename", "")),
                overwrite=bool(payload.get("overwrite", False)),
                retry_until_done=True,
                retry_delay=float(payload.get("retry_delay", 0.5)),
                progress_callback=write_progress,
            )
            write_result({"ok": True, "data": result})

        if method == "content":
            url = str(payload.get("url", ""))
            max_video_bytes = int(payload.get("max_video_bytes", 0))
            blob = api.get_content(url, max_video_bytes=max_video_bytes)
            content_type = mimetypes.guess_type(url.split("?", 1)[0])[0] or "application/octet-stream"
            write_result(
                {
                    "ok": True,
                    "data": {
                        "content_type": content_type,
                        "bytes_base64": base64.b64encode(blob).decode("ascii"),
                    },
                }
            )

        if method == "diagnostics":
            checks = [
                "https://www.erome.com/",
                "https://www.erome.com/explore",
                "https://www.erome.com/a/RHoERFQP",
            ]
            headers = getattr(api, "_Api__headers", {})
            timeout = int(getattr(api, "_Api__timeout", 20))
            results = []
            with requests.Session() as session:
                for target in checks:
                    item = {"url": target}
                    try:
                        response = session.get(target, headers=headers, timeout=timeout)
                        item["status_code"] = response.status_code
                        item["ok"] = 200 <= response.status_code <= 299
                        item["final_url"] = response.url
                        item["content_length"] = len(response.text or "")
                        text_lower = (response.text or "").lower()
                        item["possible_blocked"] = "cloudflare" in text_lower or "access denied" in text_lower
                    except Exception as exc:  # pylint: disable=broad-except
                        item["ok"] = False
                        item["error"] = str(exc)
                    results.append(item)

            write_result({"ok": True, "data": {"checks": results}})

        write_result({"ok": False, "error": f"Unknown method: {method}"}, 1)

    except Exception as exc:  # pylint: disable=broad-except
        write_result({"ok": False, "error": str(exc)}, 1)


if __name__ == "__main__":
    main()
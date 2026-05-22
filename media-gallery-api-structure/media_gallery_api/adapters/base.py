from __future__ import annotations

from urllib.parse import urlparse


def hostname(url: str) -> str:
    return urlparse(url).hostname or ''


def looks_like_gallery_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return '/gallery/' in path or '/album/' in path or path.count('/') >= 2

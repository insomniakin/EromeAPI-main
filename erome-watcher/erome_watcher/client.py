from __future__ import annotations

from datetime import datetime, timezone
import random
import re
import time
from typing import Optional
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .models import AlbumEntry, AlbumSnapshot, ProfileSnapshot


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _normalize_tag(value: str | None) -> str:
    cleaned = str(value or '').strip().lstrip('#').casefold()
    cleaned = re.sub(r'[^\w-]+', ' ', cleaned)
    return re.sub(r'\s+', ' ', cleaned).strip()


def _extract_hashtag_terms(value: str | None) -> list[str]:
    terms: list[str] = []
    for match in re.findall(r'#([\w-]+)', str(value or ''), re.I):
        tag = _normalize_tag(match)
        if tag and tag not in terms:
            terms.append(tag)
    return terms


def _site_search_query(value: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'#(?=[\w-])', '', str(value or '')).strip())


def _metadata_matches_hashtags(tags: list[str], description: str | None, hashtag_terms: list[str]) -> bool:
    tag_terms = {_normalize_tag(tag) for tag in tags if _normalize_tag(tag)}
    description_terms = set(_extract_hashtag_terms(description))
    metadata_terms = tag_terms | description_terms
    return all(term in metadata_terms for term in hashtag_terms)


class EromeClient:
    def __init__(self, base_url: str = "https://www.erome.com", timeout: float = 30.0, max_retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _fetch_html(self, url: str) -> str:
        last_exc: Exception | None = None
        with httpx.Client(timeout=self.timeout, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
            for attempt in range(self.max_retries):
                response = client.get(url)
                if response.status_code != 429:
                    response.raise_for_status()
                    return response.text
                last_exc = httpx.HTTPStatusError(
                    f"Rate limited while fetching {url}", request=response.request, response=response
                )
                if attempt < self.max_retries - 1:
                    delay = min(6.0, (1.4 ** attempt) + random.uniform(0.3, 1.2))
                    time.sleep(delay)
            if last_exc is not None:
                raise last_exc
            raise RuntimeError(f"Failed to fetch HTML for {url}")

    def _normalize_profile_url(self, username: str) -> str:
        if username.startswith('http://') or username.startswith('https://'):
            return username
        return f"{self.base_url}/{username.lstrip('/')}?t=posts"

    def _album_entry_from_anchor(self, anchor, base_url: str, username_hint: str, source: str) -> Optional[AlbumEntry]:
        href = anchor.get('href') or ''
        absolute = urljoin(base_url, href)
        if '/a/' not in absolute:
            return None

        card = anchor
        while getattr(card, 'parent', None) is not None:
            card = card.parent
            classes = card.get('class') or []
            if 'album' in classes:
                break

        title = None
        if 'album-title' in (anchor.get('class') or []):
            title = anchor.get_text(' ', strip=True)
        if not title and getattr(card, 'select_one', None):
            title_node = card.select_one('.album-title')
            if title_node:
                title = title_node.get_text(' ', strip=True)
        if not title:
            title = anchor.get_text(' ', strip=True)
        if not title:
            img = anchor.select_one('img[alt]')
            title = img.get('alt', '').strip() if img else ''
        if not title:
            title = absolute.rsplit('/', 1)[-1]

        img = anchor.select_one('img')
        thumbnail_url = urljoin(base_url, img.get('src')) if img and img.get('src') else None
        album_id = absolute.rstrip('/').rsplit('/', 1)[-1]

        published_text = None
        if getattr(card, 'select_one', None):
            published_node = card.select_one('.album-user, .album-date, .album-published')
            if published_node:
                published_text = published_node.get_text(' ', strip=True)

        views_text = None
        if getattr(card, 'select_one', None):
            views_node = card.select_one('.album-bottom-views, .album-views')
            if views_node:
                views_text = views_node.get_text(' ', strip=True)

        tags: list[str] = []
        if getattr(card, 'select', None):
            for tag_node in card.select('a[href*="/search"], a[href*="/tag/"], .tag, [class*="tag"]'):
                tag = _normalize_tag(tag_node.get_text(' ', strip=True))
                if tag and tag not in tags and len(tag) <= 64:
                    tags.append(tag)

        username = username_hint.split('?', 1)[0].strip('/').split('/')[-1]
        return AlbumEntry(
            id=album_id,
            title=title,
            url=absolute,
            username=username,
            thumbnail_url=thumbnail_url,
            published_text=published_text,
            views_text=views_text,
            tags=tags,
            source=source,
        )

    def _enrich_album_entry(self, album: AlbumEntry) -> AlbumEntry:
        try:
            snapshot = self.get_album_snapshot(album.url)
        except Exception:
            return album

        return album.model_copy(
            update={
                'tags': snapshot.tags,
                'description': snapshot.description,
                'media_count': len(snapshot.media_urls),
            }
        )

    def get_profile_snapshot(self, username: str, enrich_albums: bool = False, max_enrich: int = 24) -> ProfileSnapshot:
        profile_url = self._normalize_profile_url(username)
        html = self._fetch_html(profile_url)
        soup = BeautifulSoup(html, "html.parser")

        albums: list[AlbumEntry] = []
        seen_urls: set[str] = set()

        for anchor in soup.select('a.album-link[href], a[href*="/a/"]'):
            album = self._album_entry_from_anchor(anchor, profile_url, username, 'profile')
            if not album or album.url in seen_urls:
                continue
            seen_urls.add(album.url)
            albums.append(album)

        if enrich_albums:
            limit = max(0, max_enrich)
            albums = [self._enrich_album_entry(album) if index < limit else album for index, album in enumerate(albums)]

        return ProfileSnapshot(
            username=username.split('?', 1)[0].strip('/').split('/')[-1],
            profile_url=profile_url,
            fetched_at=self._now(),
            album_count=len(albums),
            albums=albums,
        )

    def search_public(self, query: str, page: int = 1) -> ProfileSnapshot:
        hashtag_terms = _extract_hashtag_terms(query)
        search_query = _site_search_query(query) if hashtag_terms else query
        search_url = f"{self.base_url}/search?q={quote_plus(search_query)}&page={max(1, page)}"
        html = self._fetch_html(search_url)
        soup = BeautifulSoup(html, "html.parser")

        albums: list[AlbumEntry] = []
        seen_urls: set[str] = set()
        username_hint = f"search:{query}"
        for anchor in soup.select('a.album-link[href], a.album-title[href], a[href*="/a/"]'):
            album = self._album_entry_from_anchor(anchor, search_url, username_hint, 'search')
            if not album or album.url in seen_urls:
                continue
            seen_urls.add(album.url)
            if hashtag_terms:
                album = self._enrich_album_entry(album)
                if not _metadata_matches_hashtags(album.tags, album.description, hashtag_terms):
                    continue
            albums.append(album)

        return ProfileSnapshot(
            username=username_hint,
            profile_url=search_url,
            fetched_at=self._now(),
            album_count=len(albums),
            albums=albums,
        )

    def get_explore_snapshot(self, page: int = 1) -> ProfileSnapshot:
        explore_url = f"{self.base_url}/explore?page={max(1, page)}"
        html = self._fetch_html(explore_url)
        soup = BeautifulSoup(html, "html.parser")

        albums: list[AlbumEntry] = []
        seen_urls: set[str] = set()
        for anchor in soup.select('a.album-link[href], a.album-title[href], a[href*="/a/"]'):
            album = self._album_entry_from_anchor(anchor, explore_url, 'explore', 'explore')
            if not album or album.url in seen_urls:
                continue
            seen_urls.add(album.url)
            albums.append(album)

        return ProfileSnapshot(
            username=f'explore:{page}',
            profile_url=explore_url,
            fetched_at=self._now(),
            album_count=len(albums),
            albums=albums,
        )

    def get_album_snapshot(self, album_url: str) -> AlbumSnapshot:
        html = self._fetch_html(album_url)
        soup = BeautifulSoup(html, 'html.parser')

        title = None
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        h1 = soup.select_one('h1')
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(' ', strip=True)

        description = None
        meta_desc = soup.select_one('meta[name="description"]')
        if meta_desc and meta_desc.get('content'):
            description = meta_desc.get('content').strip()

        media_urls: list[str] = []
        for node in soup.select('video source[src], video[src], img[src], a[href]'):
            src = node.get('src') or node.get('href')
            if not src:
                continue
            absolute = urljoin(album_url, src)
            if not absolute.startswith('http'):
                continue
            if any(token in absolute.lower() for token in ['/static/', '/css/', '/js/', 'favicon', 'manifest.json']):
                continue
            if any(ext in absolute.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.mp4', '.m3u8', '.webm']):
                if absolute not in media_urls:
                    media_urls.append(absolute)

        tags: list[str] = []
        for a in soup.select('a[href*="/search"], a[href*="/tag/"]'):
            candidates = [a.get_text(' ', strip=True)]
            href = a.get('href') or ''
            parsed = urlparse(href)
            if '/tag/' in parsed.path:
                candidates.append(parsed.path.rstrip('/').rsplit('/', 1)[-1])
            if parsed.path.rstrip('/').endswith('/search') and parsed.query:
                candidates.extend(parse_qs(parsed.query).get('q', []))
            for candidate in candidates:
                tag = _normalize_tag(candidate)
                if tag and tag not in tags and len(tag) <= 64:
                    tags.append(tag)

        for tag in _extract_hashtag_terms(description):
            if tag not in tags:
                tags.append(tag)

        username = None
        for a in soup.select('a[href]'):
            href = a.get('href') or ''
            absolute = urljoin(album_url, href)
            if not absolute.startswith(self.base_url + '/'):
                continue
            path = urlparse(absolute).path.strip('/')
            if not path or '/' in path or path in {'explore', 'user', 's', 'search', 'tag'}:
                continue
            username = path
            break

        return AlbumSnapshot(
            album_url=album_url,
            fetched_at=self._now(),
            title=title,
            username=username,
            description=description,
            media_urls=media_urls,
            tags=tags,
        )

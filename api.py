import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


class Api:
    def __init__(self) -> None:
        self.__session = requests.Session()
        self.__headers = {
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "referer": "https://www.erome.com/",
            "cache-control": "no-cache",
            "pragma": "no-cache",
        }
        self.__media_pattern = re.compile(r"^https?://([sv]\d+\.erome\.com)(/[^\s]*)?(\?[^#\s]*)?$", re.I)
        self.__reddit_media_pattern = re.compile(
            r"^https?://((?:i|preview|external-preview|v)\.redd\.it)(/[^\s]*)?(\?[^#\s]*)?$",
            re.I,
        )
        self.__version_list = {"all", "straight", "trans", "gay", "hentai"}
        self.__base_url = "https://www.erome.com"
        self.__timeout = 20

    def __normalize_text(self, value: str) -> str:
        return re.sub(r"\s{2,}", " ", value.strip())

    def __normalize_tag(self, value: str) -> str:
        cleaned = str(value or "").strip().lstrip("#").casefold()
        cleaned = re.sub(r"[^\w-]+", " ", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    def __extract_hashtag_terms(self, value: str, allow_multi_word: bool = True) -> List[str]:
        terms: List[str] = []
        pattern = r"#([^#,;\n\r]+)" if allow_multi_word else r"#([\w-]+)"
        for match in re.findall(pattern, str(value or ""), re.I):
            tag = self.__normalize_tag(match)
            if tag and tag not in terms:
                terms.append(tag)
        return terms

    def __normalize_match_mode(self, value: str) -> str:
        mode = self.__normalize_tag(str(value or "site")).replace(" ", "_")
        aliases = {
            "": "site",
            "site": "site",
            "default": "site",
            "legacy": "site",
            "exact": "exact",
            "exact_phrase": "exact",
            "phrase": "exact",
            "any": "any",
            "some": "any",
            "some_keywords": "any",
            "all": "all",
            "all_keywords": "all",
            "and": "all",
            "combo": "combo",
            "only_combo": "combo",
            "only_this_combo": "combo",
        }
        normalized = aliases.get(mode)
        if normalized is None:
            raise ValueError("'match_mode' should be one of site, exact, any, all, or combo.")
        return normalized

    def __extract_plain_keyword_terms(self, value: str) -> List[str]:
        without_hashtags = re.sub(r"#[^#,;\n\r]+", " ", str(value or ""))
        terms: List[str] = []
        for raw_term in re.split(r"[,;\n\r\s]+", without_hashtags):
            term = self.__normalize_tag(raw_term)
            if term and term not in terms:
                terms.append(term)
        return terms

    def __plain_search_phrase(self, value: str) -> str:
        without_hashtags = re.sub(r"#[^#,;\n\r]+", " ", str(value or ""))
        return self.__normalize_tag(without_hashtags)

    def __search_keyword_for_site(self, value: str) -> str:
        return self.__normalize_text(re.sub(r"[,;\n\r]+", " ", str(value or "")))

    def __safe_get(self, url: str, headers: Optional[Dict[str, str]] = None) -> requests.Response:
        final_headers = headers if headers is not None else self.__headers
        return self.__session.get(url, headers=final_headers, timeout=self.__timeout)

    def __normalize_media_url(self, url: str) -> str:
        media_url = self.__normalize_text(url)
        if media_url.startswith("//"):
            media_url = f"https:{media_url}"
        if not self.__media_pattern.search(media_url) and not self.__reddit_media_pattern.search(media_url):
            raise ValueError("'url' must match the erome or reddit media host pattern.")
        return media_url

    def __media_request_headers(self, media_url: str, max_video_bytes: int = 0) -> Dict[str, str]:
        match = self.__media_pattern.search(media_url)
        reddit_match = self.__reddit_media_pattern.search(media_url)
        if not match and not reddit_match:
            raise ValueError("'url' must match the erome or reddit media host pattern.")

        if reddit_match:
            headers = {
                "host": reddit_match.group(1).lower(),
                "connection": "keep-alive",
                "user-agent": self.__headers["user-agent"],
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "referer": "https://www.reddit.com/",
                "origin": "https://www.reddit.com",
            }
            if max_video_bytes > 1:
                headers["range"] = f"bytes=0-{max_video_bytes - 1}"
            return headers

        host = match.group(1).lower()
        common_headers = {
            "host": host,
            "connection": "keep-alive",
            "user-agent": self.__headers["user-agent"],
            "accept-language": "en-US,en;q=0.9",
            "referer": f"{self.__base_url}/",
            "origin": self.__base_url,
        }
        if host.startswith("s"):
            return {
                **common_headers,
                "sec-ch-ua-platform": "Android",
                "sec-ch-ua": "Google Chrome;v=131, Chromium;v=131, Not_A Brand;v=24",
                "sec-ch-ua-mobile": "?1",
                "accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "sec-fetch-site": "same-site",
                "sec-fetch-mode": "no-cors",
                "sec-fetch-dest": "image",
                "accept-encoding": "gzip, deflate, br, zstd",
                "priority": "i",
            }

        headers = {
            **common_headers,
            "sec-ch-ua-platform": "Android",
            "accept-encoding": "identity;q=1, *;q=0",
            "sec-ch-ua": "Google Chrome;v=131, Chromium;v=131, Not_A Brand;v=24",
            "sec-ch-ua-mobile": "?1",
            "accept": "*/*",
            "sec-fetch-site": "same-site",
            "sec-fetch-mode": "no-cors",
            "sec-fetch-dest": "video",
        }
        if max_video_bytes > 1:
            headers["range"] = f"bytes=0-{max_video_bytes - 1}"
        return headers

    def __response_content_length(self, response: requests.Response) -> int:
        try:
            return int(response.headers.get("content-length") or 0)
        except (TypeError, ValueError, AttributeError):
            return 0

    def __progress_fraction(self, downloaded_bytes: int, total_bytes: int, previous_fraction: float = 0.0) -> float:
        if total_bytes > 0:
            return min(1.0, max(0.0, downloaded_bytes / total_bytes))
        return min(0.95, max(previous_fraction + 0.01, 0.01))

    def __write_media_to_file(
        self,
        media_url: str,
        file_path: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        headers = self.__media_request_headers(media_url)
        response = self.__session.get(media_url, headers=headers, timeout=self.__timeout, stream=True)
        try:
            if response.status_code < 200 or response.status_code > 207:
                raise RuntimeError("Invalid or expired 'url'.")

            total_bytes = self.__response_content_length(response)
            downloaded_bytes = 0
            chunks = response.iter_content(chunk_size=1024 * 256) if hasattr(response, "iter_content") else [response.content]
            with file_path.open("wb") as media_file:
                for chunk in chunks:
                    if not chunk:
                        continue
                    media_file.write(chunk)
                    downloaded_bytes += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded_bytes, total_bytes)
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

    def __absolute_url(self, url: str) -> str:
        return urljoin(self.__base_url, url)

    def __absolute_media_url(self, url: Optional[str]) -> Optional[str]:
        if not url:
            return url
        return self.__absolute_url(url.strip())

    def __sanitize_filename(self, value: str, fallback: str = "Untitled") -> str:
        cleaned = re.sub(r'[<>:"/\\|?*]', "", value)
        cleaned = self.__normalize_text(cleaned)
        return cleaned or fallback

    def __extract_album_title(self, soup: BeautifulSoup) -> str:
        selectors = [
            ("meta", {"property": "og:title", "content": True}),
            ("meta", {"name": "twitter:title", "content": True}),
        ]
        for name, attrs in selectors:
            tag = soup.find(name, attrs)
            if tag and tag.get("content"):
                return self.__sanitize_filename(tag["content"])

        heading = soup.find(["h1", "h2"])
        if heading:
            return self.__sanitize_filename(heading.get_text(" ", strip=True))

        title = soup.find("title")
        if title:
            title_text = title.get_text(" ", strip=True).split(" - ")[0]
            return self.__sanitize_filename(title_text)

        return "Untitled"

    def __extract_username(self, soup: BeautifulSoup) -> str:
        user_tag = soup.find("a", id="user_name") or soup.find("a", class_="user")
        if user_tag:
            username = self.__sanitize_filename(user_tag.get_text(" ", strip=True), fallback="Unknown")
            if username:
                return username

        author = soup.find("meta", {"name": "author", "content": True})
        if author and author.get("content"):
            return self.__sanitize_filename(author["content"], fallback="Unknown")

        title = soup.find("title")
        if title:
            title_text = title.get_text(" ", strip=True)
            if " - " in title_text and "'s albums" in title_text:
                username = title_text.split(" - ", 1)[1].replace("'s albums", "")
                return self.__sanitize_filename(username, fallback="Unknown")

        return "Unknown"

    def __parse_abbrev_number(self, text: str) -> int:
        match = re.search(r"(\d[\d,.]*)(\s*[KMB])?", str(text or ""), re.I)
        if not match:
            return 0
        value = float(match.group(1).replace(",", ""))
        unit = (match.group(2) or "").strip().upper()
        if unit == "K":
            value *= 1_000
        elif unit == "M":
            value *= 1_000_000
        elif unit == "B":
            value *= 1_000_000_000
        return round(value)

    def __parse_duration_text(self, text: str) -> int:
        parts = [int(part) for part in re.findall(r"\d+", str(text or ""))]
        if len(parts) >= 3:
            return parts[-3] * 3600 + parts[-2] * 60 + parts[-1]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        return parts[0] if parts else 0

    def __extract_tags_from_node(self, node: Any) -> List[str]:
        tags: List[str] = []
        if not getattr(node, "select", None):
            return tags

        for tag_node in node.select('a[href*="/search"], a[href*="/tag/"], .tag, [class*="tag"]'):
            text = tag_node.get_text(" ", strip=True)
            href = tag_node.get("href") or ""
            candidates = [text]
            parsed_href = urlparse(href)
            if "/tag/" in parsed_href.path:
                candidates.append(parsed_href.path.rstrip("/").split("/")[-1])
            if parsed_href.path.rstrip("/").endswith("/search") and parsed_href.query:
                candidates.extend(parse_qs(parsed_href.query).get("q", []))
            for candidate in candidates:
                tag = self.__normalize_tag(candidate)
                if tag and tag not in tags and len(tag) <= 64:
                    tags.append(tag)
        return tags

    def __extract_description(self, soup: BeautifulSoup) -> str:
        for selector in ['meta[name="description"]', 'meta[property="og:description"]', 'meta[name="twitter:description"]']:
            tag = soup.select_one(selector)
            if tag and tag.get("content"):
                return self.__normalize_text(tag["content"])
        description = soup.select_one(".description, .album-description, [class*='description']")
        return self.__normalize_text(description.get_text(" ", strip=True)) if description else ""

    def __album_detail_metadata(self, album_url: str) -> Dict[str, Any]:
        response = self.__safe_get(album_url)
        if response.status_code < 200 or response.status_code > 207:
            return {"description": "", "tags": []}
        soup = BeautifulSoup(response.text, "html.parser")
        description = self.__extract_description(soup)
        tags = self.__extract_tags_from_node(soup)
        for tag in self.__extract_hashtag_terms(description, allow_multi_word=False):
            if tag not in tags:
                tags.append(tag)
        return {"description": description, "tags": tags}

    def __album_matches_hashtags(self, album: Dict[str, Any], hashtag_terms: List[str]) -> bool:
        metadata_terms = self.__album_metadata_terms(album)
        return all(term in metadata_terms for term in hashtag_terms)

    def __album_metadata_terms(self, album: Dict[str, Any]) -> set:
        tag_terms = {self.__normalize_tag(tag) for tag in album.get("tags", []) if self.__normalize_tag(str(tag))}
        description_hashtags = set(self.__extract_hashtag_terms(str(album.get("description") or ""), allow_multi_word=False))
        return tag_terms | description_hashtags

    def __album_search_text(self, album: Dict[str, Any]) -> str:
        terms = [
            album.get("title"),
            album.get("url"),
            album.get("username"),
            album.get("description"),
            album.get("visibility"),
            *(album.get("tags", []) if isinstance(album.get("tags"), list) else []),
            *(album.get("matched_hashtags", []) if isinstance(album.get("matched_hashtags"), list) else []),
        ]
        return self.__normalize_tag(" ".join(str(term or "") for term in terms))

    def __album_matches_search_mode(
        self,
        album: Dict[str, Any],
        keyword_terms: List[str],
        hashtag_terms: List[str],
        exact_phrase: str,
        match_mode: str,
    ) -> bool:
        search_text = self.__album_search_text(album)
        metadata_terms = self.__album_metadata_terms(album)
        plain_matches = [term for term in keyword_terms if term in search_text]
        hashtag_matches = [term for term in hashtag_terms if term in metadata_terms]

        album["matched_keywords"] = plain_matches
        if hashtag_terms:
            album["matched_hashtags"] = hashtag_matches

        if match_mode == "exact":
            plain_ok = not exact_phrase or exact_phrase in search_text
            hashtag_ok = all(term in metadata_terms for term in hashtag_terms)
            return plain_ok and hashtag_ok

        if match_mode == "any":
            requested_count = len(keyword_terms) + len(hashtag_terms)
            if requested_count == 0:
                return True
            return bool(plain_matches or hashtag_matches)

        if match_mode == "combo":
            plain_ok = all(term in search_text for term in keyword_terms)
            if hashtag_terms:
                return plain_ok and all(term in metadata_terms for term in hashtag_terms)
            return plain_ok

        plain_ok = all(term in search_text for term in keyword_terms)
        hashtag_ok = all(term in metadata_terms for term in hashtag_terms)
        return plain_ok and hashtag_ok

    def __enrich_album_results(self, albums: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched_albums: List[Dict[str, Any]] = []
        for album in albums:
            enriched = dict(album)
            try:
                metadata = self.__album_detail_metadata(str(album.get("url") or ""))
            except Exception:  # noqa: BLE001 - strict hashtag search drops unverifiable albums
                metadata = {"description": "", "tags": []}
            enriched["description"] = metadata.get("description", "")
            enriched["tags"] = metadata.get("tags", [])
            enriched_albums.append(enriched)
        return enriched_albums

    def __enrich_and_filter_hashtag_results(self, albums: List[Dict[str, Any]], hashtag_terms: List[str]) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []
        for album in self.__enrich_album_results(albums):
            if self.__album_matches_hashtags(album, hashtag_terms):
                album["matched_hashtags"] = hashtag_terms
                filtered.append(album)
        return filtered

    def __extract_profile_path(self, profile_or_url: str) -> str:
        value = self.__normalize_text(profile_or_url).strip("/@")
        parsed = urlparse(value)
        if parsed.scheme and parsed.netloc:
            parts = parsed.path.strip("/").split("/")
            value = parts[0] if parts and parts[0] else ""
        reserved = {"", "a", "album", "explore", "search", "version", "user"}
        if value.lower() in reserved:
            raise ValueError("Expected a public profile username or URL.")
        return value

    def __normalize_profile_content(self, content: str) -> str:
        value = self.__normalize_text(str(content or "albums")).lower()
        aliases = {
            "": "albums",
            "album": "albums",
            "albums": "albums",
            "post": "albums",
            "posts": "albums",
            "upload": "albums",
            "uploads": "albums",
            "repost": "reposts",
            "reposts": "reposts",
        }
        if value not in aliases:
            raise ValueError("'content' should be one of albums or reposts.")
        return aliases[value]

    def __profile_page_url(self, profile_url: str, page: int, content: str) -> str:
        params: Dict[str, Any] = {}
        if content == "reposts":
            params["t"] = "reposts"
        if page != 1:
            params["page"] = page
        return profile_url if not params else f"{profile_url}?{urlencode(params)}"

    def __extract_album_card_counts(self, card: Any) -> Dict[str, int]:
        image_text = " ".join(node.get_text(" ", strip=True) for node in card.select(".album-images, [class*='image']"))
        video_text = " ".join(node.get_text(" ", strip=True) for node in card.select(".album-videos, [class*='video']"))
        view_text = " ".join(node.get_text(" ", strip=True) for node in card.select(".album-views, .views, [class*='views'], [class*='view']"))
        duration_text = " ".join(
            (node.get_text(" ", strip=True) or node.get("title") or node.get("data-duration") or "")
            for node in card.select(".duration, [class*='duration'], time, [data-duration]")
        )
        card_text = card.get_text(" ", strip=True)
        if not view_text:
            view_match = re.search(r"(\d[\d,.]*\s*[KMB]?)\s+views?\b", card_text, re.I)
            view_text = view_match.group(0) if view_match else ""
        if not duration_text:
            duration_match = re.search(r"\b(?:\d{1,2}:)?\d{1,2}:\d{2}\b", card_text)
            duration_text = duration_match.group(0) if duration_match else ""
        class_text = " ".join(str(item) for item in (card.get("class") or []))
        hidden_marker = re.search(r"\b(hidden|unlisted|private)\b", f"{class_text} {card_text}", re.I) is not None
        return {
            "images": self.__parse_abbrev_number(image_text),
            "videos": self.__parse_abbrev_number(video_text),
            "views": self.__parse_abbrev_number(view_text),
            "duration_seconds": self.__parse_duration_text(duration_text),
            "is_hidden": hidden_marker,
        }

    def __sort_and_filter_albums(
        self,
        albums: List[Dict[str, Any]],
        sort_by: str = "default",
        sort_dir: str = "desc",
        hidden_only: bool = False,
    ) -> List[Dict[str, Any]]:
        sort_aliases = {
            "": "default",
            "default": "default",
            "relevance": "default",
            "views": "views",
            "video_length": "duration_seconds",
            "duration": "duration_seconds",
            "duration_seconds": "duration_seconds",
            "videos": "videos",
            "photos": "images",
            "images": "images",
            "title": "title",
        }
        normalized_sort = sort_aliases.get(self.__normalize_text(str(sort_by or "default")).lower())
        if normalized_sort is None:
            raise ValueError("'sort_by' should be one of default, views, video_length, videos, photos, title.")
        direction = self.__normalize_text(str(sort_dir or "desc")).lower()
        if direction not in {"asc", "desc"}:
            raise ValueError("'sort_dir' should be 'asc' or 'desc'.")

        filtered = [album for album in albums if not hidden_only or bool(album.get("is_hidden"))]
        if normalized_sort == "default":
            return filtered

        reverse = direction == "desc"
        if normalized_sort == "title":
            return sorted(filtered, key=lambda album: str(album.get("title") or "").lower(), reverse=reverse)
        return sorted(
            filtered,
            key=lambda album: (int(album.get(normalized_sort) or 0), str(album.get("title") or "").lower()),
            reverse=reverse,
        )

    def __extract_profile_albums(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        root = soup.find("div", id="albums") or soup
        albums: List[Dict[str, Any]] = []
        seen_urls = set()

        for card in root.select("div.album, article.album, .album-card, [class*='album']"):
            link = card.select_one("a.album-link[href*='/a/']") or card.select_one("a[href*='/a/']")
            if not link:
                continue

            href = (link.get("href") or "").strip()
            if not href:
                continue

            album_url = self.__absolute_url(href)
            if album_url in seen_urls:
                continue

            title_node = card.select_one("a.album-title") or card.select_one(".album-title") or link
            title = self.__normalize_text(title_node.get_text(" ", strip=True)) or album_url.rstrip("/").split("/")[-1]
            thumb = card.select_one("img.album-thumbnail") or card.select_one("img")
            thumb_url = ""
            if thumb:
                thumb_url = (thumb.get("data-src") or thumb.get("src") or thumb.get("data-original") or "").strip()

            counts = self.__extract_album_card_counts(card)
            albums.append(
                {
                    "title": title,
                    "url": album_url,
                    "thumb": self.__absolute_media_url(thumb_url) or "",
                    "images": counts["images"],
                    "videos": counts["videos"],
                    "views": counts["views"],
                    "duration_seconds": counts["duration_seconds"],
                    "is_hidden": counts["is_hidden"],
                    "visibility": "hidden" if counts["is_hidden"] else "public",
                }
            )
            seen_urls.add(album_url)

        return albums

    def __extract_ordered_media(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        media: List[Dict[str, str]] = []
        seen = set()

        for tag in soup.find_all(["div", "img", "video"]):
            media_item: Optional[Dict[str, str]] = None
            if tag.name == "div" and "img" in (tag.get("class") or []):
                img_tag = tag.find("img")
                media_url = self.__absolute_media_url((img_tag.get("data-src") or img_tag.get("src") or "") if img_tag else "")
                if media_url:
                    media_item = {"type": "photo", "url": media_url}
            elif tag.name == "img" and not tag.find_parent("div", class_="img"):
                media_url = self.__absolute_media_url(tag.get("data-src") or tag.get("src") or "")
                if media_url and ".erome.com" in urlparse(media_url).netloc:
                    media_item = {"type": "photo", "url": media_url}
            elif tag.name == "video":
                source = tag.find("source")
                video_url = ""
                if source and source.get("src"):
                    video_url = source["src"].strip()
                elif tag.get("src"):
                    video_url = tag["src"].strip()

                video_url = self.__absolute_media_url(video_url)
                if video_url:
                    poster = tag.get("poster")
                    if not poster:
                        data_setup = tag.get("data-setup")
                        if data_setup:
                            match = re.search(r'"poster"\s*:\s*"([^"]+)"', data_setup)
                            poster = match.group(1) if match else None
                    media_item = {"type": "video", "url": video_url}
                    poster_url = self.__absolute_media_url(poster)
                    if poster_url:
                        media_item["thumb_url"] = poster_url

            if media_item and media_item["url"] not in seen:
                media.append(media_item)
                seen.add(media_item["url"])

        return media

    def __format_album_directory_name(self, title: str, slug: str, username: str, max_length: int = 200) -> str:
        suffix = f" ({slug}) [{username}]"
        available_title_length = max_length - len(suffix)
        if available_title_length <= 0:
            return self.__sanitize_filename(suffix.strip(), fallback=slug)[:max_length]
        if len(title) > available_title_length:
            title = f"{title[:max(0, available_title_length - 3)]}..."
        return f"{title}{suffix}"

    def __download_filename(self, title: str, media_url: str, file_number: int, total_files: int, max_length: int = 200) -> str:
        extension = Path(urlparse(media_url).path).suffix or ".bin"
        digits = len(str(total_files))
        number_part = f"({str(file_number).zfill(digits)})"
        base_name = self.__sanitize_filename(title)
        filename = f"{base_name} {number_part}{extension}"
        if len(filename) <= max_length:
            return filename

        required_length = len(number_part) + len(extension) + 1
        available_base_length = max_length - required_length
        if available_base_length > 5:
            base_name = f"{base_name[:available_base_length - 3]}..."
            return f"{base_name} {number_part}{extension}"
        return f"{number_part}{extension}"

    def __extract_album_path(self, path_or_url: str) -> str:
        value = self.__normalize_text(path_or_url)
        parsed = urlparse(value)
        if parsed.scheme and parsed.netloc:
            slug = parsed.path.strip("/").split("/")
            if len(slug) >= 2 and slug[0] == "a":
                return slug[1]
            raise ValueError("Invalid album URL path. Expected /a/<slug>.")
        return value.strip("/").split("/")[-1]

    def __get_album_data(self, page: int, keyword: str = "", new: Optional[bool] = None) -> List[Dict[str, Any]]:
        if not keyword:
            if new:
                url = f"{self.__base_url}/explore/new?page={page}"
            else:
                url = f"{self.__base_url}/explore?page={page}"
        else:
            query = urlencode({"q": keyword, "page": page})
            url = f"{self.__base_url}/search?{query}"

        response = self.__safe_get(url)
        if response.status_code < 200 or response.status_code > 207:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        album_root = soup.find("div", id="albums")
        search_root = album_root if album_root else soup

        content: List[Dict[str, str]] = []
        seen_urls = set()

        album_cards = search_root.select("div.album, article.album, .album-card, [class*='album']")
        if not album_cards and album_root:
            album_cards = album_root.find_all(recursive=False)

        for card in album_cards:
            link = card.select_one("a.album-link[href*='/a/']") or card.select_one("a[href*='/a/']")
            if not link:
                continue

            href = (link.get("href") or "").strip()
            if not href:
                continue

            full_url = self.__absolute_url(href)
            if full_url in seen_urls:
                continue

            title_node = card.select_one("a.album-title") or card.select_one(".album-title") or link
            title_text = self.__normalize_text(title_node.get_text(" ", strip=True)) if title_node else ""
            if not title_text:
                # Fallback to slug-based title when text nodes are missing in updated markup.
                title_text = full_url.rstrip("/").split("/")[-1]

            thumb = card.select_one("img.album-thumbnail") or card.select_one("img")
            thumb_url = ""
            if thumb:
                thumb_url = (thumb.get("data-src") or thumb.get("src") or thumb.get("data-original") or "").strip()

            counts = self.__extract_album_card_counts(card)
            tags = self.__extract_tags_from_node(card)
            content.append(
                {
                    "title": title_text,
                    "thumb": self.__absolute_media_url(thumb_url) or "",
                    "url": full_url,
                    "tags": tags,
                    "images": counts["images"],
                    "videos": counts["videos"],
                    "views": counts["views"],
                    "duration_seconds": counts["duration_seconds"],
                    "is_hidden": counts["is_hidden"],
                    "visibility": "hidden" if counts["is_hidden"] else "public",
                }
            )
            seen_urls.add(full_url)

        # Some pages include album links outside expected wrappers; use a final fallback sweep.
        if not content:
            for link in soup.select("a[href*='/a/']"):
                href = (link.get("href") or "").strip()
                if not href:
                    continue
                full_url = self.__absolute_url(href)
                if full_url in seen_urls:
                    continue
                title_text = self.__normalize_text(link.get_text(" ", strip=True)) or full_url.rstrip("/").split("/")[-1]
                content.append(
                    {
                        "title": title_text,
                        "thumb": "",
                        "url": full_url,
                        "tags": [],
                        "images": 0,
                        "videos": 0,
                        "views": 0,
                        "duration_seconds": 0,
                        "is_hidden": re.search(r"\b(hidden|unlisted|private)\b", title_text, re.I) is not None,
                        "visibility": "hidden" if re.search(r"\b(hidden|unlisted|private)\b", title_text, re.I) else "public",
                    }
                )
                seen_urls.add(full_url)

        return content

    def change_version_content(self, version: str) -> bool:
        if not isinstance(version, str):
            raise TypeError("'version' should be a string.")

        version = self.__normalize_text(version).lower()
        if version not in self.__version_list:
            raise ValueError(f"'version' should be one of {sorted(self.__version_list)}")

        url = f"{self.__base_url}/version/{version}"
        response = self.__safe_get(url)
        return 200 <= response.status_code <= 399

    def get_album_content(self, path: str) -> Dict[str, Any]:
        if not isinstance(path, str):
            raise TypeError("'path' should be a string.")

        content: Dict[str, Any] = {"videos": [], "photos": []}
        info = self.get_album_info(path)

        for media_item in info["media"]:
            if media_item["type"] == "photo":
                content["photos"].append(media_item["url"])
            elif media_item["type"] == "video":
                content["videos"].append(
                    {
                        "video_url": media_item["url"],
                        "thumb_url": media_item.get("thumb_url"),
                    }
                )
        return content

    def get_album_info(self, path: str) -> Dict[str, Any]:
        if not isinstance(path, str):
            raise TypeError("'path' should be a string.")

        slug = self.__extract_album_path(path)
        url = f"{self.__base_url}/a/{slug}"
        response = self.__safe_get(url)
        if response.status_code < 200 or response.status_code > 207:
            return {"slug": slug, "url": url, "title": "Untitled", "username": "Unknown", "media": []}

        soup = BeautifulSoup(response.text, "html.parser")
        return {
            "slug": slug,
            "url": url,
            "title": self.__extract_album_title(soup),
            "username": self.__extract_username(soup),
            "media": self.__extract_ordered_media(soup),
        }

    def get_content(self, url: str, max_video_bytes: int = 0) -> bytes:
        if not isinstance(url, str):
            raise TypeError("'url' should be a string.")
        if not isinstance(max_video_bytes, int):
            raise TypeError("'max_video_bytes' should be an integer.")
        if max_video_bytes < 0:
            raise ValueError("'max_video_bytes' cannot be negative.")

        url = self.__normalize_media_url(url)
        headers = self.__media_request_headers(url, max_video_bytes=max_video_bytes)

        response = self.__safe_get(url, headers=headers)
        if 200 <= response.status_code <= 207:
            return response.content

        raise RuntimeError("Invalid or expired 'url'.")

    def get_all_album_data(
        self,
        keyword: str,
        page: int = 1,
        limit: int = 1,
        sort_by: str = "default",
        sort_dir: str = "desc",
        hidden_only: bool = False,
        match_mode: str = "site",
    ) -> List[Dict[str, Any]]:
        if not isinstance(keyword, str):
            raise TypeError("'keyword' should be a string.")
        if not isinstance(page, int) or page <= 0:
            raise ValueError("'page' should be an integer greater than or equal to 1.")
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError("'limit' should be an integer greater than or equal to 1.")
        if not isinstance(hidden_only, bool):
            raise TypeError("'hidden_only' should be a bool value.")
        if page > limit:
            raise ValueError("'page' should not be greater than 'limit'.")

        keyword = self.__normalize_text(keyword)
        normalized_match_mode = self.__normalize_match_mode(match_mode)
        hashtag_terms = self.__extract_hashtag_terms(keyword)
        keyword_terms = self.__extract_plain_keyword_terms(keyword)
        exact_phrase = self.__plain_search_phrase(keyword)
        site_keyword = self.__search_keyword_for_site(keyword) if hashtag_terms else keyword
        content: List[Dict[str, Any]] = []
        while page <= limit:
            content.extend(self.__get_album_data(page, keyword=site_keyword))
            page += 1

        if normalized_match_mode == "site" and hashtag_terms:
            content = self.__enrich_and_filter_hashtag_results(content, hashtag_terms)

        if normalized_match_mode != "site":
            if hashtag_terms or normalized_match_mode == "combo":
                content = self.__enrich_album_results(content)
            content = [
                album for album in content
                if self.__album_matches_search_mode(album, keyword_terms, hashtag_terms, exact_phrase, normalized_match_mode)
            ]
        return self.__sort_and_filter_albums(content, sort_by=sort_by, sort_dir=sort_dir, hidden_only=hidden_only)

    def get_explore(
        self,
        page: int = 1,
        limit: int = 1,
        new: bool = False,
        sort_by: str = "default",
        sort_dir: str = "desc",
        hidden_only: bool = False,
    ) -> List[Dict[str, Any]]:
        if not isinstance(page, int) or page <= 0:
            raise ValueError("'page' should be an integer greater than or equal to 1.")
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError("'limit' should be an integer greater than or equal to 1.")
        if not isinstance(new, bool):
            raise TypeError("'new' should be a bool value.")
        if not isinstance(hidden_only, bool):
            raise TypeError("'hidden_only' should be a bool value.")
        if page > limit:
            raise ValueError("'page' should not be greater than 'limit'.")

        content: List[Dict[str, Any]] = []
        while page <= limit:
            content.extend(self.__get_album_data(page, new=new))
            page += 1
        return self.__sort_and_filter_albums(content, sort_by=sort_by, sort_dir=sort_dir, hidden_only=hidden_only)

    def get_profile_info(
        self,
        profile: str,
        page: int = 1,
        limit: int = 1,
        sort_by: str = "default",
        sort_dir: str = "desc",
        hidden_only: bool = False,
        content: str = "albums",
    ) -> Dict[str, Any]:
        if not isinstance(profile, str):
            raise TypeError("'profile' should be a string.")
        if not isinstance(page, int) or page <= 0:
            raise ValueError("'page' should be an integer greater than or equal to 1.")
        if not isinstance(limit, int) or limit < 0:
            raise ValueError("'limit' should be an integer greater than or equal to 0.")
        if not isinstance(hidden_only, bool):
            raise TypeError("'hidden_only' should be a bool value.")
        if limit > 0 and page > limit:
            raise ValueError("'page' should not be greater than 'limit'.")

        profile_content = self.__normalize_profile_content(content)
        profile_path = self.__extract_profile_path(profile)
        profile_url = f"{self.__base_url}/{profile_path}"
        username = profile_path
        avatar = ""
        bio = ""
        albums: List[Dict[str, Any]] = []
        seen_urls = set()

        crawl_until_empty = limit == 0
        final_page = page + 99 if crawl_until_empty else limit

        while page <= final_page:
            url = self.__profile_page_url(profile_url, page, profile_content)
            response = self.__safe_get(url)
            if response.status_code < 200 or response.status_code > 207:
                if crawl_until_empty:
                    break
                page += 1
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            if page == 1:
                name_tag = soup.select_one("#user_name, .user-name, .username, .profile-name, [itemprop='name']")
                if name_tag and name_tag.get_text(" ", strip=True):
                    username = self.__normalize_text(name_tag.get_text(" ", strip=True))
                avatar_tag = soup.select_one(".profile img, .user-profile img, .avatar img, img.avatar, img[src*='avatar']")
                if avatar_tag:
                    avatar = self.__absolute_media_url(
                        avatar_tag.get("data-src") or avatar_tag.get("src") or avatar_tag.get("data-original") or ""
                    ) or ""
                bio_tag = soup.select_one(".profile-about, .profile-description, .user-description, .bio, [class*='about']")
                if bio_tag:
                    bio = self.__normalize_text(bio_tag.get_text(" ", strip=True))

            added_this_page = 0
            for album in self.__extract_profile_albums(soup):
                if album["url"] in seen_urls:
                    continue
                albums.append(album)
                seen_urls.add(album["url"])
                added_this_page += 1
            if crawl_until_empty and added_this_page == 0:
                break
            page += 1

        albums = self.__sort_and_filter_albums(albums, sort_by=sort_by, sort_dir=sort_dir, hidden_only=hidden_only)

        return {
            "username": username,
            "url": self.__profile_page_url(profile_url, 1, profile_content),
            "content": profile_content,
            "avatar": avatar,
            "bio": bio,
            "albums": albums,
            "totals": {
                "albums": len(albums),
                "images": sum(album["images"] for album in albums),
                "videos": sum(album["videos"] for album in albums),
            },
        }

    def get_profile_reposts(
        self,
        profile: str,
        page: int = 1,
        limit: int = 1,
        sort_by: str = "default",
        sort_dir: str = "desc",
        hidden_only: bool = False,
    ) -> Dict[str, Any]:
        return self.get_profile_info(
            profile=profile,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_dir=sort_dir,
            hidden_only=hidden_only,
            content="reposts",
        )

    def get_album_metadata(self, path: str) -> Dict[str, Any]:
        if not isinstance(path, str):
            raise TypeError("'path' should be a string.")

        slug = self.__extract_album_path(path)
        url = f"{self.__base_url}/a/{slug}"
        response = self.__safe_get(url)
        if response.status_code < 200 or response.status_code > 207:
            return {
                "slug": slug,
                "url": url,
                "title": "Untitled",
                "username": "Unknown",
                "likes": 0,
                "views": 0,
                "durations": [],
                "total_duration_seconds": 0,
                "average_duration_seconds": 0,
                "media_count": {"photos": 0, "videos": 0, "total": 0},
            }

        soup = BeautifulSoup(response.text, "html.parser")
        media = self.__extract_ordered_media(soup)
        like_candidates = [
            soup.select_one("#like_count"),
            soup.select_one(".album-likes, .likes, [class*='like']"),
        ]
        likes = 0
        for candidate in like_candidates:
            likes = self.__parse_abbrev_number(candidate.get_text(" ", strip=True) if candidate else "")
            if likes:
                break

        view_candidates = [
            soup.select_one("#view_count"),
            soup.select_one(".album-views, .views, [class*='views']"),
        ]
        views = 0
        for candidate in view_candidates:
            views = self.__parse_abbrev_number(candidate.get_text(" ", strip=True) if candidate else "")
            if views:
                break

        durations: List[int] = []
        for duration_node in soup.select(".duration, [class*='duration']"):
            seconds = self.__parse_duration_text(
                duration_node.get_text(" ", strip=True) or duration_node.get("title") or duration_node.get("data-duration") or ""
            )
            if 0 < seconds < 86_400:
                durations.append(seconds)

        total_duration = sum(durations)
        average_duration = round(total_duration / len(durations)) if durations else 0
        photos = sum(1 for item in media if item["type"] == "photo")
        videos = sum(1 for item in media if item["type"] == "video")

        return {
            "slug": slug,
            "url": url,
            "title": self.__extract_album_title(soup),
            "username": self.__extract_username(soup),
            "likes": likes,
            "views": views,
            "durations": durations,
            "total_duration_seconds": total_duration,
            "average_duration_seconds": average_duration,
            "media_count": {"photos": photos, "videos": videos, "total": len(media)},
        }

    def download_album(
        self,
        path: str,
        directory: str = "Downloads",
        include_photos: bool = True,
        include_videos: bool = True,
        overwrite: bool = False,
        max_workers: int = 4,
        skip_urls: Optional[List[str]] = None,
        retry_until_done: bool = False,
        retry_delay: float = 0.5,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> List[Dict[str, str]]:
        if not isinstance(directory, str):
            raise TypeError("'directory' should be a string.")
        if not isinstance(include_photos, bool):
            raise TypeError("'include_photos' should be a bool value.")
        if not isinstance(include_videos, bool):
            raise TypeError("'include_videos' should be a bool value.")
        if not isinstance(overwrite, bool):
            raise TypeError("'overwrite' should be a bool value.")
        if not isinstance(max_workers, int) or max_workers <= 0:
            raise ValueError("'max_workers' should be an integer greater than or equal to 1.")
        if skip_urls is not None and not isinstance(skip_urls, list):
            raise TypeError("'skip_urls' should be a list of strings.")
        if not isinstance(retry_until_done, bool):
            raise TypeError("'retry_until_done' should be a bool value.")
        if not isinstance(retry_delay, (int, float)):
            raise TypeError("'retry_delay' should be a number.")
        if retry_delay < 0:
            raise ValueError("'retry_delay' cannot be negative.")

        skip_url_set = {self.__absolute_media_url(str(item)) for item in (skip_urls or []) if item}

        info = self.get_album_info(path)
        media = [
            item
            for item in info["media"]
            if (item["type"] == "photo" and include_photos) or (item["type"] == "video" and include_videos)
        ]
        if not media:
            return []

        album_directory = Path(directory) / self.__format_album_directory_name(info["title"], info["slug"], info["username"])
        album_directory.mkdir(parents=True, exist_ok=True)

        total_files = len(media)
        completed_files = 0
        progress_lock = threading.Lock()
        item_progress: Dict[str, float] = {}

        def emit_progress(
            event: str,
            media_item: Dict[str, str],
            filename: str,
            file_path: Path,
            status: str,
            attempts: int,
            error: Optional[str] = None,
            downloaded_bytes: Optional[int] = None,
            total_bytes: Optional[int] = None,
        ) -> None:
            nonlocal completed_files
            if not progress_callback:
                return
            with progress_lock:
                url = media_item.get("url", "")
                if event == "item_done":
                    completed_files += 1
                    item_progress.pop(url, None)
                elif event == "item_progress":
                    item_progress[url] = self.__progress_fraction(
                        int(downloaded_bytes or 0),
                        int(total_bytes or 0),
                        item_progress.get(url, 0.0),
                    )
                elif event == "retry":
                    item_progress.pop(url, None)
                elif event == "item_start":
                    item_progress[url] = 0.0
                active_fraction = sum(item_progress.values())
                percent = int(round(((completed_files + active_fraction) / total_files) * 100)) if total_files else 100
                payload: Dict[str, Any] = {
                    "event": event,
                    "type": media_item.get("type", "media"),
                    "url": url,
                    "filename": filename,
                    "path": str(file_path),
                    "status": status,
                    "attempts": attempts,
                    "completed": completed_files,
                    "total": total_files,
                    "percent": percent,
                }
                if downloaded_bytes is not None:
                    payload["downloaded_bytes"] = downloaded_bytes
                if total_bytes is not None:
                    payload["total_bytes"] = total_bytes
                if event == "item_progress":
                    payload["item_percent"] = int(round(item_progress.get(url, 0.0) * 100))
                if error:
                    payload["error"] = error
                progress_callback(payload)

        def download_media(index_and_item: Any) -> Dict[str, str]:
            index, media_item = index_and_item
            filename = self.__download_filename(info["title"], media_item["url"], index + 1, total_files)
            file_path = album_directory / filename
            status = "skipped"
            error = None
            attempts = 0
            max_attempts = 8
            emit_progress("item_start", media_item, filename, file_path, "pending", attempts)
            if not self.__media_pattern.search(media_item["url"] or ""):
                status = "skipped_unsupported_url"
            elif media_item["url"] in skip_url_set:
                status = "skipped_downloaded"
            elif not overwrite and file_path.exists():
                status = "skipped"
            else:
                while retry_until_done or attempts < max_attempts:
                    attempts += 1
                    try:
                        media_url = self.__normalize_media_url(media_item["url"])
                        self.__write_media_to_file(
                            media_url,
                            file_path,
                            lambda downloaded, total: emit_progress(
                                "item_progress",
                                media_item,
                                filename,
                                file_path,
                                "downloading",
                                attempts,
                                downloaded_bytes=downloaded,
                                total_bytes=total,
                            ),
                        )
                        status = "downloaded"
                        error = None
                        break
                    except Exception as exc:  # noqa: BLE001 - retry until done or exhausted
                        status = "error"
                        error = str(exc)
                        can_retry = retry_until_done or attempts < max_attempts
                        if can_retry:
                            emit_progress("retry", media_item, filename, file_path, "retrying", attempts, error)
                        else:
                            break
                        # Exponential-ish backoff capped at ~8s.
                        delay = min(8.0, retry_delay * (2 ** (attempts - 1)))
                        time.sleep(delay)
            result = {
                "type": media_item["type"],
                "url": media_item["url"],
                "filename": filename,
                "path": str(file_path),
                "status": status,
                "attempts": attempts,
            }
            if error:
                result["error"] = error
            emit_progress("item_done", media_item, filename, file_path, status, attempts, error)
            return result

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            return list(executor.map(download_media, enumerate(media)))

    def download_media(
        self,
        url: str,
        directory: str = "Downloads",
        filename: str = "",
        overwrite: bool = False,
        retry_until_done: bool = False,
        retry_delay: float = 0.5,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        if not isinstance(url, str):
            raise TypeError("'url' should be a string.")
        if not isinstance(directory, str):
            raise TypeError("'directory' should be a string.")
        if not isinstance(filename, str):
            raise TypeError("'filename' should be a string.")
        if not isinstance(overwrite, bool):
            raise TypeError("'overwrite' should be a bool value.")
        if not isinstance(retry_until_done, bool):
            raise TypeError("'retry_until_done' should be a bool value.")
        if not isinstance(retry_delay, (int, float)):
            raise TypeError("'retry_delay' should be a number.")
        if retry_delay < 0:
            raise ValueError("'retry_delay' cannot be negative.")

        media_url = self.__normalize_media_url(url)

        default_filename = Path(urlparse(media_url).path).name or "media.bin"
        safe_filename = self.__sanitize_filename(filename or default_filename, fallback="media.bin")
        file_path = Path(directory) / safe_filename
        file_path.parent.mkdir(parents=True, exist_ok=True)

        def emit_progress(
            event: str,
            status: str,
            attempts: int,
            error: Optional[str] = None,
            downloaded_bytes: Optional[int] = None,
            total_bytes: Optional[int] = None,
        ) -> None:
            if not progress_callback:
                return
            completed = 1 if event == "item_done" else 0
            item_fraction = self.__progress_fraction(int(downloaded_bytes or 0), int(total_bytes or 0)) if event == "item_progress" else 0.0
            percent = int(round(item_fraction * 100)) if event == "item_progress" else (100 if completed else 0)
            payload: Dict[str, Any] = {
                "event": event,
                "type": "video" if re.search(r"\.(mp4|webm|mov|m3u8)(?:$|[?#])", media_url, re.I) else "photo",
                "url": media_url,
                "filename": safe_filename,
                "path": str(file_path),
                "status": status,
                "attempts": attempts,
                "completed": completed,
                "total": 1,
                "percent": percent,
            }
            if downloaded_bytes is not None:
                payload["downloaded_bytes"] = downloaded_bytes
            if total_bytes is not None:
                payload["total_bytes"] = total_bytes
            if event == "item_progress":
                payload["item_percent"] = percent
            if error:
                payload["error"] = error
            progress_callback(payload)

        emit_progress("item_start", "pending", 0)

        if file_path.exists() and not overwrite:
            result = {
                "type": "video" if re.search(r"\.(mp4|webm|mov|m3u8)(?:$|[?#])", media_url, re.I) else "photo",
                "url": media_url,
                "filename": safe_filename,
                "path": str(file_path),
                "status": "skipped",
                "attempts": 0,
            }
            emit_progress("item_done", "skipped", 0)
            return result

        attempts = 0
        error = None
        max_attempts = 8
        while retry_until_done or attempts < max_attempts:
            attempts += 1
            try:
                self.__write_media_to_file(
                    media_url,
                    file_path,
                    lambda downloaded, total: emit_progress(
                        "item_progress",
                        "downloading",
                        attempts,
                        downloaded_bytes=downloaded,
                        total_bytes=total,
                    ),
                )
                error = None
                break
            except Exception as exc:  # noqa: BLE001 - retry until done or exhausted
                error = str(exc)
                can_retry = retry_until_done or attempts < max_attempts
                if can_retry:
                    emit_progress("retry", "retrying", attempts, error)
                    delay = min(8.0, retry_delay * (2 ** (attempts - 1)))
                    time.sleep(delay)
                    continue
                emit_progress("item_done", "error", attempts, error)
                raise

        emit_progress("item_done", "downloaded", attempts)
        return {
            "type": "video" if re.search(r"\.(mp4|webm|mov|m3u8)(?:$|[?#])", media_url, re.I) else "photo",
            "url": media_url,
            "filename": safe_filename,
            "path": str(file_path),
            "status": "downloaded",
            "attempts": attempts,
        }

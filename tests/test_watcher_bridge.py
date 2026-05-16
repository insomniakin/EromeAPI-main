import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from watcher_runtime import ensure_watcher_path


ensure_watcher_path()


class WatcherBridgeTests(unittest.TestCase):
    def test_search_returns_indexed_public_results_with_filters(self):
        from watcher_bridge import handle_watcher_method

        search_result = {
            "album_id": "ABC123",
            "username": "creator",
            "title": "Public Album",
            "url": "https://www.erome.com/a/ABC123",
            "views_estimate": 4200,
            "score": 99,
            "matched_terms": ["public"],
        }
        stats = {"indexed_album_count": 1, "snapshot_count": 2}

        with patch("watcher_bridge.search_albums", return_value=[search_result]) as search_albums:
            with patch("watcher_bridge.index_stats", return_value=stats):
                response = handle_watcher_method(
                    "search",
                    {
                        "query": "public",
                        "username": "creator",
                        "limit": 5,
                        "sort_by": "views",
                        "source": "profile",
                        "min_views": 3000,
                    },
                )

        search_albums.assert_called_once()
        self.assertEqual(search_albums.call_args.kwargs["query"], "public")
        self.assertEqual(search_albums.call_args.kwargs["username"], "creator")
        self.assertEqual(search_albums.call_args.kwargs["limit"], 5)
        self.assertEqual(search_albums.call_args.kwargs["sort_by"], "views")
        self.assertEqual(search_albums.call_args.kwargs["source"], "profile")
        self.assertEqual(search_albums.call_args.kwargs["min_views"], 3000)
        self.assertEqual(response["total_returned"], 1)
        self.assertEqual(response["index_stats"], stats)
        self.assertEqual(response["results"], [search_result])
        self.assertIn("indexed public content", response["note"])

    def test_watch_alert_can_compare_without_persisting(self):
        from watcher_bridge import handle_watcher_method
        from erome_watcher.models import AlertMessage, AlbumEntry, ProfileDiff, ProfileSnapshot

        previous = ProfileSnapshot(
            username="creator",
            profile_url="https://www.erome.com/creator?t=posts",
            fetched_at="2026-05-14T00:00:00+00:00",
            album_count=0,
            albums=[],
        )
        current_album = AlbumEntry(
            id="ABC123",
            title="New Public Album",
            url="https://www.erome.com/a/ABC123",
            username="creator",
            source="profile",
        )
        current = ProfileSnapshot(
            username="creator",
            profile_url="https://www.erome.com/creator?t=posts",
            fetched_at="2026-05-14T01:00:00+00:00",
            album_count=1,
            albums=[current_album],
        )
        diff = ProfileDiff(
            username="creator",
            previous_album_count=0,
            current_album_count=1,
            new_albums=[current_album],
            removed_albums=[],
            unchanged_count=0,
        )
        alert = AlertMessage(
            username="creator",
            summary="New album",
            telegram_text="New album",
            discord_text="New album",
            new_album_count=1,
            removed_album_count=0,
        )

        with patch("watcher_bridge.client.get_profile_snapshot", return_value=current):
            with patch("watcher_bridge.load_latest_snapshot", return_value=previous):
                with patch("watcher_bridge.diff_snapshots", return_value=diff) as diff_snapshots:
                    with patch("watcher_bridge.diff_and_update") as diff_and_update:
                        with patch("watcher_bridge.format_alert", return_value=alert):
                            response = handle_watcher_method(
                                "watch_alert",
                                {"username": "creator", "persist": False},
                            )

        diff_snapshots.assert_called_once_with(previous, current)
        diff_and_update.assert_not_called()
        self.assertEqual(response["username"], "creator")
        self.assertEqual(response["new_album_count"], 1)
        self.assertEqual(response["summary"], "New album")

    def test_index_rebuild_returns_stats_and_public_content_note(self):
        from watcher_bridge import handle_watcher_method

        rebuild = {"profiles_indexed": 1, "albums_indexed": 3, "usernames": ["creator"]}
        stats = {"indexed_album_count": 3, "indexed_profile_count": 1}

        with patch("watcher_bridge.rebuild_album_index", return_value=rebuild) as rebuild_album_index:
            with patch("watcher_bridge.index_stats", return_value=stats):
                response = handle_watcher_method("index_rebuild", {"usernames": ["creator"]})

        rebuild_album_index.assert_called_once()
        self.assertEqual(rebuild_album_index.call_args.kwargs["usernames"], ["creator"])
        self.assertEqual(response["rebuild"], rebuild)
        self.assertEqual(response["index_stats"], stats)
        self.assertIn("indexed public content", response["note"])

    def test_download_album_uses_main_api_downloader(self):
        from watcher_bridge import handle_watcher_method

        expected = [{"url": "https://v71.erome.com/video.mp4", "status": "downloaded"}]

        with patch("watcher_bridge.Api") as api_class:
            api_class.return_value.download_album.return_value = expected
            response = handle_watcher_method(
                "download_album",
                {
                    "url": "https://www.erome.com/a/ABC123",
                    "directory": "Downloads",
                    "include_photos": False,
                    "include_videos": True,
                    "overwrite": True,
                    "max_workers": 2,
                },
            )

        api_class.return_value.download_album.assert_called_once_with(
            path="https://www.erome.com/a/ABC123",
            directory="Downloads",
            include_photos=False,
            include_videos=True,
            overwrite=True,
            max_workers=2,
        )
        self.assertEqual(response["downloaded"], expected)
        self.assertEqual(response["count"], 1)

    def test_indexed_search_matches_multiple_hashtags(self):
        from erome_watcher.models import AlbumEntry, ProfileSnapshot
        from erome_watcher.sqlite_state import index_profile_snapshot, search_albums

        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "watcher.sqlite3"
            snapshot = ProfileSnapshot(
                username="creator",
                profile_url="https://www.erome.com/creator?t=posts",
                fetched_at="2026-05-14T00:00:00+00:00",
                album_count=1,
                albums=[
                    AlbumEntry(
                        id="ABC123",
                        title="Tagged Album",
                        url="https://www.erome.com/a/ABC123",
                        username="creator",
                        tags=["redhair", "outdoor"],
                        description="public tagged metadata",
                        media_count=4,
                        source="profile",
                    )
                ],
            )

            index_profile_snapshot(snapshot, db_path)
            results = search_albums(query="#redhair #outdoor", db_path=db_path)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["album_id"], "ABC123")
        self.assertEqual(results[0]["tags"], "redhair outdoor")
        self.assertEqual(results[0]["media_count"], 4)

    def test_indexed_hashtag_search_requires_tag_or_hashtag_metadata(self):
        from erome_watcher.models import AlbumEntry, ProfileSnapshot
        from erome_watcher.sqlite_state import index_profile_snapshot, search_albums

        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "watcher.sqlite3"
            snapshot = ProfileSnapshot(
                username="creator",
                profile_url="https://www.erome.com/creator?t=posts",
                fetched_at="2026-05-14T00:00:00+00:00",
                album_count=2,
                albums=[
                    AlbumEntry(
                        id="MATCH1",
                        title="Plain title",
                        url="https://www.erome.com/a/MATCH1",
                        username="creator",
                        tags=["redhair"],
                        description="outdoor in text with #outdoor",
                        source="profile",
                    ),
                    AlbumEntry(
                        id="TITLE2",
                        title="redhair outdoor title only",
                        url="https://www.erome.com/a/TITLE2",
                        username="creator",
                        tags=["indoor"],
                        description="redhair outdoor words without hashtag markers",
                        source="profile",
                    ),
                ],
            )

            index_profile_snapshot(snapshot, db_path)
            results = search_albums(query="#redhair #outdoor", db_path=db_path)

        self.assertEqual([result["album_id"] for result in results], ["MATCH1"])

    def test_live_hashtag_search_enriches_and_filters_album_tags(self):
        from erome_watcher.client import EromeClient

        search_html = """
                <div class="album"><a class="album-link" href="/a/MATCH1"><span class="album-title">Outdoor set</span></a></div>
                <div class="album"><a class="album-link" href="/a/TITLE2"><span class="album-title">redhair outdoor title only</span></a></div>
                """
        album_pages = {
            "https://www.erome.com/a/MATCH1": """
                <title>Outdoor set</title>
                <meta name="description" content="#redhair outside">
                <a href="/search?q=redhair">#redhair</a>
                <a href="/tag/outdoor">outdoor</a>
            """,
            "https://www.erome.com/a/TITLE2": """
                <title>redhair outdoor title only</title>
                <meta name="description" content="redhair outdoor words without hashtag markers">
                <a href="/tag/indoor">indoor</a>
            """,
        }
        client = EromeClient()
        seen_urls = []

        def fake_fetch(url: str) -> str:
            seen_urls.append(url)
            if url.startswith("https://www.erome.com/search"):
                return search_html
            return album_pages[url]

        client._fetch_html = fake_fetch

        snapshot = client.search_public("#redhair #outdoor", page=1)

        self.assertEqual(seen_urls[0], "https://www.erome.com/search?q=redhair+outdoor&page=1")
        self.assertEqual([album.id for album in snapshot.albums], ["MATCH1"])
        self.assertEqual(snapshot.albums[0].tags, ["redhair", "outdoor"])


if __name__ == "__main__":
    unittest.main()
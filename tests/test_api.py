import unittest
from tempfile import TemporaryDirectory

from api import Api


class FakeResponse:
    def __init__(self, text="", content=b"", status_code=200, headers=None, chunks=None):
        self.text = text
        self.content = content
        self.status_code = status_code
        self.headers = headers or {}
        self.chunks = chunks

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=1):
        if self.chunks is not None:
            yield from self.chunks
            return
        for index in range(0, len(self.content), chunk_size):
            yield self.content[index:index + chunk_size]


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def get(self, url, headers=None, timeout=None, **kwargs):
        self.requests.append({"url": url, "headers": headers, "timeout": timeout, "kwargs": kwargs})
        if not self.responses:
            raise AssertionError("No fake response configured")
        return self.responses.pop(0)


class ApiTests(unittest.TestCase):
    def test_search_query_is_url_encoded(self):
        api = Api()
        fake_session = FakeSession([FakeResponse('<div id="albums"></div>')])
        api._Api__session = fake_session

        api.get_all_album_data("red & blue", page=1, limit=1)

        self.assertEqual(
            fake_session.requests[0]["url"],
            "https://www.erome.com/search?q=red+%26+blue&page=1",
        )

    def test_search_results_include_sortable_album_metadata(self):
        api = Api()
        html = """
                <div id="albums">
                    <div class="album">
                        <a class="album-link" href="/a/LOW111"><span class="album-title">Quiet Album</span></a>
                        <img class="album-thumbnail" data-src="//s71.erome.com/quiet.jpg">
                        <span class="album-images">4 photos</span>
                        <span class="album-videos">1 video</span>
                        <span class="album-views">250 views</span>
                        <span class="duration">0:45</span>
                    </div>
                    <div class="album">
                        <a class="album-link" href="/a/HIGH222"><span class="album-title">Popular Album</span></a>
                        <img class="album-thumbnail" data-src="//s71.erome.com/popular.jpg">
                        <span class="album-images">2 photos</span>
                        <span class="album-videos">3 videos</span>
                        <span class="album-views">1.5K views</span>
                        <span class="duration">2:10</span>
                    </div>
                </div>
                """
        fake_session = FakeSession([FakeResponse(html)])
        api._Api__session = fake_session

        albums = api.get_all_album_data("public", page=1, limit=1, sort_by="views", sort_dir="desc")

        self.assertEqual([album["title"] for album in albums], ["Popular Album", "Quiet Album"])
        self.assertEqual(albums[0]["views"], 1500)
        self.assertEqual(albums[0]["images"], 2)
        self.assertEqual(albums[0]["videos"], 3)
        self.assertEqual(albums[0]["duration_seconds"], 130)
        self.assertEqual(albums[0]["is_hidden"], False)

    def test_hashtag_search_enriches_and_requires_matching_album_tags(self):
        api = Api()
        search_html = """
                <div id="albums">
                    <div class="album">
                        <a class="album-link" href="/a/MATCH1"><span class="album-title">Outdoor set</span></a>
                        <img class="album-thumbnail" data-src="//s71.erome.com/match.jpg">
                    </div>
                    <div class="album">
                        <a class="album-link" href="/a/TITLE2"><span class="album-title">redhair outdoor title only</span></a>
                        <img class="album-thumbnail" data-src="//s71.erome.com/no-match.jpg">
                    </div>
                </div>
                """
        matching_album_html = """
                <meta name="description" content="#redhair outdoor shoot">
                <a href="/search?q=%23redhair">#redhair</a>
                <a href="/tag/outdoor">outdoor</a>
                """
        title_only_album_html = """
                <meta name="description" content="redhair outdoor words, but no hashtags">
                <a href="/tag/indoor">indoor</a>
                """
        fake_session = FakeSession(
            [
                FakeResponse(search_html),
                FakeResponse(matching_album_html),
                FakeResponse(title_only_album_html),
            ]
        )
        api._Api__session = fake_session

        albums = api.get_all_album_data("#redhair #outdoor", page=1, limit=1)

        self.assertEqual(fake_session.requests[0]["url"], "https://www.erome.com/search?q=redhair+outdoor&page=1")
        self.assertEqual([album["url"] for album in albums], ["https://www.erome.com/a/MATCH1"])
        self.assertEqual(albums[0]["tags"], ["redhair", "outdoor"])
        self.assertEqual(albums[0]["matched_hashtags"], ["redhair", "outdoor"])

    def test_hashtag_search_supports_comma_separated_multi_word_tags(self):
        api = Api()
        search_html = """
                <div id="albums">
                    <div class="album">
                        <a class="album-link" href="/a/MATCH1"><span class="album-title">Styled set</span></a>
                    </div>
                    <div class="album">
                        <a class="album-link" href="/a/MISS2"><span class="album-title">Styled title only</span></a>
                    </div>
                </div>
                """
        matching_album_html = """
                <a href="/tag/alternative-girl">alternative girl</a>
                <a href="/search?q=%23egirl">#egirl</a>
                """
        missing_album_html = """
                <a href="/tag/alternative-girl">alternative girl</a>
                """
        fake_session = FakeSession(
            [
                FakeResponse(search_html),
                FakeResponse(matching_album_html),
                FakeResponse(missing_album_html),
            ]
        )
        api._Api__session = fake_session

        albums = api.get_all_album_data("#alternative girl, #egirl", page=1, limit=1)

        self.assertEqual(fake_session.requests[0]["url"], "https://www.erome.com/search?q=alternative+girl+egirl&page=1")
        self.assertEqual([album["url"] for album in albums], ["https://www.erome.com/a/MATCH1"])
        self.assertEqual(albums[0]["matched_hashtags"], ["alternative girl", "egirl"])

    def test_album_content_returns_absolute_media_urls(self):
        api = Api()
        html = """
        <video poster="//s71.erome.com/thumb.jpg">
            <source src="//v71.erome.com/video.mp4">
        </video>
        <div class="img"><img data-src="/media/photo.jpg"></div>
        """
        api._Api__session = FakeSession([FakeResponse(html)])

        content = api.get_album_content("RHoERFQP")

        self.assertEqual(content["videos"][0]["video_url"], "https://v71.erome.com/video.mp4")
        self.assertEqual(content["videos"][0]["thumb_url"], "https://s71.erome.com/thumb.jpg")
        self.assertEqual(content["photos"], ["https://www.erome.com/media/photo.jpg"])

    def test_get_content_accepts_protocol_relative_media_url(self):
        api = Api()
        fake_session = FakeSession([FakeResponse(content=b"image-bytes")])
        api._Api__session = fake_session

        content = api.get_content("//s71.erome.com/album/thumb.jpg")

        self.assertEqual(content, b"image-bytes")
        self.assertEqual(fake_session.requests[0]["url"], "https://s71.erome.com/album/thumb.jpg")

    def test_album_info_preserves_order_and_removes_duplicate_media(self):
        api = Api()
        html = """
        <meta property="og:title" content="Summer / Trip?">
        <a id="user_name">Uploader</a>
        <div class="img"><img data-src="//s71.erome.com/photo-1.jpg"></div>
        <video poster="//s71.erome.com/poster.jpg"><source src="//v71.erome.com/video-1.mp4"></video>
        <div class="img"><img src="//s71.erome.com/photo-1.jpg"></div>
        """
        api._Api__session = FakeSession([FakeResponse(html)])

        info = api.get_album_info("ABC123")

        self.assertEqual(info["slug"], "ABC123")
        self.assertEqual(info["title"], "Summer Trip")
        self.assertEqual(info["username"], "Uploader")
        self.assertEqual(
            info["media"],
            [
                {"type": "photo", "url": "https://s71.erome.com/photo-1.jpg"},
                {
                    "type": "video",
                    "url": "https://v71.erome.com/video-1.mp4",
                    "thumb_url": "https://s71.erome.com/poster.jpg",
                },
            ],
        )

    def test_download_album_writes_sequential_safe_filenames(self):
        api = Api()
        html = """
        <meta property="og:title" content="Summer / Trip?">
        <a id="user_name">Uploader</a>
        <div class="img"><img data-src="//s71.erome.com/photo-1.jpg"></div>
        <video><source src="//v71.erome.com/video-1.mp4"></video>
        """
        fake_session = FakeSession(
            [
                FakeResponse(html),
                FakeResponse(content=b"photo-bytes"),
                FakeResponse(content=b"video-bytes"),
            ]
        )
        api._Api__session = fake_session

        with TemporaryDirectory() as temp_dir:
            downloaded = api.download_album("ABC123", directory=temp_dir, max_workers=1)

            self.assertEqual([item["filename"] for item in downloaded], ["Summer Trip (1).jpg", "Summer Trip (2).mp4"])
            self.assertEqual(downloaded[0]["path"].endswith("Summer Trip (ABC123) [Uploader]\\Summer Trip (1).jpg"), True)
            with open(downloaded[0]["path"], "rb") as photo_file:
                self.assertEqual(photo_file.read(), b"photo-bytes")
            with open(downloaded[1]["path"], "rb") as video_file:
                self.assertEqual(video_file.read(), b"video-bytes")

    def test_download_album_skips_previously_downloaded_urls(self):
        api = Api()
        html = """
        <meta property="og:title" content="Summer / Trip?">
        <a id="user_name">Uploader</a>
        <div class="img"><img data-src="//s71.erome.com/photo-1.jpg"></div>
        <video><source src="//v71.erome.com/video-1.mp4"></video>
        """
        fake_session = FakeSession([FakeResponse(html), FakeResponse(content=b"video-bytes")])
        api._Api__session = fake_session

        with TemporaryDirectory() as temp_dir:
            downloaded = api.download_album(
                "ABC123",
                directory=temp_dir,
                max_workers=1,
                skip_urls=["https://s71.erome.com/photo-1.jpg"],
            )

            self.assertEqual([item["status"] for item in downloaded], ["skipped_downloaded", "downloaded"])
            self.assertEqual(len(fake_session.requests), 2)
            self.assertEqual(fake_session.requests[1]["url"], "https://v71.erome.com/video-1.mp4")

    def test_download_album_retries_until_media_saves_and_reports_progress(self):
        api = Api()
        html = """
        <meta property="og:title" content="Retry Album">
        <a id="user_name">Uploader</a>
        <div class="img"><img data-src="//s71.erome.com/photo-1.jpg"></div>
        """
        fake_session = FakeSession(
            [
                FakeResponse(html),
                FakeResponse(status_code=500),
                FakeResponse(status_code=502),
                FakeResponse(content=b"photo-bytes"),
            ]
        )
        api._Api__session = fake_session
        events = []

        with TemporaryDirectory() as temp_dir:
            downloaded = api.download_album(
                "ABC123",
                directory=temp_dir,
                max_workers=1,
                retry_until_done=True,
                retry_delay=0,
                progress_callback=events.append,
            )

            self.assertEqual(downloaded[0]["status"], "downloaded")
            self.assertEqual(downloaded[0]["attempts"], 3)
            retry_events = [event for event in events if event["event"] == "retry"]
            self.assertEqual([event["attempts"] for event in retry_events], [1, 2])
            completed_events = [event for event in events if event["event"] == "item_done"]
            self.assertEqual(completed_events[-1]["percent"], 100)
            self.assertEqual(completed_events[-1]["completed"], 1)
            self.assertEqual(completed_events[-1]["total"], 1)

    def test_download_album_reports_byte_progress_before_item_done(self):
        api = Api()
        html = """
        <meta property="og:title" content="Progress Album">
        <a id="user_name">Uploader</a>
        <video><source src="//v71.erome.com/video-1.mp4"></video>
        """
        fake_session = FakeSession(
            [
                FakeResponse(html),
                FakeResponse(
                    content=b"video-bytes",
                    headers={"content-length": "11"},
                    chunks=[b"video", b"-", b"bytes"],
                ),
            ]
        )
        api._Api__session = fake_session
        events = []

        with TemporaryDirectory() as temp_dir:
            downloaded = api.download_album(
                "ABC123",
                directory=temp_dir,
                max_workers=1,
                progress_callback=events.append,
            )

            self.assertEqual(downloaded[0]["status"], "downloaded")
            progress_events = [event for event in events if event["event"] == "item_progress"]
            self.assertGreater(len(progress_events), 0)
            self.assertEqual(progress_events[0]["downloaded_bytes"], 5)
            self.assertEqual(progress_events[-1]["downloaded_bytes"], 11)
            self.assertEqual(progress_events[-1]["item_percent"], 100)
            self.assertLess(progress_events[0]["percent"], 100)
            self.assertEqual(fake_session.requests[1]["kwargs"].get("stream"), True)

    def test_download_media_retries_until_saved(self):
        api = Api()
        fake_session = FakeSession(
            [
                FakeResponse(status_code=503),
                FakeResponse(content=b"media-bytes"),
            ]
        )
        api._Api__session = fake_session
        events = []

        with TemporaryDirectory() as temp_dir:
            downloaded = api.download_media(
                "//s71.erome.com/album/photo.jpg?v=1",
                directory=temp_dir,
                retry_until_done=True,
                retry_delay=0,
                progress_callback=events.append,
            )

            self.assertEqual(downloaded["status"], "downloaded")
            self.assertEqual(downloaded["attempts"], 2)
            event_names = [event["event"] for event in events]
            self.assertEqual(event_names[0], "item_start")
            self.assertIn("retry", event_names)
            self.assertEqual(event_names[-1], "item_done")

    def test_download_media_reports_byte_progress_before_item_done(self):
        api = Api()
        fake_session = FakeSession(
            [
                FakeResponse(
                    content=b"media-bytes",
                    headers={"content-length": "11"},
                    chunks=[b"media", b"-", b"bytes"],
                )
            ]
        )
        api._Api__session = fake_session
        events = []

        with TemporaryDirectory() as temp_dir:
            downloaded = api.download_media(
                "//v71.erome.com/album/video.mp4?v=1",
                directory=temp_dir,
                progress_callback=events.append,
            )

            self.assertEqual(downloaded["status"], "downloaded")
            progress_events = [event for event in events if event["event"] == "item_progress"]
            self.assertGreater(len(progress_events), 0)
            self.assertEqual(progress_events[0]["downloaded_bytes"], 5)
            self.assertEqual(progress_events[-1]["downloaded_bytes"], 11)
            self.assertEqual(progress_events[-1]["percent"], 100)
            self.assertEqual(fake_session.requests[0]["kwargs"].get("stream"), True)

    def test_download_media_writes_to_selected_directory(self):
        api = Api()
        fake_session = FakeSession([FakeResponse(content=b"media-bytes")])
        api._Api__session = fake_session

        with TemporaryDirectory() as temp_dir:
            downloaded = api.download_media("//s71.erome.com/album/photo.jpg?v=1", directory=temp_dir)

            self.assertEqual(downloaded["filename"], "photo.jpg")
            self.assertEqual(downloaded["status"], "downloaded")
            with open(downloaded["path"], "rb") as media_file:
                self.assertEqual(media_file.read(), b"media-bytes")

    def test_change_version_content_uses_public_version_route(self):
        api = Api()
        fake_session = FakeSession([FakeResponse(status_code=302)])
        api._Api__session = fake_session

        changed = api.change_version_content("straight")

        self.assertEqual(changed, True)
        self.assertEqual(fake_session.requests[0]["url"], "https://www.erome.com/version/straight")

    def test_profile_info_extracts_visible_public_profile_fields(self):
        api = Api()
        html = """
        <h1 class="profile-name">Creator Name</h1>
        <img class="avatar" data-src="//s71.erome.com/avatar.jpg">
        <div class="profile-about">Public bio text</div>
        <div id="albums">
          <div class="album">
            <a class="album-link" href="/a/ABC123"><span class="album-title">First Album</span></a>
            <img class="album-thumbnail" data-src="//s71.erome.com/thumb.jpg">
            <span class="album-images">12 images</span>
            <span class="album-videos">3 videos</span>
          </div>
        </div>
        """
        api._Api__session = FakeSession([FakeResponse(html)])

        profile = api.get_profile_info("CreatorName")

        self.assertEqual(profile["username"], "Creator Name")
        self.assertEqual(profile["url"], "https://www.erome.com/CreatorName")
        self.assertEqual(profile["avatar"], "https://s71.erome.com/avatar.jpg")
        self.assertEqual(profile["bio"], "Public bio text")
        self.assertEqual(profile["totals"], {"albums": 1, "images": 12, "videos": 3})
        self.assertEqual(
            profile["albums"],
            [
                {
                    "title": "First Album",
                    "url": "https://www.erome.com/a/ABC123",
                    "thumb": "https://s71.erome.com/thumb.jpg",
                    "images": 12,
                    "videos": 3,
                    "views": 0,
                    "duration_seconds": 0,
                    "is_hidden": False,
                    "visibility": "public",
                }
            ],
        )
    def test_profile_info_can_filter_public_hidden_albums(self):
        api = Api()
        html = """
                <div id="albums">
                    <div class="album unlisted">
                        <a class="album-link" href="/a/HID123"><span class="album-title">Hidden public drop</span></a>
                        <span class="album-images">1 photo</span>
                        <span class="album-videos">4 videos</span>
                        <span class="album-views">900 views</span>
                        <span class="duration">3:00</span>
                    </div>
                    <div class="album">
                        <a class="album-link" href="/a/PUB456"><span class="album-title">Public drop</span></a>
                        <span class="album-images">8 photos</span>
                        <span class="album-videos">1 video</span>
                        <span class="album-views">2K views</span>
                        <span class="duration">0:30</span>
                    </div>
                </div>
        """
        api._Api__session = FakeSession([FakeResponse(html)])

        profile = api.get_profile_info("CreatorName", hidden_only=True, sort_by="videos", sort_dir="desc")

        self.assertEqual([album["title"] for album in profile["albums"]], ["Hidden public drop"])
        self.assertEqual(profile["albums"][0]["is_hidden"], True)
        self.assertEqual(profile["albums"][0]["visibility"], "hidden")
    def test_profile_reposts_use_public_reposts_tab(self):
        api = Api()
        html = """
        <h1 class="profile-name">Creator Name</h1>
        <div class="page-content row user-profile">
            <div class="album">
                <div class="album-thumbnail-container">
                    <a class="album-link" href="https://www.erome.com/a/REP123">
                        <img class="album-thumbnail" src="//s71.erome.com/repost.jpg">
                    </a>
                </div>
                <div class="album-infos">
                    <a class="album-title" href="https://www.erome.com/a/REP123">Reposted Album</a>
                    <span class="album-images">5 photos</span>
                    <span class="album-videos">2 videos</span>
                    <span class="album-bottom-views">7K views</span>
                </div>
            </div>
        </div>
        """
        fake_session = FakeSession([FakeResponse(html)])
        api._Api__session = fake_session

        profile = api.get_profile_reposts("CreatorName")

        self.assertEqual(profile["content"], "reposts")
        self.assertEqual(profile["url"], "https://www.erome.com/CreatorName?t=reposts")
        self.assertEqual(fake_session.requests[0]["url"], "https://www.erome.com/CreatorName?t=reposts")
        self.assertEqual(profile["totals"], {"albums": 1, "images": 5, "videos": 2})
        self.assertEqual(profile["albums"][0]["url"], "https://www.erome.com/a/REP123")
        self.assertEqual(profile["albums"][0]["thumb"], "https://s71.erome.com/repost.jpg")

    def test_profile_info_limit_zero_crawls_until_empty_page(self):
        api = Api()
        page_one = """
        <h1 class="profile-name">Creator Name</h1>
        <div id="albums">
            <div class="album"><a class="album-link" href="/a/ABC123">First</a></div>
        </div>
        """
        page_two = """
        <div id="albums">
            <div class="album"><a class="album-link" href="/a/DEF456">Second</a></div>
        </div>
        """
        page_three = '<div id="albums"></div>'
        fake_session = FakeSession([FakeResponse(page_one), FakeResponse(page_two), FakeResponse(page_three)])
        api._Api__session = fake_session

        profile = api.get_profile_info("CreatorName", page=1, limit=0)

        self.assertEqual([album["url"] for album in profile["albums"]], [
                "https://www.erome.com/a/ABC123",
                "https://www.erome.com/a/DEF456",
        ])
        self.assertEqual([request["url"] for request in fake_session.requests], [
                "https://www.erome.com/CreatorName",
                "https://www.erome.com/CreatorName?page=2",
                "https://www.erome.com/CreatorName?page=3",
        ])

    def test_album_metadata_extracts_likes_and_durations(self):
        api = Api()
        html = """
        <meta property="og:title" content="Metadata Album">
        <a id="user_name">Uploader</a>
        <div id="like_count">1.2K likes</div>
        <span class="views">4.3K views</span>
        <span class="duration">1:30</span>
        <span class="duration">00:02:05</span>
        <video><source src="//v71.erome.com/video-1.mp4"></video>
        <div class="img"><img data-src="//s71.erome.com/photo-1.jpg"></div>
        """
        api._Api__session = FakeSession([FakeResponse(html)])

        metadata = api.get_album_metadata("ABC123")

        self.assertEqual(metadata["slug"], "ABC123")
        self.assertEqual(metadata["title"], "Metadata Album")
        self.assertEqual(metadata["username"], "Uploader")
        self.assertEqual(metadata["likes"], 1200)
        self.assertEqual(metadata["views"], 4300)
        self.assertEqual(metadata["durations"], [90, 125])
        self.assertEqual(metadata["total_duration_seconds"], 215)
        self.assertEqual(metadata["average_duration_seconds"], 108)
        self.assertEqual(metadata["media_count"], {"photos": 1, "videos": 1, "total": 2})


if __name__ == "__main__":
    unittest.main()
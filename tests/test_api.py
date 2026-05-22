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


class BrokenStreamResponse(FakeResponse):
    def iter_content(self, chunk_size=1):
        yield b"partial"
        raise RuntimeError("stream broke")


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

        self.assertEqual(fake_session.requests[0]["url"], "https://www.erome.com/search?q=%23redhair+%23outdoor&page=1")
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

        self.assertEqual(fake_session.requests[0]["url"], "https://www.erome.com/search?q=%23alternative+girl+%23egirl&page=1")
        self.assertEqual([album["url"] for album in albums], ["https://www.erome.com/a/MATCH1"])
        self.assertEqual(albums[0]["matched_hashtags"], ["alternative girl", "egirl"])

    def test_search_match_modes_filter_plain_keywords(self):
        api = Api()
        search_html = """
                <div id="albums">
                    <div class="album">
                        <a class="album-link" href="/a/BOTH1"><span class="album-title">red blue exact phrase</span></a>
                    </div>
                    <div class="album">
                        <a class="album-link" href="/a/RED2"><span class="album-title">red solo album</span></a>
                    </div>
                    <div class="album">
                        <a class="album-link" href="/a/BLUE3"><span class="album-title">blue solo album</span></a>
                    </div>
                </div>
                """

        api._Api__session = FakeSession([FakeResponse(search_html)])
        any_albums = api.get_all_album_data("red blue", page=1, limit=1, match_mode="any")

        api._Api__session = FakeSession([FakeResponse(search_html)])
        all_albums = api.get_all_album_data("red blue", page=1, limit=1, match_mode="all")

        api._Api__session = FakeSession([FakeResponse(search_html)])
        exact_albums = api.get_all_album_data("red blue exact phrase", page=1, limit=1, match_mode="exact")

        self.assertEqual([album["url"] for album in any_albums], [
            "https://www.erome.com/a/BOTH1",
            "https://www.erome.com/a/RED2",
            "https://www.erome.com/a/BLUE3",
        ])
        self.assertEqual([album["url"] for album in all_albums], ["https://www.erome.com/a/BOTH1"])
        self.assertEqual([album["url"] for album in exact_albums], ["https://www.erome.com/a/BOTH1"])

    def test_combo_match_requires_requested_metadata_tags_and_allows_extra_tags(self):
        api = Api()
        search_html = """
                <div id="albums">
                    <div class="album">
                        <a class="album-link" href="/a/ONLY1"><span class="album-title">Requested combo</span></a>
                    </div>
                    <div class="album">
                        <a class="album-link" href="/a/EXTRA2"><span class="album-title">Requested combo plus cosplay</span></a>
                    </div>
                </div>
                """
        only_combo_html = """
                <a href="/tag/redhair">redhair</a>
                <a href="/tag/outdoor">outdoor</a>
                """
        extra_combo_html = """
                <a href="/tag/redhair">redhair</a>
                <a href="/tag/outdoor">outdoor</a>
                <a href="/tag/cosplay">cosplay</a>
                """
        fake_session = FakeSession(
            [
                FakeResponse(search_html),
                FakeResponse(only_combo_html),
                FakeResponse(extra_combo_html),
            ]
        )
        api._Api__session = fake_session

        albums = api.get_all_album_data("#redhair #outdoor", page=1, limit=1, match_mode="combo")

        self.assertEqual([album["url"] for album in albums], ["https://www.erome.com/a/ONLY1", "https://www.erome.com/a/EXTRA2"])
        self.assertEqual(albums[0]["matched_hashtags"], ["redhair", "outdoor"])

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

    def test_get_content_accepts_xxxerome_media_hosts(self):
        api = Api()
        fake_session = FakeSession([FakeResponse(content=b"xxx-image")])
        api._Api__session = fake_session

        content = api.get_content("https://s71.xxxerome.com/album/thumb.jpg")

        self.assertEqual(content, b"xxx-image")
        self.assertEqual(fake_session.requests[0]["url"], "https://s71.xxxerome.com/album/thumb.jpg")

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

    def test_download_album_redownloads_after_failed_partial_file(self):
        api = Api()
        html = """
        <meta property="og:title" content="Retry Album">
        <a id="user_name">Uploader</a>
        <div class="img"><img data-src="//s71.erome.com/photo-1.jpg"></div>
        """
        api._Api__session = FakeSession(
            [FakeResponse(html)] +
            [BrokenStreamResponse() for _ in range(8)] +
            [FakeResponse(html), FakeResponse(content=b"complete-photo")]
        )

        with TemporaryDirectory() as temp_dir:
            first_result = api.download_album("ABC123", directory=temp_dir, max_workers=1, retry_delay=0)
            second_result = api.download_album("ABC123", directory=temp_dir, max_workers=1, retry_delay=0)

            self.assertEqual(first_result[0]["status"], "error")
            self.assertEqual(second_result[0]["status"], "downloaded")
            with open(second_result[0]["path"], "rb") as media_file:
                self.assertEqual(media_file.read(), b"complete-photo")

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

    def test_download_media_accepts_reddit_media_hosts(self):
        api = Api()
        fake_session = FakeSession([FakeResponse(content=b"reddit-image")])
        api._Api__session = fake_session

        with TemporaryDirectory() as temp_dir:
            downloaded = api.download_media("https://i.redd.it/photo.jpg?width=1080", directory=temp_dir)

            self.assertEqual(downloaded["filename"], "photo.jpg")
            self.assertEqual(downloaded["status"], "downloaded")
            self.assertEqual(fake_session.requests[0]["url"], "https://i.redd.it/photo.jpg?width=1080")
            self.assertEqual(fake_session.requests[0]["headers"]["referer"], "https://www.reddit.com/")
            with open(downloaded["path"], "rb") as media_file:
                self.assertEqual(media_file.read(), b"reddit-image")

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

    def test_album_info_keeps_xxxerome_domain_from_input_url(self):
        api = Api()
        html = """
        <meta property="og:title" content="Xxx Album">
        <a id="user_name">Uploader</a>
        <div class="img"><img data-src="/media/photo.jpg"></div>
        """
        api._Api__session = FakeSession([FakeResponse(html)])

        info = api.get_album_info("https://www.xxxerome.com/a/ABC123")

        self.assertEqual(info["slug"], "ABC123")
        self.assertEqual(info["url"], "https://xxxerome.com/a/ABC123")
        self.assertEqual(info["media"], [{"type": "photo", "url": "https://xxxerome.com/media/photo.jpg"}])

    def test_profile_info_keeps_xxxerome_domain_from_profile_url(self):
        api = Api()
        html = """
        <h1 class="profile-name">Creator Name</h1>
        <div id="albums">
            <div class="album">
                <a class="album-link" href="/a/ABC123"><span class="album-title">First Album</span></a>
            </div>
        </div>
        """
        fake_session = FakeSession([FakeResponse(html)])
        api._Api__session = fake_session

        profile = api.get_profile_info("https://www.xxxerome.com/CreatorName")

        self.assertEqual(profile["url"], "https://xxxerome.com/CreatorName")
        self.assertEqual(profile["albums"][0]["url"], "https://xxxerome.com/a/ABC123")
        self.assertEqual(fake_session.requests[0]["url"], "https://xxxerome.com/CreatorName")

    def test_profile_info_normalizes_xxxerome_www_host_to_apex(self):
        api = Api()
        html = """
        <h1 class="profile-name">Creator Name</h1>
        <div id="albums">
            <div class="album">
                <a class="album-link" href="/a/ABC123"><span class="album-title">First Album</span></a>
            </div>
        </div>
        """
        fake_session = FakeSession([FakeResponse(html)])
        api._Api__session = fake_session

        profile = api.get_profile_info("https://www.xxxerome.com/CreatorName")

        self.assertEqual(profile["url"], "https://xxxerome.com/CreatorName")
        self.assertEqual(profile["albums"][0]["url"], "https://xxxerome.com/a/ABC123")
        self.assertEqual(fake_session.requests[0]["url"], "https://xxxerome.com/CreatorName")

    def test_profile_info_parses_xxxerome_creator_post_listing(self):
        api = Api()
        html = """
        <main class="content">
            <article class="text-block model-info">
                <figure><img src="https://xxxerome.com/istorage/324584.jpg" alt="vividlyvixen"></figure>
                <h1>vividlyvixen</h1>
            </article>
            <section class="model-posts">
                <div class="posts-list">
                    <div class="post">
                        <h3><a href="/post/68990562/324584/onlyfans/vividlyvixen" title="No need to bring snacks">No need to bring snacks</a></h3>
                        <div class="post-thumbs">
                            <figure><a href="/post/68990562/324584/onlyfans/vividlyvixen"><img src="https://img1.xxxerome.com/storage/5/na/zh/sample.jpg"></a></figure>
                        </div>
                        <a class="view-post" href="/post/68990562/324584/onlyfans/vividlyvixen">View Post</a>
                    </div>
                </div>
            </section>
        </main>
        """
        fake_session = FakeSession([FakeResponse(html)])
        api._Api__session = fake_session

        profile = api.get_profile_info("https://xxxerome.com/a/onlyfans/324584/vividlyvixenvip")

        self.assertEqual(profile["username"], "vividlyvixen")
        self.assertEqual(profile["url"], "https://xxxerome.com/a/onlyfans/324584/vividlyvixenvip")
        self.assertEqual(profile["totals"], {"albums": 1, "images": 1, "videos": 0})
        self.assertEqual(profile["albums"][0]["url"], "https://xxxerome.com/post/68990562/324584/onlyfans/vividlyvixen")
        self.assertEqual(profile["albums"][0]["thumb"], "https://img1.xxxerome.com/storage/5/na/zh/sample.jpg")
        self.assertEqual(profile["albums"][0]["images"], 1)
        self.assertEqual(profile["albums"][0]["videos"], 0)

    def test_album_info_supports_xxxerome_post_urls(self):
        api = Api()
        html = """
        <title>No need to bring snacks</title>
        <article class="text-block model-info"><h1>vividlyvixen</h1></article>
        <video poster="https://img1.xxxerome.com/storage/poster.jpg">
            <source src="https://v71.xxxerome.com/storage/video.mp4">
        </video>
        <img src="https://img1.xxxerome.com/storage/photo.jpg">
        """
        api._Api__session = FakeSession([FakeResponse(html)])

        info = api.get_album_info("https://xxxerome.com/post/68990562/324584/onlyfans/vividlyvixen")

        self.assertEqual(info["slug"], "post/68990562/324584/onlyfans/vividlyvixen")
        self.assertEqual(info["url"], "https://xxxerome.com/post/68990562/324584/onlyfans/vividlyvixen")
        self.assertEqual(
            info["media"],
            [
                {
                    "type": "video",
                    "url": "https://v71.xxxerome.com/storage/video.mp4",
                    "thumb_url": "https://img1.xxxerome.com/storage/poster.jpg",
                },
                {"type": "photo", "url": "https://img1.xxxerome.com/storage/photo.jpg"},
            ],
        )

    def test_album_content_maps_rich_xxxerome_post_media(self):
        api = Api()
        html = """
        <title>Rich Post</title>
        <article class="text-block model-info"><h1>vividlyvixen</h1></article>
        <div class="img"><img data-src="https://img5.xxxerome.com/storage/photo-1.jpg"></div>
        <img src="https://img5.xxxerome.com/storage/photo-2.jpg">
        <video poster="https://img5.xxxerome.com/storage/poster-1.jpg">
            <source src="https://v71.xxxerome.com/storage/video-1.mp4">
        </video>
        <video src="https://v71.xxxerome.com/storage/video-2.mp4"></video>
        """
        api._Api__session = FakeSession([FakeResponse(html)])

        content = api.get_album_content("https://xxxerome.com/post/123/324584/onlyfans/vividlyvixen")

        self.assertEqual(
            content["photos"],
            [
                "https://img5.xxxerome.com/storage/photo-1.jpg",
                "https://img5.xxxerome.com/storage/photo-2.jpg",
            ],
        )
        self.assertEqual(
            content["videos"],
            [
                {
                    "video_url": "https://v71.xxxerome.com/storage/video-1.mp4",
                    "thumb_url": "https://img5.xxxerome.com/storage/poster-1.jpg",
                },
                {
                    "video_url": "https://v71.xxxerome.com/storage/video-2.mp4",
                    "thumb_url": None,
                },
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
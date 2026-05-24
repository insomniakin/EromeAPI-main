from pathlib import Path
import unittest


class WatcherGuiSourceTests(unittest.TestCase):
    def test_watcher_player_uses_main_media_proxy_when_mounted(self):
        source = Path("erome-watcher/gui/src/App.tsx").read_text(encoding="utf-8")

        self.assertIn("function mediaDisplayUrl", source)
        self.assertIn("/proxy?url=", source)
        self.assertIn("src={mediaDisplayUrl(currentMedia.url)}", source)
        self.assertIn("poster={mediaDisplayUrl(currentMedia.poster ?? poster)}", source)

    def test_watcher_gui_supports_mobile_multi_tag_search_and_downloads(self):
        source = Path("erome-watcher/gui/src/App.tsx").read_text(encoding="utf-8")

        self.assertIn("selectedTags", source)
        self.assertIn("function toggleTag", source)
        self.assertIn("function searchQueryWithTags", source)
        self.assertIn("function downloadSelectedAlbum", source)
        self.assertIn("/download", source)
        self.assertIn("enrich_albums", source)
        self.assertIn("watcher-search-panel", source)
        self.assertIn("watcher-result-card", source)
        self.assertIn("watcher-media-strip", source)

        styles = Path("erome-watcher/gui/src/index.css").read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 640px)", styles)
        self.assertIn(".watcher-result-card", styles)
        self.assertIn(".watcher-player-panel", styles)
        self.assertIn("min-width: 0", styles)
        self.assertIn(".watcher-media-strip", styles)

    def test_watcher_routes_tolerate_trailing_api_base_slashes(self):
        source = Path("erome-watcher/gui/src/App.tsx").read_text(encoding="utf-8")
        server = Path("server.js").read_text(encoding="utf-8")

        self.assertIn("function buildApiUrl", source)
        self.assertIn("replace(/\\/+$/, '')", source)
        self.assertIn("fetch(buildApiUrl(baseUrl, path)", source)
        self.assertIn("function normalizeWatcherPath", server)
        self.assertIn("normalizeWatcherPath(pathname.slice", server)

    def test_root_feed_supports_profile_reposts_without_overfetching_pages(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn('value="profileReposts"', source)
        self.assertIn('id="feedProfileName"', source)
        self.assertIn('content=reposts', source)
        self.assertIn('limit=${page}', source)
        self.assertIn('slice(0, albumLimit)', source)

        server = Path("server.js").read_text(encoding="utf-8")
        self.assertIn('path === "/api/profile/reposts"', server)
        self.assertIn('content: "reposts"', server)

    def test_root_ui_persists_search_and_feed_form_settings(self):
        source = Path("ui.html").read_text(encoding="utf-8")
        server = Path("server.js").read_text(encoding="utf-8")

        self.assertIn("FORM_SETTING_IDS", source)
        self.assertIn("collectFormSettings", source)
        self.assertIn("applyFormSettings", source)
        self.assertIn("scheduleSettingsSave", source)
        self.assertIn("settings.form_values", source)
        self.assertIn("'feedSource'", source)
        self.assertIn("'feedKeyword'", source)
        self.assertIn("'searchKeyword'", source)
        self.assertIn("'profileName'", source)
        self.assertIn("'albumPath'", source)
        self.assertIn("'mediaUrl'", source)
        self.assertIn("form_values: {}", server)

    def test_root_ui_supports_multi_term_search_and_hide_filters(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn('id="hideTerms"', source)
        self.assertIn('<textarea id="searchKeyword"', source)
        self.assertIn('<textarea id="feedKeyword"', source)
        self.assertIn("function parseSearchTerms", source)
        self.assertIn("function searchQueryFromInput", source)
        self.assertIn("function albumMatchesHideTerms", source)
        self.assertIn("function visibleAlbums", source)
        self.assertIn("searchQueryFromInput('searchKeyword')", source)
        self.assertIn("searchQueryFromInput('feedKeyword')", source)
        self.assertIn("visibleAlbums(albums).filter", source)
        self.assertIn("sortAlbumsForDisplay(resultState.allAlbums)", source)
        self.assertIn("visibleAlbums(albums)", source)
        self.assertIn("'hideTerms'", source)

    def test_root_ui_has_add_hashtag_chip_panel(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn('id="hashtagInput"', source)
        self.assertIn('id="addHashtags"', source)
        self.assertIn('id="clearHashtags"', source)
        self.assertIn('id="selectedHashtags"', source)
        self.assertIn('id="suggestedHashtags"', source)
        self.assertIn('id="hashtagTerms"', source)
        self.assertIn('class="hashtag-help"', source)
        self.assertIn('hashtag-selected', source)
        self.assertIn('hashtag-suggested', source)
        self.assertIn('combine them with AND search', source)
        self.assertIn("SUGGESTED_HASHTAGS", source)
        self.assertIn("let selectedHashtags", source)
        self.assertIn("function parseHashtagInput", source)
        self.assertIn("function renderHashtagChips", source)
        self.assertIn("function addHashtagTerms", source)
        self.assertIn("function selectedHashtagQuery", source)
        self.assertIn("'#alternative girl'", source)
        self.assertIn("'hashtagTerms'", source)

    def test_root_ui_has_search_modes_and_album_history_controls(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn('id="searchMatchMode"', source)
        self.assertIn('id="feedMatchMode"', source)
        self.assertIn('Exact phrase', source)
        self.assertIn('Any keyword', source)
        self.assertIn('All keywords', source)
        self.assertIn('Only this combo', source)
        self.assertIn('id="hideSeenAlbums"', source)
        self.assertIn('id="hideSkippedAlbums"', source)
        self.assertIn('id="hideSavedAlbums"', source)
        self.assertIn('function markAlbumState', source)
        self.assertIn('function albumMatchesHistoryFilters', source)
        self.assertIn('function loadAlbumHistory', source)
        self.assertIn('data-act="seen"', source)
        self.assertIn('data-act="skip"', source)
        self.assertIn('data-act="save"', source)
        self.assertIn('/api/albums/mark', source)
        self.assertIn('/api/albums/history', source)

    def test_root_feed_empty_state_explains_search_and_filter_misses(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn('function feedEmptyMessage', source)
        self.assertIn('rawCount', source)
        self.assertIn('visibleCount', source)
        self.assertIn('No albums matched the current search:', source)
        self.assertIn('Albums matched, but current hide/history filters removed them all.', source)
        self.assertIn('Albums loaded, but no media items could be displayed.', source)
        self.assertIn('Feed items loaded, but none matched the current filters.', source)

    def test_server_persists_album_history_state(self):
        server = Path("server.js").read_text(encoding="utf-8")

        self.assertIn('albums: {', server)
        self.assertIn('seen: {', server)
        self.assertIn('skipped: {', server)
        self.assertIn('saved: {', server)
        self.assertIn('function normalizeAlbumKey', server)
        self.assertIn('function recordAlbumState', server)
        self.assertIn('path === "/api/albums/history"', server)
        self.assertIn('path === "/api/albums/mark"', server)
        self.assertIn('path === "/api/albums/clear-history"', server)

    def test_server_proxy_allows_xxxerome_hosts(self):
        server = Path("server.js").read_text(encoding="utf-8")

        self.assertIn('function isAllowedProxyHost', server)
        self.assertIn('xxxerome.com', server)
        self.assertIn('Only erome.com and xxxerome.com hosts are proxied.', server)

    def test_server_has_reddit_oauth_routes(self):
        server = Path("server.js").read_text(encoding="utf-8")

        self.assertIn('reddit: {', server)
        self.assertIn('function sanitizeState', server)
        self.assertIn('path === "/api/reddit/status"', server)
        self.assertIn('path === "/api/reddit/config"', server)
        self.assertIn('path === "/api/reddit/login"', server)
        self.assertIn('path === "/api/reddit/callback"', server)
        self.assertIn('path === "/api/reddit/disconnect"', server)
        self.assertIn('refresh_token', server)
        self.assertIn('access_token', server)

    def test_reddit_oauth_supports_web_app_secret_without_public_exposure(self):
        server = Path("server.js").read_text(encoding="utf-8")
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn('client_secret: ""', server)
        self.assertIn('function redditBasicAuth(clientId, clientSecret = "")', server)
        self.assertIn('state.reddit.client_secret = clientSecret', server)
        self.assertIn('has_client_secret: !!redditState.client_secret', server)
        self.assertNotIn('client_secret: redditState.client_secret', server)
        self.assertIn('id="redditClientSecret"', source)
        self.assertIn("document.getElementById('redditClientSecret')", source)
        self.assertIn('client_secret: clientSecret', source)
        form_setting_ids = source.split("const FORM_SETTING_IDS =", 1)[1].split("];", 1)[0]
        self.assertNotIn("redditClientSecret", form_setting_ids)

    def test_server_has_reddit_feed_route_and_normalizer(self):
        server = Path("server.js").read_text(encoding="utf-8")

        self.assertIn('function normalizeRedditPost', server)
        self.assertIn('path === "/api/reddit/feed"', server)
        self.assertIn('oauth.reddit.com', server)
        self.assertIn('reddit_video', server)
        self.assertIn('source: "reddit"', server)

    def test_root_ui_has_reddit_feed_controls(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn('id="feedNetwork"', source)
        self.assertIn('Erome only', source)
        self.assertIn('Reddit only', source)
        self.assertIn('All', source)
        self.assertIn('id="redditClientId"', source)
        self.assertIn('id="redditConnect"', source)
        self.assertIn('id="redditDisconnect"', source)
        self.assertIn('function fetchRedditFeedBatch', source)
        self.assertIn('function appendRedditFeedItems', source)
        self.assertIn('function appendMixedFeedItems', source)
        self.assertIn('/api/reddit/feed', source)

    def test_root_feed_has_twitter_and_all_network_modes(self):
        source = Path("ui.html").read_text(encoding="utf-8")
        server = Path("server.js").read_text(encoding="utf-8")

        self.assertIn('value="twitter"', source)
        self.assertIn('Twitter/X only', source)
        self.assertIn('value="all"', source)
        self.assertIn('>All<', source)
        self.assertIn("function fetchTwitterFeedBatch", source)
        self.assertIn("function appendExternalFeedItems", source)
        self.assertIn("network === 'all'", source)
        self.assertIn("fetchTwitterFeedBatch()", source)
        self.assertIn('path === "/api/twitter/feed"', server)
        self.assertIn('function normalizeTwitterPost', server)

    def test_root_feed_uses_tags_for_erome_and_reddit_search(self):
        source = Path("ui.html").read_text(encoding="utf-8")
        server = Path("server.js").read_text(encoding="utf-8")

        self.assertIn('function feedSearchQuery', source)
        self.assertIn('function effectiveEromeFeedSource', source)
        self.assertIn("hasFeedSearchQuery() && (source === 'explore' || source === 'exploreNew')", source)
        self.assertIn('function normalizeRedditSearchQuery', source)
        self.assertIn('function redditSearchQueryFromInput', source)
        self.assertIn('function effectiveRedditFeedKind', source)
        self.assertIn("kind: effectiveRedditFeedKind()", source)
        self.assertIn("query: redditSearchQueryFromInput()", source)
        self.assertIn('function normalizeRedditSearchQuery', server)
        self.assertIn('params.set("q", normalizeRedditSearchQuery(query))', server)

    def test_root_feed_can_download_reddit_media(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn("open.title = 'Open Reddit source'", source)
        self.assertIn("download.title = 'Download this media'", source)
        self.assertIn("download.onclick = () => downloadMediaToDir(media, album)", source)
        self.assertIn("actions.appendChild(download)", source)

    def test_root_feed_fetch_album_media_preserves_full_album_url(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn("const lookup = album.url || path;", source)
        self.assertIn("/api/album/info?path=${encodeURIComponent(lookup)}", source)

    def test_root_feed_parses_post_urls_to_album_paths(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn("if (parts[0] === 'post' && parts.length >= 2) return parts.join('/');", source)
        self.assertIn("const postMatch = String(url).match(/\\/?(post\\/[^?#]+)/);", source)

    def test_root_feed_download_groups_items_without_css_selector_path_injection(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn("Array.from(document.querySelectorAll('.feed-item'))", source)
        self.assertIn(".filter((el) => (el.dataset.albumPath || '') === path);", source)

    def test_root_download_retries_with_all_media_when_filter_returns_empty(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn("No media matched current type. Retrying with photos + videos...", source)
        self.assertIn("body.include_photos !== body.include_videos", source)
        self.assertIn("include_photos: true", source)
        self.assertIn("include_videos: true", source)

    def test_root_download_empty_hint_mentions_media_filter_not_blocking(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn("if (action === 'download' && emptyArrayData)", source)
        self.assertIn("No downloadable items matched the current Photos/Videos filter", source)

    def test_root_feed_treats_twitter_as_external_media(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn("return (source === 'reddit' || source === 'twitter') ? mediaUrl : proxyUrl(mediaUrl);", source)
        self.assertIn("const isExternalFeedSource = source === 'reddit' || source === 'twitter';", source)
        self.assertIn("open.title = 'Open Twitter/X source'", source)
        self.assertIn("source === 'twitter'", source)
        self.assertIn("'Twitter/X'", source)

    def test_root_feed_supports_xxxerome_site_selection(self):
        source = Path("ui.html").read_text(encoding="utf-8")
        bridge = Path("api_bridge.py").read_text(encoding="utf-8")
        server = Path("server.js").read_text(encoding="utf-8")

        self.assertIn('id="feedSite"', source)
        self.assertIn('https://xxxerome.com', source)
        self.assertIn('value="xxxerome"', source)
        self.assertIn('XXXErome only', source)
        self.assertIn("if (network === 'xxxerome') return 'https://xxxerome.com';", source)
        self.assertIn('site: siteOverride || selectedFeedSite(selectedFeedNetwork())', source)
        self.assertIn('site_base', bridge)
        self.assertIn('site_base', server)

    def test_search_and_profile_have_explicit_xxxerome_site_controls(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn('id="searchSite"', source)
        self.assertIn('id="exploreSite"', source)
        self.assertIn('id="profileSite"', source)
        self.assertIn('selectedSearchSite()', source)
        self.assertIn('selectedExploreSite()', source)
        self.assertIn('selectedProfileSite()', source)
        self.assertIn("albumQueryParams(hidden, selectedSearchSite())", source)
        self.assertIn("albumQueryParams(false, selectedExploreSite())", source)

    def test_profile_action_does_not_override_explicit_profile_url_site(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn('function looksLikeAbsoluteProfileUrl', source)
        self.assertIn('const inferredSite = inferPreferredSiteFromProfileValue(rawProfile);', source)
        self.assertIn("const siteOverride = looksLikeAbsoluteProfileUrl(rawProfile) ? '' : (inferredSite || selectedProfileSite());", source)
        self.assertIn('placeholder="username or https://xxxerome.com/a/onlyfans/123/name"', source)

    def test_root_feed_prevents_duplicate_media_download_clicks(self):
        source = Path("ui.html").read_text(encoding="utf-8")
        server = Path("server.js").read_text(encoding="utf-8")

        self.assertIn('pendingMediaDownloads: new Set()', source)
        self.assertIn('This media is already downloading.', source)
        self.assertIn("feedState.pendingMediaDownloads.add(mediaKey)", source)
        self.assertIn("feedState.pendingMediaDownloads.delete(mediaKey)", source)
        self.assertIn('normalizeMediaUrl(job.media_url || "") === mediaUrl', server)

    def test_server_only_skips_successfully_downloaded_media(self):
        server = Path("server.js").read_text(encoding="utf-8")

        self.assertIn("function isDownloadedMediaRecord(record)", server)
        self.assertIn('return !record.status || record.status === "downloaded";', server)
        self.assertIn("function downloadedMediaUrls(state)", server)
        self.assertIn('const skipDownloaded = !overwrite && body.skip_downloaded !== false && state.settings.skip_downloaded !== false;', server)
        self.assertIn('skip_urls: skipDownloaded ? downloadedMediaUrls(state) : [],', server)
        self.assertIn('if (skipDownloaded && isDownloadedMediaRecord(state.downloaded.media[mediaUrl]))', server)
        self.assertIn('if (status !== "downloaded") continue;', server)

    def test_root_feed_has_video_mute_toggle(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn('id="feedStartMuted"', source)
        self.assertIn('Start videos muted', source)
        self.assertIn("'feedStartMuted'", source)
        self.assertIn('function shouldStartVideosMuted', source)
        self.assertIn('function applyFeedVideoMutePreference', source)
        self.assertIn('video.muted = shouldStartVideosMuted()', source)
        self.assertIn("document.getElementById('feedStartMuted').onchange = applyFeedVideoMutePreference", source)

    def test_root_feed_observers_do_not_force_remute(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertEqual(source.count('video.muted = shouldStartVideosMuted();'), 1)

    def test_root_feed_native_volume_changes_update_mute_preference(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn('function syncFeedMutePreferenceFromVideo', source)
        self.assertIn("video.addEventListener('volumechange', syncFeedMutePreferenceFromVideo)", source)
        self.assertIn("if (other !== video && other.muted !== muted) other.muted = muted", source)

    def test_preview_album_auto_advances_to_next_post_when_media_missing(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn('function nextAlbumForPreviewFallback', source)
        self.assertIn('let currentAlbum = album', source)
        self.assertIn('const visitedAlbumUrls = new Set()', source)
        self.assertIn("const matchingMedia = mediaItems.filter((item) => item && item.url && mediaTypeAllowed(item.type));", source)
        self.assertIn("if (!matchingMedia.length)", source)
        self.assertIn('const nextAlbum = nextAlbumForPreviewFallback(currentAlbum)', source)
        self.assertIn("No ${selectedType} in this post. Loading next post...", source)
        self.assertIn('continue;', source)

    def test_root_ui_keeps_selected_media_type_without_forced_fallback(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertNotIn("No media matched the selected type. Switched to Photos + Videos.", source)
        self.assertNotIn("No profile media matched the selected type. Switched to Photos + Videos.", source)

    def test_feed_profile_fetch_retries_with_profile_tab_value_when_feed_field_empty_results(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn("const feedRawProfile = (document.getElementById('feedProfileName').value || '').trim();", source)
        self.assertIn("const profileTabRawProfile = (document.getElementById('profileName').value || '').trim();", source)
        self.assertIn("if (!rawAlbums.length && secondaryProfile)", source)
        self.assertIn("Retrying with Profile tab value", source)

    def test_feed_and_profile_inputs_stay_in_sync(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn("function syncProfileInputs(sourceId = '', persist = true)", source)
        self.assertIn("function bindProfileInputSync()", source)
        self.assertIn("feedInput.addEventListener('input', () => syncProfileInputs('feedProfileName'))", source)
        self.assertIn("profileInput.addEventListener('input', () => syncProfileInputs('profileName'))", source)
        self.assertIn("bindProfileInputSync();", source)

    def test_root_feed_uses_youtube_style_video_player(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn('function createVideoPlayerClone', source)
        self.assertIn('className = \'yt-clone-player paused show-controls\'', source)
        self.assertIn('yt-clone-timeline', source)
        self.assertIn('yt-clone-volume-slider', source)
        self.assertIn('yt-clone-time-display', source)
        self.assertIn('yt-clone-fullscreen', source)
        self.assertIn('createVideoPlayerClone(album, media, source, item)', source)
        self.assertIn('function createVideoPlayerPreview', source)
        self.assertIn("previewEl.appendChild(createVideoPlayerPreview(objectUrl, 'Preview'))", source)
        self.assertNotIn('video.controls = true', source)
        self.assertNotIn('<video src="${objectUrl}" controls></video>', source)

    def test_twitter_feed_explains_public_app_shell_limitation(self):
        source = Path("ui.html").read_text(encoding="utf-8")
        server = Path("server.js").read_text(encoding="utf-8")

        self.assertIn('id="twitterHelp"', source)
        self.assertIn('public X pages may return only the app shell', source)
        self.assertIn('without media URLs', server)
        self.assertIn('official API or logged-in session support', server)

    def test_twitter_feed_supports_official_x_api_bearer_token(self):
        server = Path("server.js").read_text(encoding="utf-8")

        self.assertIn('const TWITTER_BEARER_TOKEN = process.env.X_BEARER_TOKEN || process.env.TWITTER_BEARER_TOKEN || "";', server)
        self.assertIn('const TWITTER_API_BASE = (process.env.X_API_BASE || "https://api.twitter.com/2").replace(/\\/+$/, "");', server)
        self.assertIn('function twitterApiSearchQuery', server)
        self.assertIn('async function fetchTwitterApiFeed', server)
        self.assertIn('Authorization: `Bearer ${TWITTER_BEARER_TOKEN}`', server)
        self.assertIn('/tweets/search/recent?', server)
        self.assertIn('/users/by/username/', server)
        self.assertIn('normalizeTwitterApiFeed', server)
        self.assertIn('authenticated: true', server)

    def test_root_twitter_feed_uses_api_pagination_token(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn("twitterAfter: ''", source)
        self.assertIn("if (feedState.twitterAfter) params.set('after', feedState.twitterAfter);", source)
        self.assertIn("feedState.twitterAfter = data.after || '';", source)
        self.assertIn("feedState.twitterAfter = '';", source)

    def test_readme_documents_twitter_x_api_setup(self):
        readme = Path("README.md").read_text(encoding="utf-8")

        self.assertIn('## Twitter/X Feed Setup', readme)
        self.assertIn('X_BEARER_TOKEN', readme)
        self.assertIn('TWITTER_BEARER_TOKEN', readme)
        self.assertIn('https://developer.x.com', readme)

    def test_root_ui_stabilizes_download_status_layout(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn("white-space: nowrap", source)
        self.assertIn("text-overflow: ellipsis", source)
        self.assertIn("statusEl.title = message", source)
        self.assertIn("min-width: 72px", source)
        self.assertIn("font-variant-numeric: tabular-nums", source)

    def test_download_jobs_are_persistent_retry_queue(self):
        source = Path("server.js").read_text(encoding="utf-8")

        self.assertIn("download_queue: []", source)
        self.assertIn("function queueDownloadJob", source)
        self.assertIn("function persistDownloadJobSnapshot", source)
        self.assertIn('path === "/api/download/queue"', source)
        self.assertIn("retry_until_done: true", source)

    def test_root_ui_shows_permanent_download_queue(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn('id="downloadQueue"', source)
        self.assertIn("function renderDownloadQueue", source)
        self.assertIn("refreshDownloadQueue", source)
        self.assertIn("/api/download/queue", source)
        self.assertIn("retry_until_done: true", source)

    def test_root_ui_has_buy_me_coffee_support_link(self):
        source = Path("ui.html").read_text(encoding="utf-8")
        qr_path = Path("app/assets/cashapp-qr.jpg")

        self.assertTrue(qr_path.is_file())
        self.assertGreater(qr_path.stat().st_size, 0)
        self.assertIn('id="supportQr"', source)
        self.assertIn('src="/app/assets/cashapp-qr.jpg"', source)
        self.assertIn('alt="Cash App QR code for $cjordanhot"', source)
        self.assertIn('Buy me coffee', source)
        self.assertIn('$20 starter', source)
        self.assertIn('$cjordanhot', source)
        self.assertNotIn('href="https://cash.app', source)
        self.assertNotIn('If Cash App blocks the browser', source)
        self.assertNotIn('send $20 to', source)

    def test_userscript_mirrors_core_erotok_features(self):
        source = Path("userscript/erotok.user.js").read_text(encoding="utf-8")

        self.assertIn("// @name         EroTok Mini", source)
        self.assertIn("// @match        https://www.erome.com/*", source)
        self.assertIn("// @copyright   2026, cjordanhot", source)
        self.assertIn("// @license     BSD-2-Clause", source)
        self.assertIn("// @grant        GM_xmlhttpRequest", source)
        self.assertIn("const FULL_APP_URL = 'http://127.0.0.1:3000/'", source)
        self.assertIn("const GITHUB_URL = 'https://github.com/insomniakin/EromeAPI-main'", source)
        self.assertIn("SUGGESTED_HASHTAGS", source)
        self.assertIn("function parseHashtagInput", source)
        self.assertIn("function searchQuery", source)
        self.assertIn("function visibleAlbums", source)
        self.assertIn("function downloadCurrentAlbum", source)
        self.assertIn("/api/search", source)
        self.assertIn("/api/explore", source)
        self.assertIn("/api/profile", source)
        self.assertIn("/api/download/jobs", source)
        self.assertIn("Open full local app", source)
        self.assertIn("Upgrade on GitHub", source)
        self.assertIn("erotok-hide-terms", source)
        self.assertIn("erotok-selected-tags", source)

    def test_root_erome_userscript_is_synced_and_not_duplicated(self):
        source = Path("erome.js").read_text(encoding="utf-8")

        self.assertEqual(source.count("// ==UserScript=="), 1)
        self.assertEqual(source.count("(function () {"), 1)
        self.assertEqual(source.count("})();"), 1)
        self.assertIn("// @version      8.1.3-xxx-fixes", source)
        self.assertIn("// @match        https://*.xxxerome.com/*", source)
        self.assertIn("// @match        https://xxxerome.com/*", source)
        self.assertIn("const isXxxErome", source)
        self.assertIn("/^\\/(?:post|a)\\//", source)
        self.assertNotIn("Insomniaqqqxxx", source)

    def test_sleazyfork_readme_requires_local_gui_api_and_assets(self):
        source = Path("SLEAZYFORK_README.md").read_text(encoding="utf-8")

        self.assertIn("EroTok Mini - SleazyFork Listing README", source)
        self.assertIn("Requires the local EroTok GUI/API from GitHub", source)
        self.assertIn("https://github.com/insomniakin/EromeAPI-main", source)
        self.assertIn("git clone https://github.com/insomniakin/EromeAPI-main.git", source)
        self.assertIn("pip install -r requirements.txt", source)
        self.assertIn("node server.js", source)
        self.assertIn("http://127.0.0.1:3000", source)
        self.assertIn("License And Copyright", source)
        self.assertIn("// @copyright   2026, cjordanhot", source)
        self.assertIn("// @license     BSD-2-Clause", source)
        self.assertIn("Copyright (c) 2026 cjordanhot", source)
        self.assertIn("SPDX-License-Identifier: BSD-2-Clause", source)
        self.assertIn("repository `LICENSE` file", source)
        self.assertIn("https://raw.githubusercontent.com/insomniakin/EromeAPI-main/main/docs/screenshots/erotok-control-panel.png", source)
        self.assertIn("https://raw.githubusercontent.com/insomniakin/EromeAPI-main/main/docs/screenshots/erotok-controls.png", source)
        self.assertIn("https://raw.githubusercontent.com/insomniakin/EromeAPI-main/main/app/assets/cashapp-qr.jpg", source)
        self.assertIn("Raw install source", source)
        self.assertIn("https://raw.githubusercontent.com/insomniakin/EromeAPI-main/main/userscript/erotok.user.js", source)


if __name__ == "__main__":
    unittest.main()
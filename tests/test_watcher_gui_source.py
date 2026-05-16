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

    def test_root_ui_stabilizes_download_status_layout(self):
        source = Path("ui.html").read_text(encoding="utf-8")

        self.assertIn("white-space: nowrap", source)
        self.assertIn("text-overflow: ellipsis", source)
        self.assertIn("statusEl.title = message", source)
        self.assertIn("min-width: 72px", source)
        self.assertIn("font-variant-numeric: tabular-nums", source)

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

    def test_sleazyfork_readme_requires_local_gui_api_and_assets(self):
        source = Path("SLEAZYFORK_README.md").read_text(encoding="utf-8")

        self.assertIn("EroTok Mini - SleazyFork Listing README", source)
        self.assertIn("Requires the local EroTok GUI/API from GitHub", source)
        self.assertIn("https://github.com/insomniakin/EromeAPI-main", source)
        self.assertIn("git clone https://github.com/insomniakin/EromeAPI-main.git", source)
        self.assertIn("pip install -r requirements.txt", source)
        self.assertIn("node server.js", source)
        self.assertIn("http://127.0.0.1:3000", source)
        self.assertIn("https://raw.githubusercontent.com/insomniakin/EromeAPI-main/main/docs/screenshots/erotok-control-panel.png", source)
        self.assertIn("https://raw.githubusercontent.com/insomniakin/EromeAPI-main/main/docs/screenshots/erotok-controls.png", source)
        self.assertIn("https://raw.githubusercontent.com/insomniakin/EromeAPI-main/main/app/assets/cashapp-qr.jpg", source)
        self.assertIn("Raw install source", source)
        self.assertIn("https://raw.githubusercontent.com/insomniakin/EromeAPI-main/main/userscript/erotok.user.js", source)


if __name__ == "__main__":
    unittest.main()
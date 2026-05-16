// ==UserScript==
// @name         EroTok Mini
// @namespace    https://github.com/insomniakin/EromeAPI-main
// @version      0.1.0
// @description  Local-first EroTok companion panel for public Erome pages. Uses your local EroTok server for search, preview, and downloads.
// @author       cjordanhot
// @match        https://www.erome.com/*
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// @connect      localhost
// @connect      github.com
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  const FULL_APP_URL = 'http://127.0.0.1:3000/';
  const GITHUB_URL = 'https://github.com/insomniakin/EromeAPI-main';
  const DEFAULT_API_BASE = 'http://127.0.0.1:3000';
  const SUGGESTED_HASHTAGS = [
    '#tattoos', '#alternative girl', '#egirl', '#redhair', '#outdoor', '#cosplay',
    '#pink hair', '#piercing', '#goth', '#alt style', '#cabelo rosa',
    '#skinny alternative', '#alternativa girl'
  ];
  const STORAGE_KEYS = {
    apiBase: 'erotok.apiBase',
    searchTerms: 'erotok.searchTerms',
    hideTerms: 'erotok.hideTerms',
    selectedTags: 'erotok.selectedTags',
    source: 'erotok.source',
  };

  const state = {
    apiBase: getValue(STORAGE_KEYS.apiBase, DEFAULT_API_BASE),
    searchTerms: getValue(STORAGE_KEYS.searchTerms, ''),
    hideTerms: getValue(STORAGE_KEYS.hideTerms, ''),
    selectedTags: parseHashtagInput(getValue(STORAGE_KEYS.selectedTags, '')),
    source: getValue(STORAGE_KEYS.source, 'search'),
    collapsed: false,
    results: [],
  };

  function getValue(key, fallback) {
    try { return GM_getValue(key, fallback); } catch { return fallback; }
  }

  function setValue(key, value) {
    try { GM_setValue(key, value); } catch {}
  }

  function normalizeText(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function normalizeHashtagLabel(value) {
    return normalizeText(value).replace(/^#+/, '').toLowerCase();
  }

  function uniqueTerms(terms) {
    const seen = new Set();
    return terms.filter((term) => {
      const key = normalizeHashtagLabel(term);
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function parseHashtagInput(value) {
    const raw = String(value || '').trim();
    if (!raw) return [];
    const terms = [];
    raw.split(/[,;\n\r]+/).forEach((group) => {
      const cleaned = group.trim();
      if (!cleaned) return;
      if ((cleaned.match(/#/g) || []).length > 1) {
        cleaned.split(/(?=#)/g).forEach((part) => {
          const tag = normalizeHashtagLabel(part);
          if (tag) terms.push(tag);
        });
        return;
      }
      const tag = normalizeHashtagLabel(cleaned);
      if (tag) terms.push(tag);
    });
    return uniqueTerms(terms);
  }

  function parseSearchTerms(value) {
    const raw = String(value || '').trim();
    if (!raw) return [];
    const terms = [];
    raw.split(/[,;\n\r]+/).forEach((group) => {
      const cleaned = group.trim();
      if (!cleaned) return;
      if (cleaned.includes('#')) {
        parseHashtagInput(cleaned).forEach((tag) => terms.push(`#${tag}`));
        return;
      }
      cleaned.split(/\s+/).forEach((term) => {
        if (term) terms.push(term);
      });
    });
    return uniqueTerms(terms);
  }

  function selectedHashtagQuery() {
    return state.selectedTags.map((tag) => `#${tag}`).join(', ');
  }

  function searchQuery() {
    return uniqueTerms([
      ...parseSearchTerms(selectedHashtagQuery()),
      ...parseSearchTerms(state.searchTerms),
    ]).join(', ');
  }

  function currentAlbumPath() {
    const match = location.pathname.match(/\/a\/([A-Za-z0-9]+)/);
    return match ? match[1] : '';
  }

  function currentProfileName() {
    const blocked = new Set(['a', 'search', 'explore', 'terms', 'login', 'register']);
    const first = location.pathname.split('/').filter(Boolean)[0] || '';
    return first && !blocked.has(first.toLowerCase()) ? first : '';
  }

  function buildUrl(path, params = {}) {
    const base = state.apiBase.replace(/\/+$/, '');
    const url = new URL(path, `${base}/`);
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value));
    });
    return url.toString();
  }

  function requestJson(method, path, params = {}, body = null) {
    return new Promise((resolve, reject) => {
      GM_xmlhttpRequest({
        method,
        url: buildUrl(path, params),
        headers: body ? { 'Content-Type': 'application/json' } : {},
        data: body ? JSON.stringify(body) : undefined,
        timeout: 30000,
        onload: (response) => {
          let parsed;
          try { parsed = JSON.parse(response.responseText || '{}'); }
          catch { parsed = { ok: false, error: response.responseText || 'Invalid JSON response' }; }
          if (response.status < 200 || response.status >= 300 || parsed.ok === false) {
            reject(new Error(parsed.error || `Request failed with ${response.status}`));
            return;
          }
          resolve(parsed);
        },
        onerror: () => reject(new Error('Could not reach local EroTok server. Start node server.js first.')),
        ontimeout: () => reject(new Error('Local EroTok server timed out.')),
      });
    });
  }

  function albumText(album) {
    return [
      album.title,
      album.url,
      album.username,
      album.description,
      ...(Array.isArray(album.tags) ? album.tags : []),
      ...(Array.isArray(album.matched_hashtags) ? album.matched_hashtags : []),
    ].map((value) => normalizeHashtagLabel(value)).join(' ');
  }

  function visibleAlbums(albums) {
    const hideTerms = parseSearchTerms(state.hideTerms).map(normalizeHashtagLabel).filter(Boolean);
    if (!hideTerms.length) return albums;
    return albums.filter((album) => {
      const text = albumText(album || {});
      return !hideTerms.some((term) => text.includes(term));
    });
  }

  function persistSettings() {
    setValue(STORAGE_KEYS.apiBase, state.apiBase);
    setValue(STORAGE_KEYS.searchTerms, state.searchTerms);
    setValue(STORAGE_KEYS.hideTerms, state.hideTerms);
    setValue(STORAGE_KEYS.selectedTags, selectedHashtagQuery());
    setValue(STORAGE_KEYS.source, state.source);
  }

  function setStatus(message, ok = true) {
    const status = document.getElementById('erotok-mini-status');
    if (!status) return;
    status.textContent = message;
    status.title = message;
    status.dataset.ok = ok ? 'true' : 'false';
  }

  function addHashtagTerms(terms) {
    state.selectedTags = uniqueTerms([...state.selectedTags, ...terms.map(normalizeHashtagLabel)]);
    persistSettings();
    renderHashtagChips();
  }

  function removeHashtagTerm(term) {
    const key = normalizeHashtagLabel(term);
    state.selectedTags = state.selectedTags.filter((tag) => normalizeHashtagLabel(tag) !== key);
    persistSettings();
    renderHashtagChips();
  }

  function renderHashtagChips() {
    const selected = document.getElementById('erotok-selected-tags');
    const suggested = document.getElementById('erotok-suggested-tags');
    if (!selected || !suggested) return;
    selected.textContent = '';
    state.selectedTags.forEach((tag) => {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'erotok-chip erotok-chip-active';
      chip.textContent = `#${tag} x`;
      chip.addEventListener('click', () => removeHashtagTerm(tag));
      selected.appendChild(chip);
    });
    suggested.textContent = '';
    SUGGESTED_HASHTAGS.forEach((tag) => {
      const normalized = normalizeHashtagLabel(tag);
      const active = state.selectedTags.includes(normalized);
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = `erotok-chip${active ? ' erotok-chip-active' : ''}`;
      chip.textContent = `#${normalized}`;
      chip.addEventListener('click', () => active ? removeHashtagTerm(normalized) : addHashtagTerms([normalized]));
      suggested.appendChild(chip);
    });
  }

  function resultCard(album) {
    const card = document.createElement('article');
    card.className = 'erotok-result-card';
    const title = album.title || 'Untitled album';
    const url = album.url || '';
    const path = albumPathFromUrl(url);
    card.innerHTML = `
      ${album.thumb ? `<img class="erotok-result-thumb" src="${escapeHtml(proxyUrl(album.thumb))}" alt="">` : ''}
      <div class="erotok-result-body">
        <div class="erotok-result-title">${escapeHtml(title)}</div>
        <div class="erotok-result-meta">${Number(album.images || 0)} photos · ${Number(album.videos || 0)} videos · ${Number(album.views || 0)} views</div>
        <div class="erotok-result-actions">
          <a href="${escapeHtml(url || '#')}" target="_blank" rel="noopener noreferrer">Open</a>
          <button type="button" data-action="download" ${path ? '' : 'disabled'}>Download</button>
        </div>
      </div>`;
    const download = card.querySelector('[data-action="download"]');
    if (download && path) download.addEventListener('click', () => downloadAlbum(path, title));
    return card;
  }

  function albumPathFromUrl(url) {
    const match = String(url || '').match(/\/a\/([A-Za-z0-9]+)/);
    return match ? match[1] : '';
  }

  function proxyUrl(url) {
    return buildUrl('/proxy', { url });
  }

  function escapeHtml(value) {
    return String(value || '').replace(/[&<>"']/g, (char) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[char]));
  }

  function renderResults(albums) {
    const host = document.getElementById('erotok-results');
    if (!host) return;
    host.textContent = '';
    const visible = visibleAlbums(Array.isArray(albums) ? albums : []);
    state.results = visible;
    if (!visible.length) {
      host.innerHTML = '<div class="erotok-empty">No public albums returned.</div>';
      return;
    }
    visible.slice(0, 24).forEach((album) => host.appendChild(resultCard(album)));
  }

  async function runSearch() {
    const keyword = searchQuery() || 'test';
    setStatus(`Searching ${keyword}...`, true);
    const result = await requestJson('GET', '/api/search', { keyword, page: 1, limit: 12, sort: 'default', dir: 'desc' });
    renderResults(result.data || []);
    setStatus(`Search loaded ${(result.data || []).length} album(s).`, true);
  }

  async function runExplore() {
    setStatus('Loading explore...', true);
    const result = await requestJson('GET', '/api/explore', { page: 1, limit: 12, new: 'false', sort: 'default', dir: 'desc' });
    renderResults(result.data || []);
    setStatus(`Explore loaded ${(result.data || []).length} album(s).`, true);
  }

  async function runProfile() {
    const profile = currentProfileName();
    if (!profile) throw new Error('Open a public profile page or type a profile search in the full app.');
    setStatus(`Loading profile ${profile}...`, true);
    const result = await requestJson('GET', '/api/profile', { profile, page: 1, limit: 12, content: 'albums' });
    renderResults((result.data && result.data.albums) || []);
    setStatus(`Profile loaded: ${profile}.`, true);
  }

  async function downloadAlbum(path, title = 'album') {
    setStatus(`Starting download: ${title}`, true);
    const result = await requestJson('POST', '/api/download/jobs', {}, {
      path,
      directory: 'Downloads',
      include_photos: true,
      include_videos: true,
      media_type: 'all',
      skip_downloaded: true,
      overwrite: false,
      max_workers: 4,
    });
    const job = result.data || {};
    setStatus(`Download job ${String(job.id || '').slice(0, 8)} started. Open full app for live progress.`, true);
  }

  async function downloadCurrentAlbum() {
    const path = currentAlbumPath();
    if (!path) throw new Error('This page is not an album page.');
    await downloadAlbum(path, document.title || path);
  }

  function setCollapsed(collapsed) {
    state.collapsed = collapsed;
    const panel = document.getElementById('erotok-mini');
    if (panel) panel.dataset.collapsed = collapsed ? 'true' : 'false';
  }

  function bindPanel() {
    const panel = document.getElementById('erotok-mini');
    if (!panel) return;
    const apiBase = panel.querySelector('#erotok-api-base');
    const searchTerms = panel.querySelector('#erotok-search-terms');
    const hideTerms = panel.querySelector('#erotok-hide-terms');
    const tagInput = panel.querySelector('#erotok-tag-input');

    apiBase.value = state.apiBase;
    searchTerms.value = state.searchTerms;
    hideTerms.value = state.hideTerms;

    apiBase.addEventListener('input', () => { state.apiBase = apiBase.value || DEFAULT_API_BASE; persistSettings(); });
    searchTerms.addEventListener('input', () => { state.searchTerms = searchTerms.value; persistSettings(); });
    hideTerms.addEventListener('input', () => { state.hideTerms = hideTerms.value; persistSettings(); renderResults(state.results); });

    panel.querySelector('#erotok-add-tags').addEventListener('click', () => {
      addHashtagTerms(parseHashtagInput(tagInput.value));
      tagInput.value = '';
    });
    tagInput.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      panel.querySelector('#erotok-add-tags').click();
    });
    panel.querySelector('#erotok-clear-tags').addEventListener('click', () => {
      state.selectedTags = [];
      persistSettings();
      renderHashtagChips();
    });
    panel.querySelector('#erotok-run-search').addEventListener('click', () => runSearch().catch((error) => setStatus(error.message || String(error), false)));
    panel.querySelector('#erotok-run-explore').addEventListener('click', () => runExplore().catch((error) => setStatus(error.message || String(error), false)));
    panel.querySelector('#erotok-run-profile').addEventListener('click', () => runProfile().catch((error) => setStatus(error.message || String(error), false)));
    panel.querySelector('#erotok-download-current').addEventListener('click', () => downloadCurrentAlbum().catch((error) => setStatus(error.message || String(error), false)));
    panel.querySelector('#erotok-collapse').addEventListener('click', () => setCollapsed(!state.collapsed));
    panel.querySelector('#erotok-open-full').addEventListener('click', () => window.open(FULL_APP_URL, '_blank', 'noopener,noreferrer'));
    panel.querySelector('#erotok-upgrade').addEventListener('click', () => window.open(GITHUB_URL, '_blank', 'noopener,noreferrer'));

    renderHashtagChips();
    setStatus('Ready. Start local server for downloads/search.', true);
  }

  function injectPanel() {
    if (document.getElementById('erotok-mini')) return;
    const panel = document.createElement('section');
    panel.id = 'erotok-mini';
    panel.dataset.collapsed = 'false';
    panel.innerHTML = `
      <div class="erotok-head">
        <div>
          <div class="erotok-title">EroTok Mini</div>
          <div class="erotok-subtitle">Local helper for public pages</div>
        </div>
        <button id="erotok-collapse" type="button" title="Collapse panel">_</button>
      </div>
      <div class="erotok-body">
        <div id="erotok-mini-status" class="erotok-status">Ready.</div>
        <label>Local server<input id="erotok-api-base" type="text"></label>
        <label>Keywords / hashtags<textarea id="erotok-search-terms" placeholder="travel, #outdoor, redhair"></textarea></label>
        <div class="erotok-tag-row">
          <input id="erotok-tag-input" type="text" placeholder="#redhair #outdoor or comma separated">
          <button id="erotok-add-tags" type="button">Add</button>
          <button id="erotok-clear-tags" type="button">Clear</button>
        </div>
        <div id="erotok-selected-tags" class="erotok-chips"></div>
        <div class="erotok-help">Tags combine with AND-style filtering in the local backend.</div>
        <div id="erotok-suggested-tags" class="erotok-chips"></div>
        <label>Hide terms<textarea id="erotok-hide-terms" placeholder="skip words, @names, #tags"></textarea></label>
        <div class="erotok-actions">
          <button id="erotok-run-search" type="button">Search</button>
          <button id="erotok-run-explore" type="button">Explore</button>
          <button id="erotok-run-profile" type="button">Profile</button>
          <button id="erotok-download-current" type="button">Download Page</button>
        </div>
        <div class="erotok-upgrade">
          <button id="erotok-open-full" type="button">Open full local app</button>
          <button id="erotok-upgrade" type="button">Upgrade on GitHub</button>
        </div>
        <div id="erotok-results" class="erotok-results"><div class="erotok-empty">Run Search, Explore, or Profile.</div></div>
      </div>`;
    document.body.appendChild(panel);
    bindPanel();
  }

  function injectStyles() {
    if (document.getElementById('erotok-mini-style')) return;
    const style = document.createElement('style');
    style.id = 'erotok-mini-style';
    style.textContent = `
      #erotok-mini {
        position: fixed;
        right: 16px;
        bottom: 16px;
        z-index: 2147483647;
        width: min(390px, calc(100vw - 24px));
        max-height: min(860px, calc(100vh - 24px));
        overflow: hidden;
        border: 1px solid rgba(255,255,255,.15);
        border-radius: 16px;
        background: linear-gradient(180deg, rgba(10,16,32,.98), rgba(4,8,18,.98));
        color: #f7f8f8;
        box-shadow: 0 18px 70px rgba(0,0,0,.55);
        font-family: Inter, Segoe UI, Arial, sans-serif;
      }
      #erotok-mini * { box-sizing: border-box; }
      #erotok-mini[data-collapsed="true"] .erotok-body { display: none; }
      .erotok-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px; border-bottom: 1px solid rgba(255,255,255,.12); }
      .erotok-title { font-size: 15px; font-weight: 900; }
      .erotok-subtitle { color: #9ca3af; font-size: 11px; }
      .erotok-body { display: grid; gap: 10px; max-height: calc(100vh - 92px); overflow: auto; padding: 12px; }
      #erotok-mini label { display: grid; gap: 6px; color: #9ca3af; font-size: 11px; font-weight: 800; }
      #erotok-mini input, #erotok-mini textarea, #erotok-mini button { border: 1px solid rgba(255,255,255,.13); border-radius: 10px; background: rgba(255,255,255,.06); color: #f7f8f8; font: inherit; padding: 9px 10px; }
      #erotok-mini textarea { min-height: 60px; resize: vertical; }
      #erotok-mini button { cursor: pointer; font-weight: 850; }
      #erotok-mini button:hover { border-color: #22d3ee; color: #fff; }
      .erotok-status { min-height: 34px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; border: 1px solid rgba(255,255,255,.13); border-radius: 10px; padding: 9px 10px; color: #bbf7d0; background: rgba(15,23,42,.9); font-size: 12px; }
      .erotok-status[data-ok="false"] { color: #fecaca; border-color: rgba(248,113,113,.5); }
      .erotok-tag-row { display: grid; grid-template-columns: minmax(0,1fr) auto auto; gap: 6px; }
      .erotok-chips { display: flex; flex-wrap: wrap; gap: 6px; }
      .erotok-chip { width: auto; border-radius: 999px !important; padding: 6px 9px !important; color: #d0d6e0 !important; font-size: 11px !important; }
      .erotok-chip-active { border-color: rgba(34,211,238,.58) !important; color: #a5f3fc !important; background: rgba(34,211,238,.12) !important; }
      .erotok-help { color: #9ca3af; font-size: 11px; line-height: 1.35; }
      .erotok-actions, .erotok-upgrade { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }
      #erotok-upgrade { background: linear-gradient(135deg, #818cf8, #22d3ee) !important; color: #07111f !important; }
      .erotok-results { display: grid; gap: 8px; }
      .erotok-empty { color: #9ca3af; font-size: 12px; padding: 8px; text-align: center; }
      .erotok-result-card { display: grid; grid-template-columns: 86px minmax(0,1fr); gap: 8px; border: 1px solid rgba(255,255,255,.12); border-radius: 12px; padding: 8px; background: rgba(255,255,255,.04); }
      .erotok-result-thumb { width: 86px; aspect-ratio: 4/3; object-fit: cover; border-radius: 8px; background: #000; }
      .erotok-result-body { min-width: 0; display: grid; gap: 6px; }
      .erotok-result-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; font-weight: 850; }
      .erotok-result-meta { color: #9ca3af; font-size: 11px; }
      .erotok-result-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
      .erotok-result-actions a { display: grid; place-items: center; border: 1px solid rgba(255,255,255,.13); border-radius: 10px; color: #a5f3fc; text-decoration: none; font-size: 12px; font-weight: 850; }
      @media (max-width: 520px) { #erotok-mini { right: 8px; bottom: 8px; } .erotok-actions, .erotok-upgrade { grid-template-columns: 1fr; } }
    `;
    document.head.appendChild(style);
  }

  injectStyles();
  injectPanel();
})();

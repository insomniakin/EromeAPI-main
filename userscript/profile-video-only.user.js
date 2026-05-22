// ==UserScript==
// @name         Profile Videos Only
// @namespace    https://github.com/insomniakin/EromeAPI-main
// @version      0.1.0
// @description  Adds a Videos only toggle on Erome/XXXErome profile pages.
// @author       cjordanhot
// @license      BSD-2-Clause
// @match        https://www.erome.com/*
// @match        https://xxxerome.com/*
// @match        https://www.xxxerome.com/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  const STORAGE_KEY = 'profile-videos-only-enabled';
  let enabled = localStorage.getItem(STORAGE_KEY) === '1';
  let observer = null;

  function isLikelyProfilePage() {
    const path = location.pathname || '';
    return /^\/a\//.test(path) || /^\/[A-Za-z0-9_.-]+\/?$/.test(path);
  }

  function allPostCards() {
    const selectors = [
      '.posts-list .post',
      '.posts-grid .post',
      'article.post',
      '.post-card',
      '.post'
    ];
    const nodes = new Set();
    selectors.forEach((selector) => {
      document.querySelectorAll(selector).forEach((node) => nodes.add(node));
    });
    return Array.from(nodes);
  }

  function hasDurationText(text) {
    return /\b(?:\d{1,2}:)?\d{1,2}:\d{2}\b/.test(text || '');
  }

  function cardIsVideo(card) {
    if (!card) return false;

    if (card.querySelector('video, source[src], [data-video], .video, .fa-play, .icon-play')) {
      return true;
    }

    const titleText = (card.textContent || '').replace(/\s+/g, ' ').trim();
    if (hasDurationText(titleText)) return true;

    const classBlob = (card.className || '').toString().toLowerCase();
    if (classBlob.includes('video')) return true;

    const link = card.querySelector('a[href*="/post/"]');
    if (link && hasDurationText(link.textContent || '')) return true;

    const badges = card.querySelectorAll('.badge, .tag, .label, .meta, .duration');
    for (const badge of badges) {
      if (hasDurationText(badge.textContent || '')) return true;
      const t = (badge.textContent || '').toLowerCase();
      if (t.includes('video') || t.includes('vid')) return true;
    }

    return false;
  }

  function setCardVisibility(card, show) {
    if (!card) return;
    if (!card.dataset.pvoDisplay) {
      card.dataset.pvoDisplay = card.style.display || '';
    }
    card.style.display = show ? (card.dataset.pvoDisplay || '') : 'none';
  }

  function statsText(videoCount, totalCount) {
    if (!totalCount) return 'No posts found';
    return `${videoCount} video posts / ${totalCount} total`;
  }

  function refreshFilter() {
    const cards = allPostCards();
    let videoCount = 0;

    cards.forEach((card) => {
      const isVideo = cardIsVideo(card);
      if (isVideo) videoCount += 1;
      setCardVisibility(card, enabled ? isVideo : true);
    });

    const status = document.getElementById('pvo-status');
    if (status) status.textContent = statsText(videoCount, cards.length);
  }

  function setEnabled(next) {
    enabled = !!next;
    localStorage.setItem(STORAGE_KEY, enabled ? '1' : '0');
    const toggle = document.getElementById('pvo-toggle');
    if (toggle) toggle.textContent = enabled ? 'Videos only: ON' : 'Videos only: OFF';
    refreshFilter();
  }

  function ensureToolbar() {
    if (document.getElementById('pvo-toolbar')) return;

    const toolbar = document.createElement('div');
    toolbar.id = 'pvo-toolbar';
    toolbar.style.cssText = [
      'position:fixed',
      'right:14px',
      'bottom:14px',
      'z-index:999999',
      'display:flex',
      'flex-direction:column',
      'gap:8px',
      'background:rgba(10,12,20,0.92)',
      'border:1px solid rgba(255,255,255,0.18)',
      'border-radius:10px',
      'padding:10px',
      'color:#fff',
      'font:12px/1.3 Arial, sans-serif',
      'box-shadow:0 8px 24px rgba(0,0,0,0.35)'
    ].join(';');

    const toggle = document.createElement('button');
    toggle.id = 'pvo-toggle';
    toggle.type = 'button';
    toggle.style.cssText = 'cursor:pointer;border:1px solid #666;border-radius:6px;background:#111827;color:#fff;padding:6px 9px;';
    toggle.onclick = () => setEnabled(!enabled);

    const refresh = document.createElement('button');
    refresh.type = 'button';
    refresh.textContent = 'Refresh scan';
    refresh.style.cssText = 'cursor:pointer;border:1px solid #666;border-radius:6px;background:#111827;color:#fff;padding:6px 9px;';
    refresh.onclick = () => refreshFilter();

    const status = document.createElement('div');
    status.id = 'pvo-status';
    status.textContent = 'Scanning...';

    toolbar.appendChild(toggle);
    toolbar.appendChild(refresh);
    toolbar.appendChild(status);
    document.body.appendChild(toolbar);

    setEnabled(enabled);
  }

  function startObserver() {
    if (observer) observer.disconnect();
    observer = new MutationObserver(() => {
      if (!enabled) return;
      refreshFilter();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function init() {
    if (!isLikelyProfilePage()) return;
    ensureToolbar();
    startObserver();
    refreshFilter();
  }

  init();
})();

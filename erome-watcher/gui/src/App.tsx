import { FormEvent, ReactNode, useEffect, useMemo, useState } from 'react';
import VideoPlayerClone from './components/VideoPlayerClone';

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

type IndexStats = {
  snapshot_count: number;
  indexed_album_count: number;
  indexed_profile_count: number;
  latest_snapshot_at: string | null;
  latest_indexed_at: string | null;
  fts_row_count?: number;
  note?: string;
};

type HealthResponse = {
  status: string;
  version: string;
  gui_packaged?: boolean;
  index_stats: IndexStats;
};

type SearchResult = {
  album_id: string;
  username: string;
  title: string;
  url: string;
  thumbnail_url?: string | null;
  published_text?: string | null;
  views_text?: string | null;
  views_estimate?: number | null;
  description?: string | null;
  media_count?: number | null;
  tags?: string;
  source?: string | null;
  profile_url: string;
  snapshot_fetched_at: string;
  indexed_at: string;
  score: number;
  rank?: number | null;
  matched_terms: string[];
};

type SearchResponse = {
  query: string;
  username?: string | null;
  limit: number;
  total_returned: number;
  sort_by: string;
  source?: string | null;
  min_views?: number | null;
  index_stats: IndexStats;
  results: SearchResult[];
  note?: string;
};

type HistoryEntry = {
  fetched_at: string;
  album_count: number;
  profile_url: string;
};

type HistoryResponse = {
  username: string;
  history: HistoryEntry[];
};

type WatchAlertResponse = {
  username?: string;
  summary?: string;
  telegram_text?: string;
  discord_text?: string;
  new_album_count?: number;
  removed_album_count?: number;
  message?: string;
};

type IndexActionResponse = {
  note?: string;
  index_stats?: IndexStats;
  rebuild?: {
    profiles_indexed: number;
    albums_indexed: number;
    usernames: string[];
  };
  indexing?: {
    albums_indexed: number;
    username: string;
  };
  mode?: string;
  snapshot?: {
    username: string;
    album_count: number;
    fetched_at: string;
  };
};

type AlbumSnapshotResponse = {
  album_url: string;
  fetched_at: string;
  title?: string | null;
  username?: string | null;
  description?: string | null;
  media_urls: string[];
  tags: string[];
};

type MediaEntry = {
  url: string;
  kind: 'video' | 'image';
  label: string;
  poster?: string | null;
};

type ApiError = {
  message: string;
  detail?: JsonValue;
};

type DownloadJob = {
  id: string;
  kind: string;
  status: 'running' | 'retrying' | 'done' | 'error' | string;
  percent: number;
  completed: number;
  total: number;
  attempts: number;
  retry_count: number;
  last_error?: string | null;
  current?: {
    filename?: string;
    status?: string;
    attempts?: number;
  } | null;
  result?: JsonValue;
  error?: string | null;
};

type DownloadJobEnvelope = {
  ok: boolean;
  data: DownloadJob;
};

const DEFAULT_API_BASE = (() => {
  const origin = window.location.origin.startsWith('http') ? window.location.origin : 'http://127.0.0.1:8011';
  return window.location.pathname.startsWith('/watcher') ? `${origin}/api/watcher` : origin;
})();
const MAIN_APP_MOUNTED = window.location.pathname.startsWith('/watcher') || DEFAULT_API_BASE.endsWith('/api/watcher');

function mediaDisplayUrl(url?: string | null) {
  const raw = String(url || '').trim();
  if (!raw) return '';
  const normalized = raw.startsWith('//') ? `https:${raw}` : raw;
  if (!MAIN_APP_MOUNTED) return normalized;

  try {
    const parsed = new URL(normalized, window.location.origin);
    if (parsed.hostname.toLowerCase().endsWith('erome.com')) {
      return `/proxy?url=${encodeURIComponent(parsed.href)}`;
    }
  } catch {
    return normalized;
  }

  return normalized;
}

function normalizeTag(value: string) {
  return value.trim().replace(/^#+/, '').replace(/\s+/g, ' ').toLowerCase();
}

function tagsFromText(value: string) {
  return value
    .split(/[#,\s]+/)
    .map(normalizeTag)
    .filter(Boolean);
}

function searchQueryWithTags(query: string, tags: string[]) {
  const parts = [query.trim(), ...tags.map((tag) => `#${normalizeTag(tag)}`)].filter(Boolean);
  return parts.join(' ');
}

function tagsFromSearchResult(result?: SearchResult | null) {
  if (!result?.tags) return [];
  return tagsFromText(result.tags);
}
const QUICK_USERS = ['Hellokitty66695'];
const SORT_OPTIONS = [
  { value: 'relevance', label: 'Relevance' },
  { value: 'recent', label: 'Most recent' },
  { value: 'views', label: 'Highest views' },
  { value: 'title', label: 'Title A–Z' },
] as const;
const SOURCE_OPTIONS = [
  { value: '', label: 'Any source' },
  { value: 'profile', label: 'Profile' },
  { value: 'explore', label: 'Explore' },
  { value: 'search', label: 'Live search ingest' },
] as const;

function formatDate(value?: string | null) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function timeAgo(value?: string | null) {
  if (!value) return 'never';
  const now = Date.now();
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return value;
  const diff = Math.max(0, now - then);
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatViews(value?: number | null) {
  if (value == null) return '—';
  return new Intl.NumberFormat().format(value);
}

function isPlayableMedia(url: string) {
  return /\.(mp4|webm|m3u8)(\?|$)/i.test(url);
}

function isImageMedia(url: string) {
  return /\.(jpg|jpeg|png|webp|gif)(\?|$)/i.test(url);
}

function isNoiseAsset(url: string) {
  return /avatar\.erome\.com|logo-erome-(horizontal|vertical)\.png|\/img\/bg\.jpg/i.test(url);
}

function buildMediaEntries(mediaUrls: string[], thumbnailUrl?: string | null): MediaEntry[] {
  const seen = new Set<string>();
  const entries: MediaEntry[] = [];
  let videoIndex = 0;
  let imageIndex = 0;

  for (const url of mediaUrls) {
    if (!url || seen.has(url) || isNoiseAsset(url)) continue;
    seen.add(url);

    if (isPlayableMedia(url)) {
      videoIndex += 1;
      entries.push({
        url,
        kind: 'video',
        label: `Video ${videoIndex}`,
        poster: thumbnailUrl ?? null,
      });
      continue;
    }

    if (isImageMedia(url)) {
      imageIndex += 1;
      entries.push({
        url,
        kind: 'image',
        label: `Image ${imageIndex}`,
        poster: url,
      });
    }
  }

  if (!entries.length && thumbnailUrl && !seen.has(thumbnailUrl)) {
    entries.push({
      url: thumbnailUrl,
      kind: 'image',
      label: 'Thumbnail',
      poster: thumbnailUrl,
    });
  }

  return entries;
}

async function parseResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  const data = text ? (JSON.parse(text) as T | { detail?: JsonValue }) : ({} as T);
  if (!response.ok) {
    const detail = typeof data === 'object' && data && 'detail' in data ? data.detail : text;
    throw new Error(typeof detail === 'string' ? detail : `HTTP ${response.status}`);
  }
  return data as T;
}

function buildApiUrl(baseUrl: string, path: string) {
  const base = baseUrl.trim().replace(/\/+$/, '');
  const suffix = path.startsWith('/') ? path : `/${path}`;
  return `${base}${suffix}`;
}

async function fetchJson<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildApiUrl(baseUrl, path), {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });
  return parseResponse<T>(response);
}

function MetricCard({ label, value, hint }: { label: string; value: string | number; hint: string }) {
  return (
    <div className="panel-muted rounded-2xl p-4">
      <div className="text-[11px] uppercase tracking-[0.24em] text-[color:var(--color-text-muted)]">{label}</div>
      <div className="mt-3 text-3xl font-semibold tracking-tight text-[color:var(--color-text-main)]">{value}</div>
      <div className="mt-2 text-sm text-[color:var(--color-text-muted)]">{hint}</div>
    </div>
  );
}

function SectionTitle({ eyebrow, title, body }: { eyebrow: string; title: string; body: string }) {
  return (
    <div>
      <div className="text-[11px] font-medium uppercase tracking-[0.3em] text-[color:var(--color-brand-bright)]">{eyebrow}</div>
      <h2 className="mt-3 text-2xl font-semibold tracking-[-0.04em] text-[color:var(--color-text-main)]">{title}</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-[color:var(--color-text-muted)]">{body}</p>
    </div>
  );
}

function FilterChip({ active, children }: { active: boolean; children: ReactNode }) {
  return (
    <span
      className={[
        'rounded-full border px-3 py-1.5 text-[11px] uppercase tracking-[0.18em]',
        active
          ? 'border-[color:var(--color-brand-bright)] bg-[color:var(--color-brand-soft)] text-[color:var(--color-brand-bright)]'
          : 'border-white/10 bg-white/5 text-[color:var(--color-text-muted)]',
      ].join(' ')}
    >
      {children}
    </span>
  );
}

function AlbumMediaViewer({
  title,
  entries,
  currentMedia,
  currentIndex,
  poster,
  compact = false,
  onSelect,
  onPrevious,
  onNext,
}: {
  title: string;
  entries: MediaEntry[];
  currentMedia: MediaEntry | null;
  currentIndex: number;
  poster?: string | null;
  compact?: boolean;
  onSelect: (index: number) => void;
  onPrevious: () => void;
  onNext: () => void;
}) {
  const previewHeight = compact ? 'h-72 md:h-80' : 'h-[340px] md:h-[440px]';

  return (
    <div className="watcher-media-viewer min-w-0 max-w-full space-y-4">
      <div className="overflow-hidden rounded-[24px] border border-white/8 bg-black/35">
        {currentMedia ? (
          currentMedia.kind === 'video' ? (
            <VideoPlayerClone key={currentMedia.url} src={mediaDisplayUrl(currentMedia.url)} poster={mediaDisplayUrl(currentMedia.poster ?? poster)} title={title} />
          ) : (
            <div className={`${previewHeight} bg-black/70`}>
              <img src={mediaDisplayUrl(currentMedia.url)} alt={title} className="h-full w-full object-contain" />
            </div>
          )
        ) : (
          <div className={`${previewHeight} flex items-center justify-center text-xs uppercase tracking-[0.2em] text-white/30`}>
            No playable or preview media extracted yet
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5">{currentMedia?.label ?? 'No media'}</span>
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5">{currentMedia?.kind ?? 'none'}</span>
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5">{entries.length} item{entries.length === 1 ? '' : 's'}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm font-medium hover:border-[color:var(--color-brand-bright)] hover:text-white disabled:opacity-40"
            onClick={onPrevious}
            disabled={entries.length < 2}
          >
            ← Prev
          </button>
          <button
            type="button"
            className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm font-medium hover:border-[color:var(--color-brand-bright)] hover:text-white disabled:opacity-40"
            onClick={onNext}
            disabled={entries.length < 2}
          >
            Next →
          </button>
        </div>
      </div>

      {entries.length > 0 && (
        <div className="watcher-media-strip flex min-w-0 max-w-full gap-3 overflow-x-auto overflow-y-hidden pb-1">
          {entries.map((entry, index) => {
            const thumb = entry.kind === 'image' ? entry.url : entry.poster ?? poster ?? null;
            return (
              <button
                key={`${entry.url}-${index}`}
                type="button"
                onClick={() => onSelect(index)}
                className={[
                  'group relative w-28 shrink-0 overflow-hidden rounded-2xl border bg-black/40 text-left transition',
                  index === currentIndex
                    ? 'border-[color:var(--color-brand-bright)] shadow-[0_0_0_1px_rgba(113,112,255,0.35)]'
                    : 'border-white/10 hover:border-[color:var(--color-brand-bright)]',
                ].join(' ')}
              >
                <div className="relative h-20 w-full overflow-hidden bg-black/70">
                  {thumb ? (
                    <img src={mediaDisplayUrl(thumb)} alt={entry.label} className="h-full w-full object-cover transition duration-200 group-hover:scale-[1.03]" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-[10px] uppercase tracking-[0.2em] text-white/35">{entry.kind}</div>
                  )}
                  {entry.kind === 'video' && <div className="absolute right-2 top-2 rounded-full bg-black/75 px-2 py-1 text-[10px] font-semibold text-white">▶</div>}
                </div>
                <div className="px-3 py-2">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-text-muted)]">{entry.label}</div>
                  <div className="mt-1 text-xs font-medium text-[color:var(--color-text-main)]">{entry.kind}</div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [apiBaseInput, setApiBaseInput] = useState(DEFAULT_API_BASE);
  const [apiBase, setApiBase] = useState(DEFAULT_API_BASE);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [search, setSearch] = useState<SearchResponse | null>(null);
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [watchAlert, setWatchAlert] = useState<WatchAlertResponse | null>(null);
  const [selectedUser, setSelectedUser] = useState('Hellokitty66695');
  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(null);
  const [selectedAlbum, setSelectedAlbum] = useState<AlbumSnapshotResponse | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [currentMediaIndex, setCurrentMediaIndex] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchUser, setSearchUser] = useState('Hellokitty66695');
  const [searchLimit, setSearchLimit] = useState(12);
  const [sortBy, setSortBy] = useState('relevance');
  const [sourceFilter, setSourceFilter] = useState('');
  const [minViewsInput, setMinViewsInput] = useState('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState('');
  const [indexProfileInput, setIndexProfileInput] = useState('Hellokitty66695');
  const [enrichProfile, setEnrichProfile] = useState(true);
  const [explorePage, setExplorePage] = useState(1);
  const [statusMessage, setStatusMessage] = useState('Ready. API is public-index only, not a private-content bypasser.');
  const [downloadJobs, setDownloadJobs] = useState<DownloadJob[]>([]);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const effectiveStats = useMemo(() => search?.index_stats ?? health?.index_stats ?? null, [health, search]);
  const topResult = search?.results[0] ?? null;
  const activeMinViews = minViewsInput.trim() ? Number(minViewsInput) || 0 : null;
  const galleryEntries = useMemo(
    () => buildMediaEntries(selectedAlbum?.media_urls ?? [], selectedResult?.thumbnail_url ?? null),
    [selectedAlbum, selectedResult],
  );
  const currentMedia = galleryEntries[currentMediaIndex] ?? null;
  const hasVideo = galleryEntries.some((entry) => entry.kind === 'video');
  const tagPalette = useMemo(() => {
    const tags = new Set<string>();
    for (const tag of selectedAlbum?.tags ?? []) tags.add(normalizeTag(tag));
    for (const tag of tagsFromSearchResult(selectedResult)) tags.add(tag);
    for (const result of search?.results ?? []) {
      for (const tag of tagsFromSearchResult(result)) tags.add(tag);
    }
    return Array.from(tags).filter(Boolean).slice(0, 32);
  }, [search, selectedAlbum, selectedResult]);

  function toggleTag(tag: string) {
    const normalized = normalizeTag(tag);
    if (!normalized) return;
    setSelectedTags((current) =>
      current.includes(normalized) ? current.filter((item) => item !== normalized) : [...current, normalized],
    );
  }

  function addTagsFromInput() {
    const tags = tagsFromText(tagInput);
    if (!tags.length) return;
    setSelectedTags((current) => Array.from(new Set([...current, ...tags])));
    setTagInput('');
  }

  async function runTask<T>(key: string, task: () => Promise<T>) {
    setBusyKey(key);
    setError(null);
    try {
      return await task();
    } catch (taskError) {
      const message = taskError instanceof Error ? taskError.message : 'Unknown error';
      setError({ message });
      throw taskError;
    } finally {
      setBusyKey(null);
    }
  }

  function rememberDownloadJob(job: DownloadJob) {
    setDownloadJobs((current) => {
      const next = current.filter((item) => item.id !== job.id);
      return [job, ...next].slice(0, 8);
    });
    return job;
  }

  function describeDownloadJob(job: DownloadJob, title: string) {
    const total = job.total ? `${job.completed}/${job.total}` : `${job.completed || 0}/?`;
    const current = job.current?.filename ? ` ${job.current.filename}` : '';
    const retry = job.last_error ? ` Retrying after: ${job.last_error}` : '';
    return `${title}: ${job.percent || 0}% (${total}) ${job.status}${current}.${retry}`;
  }

  function downloadResultCount(job: DownloadJob) {
    if (Array.isArray(job.result)) return job.result.length;
    if (job.result && typeof job.result === 'object' && !Array.isArray(job.result) && 'count' in job.result) {
      const count = (job.result as { count?: JsonValue }).count;
      return typeof count === 'number' ? count : 0;
    }
    return job.completed || 0;
  }

  async function wait(ms: number) {
    await new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  async function pollDownloadJob(jobId: string, title: string) {
    while (true) {
      await wait(900);
      const envelope = await fetchJson<DownloadJobEnvelope>(apiBase, `/download/jobs/${encodeURIComponent(jobId)}`);
      const job = rememberDownloadJob(envelope.data);
      setStatusMessage(describeDownloadJob(job, title));
      if (job.status === 'done' || job.status === 'error') return job;
    }
  }

  async function startAlbumDownloadJob(result: SearchResult) {
    const envelope = await fetchJson<DownloadJobEnvelope>(apiBase, '/download/jobs', {
      method: 'POST',
      body: JSON.stringify({
        url: result.url,
        directory: 'Downloads',
        include_photos: true,
        include_videos: true,
        overwrite: false,
        max_workers: 4,
      }),
    });
    const started = rememberDownloadJob(envelope.data);
    setStatusMessage(describeDownloadJob(started, result.title));
    if (started.status === 'done' || started.status === 'error') return started;
    return pollDownloadJob(started.id, result.title);
  }

  function stepMedia(direction: number) {
    if (!galleryEntries.length) return;
    setCurrentMediaIndex((prev) => (prev + direction + galleryEntries.length) % galleryEntries.length);
  }

  async function refreshHealth() {
    const data = await runTask('health', () => fetchJson<HealthResponse>(apiBase, '/health'));
    setHealth(data);
    setStatusMessage(
      `Connected to API v${data.version}. ${data.index_stats.indexed_album_count} indexed albums ready${data.gui_packaged ? ' with packaged GUI' : ''}.`,
    );
  }

  async function runSearch(
    query = searchQuery,
    username = searchUser,
    limit = searchLimit,
    nextSortBy = sortBy,
    nextSource = sourceFilter,
    nextMinViews = activeMinViews,
    nextTags = selectedTags,
  ) {
    const params = new URLSearchParams();
    const effectiveQuery = searchQueryWithTags(query, nextTags);
    if (effectiveQuery) params.set('query', effectiveQuery);
    if (username.trim()) params.set('username', username.trim());
    params.set('limit', String(limit));
    params.set('sort_by', nextSortBy);
    if (nextSource.trim()) params.set('source', nextSource.trim());
    if (nextMinViews != null && !Number.isNaN(nextMinViews)) params.set('min_views', String(nextMinViews));

    const data = await runTask('search', () => fetchJson<SearchResponse>(apiBase, `/search?${params.toString()}`));
    setSearch(data);
    setSelectedAlbum(null);
    setCurrentMediaIndex(0);

    if (data.results[0]) {
      await inspectResult(data.results[0], data, false);
    } else {
      setSelectedResult(null);
      setDrawerOpen(false);
    }

    setStatusMessage(`Search returned ${data.total_returned} result${data.total_returned === 1 ? '' : 's'}${nextTags.length ? ` for ${nextTags.map((tag) => `#${tag}`).join(' ')}` : ''}.`);
  }

  async function downloadSelectedAlbum(result = selectedResult) {
    if (!result) return;
    setError(null);
    try {
      const job = await startAlbumDownloadJob(result);
      const count = downloadResultCount(job);
      if (job.status === 'done') {
        setStatusMessage(`Downloaded or skipped ${count} media file${count === 1 ? '' : 's'} for ${result.title}.`);
      } else {
        setStatusMessage(`Download ended with an error for ${result.title}: ${job.error || job.last_error || 'unknown error'}`);
      }
    } catch (downloadError) {
      const message = downloadError instanceof Error ? downloadError.message : 'Unknown download error';
      setError({ message });
      setStatusMessage(`Download failed to start: ${message}`);
    }
  }

  async function inspectResult(result: SearchResult, searchState = search, openDrawer = false) {
    setSelectedResult(result);
    setDrawerOpen(openDrawer);
    const album = await runTask('album', () => fetchJson<AlbumSnapshotResponse>(apiBase, `/album?url=${encodeURIComponent(result.url)}`));
    setSelectedAlbum(album);
    const entries = buildMediaEntries(album.media_urls ?? [], result.thumbnail_url ?? null);
    const preferredIndex = entries.findIndex((entry) => entry.kind === 'video');
    setCurrentMediaIndex(preferredIndex >= 0 ? preferredIndex : 0);
    setStatusMessage(`Loaded album details for ${result.title}. ${entries.length} gallery item${entries.length === 1 ? '' : 's'} ready.`);
    if (searchState) setSearch(searchState);
  }

  async function loadHistory(username = selectedUser) {
    const data = await runTask('history', () => fetchJson<HistoryResponse>(apiBase, `/profile/${encodeURIComponent(username)}/history?limit=12`));
    setHistory(data);
    setStatusMessage(`Loaded ${data.history.length} history entries for ${username}.`);
  }

  async function loadAlert(username = selectedUser) {
    const data = await runTask('watch', () =>
      fetchJson<WatchAlertResponse>(apiBase, '/watch/alert', {
        method: 'POST',
        body: JSON.stringify({ username, persist: true }),
      }),
    );
    setWatchAlert(data);
    setStatusMessage(
      data.summary ? `Watcher checked ${username}: +${data.new_album_count ?? 0} / -${data.removed_album_count ?? 0}.` : data.message ?? `Watcher checked ${username}.`,
    );
    await Promise.all([refreshHealth(), runSearch(searchQuery, searchUser, searchLimit), loadHistory(username)]);
  }

  async function rebuildIndex() {
    const data = await runTask('rebuild', () =>
      fetchJson<IndexActionResponse>(apiBase, '/index/rebuild', {
        method: 'POST',
        body: JSON.stringify({}),
      }),
    );
    setStatusMessage(`Rebuilt local index for ${data.rebuild?.profiles_indexed ?? 0} profile(s).`);
    await Promise.all([refreshHealth(), runSearch(searchQuery, searchUser, searchLimit)]);
  }

  async function indexProfile(username = indexProfileInput) {
    const trimmed = username.trim();
    if (!trimmed) return;
    const data = await runTask('index-profile', () =>
      fetchJson<IndexActionResponse>(apiBase, '/index/profile', {
        method: 'POST',
        body: JSON.stringify({ username: trimmed, enrich_albums: enrichProfile, max_enrich: 24 }),
      }),
    );
    setSelectedUser(trimmed);
    setSearchUser(trimmed);
    setIndexProfileInput(trimmed);
    setStatusMessage(`Indexed ${data.indexing?.albums_indexed ?? 0} public album(s) for ${trimmed}.`);
    await Promise.all([refreshHealth(), runSearch(searchQuery, trimmed, searchLimit), loadHistory(trimmed)]);
  }

  async function indexExplore() {
    const data = await runTask('index-explore', () =>
      fetchJson<IndexActionResponse>(apiBase, '/index/explore', {
        method: 'POST',
        body: JSON.stringify({ page: explorePage, persist_snapshot: true }),
      }),
    );
    setStatusMessage(`Explore page ${explorePage} indexed ${data.indexing?.albums_indexed ?? 0} album(s) into local search.`);
    await Promise.all([refreshHealth(), runSearch(searchQuery, searchUser, searchLimit)]);
  }

  useEffect(() => {
    void (async () => {
      try {
        await refreshHealth();
        await runSearch();
        await loadHistory();
      } catch {
        // handled by runTask
      }
    })();
  }, [apiBase]);

  return (
    <div className="relative min-h-screen overflow-hidden text-[color:var(--color-text-main)]">
      <div className="grid-bg absolute inset-0 opacity-40" />
      <div className="watcher-shell relative mx-auto flex min-h-screen max-w-[1660px] flex-col px-3 py-4 sm:px-6 sm:py-8 lg:px-8">
        <header className="watcher-hero panel glow-ring overflow-hidden rounded-[20px] px-4 py-5 sm:rounded-[28px] sm:px-6 sm:py-6 lg:px-8">
          <div className="flex flex-col gap-8 xl:flex-row xl:items-end xl:justify-between">
            <div className="max-w-3xl">
              <div className="text-[11px] font-medium uppercase tracking-[0.34em] text-[color:var(--color-brand-bright)]">Erome Watcher / Control Room</div>
              <h1 className="mt-4 text-2xl font-semibold tracking-[-0.04em] text-[color:var(--color-text-main)] sm:text-5xl sm:tracking-[-0.06em]">
                Local discovery engine with ranked search, filters, and fast operator tooling.
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-[color:var(--color-text-soft)]">
                Search indexed public albums, refresh watched profiles, inspect history, and manage your local discovery graph. This UI is built for serious public-content discovery, not for bypassing private or access-controlled content.
              </p>
            </div>
            <div className="panel-muted rounded-2xl p-4 xl:w-[420px]">
              <div className="text-[11px] uppercase tracking-[0.28em] text-[color:var(--color-text-muted)]">API base</div>
              <form
                className="mt-3 flex gap-2"
                onSubmit={(event: FormEvent<HTMLFormElement>) => {
                  event.preventDefault();
                  setApiBase(apiBaseInput.trim() || DEFAULT_API_BASE);
                }}
              >
                <input
                  value={apiBaseInput}
                  onChange={(event) => setApiBaseInput(event.target.value)}
                  className="min-w-0 flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none placeholder:text-white/35 focus:border-[color:var(--color-brand-bright)]"
                  placeholder="http://127.0.0.1:8011"
                />
                <button type="submit" className="rounded-xl bg-[color:var(--color-brand)] px-4 py-3 text-sm font-medium text-white transition hover:bg-[color:var(--color-brand-bright)]">
                  Connect
                </button>
              </form>
              <div className="mt-3 flex items-center justify-between gap-3 text-xs text-[color:var(--color-text-muted)]">
                <span>{statusMessage}</span>
                <button className="text-[color:var(--color-brand-bright)] hover:text-white" onClick={() => void refreshHealth()}>
                  Refresh
                </button>
              </div>
              {downloadJobs.length > 0 && (
                <div className="mt-4 space-y-2">
                  {downloadJobs.map((job) => (
                    <div key={job.id} className="rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-[color:var(--color-text-muted)]">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-medium text-[color:var(--color-text-main)]">{job.kind} {job.id.slice(0, 8)}</span>
                        <span>{job.percent || 0}%</span>
                      </div>
                      <progress className="mt-2 h-2 w-full overflow-hidden rounded-full accent-[color:var(--color-brand-bright)]" value={Math.max(0, Math.min(100, job.percent || 0))} max={100} />
                      <div className="mt-2 flex flex-wrap gap-2">
                        <span>{job.status}</span>
                        <span>{job.completed || 0}/{job.total || '?'} files</span>
                        <span>{job.retry_count || 0} retries</span>
                        {job.current?.filename && <span>{job.current.filename}</span>}
                      </div>
                      {job.last_error && <div className="mt-2 text-rose-200">Retrying after: {job.last_error}</div>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="watcher-main mt-5 grid gap-5 sm:mt-8 sm:gap-8 xl:grid-cols-[1.25fr_0.75fr]">
          <section className="flex flex-col gap-5 sm:gap-8">
            <div className="order-1 grid gap-3 sm:grid-cols-2 sm:gap-4 xl:grid-cols-5">
              <MetricCard label="Indexed albums" value={effectiveStats?.indexed_album_count ?? '—'} hint={`Last indexed ${timeAgo(effectiveStats?.latest_indexed_at)}`} />
              <MetricCard label="Snapshots" value={effectiveStats?.snapshot_count ?? '—'} hint={`Latest snapshot ${timeAgo(effectiveStats?.latest_snapshot_at)}`} />
              <MetricCard label="Profiles" value={effectiveStats?.indexed_profile_count ?? '—'} hint="Indexed public personas" />
              <MetricCard label="FTS rows" value={effectiveStats?.fts_row_count ?? '—'} hint="Full-text mirror health" />
              <MetricCard label="API version" value={health?.version ?? '—'} hint={health?.gui_packaged ? 'Packaged GUI active' : health?.status === 'ok' ? 'Healthy and listening' : 'Waiting for health'} />
            </div>

            <div className="watcher-player-panel panel order-3 rounded-[20px] p-4 sm:rounded-[28px] sm:p-6 lg:p-8 xl:order-2">
              <SectionTitle
                eyebrow="Screening room"
                title="Active album player"
                body="The selected result drives a central preview stage with next/previous media navigation and thumbnail-strip previews. Use Inspect when you want the full details drawer."
              />

              {selectedResult ? (
                <div className="mt-6 space-y-5">
                  <AlbumMediaViewer
                    title={selectedAlbum?.title ?? selectedResult.title}
                    entries={galleryEntries}
                    currentMedia={currentMedia}
                    currentIndex={currentMediaIndex}
                    poster={selectedResult.thumbnail_url ?? null}
                    onSelect={setCurrentMediaIndex}
                    onPrevious={() => stepMedia(-1)}
                    onNext={() => stepMedia(1)}
                  />

                  <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr_auto]">
                    <div className="panel-muted rounded-2xl p-4">
                      <div className="text-xs uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">Active selection</div>
                      <div className="mt-3 text-lg font-medium text-[color:var(--color-text-main)]">{selectedResult.title}</div>
                      <div className="mt-2 text-sm text-[color:var(--color-text-muted)]">
                        @{selectedResult.username} • {selectedResult.views_text ?? 'views unknown'} • {selectedResult.source ?? 'indexed'}
                      </div>
                      <div className="mt-4 grid gap-2 text-sm text-[color:var(--color-text-soft)]">
                        <div>Current media: {currentMedia?.label ?? 'none selected'}</div>
                        <div>Current type: {currentMedia?.kind ?? 'none'}</div>
                        <div>Gallery items: {galleryEntries.length}</div>
                        <div>Playable video present: {hasVideo ? 'yes' : 'no'}</div>
                      </div>
                    </div>

                    <div className="panel-muted rounded-2xl p-4">
                      <div className="text-xs uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">Tag preview</div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {(selectedAlbum?.tags ?? []).slice(0, 8).map((tag) => (
                          <button key={tag} type="button" className="rounded-full border border-white/10 px-3 py-1.5 text-xs uppercase tracking-[0.18em] hover:border-[color:var(--color-brand-bright)] hover:text-white" onClick={() => toggleTag(tag)}>
                            #{tag}
                          </button>
                        ))}
                        {!(selectedAlbum?.tags ?? []).length && <span className="text-sm text-[color:var(--color-text-muted)]">No public tags extracted yet.</span>}
                      </div>
                    </div>

                    <div className="flex flex-col gap-3">
                      <button
                        type="button"
                        className="rounded-2xl bg-[color:var(--color-success)] px-4 py-3 text-sm font-medium text-white transition hover:brightness-110 disabled:opacity-50"
                        onClick={() => void downloadSelectedAlbum()}
                        disabled={busyKey === 'download'}
                      >
                        {busyKey === 'download' ? 'Downloading...' : 'Download album'}
                      </button>
                      <button
                        type="button"
                        className="rounded-2xl bg-[color:var(--color-brand)] px-4 py-3 text-sm font-medium text-white transition hover:bg-[color:var(--color-brand-bright)]"
                        onClick={() => setDrawerOpen(true)}
                      >
                        Open detail drawer
                      </button>
                      <a
                        className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-center text-sm font-medium hover:border-[color:var(--color-brand-bright)] hover:text-white"
                        href={selectedResult.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open album ↗
                      </a>
                      <a
                        className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-center text-sm font-medium hover:border-[color:var(--color-brand-bright)] hover:text-white"
                        href={selectedResult.profile_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open profile ↗
                      </a>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-6 text-sm text-[color:var(--color-text-muted)]">
                  Run a search or pick a result to populate the central player panel.
                </div>
              )}
            </div>

            <div className="watcher-search-panel panel order-2 rounded-[20px] p-4 sm:rounded-[28px] sm:p-6 lg:p-8 xl:order-3">
              <SectionTitle
                eyebrow="Discovery"
                title="Search the local public index"
                body="FTS-backed local search is the reliable path. Rebuild the index from stored snapshots or add new public profiles before you query."
              />

              <form
                className="mt-6 grid gap-4 lg:grid-cols-[1.15fr_0.8fr_160px_170px_170px_150px]"
                onSubmit={(event) => {
                  event.preventDefault();
                  void runSearch();
                }}
              >
                <label className="block">
                  <div className="mb-2 text-xs uppercase tracking-[0.2em] text-[color:var(--color-text-muted)]">Query</div>
                  <input
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                    className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none placeholder:text-white/35 focus:border-[color:var(--color-brand-bright)]"
                    placeholder="blowjob, goth, cosplay, username fragments..."
                  />
                </label>
                <label className="block">
                  <div className="mb-2 text-xs uppercase tracking-[0.2em] text-[color:var(--color-text-muted)]">Username filter</div>
                  <input
                    value={searchUser}
                    onChange={(event) => setSearchUser(event.target.value)}
                    className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none placeholder:text-white/35 focus:border-[color:var(--color-brand-bright)]"
                    placeholder="optional profile filter"
                  />
                </label>
                <label className="block">
                  <div className="mb-2 text-xs uppercase tracking-[0.2em] text-[color:var(--color-text-muted)]">Sort</div>
                  <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none focus:border-[color:var(--color-brand-bright)]">
                    {SORT_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <div className="mb-2 text-xs uppercase tracking-[0.2em] text-[color:var(--color-text-muted)]">Source</div>
                  <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)} className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none focus:border-[color:var(--color-brand-bright)]">
                    {SOURCE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <div className="mb-2 text-xs uppercase tracking-[0.2em] text-[color:var(--color-text-muted)]">Min views</div>
                  <input
                    type="number"
                    min={0}
                    value={minViewsInput}
                    onChange={(event) => setMinViewsInput(event.target.value)}
                    className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none focus:border-[color:var(--color-brand-bright)]"
                    placeholder="0"
                  />
                </label>
                <div className="grid gap-3 lg:grid-cols-2">
                  <label className="block">
                    <div className="mb-2 text-xs uppercase tracking-[0.2em] text-[color:var(--color-text-muted)]">Limit</div>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={searchLimit}
                      onChange={(event) => setSearchLimit(Number(event.target.value) || 12)}
                      className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none focus:border-[color:var(--color-brand-bright)]"
                    />
                  </label>
                  <button type="submit" className="mt-auto rounded-2xl bg-[color:var(--color-brand)] px-5 py-3 text-sm font-medium text-white transition hover:bg-[color:var(--color-brand-bright)] disabled:opacity-50" disabled={busyKey === 'search'}>
                    {busyKey === 'search' ? 'Searching…' : 'Search'}
                  </button>
                </div>
              </form>

              <div className="mt-4 flex flex-wrap gap-2 text-xs">
                <FilterChip active={Boolean(searchQuery.trim())}>query {searchQuery.trim() || 'none'}</FilterChip>
                <FilterChip active={Boolean(searchUser.trim())}>user {searchUser.trim() || 'any'}</FilterChip>
                <FilterChip active={sortBy !== 'relevance'}>sort {sortBy}</FilterChip>
                <FilterChip active={Boolean(sourceFilter)}>source {sourceFilter || 'any'}</FilterChip>
                <FilterChip active={activeMinViews != null}>min views {activeMinViews ?? 'none'}</FilterChip>
                <FilterChip active={selectedTags.length > 0}>tags {selectedTags.length ? selectedTags.map((tag) => `#${tag}`).join(' ') : 'none'}</FilterChip>
              </div>

              <div className="mt-4 rounded-2xl border border-white/8 bg-white/[0.03] p-3 sm:p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                  <label className="min-w-0 flex-1">
                    <div className="mb-2 text-xs uppercase tracking-[0.2em] text-[color:var(--color-text-muted)]">Add hashtags</div>
                    <input
                      value={tagInput}
                      onChange={(event) => setTagInput(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          event.preventDefault();
                          addTagsFromInput();
                        }
                      }}
                      className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none placeholder:text-white/35 focus:border-[color:var(--color-brand-bright)]"
                      placeholder="#redhair #outdoor or comma separated"
                    />
                  </label>
                  <div className="grid grid-cols-2 gap-2 sm:flex">
                    <button type="button" className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium hover:border-[color:var(--color-brand-bright)] hover:text-white" onClick={addTagsFromInput}>
                      Add tags
                    </button>
                    <button type="button" className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium hover:border-[color:var(--color-brand-bright)] hover:text-white" onClick={() => setSelectedTags([])}>
                      Clear
                    </button>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  {selectedTags.map((tag) => (
                    <button key={tag} type="button" className="rounded-full border border-[color:var(--color-brand-bright)] bg-[color:var(--color-brand-soft)] px-3 py-1.5 text-xs font-medium text-[color:var(--color-brand-bright)]" onClick={() => toggleTag(tag)}>
                      #{tag} ×
                    </button>
                  ))}
                  {!selectedTags.length && <span className="text-xs text-[color:var(--color-text-muted)]">Select album tags below or type multiple hashtags to combine them with AND search.</span>}
                </div>

                {tagPalette.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {tagPalette.map((tag) => (
                      <button
                        key={tag}
                        type="button"
                        className={[
                          'rounded-full border px-3 py-1.5 text-xs transition',
                          selectedTags.includes(tag)
                            ? 'border-[color:var(--color-brand-bright)] bg-[color:var(--color-brand-soft)] text-[color:var(--color-brand-bright)]'
                            : 'border-white/10 bg-white/5 text-[color:var(--color-text-soft)] hover:border-[color:var(--color-brand-bright)] hover:text-white',
                        ].join(' ')}
                        onClick={() => toggleTag(tag)}
                      >
                        #{tag}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="mt-4 flex flex-wrap gap-2 text-xs text-[color:var(--color-text-muted)]">
                {QUICK_USERS.map((username) => (
                  <button
                    key={username}
                    className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 hover:border-[color:var(--color-brand-bright)] hover:text-white"
                    onClick={() => {
                      setSelectedUser(username);
                      setSearchUser(username);
                      setIndexProfileInput(username);
                      void Promise.all([runSearch(searchQuery, username, searchLimit), loadHistory(username)]);
                    }}
                  >
                    {username}
                  </button>
                ))}
              </div>

              <div className="watcher-results-layout mt-6 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
                <div className="space-y-3">
                  {(search?.results ?? []).map((result) => (
                    <article
                      key={`${result.album_id}-${result.url}`}
                      className="watcher-result-card panel-muted cursor-pointer rounded-2xl p-4 transition hover:border-[color:var(--color-brand-bright)]"
                      onClick={() => void inspectResult(result)}
                    >
                      <div className="flex flex-col gap-4 sm:flex-row">
                        <div className="h-28 w-full overflow-hidden rounded-xl bg-black/40 sm:w-40">
                          {result.thumbnail_url ? (
                            <img src={mediaDisplayUrl(result.thumbnail_url)} alt={result.title} className="h-full w-full object-cover" />
                          ) : (
                            <div className="flex h-full items-center justify-center text-xs uppercase tracking-[0.2em] text-white/30">No thumb</div>
                          )}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-[0.2em] text-[color:var(--color-text-muted)]">
                            <span className="rounded-full bg-[color:var(--color-brand-soft)] px-2 py-1 text-[color:var(--color-brand-bright)]">{result.source ?? 'indexed'}</span>
                            <span>@{result.username}</span>
                            <span>{result.views_text ?? 'views unknown'}</span>
                            <span>score {result.score}</span>
                            <span>rank {result.rank?.toFixed(2) ?? '—'}</span>
                          </div>
                          <h3 className="mt-3 text-lg font-medium tracking-[-0.03em] text-[color:var(--color-text-main)]">{result.title}</h3>
                          {result.description && <p className="mt-2 line-clamp-2 text-sm leading-6 text-[color:var(--color-text-muted)]">{result.description}</p>}
                          <div className="mt-3 flex flex-wrap gap-2 text-xs text-[color:var(--color-text-muted)]">
                            {tagsFromSearchResult(result).map((tag) => (
                              <button
                                key={tag}
                                className="rounded-full border border-white/10 px-2 py-1 hover:border-[color:var(--color-brand-bright)] hover:text-white"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  toggleTag(tag);
                                }}
                              >
                                #{tag}
                              </button>
                            ))}
                            {result.matched_terms.map((term) => (
                              <span key={term} className="rounded-full border border-white/10 px-2 py-1">
                                {term}
                              </span>
                            ))}
                            {!result.matched_terms.length && <span className="rounded-full border border-white/10 px-2 py-1">recent/indexed</span>}
                          </div>
                          <div className="watcher-result-actions mt-4 flex flex-wrap gap-3 text-sm text-[color:var(--color-text-soft)]">
                            <a className="text-[color:var(--color-brand-bright)] hover:text-white" href={result.url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>
                              Open album ↗
                            </a>
                            <a className="hover:text-white" href={result.profile_url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>
                              Open profile ↗
                            </a>
                            <button
                              className="text-[color:var(--color-brand-bright)] hover:text-white"
                              onClick={(event) => {
                                event.stopPropagation();
                                void inspectResult(result, search, true);
                              }}
                            >
                              Inspect
                            </button>
                            <button
                              className="text-[color:var(--color-success)] hover:text-white disabled:opacity-50"
                              disabled={busyKey === 'download'}
                              onClick={(event) => {
                                event.stopPropagation();
                                void downloadSelectedAlbum(result);
                              }}
                            >
                              Download
                            </button>
                            {result.media_count != null && <span>{result.media_count} media</span>}
                            <span>Indexed {formatDate(result.indexed_at)}</span>
                          </div>
                        </div>
                      </div>
                    </article>
                  ))}
                  {!search?.results?.length && <div className="panel-muted rounded-2xl p-8 text-sm text-[color:var(--color-text-muted)]">No results yet. Try rebuilding the index or indexing a profile first.</div>}
                </div>

                <aside className="space-y-4">
                  <div className="panel-muted rounded-2xl p-5">
                    <div className="text-xs uppercase tracking-[0.24em] text-[color:var(--color-text-muted)]">Top hit</div>
                    {topResult ? (
                      <>
                        <div className="mt-3 text-lg font-medium">{topResult.title}</div>
                        <div className="mt-2 text-sm text-[color:var(--color-text-muted)]">@{topResult.username} • {topResult.views_text ?? 'unknown views'} • {topResult.source ?? 'indexed'}</div>
                        <div className="mt-4 grid gap-2 text-sm text-[color:var(--color-text-soft)]">
                          <div>Score: {topResult.score}</div>
                          <div>FTS rank: {topResult.rank?.toFixed(2) ?? '—'}</div>
                          <div>Views estimate: {formatViews(topResult.views_estimate)}</div>
                          <div>Fetched: {formatDate(topResult.snapshot_fetched_at)}</div>
                          <div>Matched: {topResult.matched_terms.join(', ') || 'none'}</div>
                        </div>
                      </>
                    ) : (
                      <div className="mt-3 text-sm text-[color:var(--color-text-muted)]">Run a search to highlight the strongest match.</div>
                    )}
                  </div>

                  <div className="panel-muted rounded-2xl p-5">
                    <div className="text-xs uppercase tracking-[0.24em] text-[color:var(--color-text-muted)]">Search lens</div>
                    <div className="mt-3 grid gap-3 text-sm text-[color:var(--color-text-soft)]">
                      <div className="flex items-center justify-between gap-3"><span>Sort mode</span><span className="font-mono text-[color:var(--color-text-main)]">{sortBy}</span></div>
                      <div className="flex items-center justify-between gap-3"><span>Source filter</span><span className="font-mono text-[color:var(--color-text-main)]">{sourceFilter || 'any'}</span></div>
                      <div className="flex items-center justify-between gap-3"><span>Min views</span><span className="font-mono text-[color:var(--color-text-main)]">{activeMinViews ?? 'none'}</span></div>
                      <div className="flex items-center justify-between gap-3"><span>Returned</span><span className="font-mono text-[color:var(--color-text-main)]">{search?.total_returned ?? 0}</span></div>
                    </div>
                  </div>

                  <div className="panel-muted rounded-2xl p-5">
                    <div className="text-xs uppercase tracking-[0.24em] text-[color:var(--color-text-muted)]">Index note</div>
                    <p className="mt-3 text-sm leading-6 text-[color:var(--color-text-soft)]">
                      {search?.note ?? 'This system searches local indexed public metadata only. It is designed for discovery, ranking, and watcher operations on content you explicitly ingest.'}
                    </p>
                  </div>
                </aside>
              </div>
            </div>
          </section>

          <section className="space-y-8">
            <div className="panel rounded-[28px] p-6 lg:p-8">
              <SectionTitle eyebrow="Ingestion" title="Control the index" body="Pull in a public profile, rebuild from saved snapshots, or sample public explore pages." />

              <div className="mt-6 space-y-4">
                <div className="panel-muted rounded-2xl p-4">
                  <div className="text-xs uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">Index one profile</div>
                  <div className="mt-3 flex gap-2">
                    <input
                      value={indexProfileInput}
                      onChange={(event) => setIndexProfileInput(event.target.value)}
                      className="min-w-0 flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none focus:border-[color:var(--color-brand-bright)]"
                      placeholder="username"
                    />
                    <button className="rounded-xl bg-[color:var(--color-brand)] px-4 py-3 text-sm font-medium text-white transition hover:bg-[color:var(--color-brand-bright)] disabled:opacity-50" onClick={() => void indexProfile()} disabled={busyKey === 'index-profile'}>
                      {busyKey === 'index-profile' ? 'Indexing…' : 'Index'}
                    </button>
                  </div>
                  <label className="mt-3 flex items-start gap-3 rounded-2xl border border-white/8 bg-white/[0.03] p-3 text-sm text-[color:var(--color-text-soft)]">
                    <input type="checkbox" checked={enrichProfile} onChange={(event) => setEnrichProfile(event.target.checked)} className="mt-1 h-4 w-4 accent-[color:var(--color-brand-bright)]" />
                    <span>
                      Deep index album pages for tags, descriptions, and media counts. This is slower, but it makes hashtag search and result details much better.
                    </span>
                  </label>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="panel-muted rounded-2xl p-4">
                    <div className="text-xs uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">Rebuild local index</div>
                    <p className="mt-3 text-sm text-[color:var(--color-text-muted)]">Reconstruct album_index and the FTS mirror from the most recent stored snapshots.</p>
                    <button className="mt-4 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium hover:border-[color:var(--color-brand-bright)] hover:text-white disabled:opacity-50" onClick={() => void rebuildIndex()} disabled={busyKey === 'rebuild'}>
                      {busyKey === 'rebuild' ? 'Rebuilding…' : 'Rebuild'}
                    </button>
                  </div>

                  <div className="panel-muted rounded-2xl p-4">
                    <div className="text-xs uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">Index explore</div>
                    <div className="mt-3 flex gap-2">
                      <input
                        type="number"
                        min={1}
                        max={50}
                        aria-label="Explore page"
                        title="Explore page"
                        value={explorePage}
                        onChange={(event) => setExplorePage(Number(event.target.value) || 1)}
                        className="w-24 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none focus:border-[color:var(--color-brand-bright)]"
                      />
                      <button className="flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium hover:border-[color:var(--color-brand-bright)] hover:text-white disabled:opacity-50" onClick={() => void indexExplore()} disabled={busyKey === 'index-explore'}>
                        {busyKey === 'index-explore' ? 'Sampling…' : 'Sample explore'}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="panel rounded-[28px] p-6 lg:p-8">
              <SectionTitle eyebrow="Watcher" title="Profile pulse" body="Run the persisted watcher alert, then inspect stored history to see whether your source actually moved." />

              <div className="mt-6 flex flex-wrap gap-3">
                <button className="rounded-xl bg-[color:var(--color-brand)] px-4 py-3 text-sm font-medium text-white hover:bg-[color:var(--color-brand-bright)] disabled:opacity-50" onClick={() => void loadAlert(selectedUser)} disabled={busyKey === 'watch'}>
                  {busyKey === 'watch' ? 'Watching…' : `Watch ${selectedUser}`}
                </button>
                <button className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium hover:border-[color:var(--color-brand-bright)] hover:text-white disabled:opacity-50" onClick={() => void loadHistory(selectedUser)} disabled={busyKey === 'history'}>
                  {busyKey === 'history' ? 'Loading…' : 'Refresh history'}
                </button>
              </div>

              <div className="mt-5 grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
                <div className="panel-muted rounded-2xl p-5">
                  <div className="text-xs uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">Latest alert</div>
                  {watchAlert ? (
                    <>
                      <div className="mt-3 text-lg font-medium text-[color:var(--color-text-main)]">{watchAlert.summary ?? watchAlert.message ?? 'No watcher summary yet.'}</div>
                      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                        <div className="rounded-xl border border-emerald-400/15 bg-emerald-500/8 p-3 text-emerald-300">+{watchAlert.new_album_count ?? 0} new</div>
                        <div className="rounded-xl border border-red-400/15 bg-red-500/8 p-3 text-red-300">-{watchAlert.removed_album_count ?? 0} removed</div>
                      </div>
                      <pre className="mt-4 max-h-52 overflow-auto rounded-2xl bg-black/30 p-4 font-mono text-xs leading-5 text-[color:var(--color-text-soft)] whitespace-pre-wrap">
                        {watchAlert.telegram_text ?? watchAlert.discord_text ?? watchAlert.message ?? 'No text payload yet.'}
                      </pre>
                    </>
                  ) : (
                    <div className="mt-3 text-sm text-[color:var(--color-text-muted)]">Trigger a watcher run to populate alert output.</div>
                  )}
                </div>

                <div className="panel-muted rounded-2xl p-5">
                  <div className="flex items-center justify-between">
                    <div className="text-xs uppercase tracking-[0.22em] text-[color:var(--color-text-muted)]">Snapshot history</div>
                    <div className="text-xs text-[color:var(--color-text-muted)]">{history?.history.length ?? 0} entries</div>
                  </div>
                  <div className="mt-4 space-y-3">
                    {(history?.history ?? []).map((entry) => (
                      <div key={`${entry.fetched_at}-${entry.album_count}`} className="rounded-2xl border border-white/8 bg-white/3 p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <div className="text-sm font-medium text-[color:var(--color-text-main)]">{entry.album_count} albums</div>
                            <div className="mt-1 text-xs text-[color:var(--color-text-muted)]">{formatDate(entry.fetched_at)}</div>
                          </div>
                          <a className="text-xs text-[color:var(--color-brand-bright)] hover:text-white" href={entry.profile_url} target="_blank" rel="noreferrer">
                            profile ↗
                          </a>
                        </div>
                      </div>
                    ))}
                    {!history?.history.length && <div className="text-sm text-[color:var(--color-text-muted)]">No stored history yet for this profile.</div>}
                  </div>
                </div>
              </div>
            </div>
          </section>
        </main>

        <footer className="mt-8 grid gap-4 pb-4 text-sm text-[color:var(--color-text-muted)] lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            Built in React + Tailwind inside the erome-watcher folder. Current API target: <span className="font-mono text-[color:var(--color-text-soft)]">{apiBase}</span>
          </div>
          <div className="flex flex-wrap gap-4 font-mono text-xs">
            <span>selected: {selectedUser}</span>
            <span>health: {health?.status ?? 'unknown'}</span>
            <span>top score: {topResult?.score ?? 0}</span>
            <span>fts rows: {effectiveStats?.fts_row_count ?? 0}</span>
          </div>
        </footer>

        {drawerOpen && selectedResult && (
          <div className="fixed inset-0 z-40 flex justify-end bg-black/55 backdrop-blur-sm">
            <button className="absolute inset-0 cursor-default" aria-label="Close details" onClick={() => setDrawerOpen(false)} />
            <aside className="drawer-panel relative z-10 h-full w-full max-w-[720px] overflow-y-auto px-6 py-6 shadow-2xl">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.26em] text-[color:var(--color-brand-bright)]">Result details</div>
                  <h3 className="mt-3 text-2xl font-semibold tracking-[-0.04em]">{selectedResult.title}</h3>
                  <div className="mt-2 text-sm text-[color:var(--color-text-muted)]">@{selectedResult.username}</div>
                </div>
                <div className="grid gap-2 sm:flex">
                  <button className="rounded-xl border border-emerald-400/25 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200 hover:bg-emerald-500/20 disabled:opacity-50" onClick={() => void downloadSelectedAlbum()} disabled={busyKey === 'download'}>
                    {busyKey === 'download' ? 'Downloading...' : 'Download'}
                  </button>
                  <button className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm hover:border-[color:var(--color-brand-bright)] hover:text-white" onClick={() => setDrawerOpen(false)}>
                    Close
                  </button>
                </div>
              </div>

              <div className="mt-6">
                {busyKey === 'album' && !selectedAlbum ? (
                  <div className="panel-muted rounded-2xl p-6 text-sm text-[color:var(--color-text-muted)]">Loading album media…</div>
                ) : (
                  <AlbumMediaViewer
                    title={selectedAlbum?.title ?? selectedResult.title}
                    entries={galleryEntries}
                    currentMedia={currentMedia}
                    currentIndex={currentMediaIndex}
                    poster={selectedResult.thumbnail_url ?? null}
                    compact
                    onSelect={setCurrentMediaIndex}
                    onPrevious={() => stepMedia(-1)}
                    onNext={() => stepMedia(1)}
                  />
                )}
              </div>

              <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <div className="panel-muted rounded-2xl p-4">
                  <div className="text-xs uppercase tracking-[0.2em] text-[color:var(--color-text-muted)]">Score</div>
                  <div className="mt-2 text-2xl font-semibold">{selectedResult.score}</div>
                </div>
                <div className="panel-muted rounded-2xl p-4">
                  <div className="text-xs uppercase tracking-[0.2em] text-[color:var(--color-text-muted)]">Views estimate</div>
                  <div className="mt-2 text-2xl font-semibold">{formatViews(selectedResult.views_estimate)}</div>
                </div>
                <div className="panel-muted rounded-2xl p-4">
                  <div className="text-xs uppercase tracking-[0.2em] text-[color:var(--color-text-muted)]">Gallery items</div>
                  <div className="mt-2 text-2xl font-semibold">{galleryEntries.length}</div>
                </div>
                <div className="panel-muted rounded-2xl p-4">
                  <div className="text-xs uppercase tracking-[0.2em] text-[color:var(--color-text-muted)]">Playable</div>
                  <div className="mt-2 text-2xl font-semibold">{hasVideo ? 'Yes' : 'No'}</div>
                </div>
              </div>

              <div className="mt-6 space-y-4 text-sm text-[color:var(--color-text-soft)]">
                <div className="panel-muted rounded-2xl p-4">
                  <div className="grid gap-3">
                    <div className="flex items-center justify-between gap-4"><span>Source</span><span className="font-mono">{selectedResult.source ?? 'indexed'}</span></div>
                    <div className="flex items-center justify-between gap-4"><span>Views text</span><span className="font-mono">{selectedResult.views_text ?? '—'}</span></div>
                    <div className="flex items-center justify-between gap-4"><span>FTS rank</span><span className="font-mono">{selectedResult.rank?.toFixed(2) ?? '—'}</span></div>
                    <div className="flex items-center justify-between gap-4"><span>Snapshot</span><span className="font-mono">{formatDate(selectedResult.snapshot_fetched_at)}</span></div>
                    <div className="flex items-center justify-between gap-4"><span>Indexed</span><span className="font-mono">{formatDate(selectedResult.indexed_at)}</span></div>
                    <div className="flex items-center justify-between gap-4"><span>Album fetched</span><span className="font-mono">{formatDate(selectedAlbum?.fetched_at)}</span></div>
                  </div>
                </div>

                <div className="panel-muted rounded-2xl p-4">
                  <div className="text-xs uppercase tracking-[0.2em] text-[color:var(--color-text-muted)]">Description</div>
                  <p className="mt-3 leading-6 text-[color:var(--color-text-soft)]">{selectedAlbum?.description ?? 'No album description available from the public page.'}</p>
                </div>

                <div className="panel-muted rounded-2xl p-4">
                  <div className="text-xs uppercase tracking-[0.2em] text-[color:var(--color-text-muted)]">Matched terms</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {selectedResult.matched_terms.length ? (
                      selectedResult.matched_terms.map((term) => (
                        <span key={term} className="rounded-full border border-white/10 px-3 py-1.5 text-xs uppercase tracking-[0.18em]">
                          {term}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-[color:var(--color-text-muted)]">No explicit matched terms recorded for this row.</span>
                    )}
                  </div>
                </div>

                <div className="panel-muted rounded-2xl p-4">
                  <div className="text-xs uppercase tracking-[0.2em] text-[color:var(--color-text-muted)]">Tags</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(selectedAlbum?.tags ?? []).length ? (
                      selectedAlbum?.tags.map((tag) => (
                        <button key={tag} type="button" className="rounded-full border border-white/10 px-3 py-1.5 text-xs uppercase tracking-[0.18em] hover:border-[color:var(--color-brand-bright)] hover:text-white" onClick={() => toggleTag(tag)}>
                          #{tag}
                        </button>
                      ))
                    ) : (
                      <span className="text-sm text-[color:var(--color-text-muted)]">No public tags extracted for this album.</span>
                    )}
                  </div>
                </div>

                <div className="panel-muted rounded-2xl p-4">
                  <div className="text-xs uppercase tracking-[0.2em] text-[color:var(--color-text-muted)]">Links</div>
                  <div className="mt-3 grid gap-2">
                    <a className="break-all text-[color:var(--color-brand-bright)] hover:text-white" href={selectedResult.url} target="_blank" rel="noreferrer">
                      {selectedResult.url}
                    </a>
                    <a className="break-all hover:text-white" href={selectedResult.profile_url} target="_blank" rel="noreferrer">
                      {selectedResult.profile_url}
                    </a>
                  </div>
                </div>

                <div className="panel-muted rounded-2xl p-4">
                  <div className="text-xs uppercase tracking-[0.2em] text-[color:var(--color-text-muted)]">Media inventory</div>
                  <div className="mt-3 grid gap-2">
                    {galleryEntries.length ? (
                      galleryEntries.map((entry) => (
                        <a key={entry.url} className="break-all text-sm text-[color:var(--color-brand-bright)] hover:text-white" href={entry.url} target="_blank" rel="noreferrer">
                          {entry.label}: {entry.url}
                        </a>
                      ))
                    ) : (
                      <span className="text-sm text-[color:var(--color-text-muted)]">No public media URLs extracted for this album.</span>
                    )}
                  </div>
                </div>
              </div>
            </aside>
          </div>
        )}

        {error && (
          <div className="fixed bottom-4 right-4 max-w-md rounded-2xl border border-red-400/20 bg-red-950/80 px-4 py-3 text-sm text-red-100 shadow-2xl backdrop-blur">
            <div className="font-medium">Request failed</div>
            <div className="mt-1 text-red-100/80">{error.message}</div>
          </div>
        )}
      </div>
    </div>
  );
}

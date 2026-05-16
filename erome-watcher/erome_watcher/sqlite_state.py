from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
from typing import Optional, Sequence

from .models import ProfileDiff, ProfileSnapshot


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / 'state' / 'erome_state.sqlite3'
VALID_SORTS = {'relevance', 'recent', 'views', 'title'}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: str | None) -> str:
    if not value:
        return ''
    lowered = value.casefold()
    lowered = re.sub(r'[^\w\s:/.-]+', ' ', lowered)
    return re.sub(r'\s+', ' ', lowered).strip()


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


def _row_matches_hashtags(row: sqlite3.Row | dict, hashtag_terms: list[str]) -> bool:
    row_dict = dict(row)
    tag_terms = {_normalize_tag(tag) for tag in str(row_dict.get('tags') or '').split() if _normalize_tag(tag)}
    description_terms = set(_extract_hashtag_terms(row_dict.get('description')))
    metadata_terms = tag_terms | description_terms
    return all(term in metadata_terms for term in hashtag_terms)


def _search_blob(*parts: str | None) -> str:
    return ' '.join(filter(None, (_normalize_text(part) for part in parts))).strip()


def _parse_views_estimate(value: str | None) -> Optional[int]:
    if not value:
        return None
    text = value.strip().casefold().replace('views', '').replace('view', '').strip()
    text = text.replace(' ', '')
    if not text:
        return None

    multiplier = 1
    if text.endswith('k'):
        multiplier = 1_000
        text = text[:-1]
    elif text.endswith('m'):
        multiplier = 1_000_000
        text = text[:-1]

    if ',' in text and '.' not in text:
        text = text.replace(',', '.')
    else:
        text = text.replace(',', '')

    try:
        return int(float(text) * multiplier)
    except ValueError:
        digits = re.sub(r'\D', '', text)
        return int(digits) if digits else None


def _fts_query_from_terms(query: str) -> tuple[str, list[str]]:
    clean_query = _normalize_text(query)
    terms = [term for term in clean_query.split() if term]
    if not terms:
        return '', []
    clauses = [f'{term}*' for term in terms]
    return ' AND '.join(clauses), terms


def _ensure_album_index_columns(conn: sqlite3.Connection) -> None:
    table_info = conn.execute('PRAGMA table_info(album_index)').fetchall()
    existing = {row['name'] for row in table_info}
    if 'views_estimate' not in existing:
        conn.execute('ALTER TABLE album_index ADD COLUMN views_estimate INTEGER')
    if 'description' not in existing:
        conn.execute('ALTER TABLE album_index ADD COLUMN description TEXT')
    if 'media_count' not in existing:
        conn.execute('ALTER TABLE album_index ADD COLUMN media_count INTEGER')
    if 'tags' not in existing:
        conn.execute('ALTER TABLE album_index ADD COLUMN tags TEXT NOT NULL DEFAULT ""')


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS profile_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            profile_url TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            album_count INTEGER NOT NULL,
            payload_json TEXT NOT NULL
        )
        '''
    )
    conn.execute(
        '''
        CREATE INDEX IF NOT EXISTS idx_profile_snapshots_user_time
        ON profile_snapshots(username, fetched_at DESC)
        '''
    )
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS album_index (
            album_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            thumbnail_url TEXT,
            published_text TEXT,
            views_text TEXT,
            views_estimate INTEGER,
            description TEXT,
            media_count INTEGER,
            tags TEXT NOT NULL DEFAULT '',
            source TEXT,
            profile_url TEXT NOT NULL,
            snapshot_fetched_at TEXT NOT NULL,
            indexed_at TEXT NOT NULL,
            search_blob TEXT NOT NULL
        )
        '''
    )
    _ensure_album_index_columns(conn)
    conn.execute('CREATE INDEX IF NOT EXISTS idx_album_index_username ON album_index(username)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_album_index_snapshot_time ON album_index(snapshot_fetched_at DESC)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_album_index_views ON album_index(views_estimate DESC)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_album_index_source ON album_index(source)')
    conn.execute(
        '''
        CREATE VIRTUAL TABLE IF NOT EXISTS album_index_fts USING fts5(
            album_id UNINDEXED,
            username,
            title,
            search_blob
        )
        '''
    )


def get_conn(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _delete_index_rows_for_username(conn: sqlite3.Connection, username: str) -> None:
    conn.execute('DELETE FROM album_index WHERE username = ?', (username,))
    conn.execute('DELETE FROM album_index_fts WHERE username = ?', (username,))


def _replace_index_rows(conn: sqlite3.Connection, snapshot: ProfileSnapshot) -> dict:
    _delete_index_rows_for_username(conn, snapshot.username)
    indexed_at = utcnow()
    album_rows = []
    fts_rows = []

    for album in snapshot.albums:
        tags_text = ' '.join(tag.strip().lstrip('#') for tag in album.tags if tag and tag.strip())
        search_blob = _search_blob(
            snapshot.username,
            album.id,
            album.title,
            album.url,
            album.published_text,
            album.views_text,
            album.description,
            tags_text,
            album.source,
        )
        views_estimate = _parse_views_estimate(album.views_text)
        album_rows.append(
            (
                album.id,
                snapshot.username,
                album.title,
                album.url,
                album.thumbnail_url,
                album.published_text,
                album.views_text,
                views_estimate,
                album.description,
                album.media_count,
                tags_text,
                album.source,
                snapshot.profile_url,
                snapshot.fetched_at,
                indexed_at,
                search_blob,
            )
        )
        fts_rows.append((album.id, snapshot.username, album.title, search_blob))

    conn.executemany(
        '''
        INSERT OR REPLACE INTO album_index(
            album_id, username, title, url, thumbnail_url, published_text, views_text,
            views_estimate, description, media_count, tags, source, profile_url, snapshot_fetched_at, indexed_at, search_blob
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        album_rows,
    )
    conn.executemany(
        'INSERT INTO album_index_fts(album_id, username, title, search_blob) VALUES (?, ?, ?, ?)',
        fts_rows,
    )
    return {
        'username': snapshot.username,
        'albums_indexed': len(album_rows),
        'profile_url': snapshot.profile_url,
        'snapshot_fetched_at': snapshot.fetched_at,
        'indexed_at': indexed_at,
    }


def load_latest_snapshot(username: str, db_path: Optional[Path] = None) -> Optional[ProfileSnapshot]:
    conn = get_conn(db_path)
    row = conn.execute(
        'SELECT payload_json FROM profile_snapshots WHERE username = ? ORDER BY fetched_at DESC, id DESC LIMIT 1',
        (username,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return ProfileSnapshot.model_validate_json(row['payload_json'])


def save_snapshot(snapshot: ProfileSnapshot, db_path: Optional[Path] = None) -> Path:
    conn = get_conn(db_path)
    conn.execute(
        'INSERT INTO profile_snapshots(username, profile_url, fetched_at, album_count, payload_json) VALUES (?, ?, ?, ?, ?)',
        (
            snapshot.username,
            snapshot.profile_url,
            snapshot.fetched_at,
            snapshot.album_count,
            snapshot.model_dump_json(),
        ),
    )
    conn.commit()
    db_file = Path(conn.execute('PRAGMA database_list').fetchone()[2])
    conn.close()
    return db_file


def history(username: str, limit: int = 20, db_path: Optional[Path] = None) -> list[dict]:
    conn = get_conn(db_path)
    rows = conn.execute(
        'SELECT fetched_at, album_count, profile_url FROM profile_snapshots WHERE username = ? ORDER BY fetched_at DESC, id DESC LIMIT ?',
        (username, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def index_profile_snapshot(snapshot: ProfileSnapshot, db_path: Optional[Path] = None) -> dict:
    conn = get_conn(db_path)
    result = _replace_index_rows(conn, snapshot)
    conn.commit()
    conn.close()
    return result


def latest_snapshots(usernames: Optional[Sequence[str]] = None, db_path: Optional[Path] = None) -> list[ProfileSnapshot]:
    conn = get_conn(db_path)
    if usernames:
        placeholders = ','.join('?' for _ in usernames)
        query = (
            f'SELECT username, payload_json FROM profile_snapshots '
            f'WHERE username IN ({placeholders}) ORDER BY username ASC, fetched_at DESC, id DESC'
        )
        rows = conn.execute(query, tuple(usernames)).fetchall()
    else:
        rows = conn.execute(
            'SELECT username, payload_json FROM profile_snapshots ORDER BY username ASC, fetched_at DESC, id DESC'
        ).fetchall()
    conn.close()

    seen: set[str] = set()
    snapshots: list[ProfileSnapshot] = []
    for row in rows:
        username = row['username']
        if username in seen:
            continue
        seen.add(username)
        snapshots.append(ProfileSnapshot.model_validate_json(row['payload_json']))
    return snapshots


def rebuild_album_index(usernames: Optional[Sequence[str]] = None, db_path: Optional[Path] = None) -> dict:
    snapshots = latest_snapshots(usernames=usernames, db_path=db_path)
    conn = get_conn(db_path)
    if usernames is None:
        conn.execute('DELETE FROM album_index')
        conn.execute('DELETE FROM album_index_fts')

    total_albums = 0
    indexed_users: list[str] = []
    for snapshot in snapshots:
        result = _replace_index_rows(conn, snapshot)
        total_albums += result['albums_indexed']
        indexed_users.append(snapshot.username)
    conn.commit()
    conn.close()
    return {
        'profiles_indexed': len(indexed_users),
        'albums_indexed': total_albums,
        'usernames': indexed_users,
    }


def _score_search_row(row: sqlite3.Row | dict, query: str, terms: list[str], rank: Optional[float]) -> tuple[int, list[str]]:
    title = _normalize_text(row['title'])
    username = _normalize_text(row['username'])
    url = _normalize_text(row['url'])
    blob = _normalize_text(row['search_blob'])
    album_id = _normalize_text(row['album_id'])
    exact_query = _normalize_text(query)

    score = 0
    if rank is not None:
        score += max(0, 1200 - int(rank * 120))

    matched_terms: list[str] = []

    if exact_query and title == exact_query:
        score += 220
    if exact_query and album_id == exact_query:
        score += 200
    if exact_query and title.startswith(exact_query):
        score += 110
    if exact_query and exact_query in title:
        score += 80
    if exact_query and username.startswith(exact_query):
        score += 70
    if exact_query and exact_query in username:
        score += 45

    for term in terms:
        term_score = 0
        if term in title:
            term_score += 45
        if any(word.startswith(term) for word in title.split()):
            term_score += 25
        if term in username:
            term_score += 25
        if term in url:
            term_score += 10
        if term in blob:
            term_score += 8
        if term_score:
            matched_terms.append(term)
            score += term_score

    views_estimate = row['views_estimate'] if 'views_estimate' in row.keys() else None
    if views_estimate:
        score += min(120, int(views_estimate / 2500))

    return score, matched_terms


def _sort_results(results: list[dict], sort_by: str, has_query: bool) -> list[dict]:
    mode = sort_by if sort_by in VALID_SORTS else 'relevance'
    if not has_query and mode == 'relevance':
        mode = 'recent'

    if mode == 'views':
        return sorted(
            results,
            key=lambda item: (-(item.get('views_estimate') or -1), -item.get('score', 0), item['title'].casefold(), item['url']),
        )
    if mode == 'title':
        return sorted(results, key=lambda item: (item['title'].casefold(), item['username'].casefold(), item['url']))
    if mode == 'recent':
        return sorted(
            results,
            key=lambda item: (
                item.get('snapshot_fetched_at') or '',
                item.get('indexed_at') or '',
                item.get('views_estimate') or -1,
                item.get('score', 0),
            ),
            reverse=True,
        )
    return sorted(
        results,
        key=lambda item: (-item.get('score', 0), item.get('rank') if item.get('rank') is not None else 999999, item['title'].casefold(), item['url']),
    )


def _fallback_scan_rows(
    conn: sqlite3.Connection,
    query: str,
    username: Optional[str],
    source: Optional[str],
    min_views: Optional[int],
) -> list[sqlite3.Row]:
    sql = 'SELECT *, NULL AS rank FROM album_index WHERE 1=1'
    params: list[object] = []
    if username:
        sql += ' AND username = ?'
        params.append(username)
    if source:
        sql += ' AND source = ?'
        params.append(source)
    if min_views is not None:
        sql += ' AND COALESCE(views_estimate, 0) >= ?'
        params.append(min_views)

    clean_query = _normalize_text(query)
    terms = [term for term in clean_query.split() if term]
    if terms:
        for term in terms:
            sql += ' AND search_blob LIKE ?'
            params.append(f'%{term}%')

    sql += ' ORDER BY snapshot_fetched_at DESC, indexed_at DESC, title ASC LIMIT 500'
    return conn.execute(sql, params).fetchall()


def search_albums(
    query: str = '',
    username: Optional[str] = None,
    limit: int = 20,
    sort_by: str = 'relevance',
    source: Optional[str] = None,
    min_views: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> list[dict]:
    conn = get_conn(db_path)
    fts_query, terms = _fts_query_from_terms(query)
    hashtag_terms = _extract_hashtag_terms(query)
    rows: list[sqlite3.Row]

    if terms:
        sql = (
            'SELECT ai.*, bm25(album_index_fts, 6.0, 10.0, 2.0) AS rank '
            'FROM album_index_fts '
            'JOIN album_index ai ON ai.album_id = album_index_fts.album_id '
            'WHERE album_index_fts MATCH ?'
        )
        params: list[object] = [fts_query]
        if username:
            sql += ' AND ai.username = ?'
            params.append(username)
        if source:
            sql += ' AND ai.source = ?'
            params.append(source)
        if min_views is not None:
            sql += ' AND COALESCE(ai.views_estimate, 0) >= ?'
            params.append(min_views)
        sql += ' ORDER BY rank ASC, ai.snapshot_fetched_at DESC LIMIT 500'
        rows = conn.execute(sql, params).fetchall()
        if not rows:
            rows = _fallback_scan_rows(conn, query, username, source, min_views)
    else:
        sql = 'SELECT *, NULL AS rank FROM album_index WHERE 1=1'
        params = []
        if username:
            sql += ' AND username = ?'
            params.append(username)
        if source:
            sql += ' AND source = ?'
            params.append(source)
        if min_views is not None:
            sql += ' AND COALESCE(views_estimate, 0) >= ?'
            params.append(min_views)
        sql += ' ORDER BY snapshot_fetched_at DESC, indexed_at DESC, title ASC LIMIT 500'
        rows = conn.execute(sql, params).fetchall()

    conn.close()

    results: list[dict] = []
    for row in rows:
        if hashtag_terms and not _row_matches_hashtags(row, hashtag_terms):
            continue
        row_dict = dict(row)
        rank = row_dict.get('rank')
        score, matched_terms = _score_search_row(row, query, terms, rank)
        row_dict['score'] = score
        row_dict['rank'] = rank
        row_dict['matched_terms'] = matched_terms
        row_dict['views_estimate'] = row_dict.get('views_estimate')
        results.append(row_dict)

    ordered = _sort_results(results, sort_by=sort_by, has_query=bool(terms))
    return ordered[: max(1, limit)]


def index_stats(db_path: Optional[Path] = None) -> dict:
    conn = get_conn(db_path)
    snapshot_count = conn.execute('SELECT COUNT(*) FROM profile_snapshots').fetchone()[0]
    indexed_album_count = conn.execute('SELECT COUNT(*) FROM album_index').fetchone()[0]
    indexed_profile_count = conn.execute('SELECT COUNT(DISTINCT username) FROM album_index').fetchone()[0]
    latest_snapshot_at = conn.execute('SELECT MAX(fetched_at) FROM profile_snapshots').fetchone()[0]
    latest_indexed_at = conn.execute('SELECT MAX(indexed_at) FROM album_index').fetchone()[0]
    fts_row_count = conn.execute('SELECT COUNT(*) FROM album_index_fts').fetchone()[0]
    conn.close()
    return {
        'snapshot_count': snapshot_count,
        'indexed_album_count': indexed_album_count,
        'indexed_profile_count': indexed_profile_count,
        'latest_snapshot_at': latest_snapshot_at,
        'latest_indexed_at': latest_indexed_at,
        'fts_row_count': fts_row_count,
    }


def diff_snapshots(previous: ProfileSnapshot, current: ProfileSnapshot) -> ProfileDiff:
    prev_map = {album.id: album for album in previous.albums}
    curr_map = {album.id: album for album in current.albums}

    new_ids = [album_id for album_id in curr_map if album_id not in prev_map]
    removed_ids = [album_id for album_id in prev_map if album_id not in curr_map]
    unchanged_count = sum(1 for album_id in curr_map if album_id in prev_map)

    return ProfileDiff(
        username=current.username,
        previous_album_count=previous.album_count,
        current_album_count=current.album_count,
        new_albums=[curr_map[album_id] for album_id in new_ids],
        removed_albums=[prev_map[album_id] for album_id in removed_ids],
        unchanged_count=unchanged_count,
    )


def diff_and_update(current: ProfileSnapshot, db_path: Optional[Path] = None) -> ProfileDiff:
    previous = load_latest_snapshot(current.username, db_path)
    if previous is None:
        diff = ProfileDiff(
            username=current.username,
            previous_album_count=0,
            current_album_count=current.album_count,
            new_albums=current.albums,
            removed_albums=[],
            unchanged_count=0,
        )
    else:
        diff = diff_snapshots(previous, current)
    save_snapshot(current, db_path)
    index_profile_snapshot(current, db_path)
    return diff

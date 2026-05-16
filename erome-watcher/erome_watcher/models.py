from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class AlbumEntry(BaseModel):
    id: str
    title: str
    url: str
    username: Optional[str] = None
    thumbnail_url: Optional[str] = None
    published_text: Optional[str] = None
    views_text: Optional[str] = None
    description: Optional[str] = None
    media_count: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    source: Optional[str] = None


class ProfileSnapshot(BaseModel):
    username: str
    profile_url: str
    fetched_at: str
    album_count: int = 0
    albums: List[AlbumEntry] = Field(default_factory=list)


class ProfileDiff(BaseModel):
    username: str
    previous_album_count: int
    current_album_count: int
    new_albums: List[AlbumEntry] = Field(default_factory=list)
    removed_albums: List[AlbumEntry] = Field(default_factory=list)
    unchanged_count: int = 0


class AlbumSnapshot(BaseModel):
    album_url: str
    fetched_at: str
    title: Optional[str] = None
    username: Optional[str] = None
    description: Optional[str] = None
    media_urls: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class AlertMessage(BaseModel):
    username: str
    summary: str
    telegram_text: str
    discord_text: str
    new_album_count: int = 0
    removed_album_count: int = 0


class SearchResult(BaseModel):
    album_id: str
    username: str
    title: str
    url: str
    thumbnail_url: Optional[str] = None
    published_text: Optional[str] = None
    views_text: Optional[str] = None
    views_estimate: Optional[int] = None
    description: Optional[str] = None
    media_count: Optional[int] = None
    tags: str = ''
    source: Optional[str] = None
    profile_url: str
    snapshot_fetched_at: str
    indexed_at: str
    score: int = 0
    rank: Optional[float] = None
    matched_terms: List[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query: str = ''
    username: Optional[str] = None
    limit: int = 20
    total_returned: int = 0
    sort_by: str = 'relevance'
    source: Optional[str] = None
    min_views: Optional[int] = None
    index_stats: dict = Field(default_factory=dict)
    results: List[SearchResult] = Field(default_factory=list)
    note: Optional[str] = None

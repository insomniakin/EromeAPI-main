from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


MediaType = Literal['image', 'video']
ResourceKind = Literal['profile', 'gallery', 'media']


class SourceInfo(BaseModel):
    key: str
    display_name: str
    capabilities: list[str] = Field(default_factory=list)


class ProfileSummary(BaseModel):
    id: str | None = None
    handle: str | None = None
    display_name: str | None = None
    bio: str | None = None
    avatar_url: HttpUrl | None = None
    gallery_count: int | None = None
    source_url: HttpUrl | None = None


class GalleryStats(BaseModel):
    views: int | None = None
    likes: int | None = None
    comments: int | None = None


class MediaItem(BaseModel):
    id: str | None = None
    gallery_id: str | None = None
    media_type: MediaType
    direct_url: HttpUrl | None = None
    thumbnail_url: HttpUrl | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    mime_type: str | None = None
    sort_index: int | None = None


class GallerySummary(BaseModel):
    id: str | None = None
    title: str | None = None
    source_url: HttpUrl | None = None
    owner: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: str | None = None
    media_count: int | None = None
    cover_url: HttpUrl | None = None
    stats: GalleryStats | None = None


class ProfilePayload(BaseModel):
    profile: ProfileSummary
    galleries: list[GallerySummary] = Field(default_factory=list)


class GalleryPayload(BaseModel):
    gallery: GallerySummary
    media: list[MediaItem] = Field(default_factory=list)


class ResolvePayload(BaseModel):
    url: HttpUrl
    source: str | None = None
    kind: ResourceKind | None = None
    supported: bool


class ApiError(BaseModel):
    code: str
    message: str


class ApiEnvelope(BaseModel):
    ok: bool
    source: str | None = None
    kind: ResourceKind | None = None
    data: dict | list | None = None
    warnings: list[str] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    error: ApiError | None = None

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from media_gallery_api.models.schemas import GalleryPayload, ProfilePayload, ResolvePayload, SourceInfo


class GalleryAdapter(ABC):
    key: str
    display_name: str
    capabilities: list[str]

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def resolve(self, url: str) -> ResolvePayload:
        raise NotImplementedError

    @abstractmethod
    async def get_profile(self, url: str) -> ProfilePayload:
        raise NotImplementedError

    @abstractmethod
    async def get_gallery(self, url: str) -> GalleryPayload:
        raise NotImplementedError


class AdapterRegistry(Protocol):
    def list_sources(self) -> list[SourceInfo]: ...
    def match(self, url: str) -> GalleryAdapter | None: ...

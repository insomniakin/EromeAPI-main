from __future__ import annotations

from media_gallery_api.core.interfaces import GalleryAdapter
from media_gallery_api.models.schemas import ApiEnvelope, SourceInfo


class GalleryService:
    def __init__(self, adapters: list[GalleryAdapter]):
        self.adapters = adapters

    def list_sources(self) -> list[SourceInfo]:
        return [
            SourceInfo(
                key=adapter.key,
                display_name=adapter.display_name,
                capabilities=adapter.capabilities,
            )
            for adapter in self.adapters
        ]

    def match(self, url: str) -> GalleryAdapter | None:
        for adapter in self.adapters:
            if adapter.can_handle(url):
                return adapter
        return None

    async def resolve(self, url: str) -> ApiEnvelope:
        adapter = self.match(url)
        if not adapter:
            return ApiEnvelope(
                ok=False,
                error={
                    'code': 'UNSUPPORTED_URL',
                    'message': 'No adapter matched the provided URL',
                },
                warnings=['Add a site-specific adapter under media_gallery_api/adapters/'],
            )
        payload = await adapter.resolve(url)
        return ApiEnvelope(ok=True, source=adapter.key, kind=payload.kind, data=payload.model_dump())

    async def get_profile(self, url: str) -> ApiEnvelope:
        adapter = self.match(url)
        if not adapter:
            return ApiEnvelope(
                ok=False,
                error={'code': 'UNSUPPORTED_URL', 'message': 'No adapter matched the provided URL'},
            )
        payload = await adapter.get_profile(url)
        return ApiEnvelope(ok=True, source=adapter.key, kind='profile', data=payload.model_dump())

    async def get_gallery(self, url: str) -> ApiEnvelope:
        adapter = self.match(url)
        if not adapter:
            return ApiEnvelope(
                ok=False,
                error={'code': 'UNSUPPORTED_URL', 'message': 'No adapter matched the provided URL'},
            )
        payload = await adapter.get_gallery(url)
        return ApiEnvelope(ok=True, source=adapter.key, kind='gallery', data=payload.model_dump())

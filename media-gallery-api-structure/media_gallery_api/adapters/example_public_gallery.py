from __future__ import annotations

from media_gallery_api.adapters.base import hostname, looks_like_gallery_url
from media_gallery_api.core.interfaces import GalleryAdapter
from media_gallery_api.models.schemas import GalleryPayload, GallerySummary, ProfilePayload, ProfileSummary, ResolvePayload


class ExamplePublicGalleryAdapter(GalleryAdapter):
    key = 'example_public_gallery'
    display_name = 'Example Public Gallery'
    capabilities = ['profile', 'gallery', 'media', 'images', 'video']

    def can_handle(self, url: str) -> bool:
        return hostname(url) in {'example.com', 'www.example.com'}

    async def resolve(self, url: str) -> ResolvePayload:
        kind = 'gallery' if looks_like_gallery_url(url) else 'profile'
        return ResolvePayload(url=url, source=self.key, kind=kind, supported=True)

    async def get_profile(self, url: str) -> ProfilePayload:
        return ProfilePayload(
            profile=ProfileSummary(
                id='demo-profile',
                handle='demo',
                display_name='Demo Profile',
                bio='Replace with site-specific parser output.',
                gallery_count=1,
                source_url=url,
            ),
            galleries=[
                GallerySummary(
                    id='demo-gallery',
                    title='Demo Gallery',
                    owner='demo',
                    source_url='https://example.com/gallery/demo-gallery',
                    media_count=2,
                )
            ],
        )

    async def get_gallery(self, url: str) -> GalleryPayload:
        return GalleryPayload(
            gallery=GallerySummary(
                id='demo-gallery',
                title='Demo Gallery',
                owner='demo',
                source_url=url,
                media_count=2,
            ),
            media=[],
        )

from __future__ import annotations

from fastapi import FastAPI, Query

from media_gallery_api.adapters.example_public_gallery import ExamplePublicGalleryAdapter
from media_gallery_api.core.service import GalleryService

app = FastAPI(title='Media Gallery API Structure', version='0.1.0')
service = GalleryService(adapters=[ExamplePublicGalleryAdapter()])


@app.get('/health')
async def health():
    return {'ok': True, 'service': 'media-gallery-api-structure'}


@app.get('/sources')
async def sources():
    return {'sources': [source.model_dump() for source in service.list_sources()]}


@app.get('/resolve')
async def resolve(url: str = Query(..., description='Public profile/gallery/media URL')):
    return (await service.resolve(url)).model_dump()


@app.get('/profile')
async def profile(url: str = Query(..., description='Public profile URL')):
    return (await service.get_profile(url)).model_dump()


@app.get('/gallery')
async def gallery(url: str = Query(..., description='Public gallery URL')):
    return (await service.get_gallery(url)).model_dump()

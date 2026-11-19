# SPDX-License-Identifier: AGPL-3.0-or-later
"""Alt text: a short description of an image, written by a Cloudflare image-to-text model.

Best effort and never blocking: runs after the image is stored, uses the user's own Cloudflare
key if they saved one, else the server key, and simply leaves ``alt_text`` empty when no key is
available, the provider is in a cooldown, or the call fails. A quota error feeds the learner's
cooldown so we stop calling a provider that is out of Neurons.
"""

import asyncio
import logging

from app import db
from app.config import get_settings
from app.images import InvalidImageError, image_for_provider
from app.models import Asset
from app.providers import cloudflare
from app.providers.base import ProviderError
from app.providers.registry import get_provider, resolve_credentials
from app.services import quota

log = logging.getLogger(__name__)
CAPTION_IMAGE_SIDE = 512  # small input = few image tokens = few Neurons


async def describe_asset(asset_id: str) -> None:
    if not get_settings().alt_text_enabled:
        return
    provider = get_provider("cloudflare")
    if provider is None:
        return
    async with db.session_factory()() as session:
        asset = await session.get(Asset, asset_id)
        if asset is None or not asset.mime.startswith("image/") or asset.alt_text:
            return
        creds = await resolve_credentials(session, provider, asset.user_id)
        if creds.source == "none":
            return
        scope = quota.scope_for(creds.source, asset.user_id)
        q = await quota.view(session, provider.info.id, scope, provider.info.daily_quota_prior)
        if q.blocked_seconds:
            return
        storage_key, user_id = asset.storage_key, asset.user_id
    try:
        jpeg = await asyncio.to_thread(image_for_provider, storage_key, CAPTION_IMAGE_SIDE)
        text = await cloudflare.describe_image(jpeg, creds)
    except ProviderError as exc:
        if exc.quota:
            async with db.session_factory()() as session:
                await quota.record_quota_hit(
                    session, provider.info.id, scope, provider.info.daily_quota_prior
                )
                await session.commit()
        log.info("alt text skipped asset=%s: %s", asset_id, exc.public)
        return
    except (OSError, InvalidImageError):
        return
    if not text:
        return
    async with db.session_factory()() as session:
        asset = await session.get(Asset, asset_id)
        if asset is not None and asset.user_id == user_id:
            asset.alt_text = text
            await session.commit()

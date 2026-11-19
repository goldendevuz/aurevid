# SPDX-License-Identifier: AGPL-3.0-or-later
"""Provider registry: which adapters are enabled, and how credentials are resolved."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.crypto import CryptoUnavailable, byok_available, decrypt_secret
from app.models import ProviderKey
from app.providers.base import Credentials, ImageProvider, ModelInfo
from app.providers.cloudflare import CloudflareProvider
from app.providers.fal import FalProvider
from app.providers.mock import MockProvider
from app.providers.modal_video import ModalVideoProvider
from app.providers.pollinations import PollinationsProvider
from app.providers.pollinations_video import PollinationsVideoProvider


def enabled_providers() -> dict[str, ImageProvider]:
    s = get_settings()
    providers: list[ImageProvider] = []
    if s.cloudflare_enabled:
        providers.append(CloudflareProvider())
    if s.pollinations_enabled:
        providers.append(PollinationsProvider())
    if s.pollinations_video_enabled:
        providers.append(PollinationsVideoProvider())
    if s.modal_video_enabled:
        providers.append(ModalVideoProvider())
    if s.fal_enabled:
        providers.append(FalProvider())
    if s.mock_provider_enabled:
        providers.append(MockProvider())
    out: dict[str, ImageProvider] = {}
    for p in providers:
        allowed = [m for m in p.info.models if s.allow_unclear_models or m.commercial_use == "yes"]
        if not allowed:
            continue
        if len(allowed) != len(p.info.models):
            # Per-instance copy: the class-level catalogue stays intact, this instance only
            # exposes models whose commercial use is clearly allowed.
            p.info = p.info.model_copy(update={"models": allowed})
        out[p.info.id] = p
    return out


def allowed_upscales(model: ModelInfo) -> list[str]:
    """4K/8K targets: images use the free local upscaler, videos their provider's own."""
    if model.kind == "image":
        from app import upscaler

        return ["4k", "8k"] if upscaler.available() else []
    s = get_settings()
    # Video upscaling runs on Topaz (fal), whose output terms are unclear: same rule as models.
    if model.kind == "video" and not (s.fal_video_upscale_enabled and s.allow_unclear_models):
        return []
    return list(model.upscale_targets)


def get_provider(provider_id: str) -> ImageProvider | None:
    return enabled_providers().get(provider_id)


async def resolve_credentials(
    session: AsyncSession, provider: ImageProvider, user_id: str
) -> Credentials:
    """User's own key wins over the server key. Keys never leave the server."""
    if provider.info.byok and byok_available():
        row = (
            await session.execute(
                select(ProviderKey).where(
                    ProviderKey.user_id == user_id, ProviderKey.provider == provider.info.id
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            try:
                return Credentials(decrypt_secret(row.ciphertext), "user")
            except CryptoUnavailable:
                pass
    return provider.server_credentials()

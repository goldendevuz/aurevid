# SPDX-License-Identifier: AGPL-3.0-or-later
"""Public catalog: providers/models (with free/paid labels) and presets."""

from fastapi import APIRouter

from app.deps import CurrentUser, Session
from app.providers.base import UPSCALE_CREDITS
from app.providers.registry import (
    allowed_upscales,
    enabled_providers,
    publish_image_model,
    resolve_credentials,
)
from app.services import allowance, quota
from app.services.presets import load_presets

router = APIRouter(prefix="/api", tags=["catalog"])


def _clean_provider_name(provider) -> str:
    pid = provider.info.id.lower()
    if pid.startswith("openrouter"):
        return "OpenRouter"
    if pid.startswith("fal"):
        return "Fal"
    if pid.startswith("replicate"):
        return "Replicate"
    if pid.startswith("modal"):
        return "Modal"
    if pid.startswith("cloudflare"):
        return "Cloudflare"
    return provider.info.name


def _build_inactive_model(provider, m) -> dict:
    usd_values = [
        provider.usd_per_second(m.id, res, a)
        for res in m.resolutions
        for a in m.resolution_sizes.get(res, [])
    ]
    valid_usd = [u for u in usd_values if u is not None]
    if valid_usd:
        min_usd = min(valid_usd)
        cents = round(min_usd * 100)
        price_text = f"from ≈ {cents}¢ / s" if min_usd < 1.0 else f"from ${min_usd:.2f} / s"
    else:
        min_usd = None
        cents = m.credit_cost
        price_text = f"from {m.credit_cost} credits"

    brand = _clean_provider_name(provider)
    return {
        "provider_id": provider.info.id,
        "provider_name": brand,
        "id": m.id,
        "label": m.label,
        "kind": m.kind,
        "commercial_use": m.commercial_use,
        "reason": f"Needs your {brand} key",
        "price_text": price_text,
        "price_cents": cents,
        "min_usd_per_second": min_usd,
        "key_url": provider.info.key_url,
        "settings_path": "/settings",
    }


@router.get("/providers")
async def list_providers(user: CurrentUser, session: Session):
    out = []
    publish = publish_image_model()
    for provider in enabled_providers().values():
        creds = await resolve_credentials(session, provider, user.id)
        has_creds = provider.has_usable_credentials(creds)
        visible_models = [
            m for m in provider.info.models if m.commercial_use == "yes" or creds.source == "user"
        ]
        data = provider.info.model_copy(update={"models": visible_models}).model_dump()
        for m_out, m in zip(data["models"], visible_models, strict=True):
            m_out["upscale_targets"] = allowed_upscales(m)
            m_out["upscale_credits"] = {
                t: UPSCALE_CREDITS.get(m.kind, {}).get(t, 0) for t in m_out["upscale_targets"]
            }
            # "Publish quality" runs on exactly one model: the best free, commercial one.
            m_out["publish_quality"] = publish is not None and (
                publish[0].info.id,
                publish[1].id,
            ) == (
                provider.info.id,
                m.id,
            )
            # Estimated USD per second of video, per resolution and aspect ratio (margin included).
            m_out["usd_per_second"] = {
                res: {a: provider.usd_per_second(m.id, res, a) for a in m.resolution_sizes[res]}
                for res in m.resolutions
                if provider.usd_per_second(m.id, res, next(iter(m.resolution_sizes[res])))
                is not None
            }
        data["available"] = has_creds
        data["key_source"] = creds.source  # "server" | "user" | "none"; never the key itself
        # Inactive models for this user on this provider
        inactive = []
        for m in provider.info.models:
            is_inactive = False
            if not has_creds:
                is_inactive = True
            elif m.commercial_use == "byok_only" and creds.source != "user":
                is_inactive = True
            if is_inactive:
                inactive.append(_build_inactive_model(provider, m))
        data["inactive_models"] = inactive
        # Free outputs left on the owner's key for this user (None = no per-user cap).
        data["free_left"] = (
            await allowance.server_left(session, provider, user.id)
            if creds.source == "server"
            else None
        )
        data["quota"] = None
        if provider.info.track_quota:
            view = await quota.view(
                session,
                provider.info.id,
                quota.scope_for(creds.source, user.id),
                provider.info.daily_quota_prior,
            )
            data["quota"] = view.as_dict()
        out.append(data)
    return out


@router.get("/catalog/inactive-models")
async def list_inactive_models(user: CurrentUser, session: Session):
    """Models the current user cannot run right now because they need the user's own key.

    Only returned to signed-in users. Never leaks other users' keys or state.
    """
    out = []
    for provider in enabled_providers().values():
        creds = await resolve_credentials(session, provider, user.id)
        has_creds = provider.has_usable_credentials(creds)
        for m in provider.info.models:
            is_inactive = False
            if not has_creds:
                is_inactive = True
            elif m.commercial_use == "byok_only" and creds.source != "user":
                is_inactive = True

            if is_inactive:
                out.append(_build_inactive_model(provider, m))
    return out


@router.get("/catalog/models")
async def public_models():
    """Public, credential-free list of the models this instance really offers (landing page).

    Same registry as ``/api/providers`` (so the commercial-use filter applies), but no keys,
    quotas or per-user state.
    """
    return [
        {
            "provider_id": provider.info.id,
            "provider": provider.info.name,
            "id": m.id,
            "label": m.label,
            "kind": m.kind,
        }
        for provider in enabled_providers().values()
        for m in provider.info.models
        if m.kind in ("image", "video") and m.commercial_use == "yes"
    ]


@router.get("/presets")
async def list_presets():
    return [p.model_dump() for p in load_presets().values()]

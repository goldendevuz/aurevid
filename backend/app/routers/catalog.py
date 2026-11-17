# SPDX-License-Identifier: AGPL-3.0-or-later
"""Public catalog: providers/models (with free/paid labels) and presets."""

from fastapi import APIRouter

from app.deps import CurrentUser, Session
from app.providers.registry import enabled_providers, resolve_credentials
from app.services.presets import load_presets

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/providers")
async def list_providers(user: CurrentUser, session: Session):
    out = []
    for provider in enabled_providers().values():
        creds = await resolve_credentials(session, provider, user.id)
        data = provider.info.model_dump()
        data["available"] = provider.has_usable_credentials(creds)
        data["key_source"] = creds.source  # "server" | "user" | "none"; never the key itself
        out.append(data)
    return out


@router.get("/presets")
async def list_presets():
    return [p.model_dump() for p in load_presets().values()]

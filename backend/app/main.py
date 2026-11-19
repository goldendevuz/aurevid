# SPDX-License-Identifier: AGPL-3.0-or-later
"""FastAPI application: middleware (security headers, CSRF, CORS), routers, worker."""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import admin, assets, auth, catalog, credits, jobs, marketing, me, recipes
from app.security import CSRF_COOKIE, CSRF_HEADER, csrf_matches
from app.services.presets import load_presets

log = logging.getLogger("aurevid")
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_presets()  # fail fast on a broken preset file
    stop = asyncio.Event()
    task = None
    if get_settings().run_worker_in_api:
        from app.worker import run_forever

        task = asyncio.create_task(run_forever(stop))
    yield
    stop.set()
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Aurevid API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if s.app_env != "prod" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if s.app_env != "prod" else None,
    )

    @app.middleware("http")
    async def csrf_and_headers(request: Request, call_next):
        if request.method in UNSAFE_METHODS and request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            if origin and origin not in s.cors_origins:
                return JSONResponse({"detail": {"code": "bad_origin"}}, status_code=403)
            if not csrf_matches(request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER)):
                return JSONResponse({"detail": {"code": "csrf_failed"}}, status_code=403)
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if not request.url.path.startswith("/api/docs"):
            h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        if s.cookie_secure:
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"],
        max_age=600,
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        # Return field locations + messages only, never echo the submitted input back.
        errors = [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]
        return JSONResponse({"detail": {"code": "validation_error", "errors": errors}}, 422)

    for router in (
        auth.router,
        me.router,
        catalog.router,
        jobs.router,
        recipes.router,
        assets.router,
        credits.router,
        admin.router,
        admin.public,
        marketing.router,
    ):
        app.include_router(router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()

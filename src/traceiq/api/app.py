"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from traceiq import __version__
from traceiq.api.errors import AppError, app_error_handler
from traceiq.api.routes import admin, auth, health, incidents, investigations, reports, webhooks
from traceiq.auth.rbac import ROUTE_ROLE_MATRIX, Role


def create_app() -> FastAPI:
    app = FastAPI(
        title="TraceIQ",
        version=__version__,
        openapi_url="/openapi.json",
    )
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/v1")
    app.include_router(auth.router, prefix="/v1")
    # /me lives under auth in prompt as GET /me — also expose top-level
    app.add_api_route("/v1/me", auth.me, methods=["GET"])
    app.include_router(incidents.router, prefix="/v1")
    app.include_router(investigations.router, prefix="/v1")
    app.include_router(reports.router, prefix="/v1")
    app.include_router(admin.router, prefix="/v1")
    app.include_router(webhooks.router, prefix="/v1")

    # Keep matrix in sync with mounted routes (tests assert coverage)
    ROUTE_ROLE_MATRIX.update(
        {
            "GET /v1/healthz": Role.VIEWER,
            "GET /v1/readyz": Role.VIEWER,
            "GET /v1/me": Role.VIEWER,
            "POST /v1/auth/login": Role.VIEWER,
            "GET /v1/incidents": Role.VIEWER,
            "POST /v1/incidents": Role.INVESTIGATOR,
            "GET /v1/incidents/{id}": Role.VIEWER,
            "POST /v1/incidents/{id}/investigations": Role.INVESTIGATOR,
            "GET /v1/investigations/{id}": Role.VIEWER,
            "GET /v1/investigations/{id}/events": Role.VIEWER,
            "POST /v1/investigations/{id}/cancel": Role.INVESTIGATOR,
            "GET /v1/reports/{id}": Role.VIEWER,
            "POST /v1/reports/{id}/feedback": Role.INVESTIGATOR,
            "GET /v1/audit": Role.ADMIN,
            "GET /v1/egress-ledger": Role.ADMIN,
            "POST /v1/webhooks/alerts": Role.INVESTIGATOR,
        }
    )
    return app


app = create_app()

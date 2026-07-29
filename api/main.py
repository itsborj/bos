import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

from first_boot import ensure_secrets, ensure_workspace

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

# Must run before get_settings() so generated keys are in os.environ when pydantic reads them
ensure_secrets()

from auth import require_api_key  # noqa: E402
from config import get_settings, validate_settings  # noqa: E402
from db import get_engine  # noqa: E402
from errors import BosError, bos_error_handler, unhandled_error_handler  # noqa: E402
from middleware import RequestLoggingMiddleware, TraceBlockMiddleware  # noqa: E402

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import models  # noqa: F401 — registers all ORM models with Base.metadata
    from registry import list_all  # eager module scan on startup
    from pipeline.hooks import hooks
    from pipeline.system_hooks import register_system_hooks

    validate_settings(settings)
    list_all()
    register_system_hooks(hooks)
    await ensure_workspace(settings.frontend_url)

    yield

    engine = get_engine()
    if engine:
        await engine.dispose()


app = FastAPI(
    title="BOS — Business Operating System",
    version=settings.app_version,
    description="A self-hosted business operating system. One API, three interfaces.",
    lifespan=lifespan,
)

app.add_middleware(TraceBlockMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)
app.add_exception_handler(BosError, bos_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

from routers import auth as auth_router, google_auth as google_auth_router  # noqa: E402
from routers import agent, backend_settings, billing, brands, calendar, capabilities, chat_v2, council, decision_briefs, documents, handoff, health, intents, media, memory, objectives, onboarding, outcomes, plugins, providers, runs, social, stream, strategy_workflows, verticals, webhooks, workspace  # noqa: E402
from campaign.api import router as campaign_router  # noqa: E402
from plugin_loader import iter_plugin_api_routers  # noqa: E402

app.include_router(health.router)
app.include_router(agent.router)
app.include_router(workspace.router)
app.include_router(brands.router)
app.include_router(documents.router)
app.include_router(verticals.router)
app.include_router(capabilities.router)
app.include_router(runs.router)
app.include_router(chat_v2.router)
app.include_router(providers.router)
app.include_router(backend_settings.router)
app.include_router(billing.router)
app.include_router(intents.router)
app.include_router(objectives.router)
app.include_router(memory.router)
app.include_router(outcomes.router)
app.include_router(decision_briefs.router)
app.include_router(handoff.router)
app.include_router(onboarding.router)
app.include_router(stream.router)
app.include_router(auth_router.router)
app.include_router(google_auth_router.router)
app.include_router(campaign_router)

# Plugin-owned HTTP adapters must mount before the generic /social/{platform}/callback
# fallback so exact plugin callback routes (for example /social/google-drive/callback)
# are not shadowed by the catch-all social callback handler.
for _plugin_id, _plugin_router in iter_plugin_api_routers():
    app.include_router(_plugin_router)

app.include_router(social.router)
app.include_router(webhooks.router)
app.include_router(plugins.router)
app.include_router(plugins.capability_manifest_router)
app.include_router(calendar.router)
app.include_router(council.router)
app.include_router(media.router)
app.include_router(strategy_workflows.router)


_UNAUTHORIZED_RESPONSE = {
    "description": "Missing or invalid API key",
    "content": {
        "application/json": {
            "example": {
                "detail": {
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Missing X-API-Key header",
                        "details": None,
                    }
                }
            }
        }
    },
}

_REDIRECT_HTML_RESPONSE = {
    "description": "Redirect to the admin UI after OAuth callback handling",
    "content": {"text/html": {}},
    "headers": {
        "location": {
            "description": "Admin UI URL with connection status query parameters",
            "schema": {"type": "string"},
        }
    },
}

_FRONTEND_HTML_RESPONSE = {
    "description": "Admin UI page after following the OAuth callback redirect",
    "content": {"text/html": {"schema": {"type": "string"}}},
}

_JAVASCRIPT_RESPONSE = {
    "description": "Embeddable booking widget JavaScript",
    "content": {"application/javascript": {"schema": {"type": "string"}}},
}

_SSE_RESPONSE = {
    "description": "Server-sent chat events",
    "content": {"text/event-stream": {"schema": {"type": "string"}}},
}


def _route_requires_api_key(route: APIRoute) -> bool:
    def walk(dependant) -> bool:
        if getattr(dependant, "call", None) is require_api_key:
            return True
        return any(walk(dep) for dep in getattr(dependant, "dependencies", []) or [])

    return walk(route.dependant)


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    route_map: dict[tuple[str, str], APIRoute] = {}
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods or []:
                route_map[(route.path, method.lower())] = route

    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            route = route_map.get((path, method))
            if route and _route_requires_api_key(route):
                operation.setdefault("responses", {}).setdefault("401", _UNAUTHORIZED_RESPONSE)

            if method == "get" and (
                (path.startswith("/social/") and path.endswith("/callback"))
                or path == "/auth/google/callback"
            ):
                operation["responses"] = {"302": _REDIRECT_HTML_RESPONSE, "200": _FRONTEND_HTML_RESPONSE}

            if method == "get" and path == "/calendar/widget.js":
                operation["responses"] = {"200": _JAVASCRIPT_RESPONSE}

            if method == "post" and path == "/chat/stream":
                operation["responses"] = {
                    "200": _SSE_RESPONSE,
                    "422": {"description": "Validation Error"},
                }
                if route and _route_requires_api_key(route):
                    operation["responses"]["401"] = _UNAUTHORIZED_RESPONSE

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _custom_openapi

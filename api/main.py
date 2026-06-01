import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from first_boot import ensure_secrets, ensure_workspace

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

# Must run before get_settings() so generated keys are in os.environ when pydantic reads them
ensure_secrets()

from config import get_settings, validate_settings  # noqa: E402
from db import get_engine  # noqa: E402
from errors import BosError, bos_error_handler, unhandled_error_handler  # noqa: E402
from middleware import RequestLoggingMiddleware  # noqa: E402

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import models  # noqa: F401 — registers all ORM models with Base.metadata
    from registry import list_all  # eager module scan on startup

    validate_settings(settings)
    list_all()
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

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.add_exception_handler(BosError, bos_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

from routers import auth as auth_router  # noqa: E402
from routers import agent, backend_settings, billing, brands, calendar, capabilities, campaigns, chat, council, decision_briefs, documents, handoff, health, intents, media, memory, objectives, onboarding, outcomes, plugins, providers, runs, social, stream, verticals, webhooks, workspace  # noqa: E402

app.include_router(health.router)
app.include_router(agent.router)
app.include_router(workspace.router)
app.include_router(brands.router)
app.include_router(documents.router)
app.include_router(verticals.router)
app.include_router(capabilities.router)
app.include_router(runs.router)
app.include_router(chat.router)
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
app.include_router(campaigns.router)
app.include_router(social.router)
app.include_router(webhooks.router)
app.include_router(plugins.router)
app.include_router(calendar.router)
app.include_router(council.router)
app.include_router(media.router)

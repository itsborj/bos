import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import get_settings
from db import get_engine
from errors import BosError, bos_error_handler, unhandled_error_handler
from middleware import RequestLoggingMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import models  # noqa: F401 — registers all ORM models with Base.metadata
    from registry import list_all  # eager module scan on startup

    list_all()

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
app.add_exception_handler(BosError, bos_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

from routers import auth as auth_router  # noqa: E402
from routers import backend_settings, billing, brands, capabilities, campaigns, chat, documents, health, intents, onboarding, providers, runs, social, stream, verticals, workspace  # noqa: E402

app.include_router(health.router)
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
app.include_router(onboarding.router)
app.include_router(stream.router)
app.include_router(auth_router.router)
app.include_router(campaigns.router)
app.include_router(social.router)

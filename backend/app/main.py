import asyncio
import sys

if sys.platform == "win32":
    _policy = getattr(asyncio, "WindowsProactorEventLoopPolicy", None)
    if _policy is not None:
        asyncio.set_event_loop_policy(_policy())

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.database import init_db
from app.core.exceptions import register_exception_handlers
from app.api.v1.router import api_router

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Resume JD Matcher",
        description="AI-powered resume evaluation and job description matching system",
        version="0.1.0",
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    register_exception_handlers(app)

    # API routes under /api/v1
    app.include_router(api_router)

    # Health check (outside /api/v1 for load balancers)
    @app.get("/health", tags=["System"])
    async def health_check():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()

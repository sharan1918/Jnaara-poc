from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jnaara.api.dependencies import get_configured_engine
from jnaara.api.routes import router
from jnaara.api.security import setup_security
from jnaara.config import get_settings

logger = logging.getLogger("jnaara.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown routines."""
    settings = get_settings()
    logger.info("Starting Jnaara API with DB path: %s", settings.db_path)
    # Ensure database schema is initialized
    get_configured_engine(settings)
    yield
    logger.info("Shutting down Jnaara API.")


def create_app() -> FastAPI:
    """Factory creating and configuring the FastAPI application."""
    app = FastAPI(
        title="Jnaara Belief Engine API",
        description=(
            "Deterministic belief engine with LLM-powered semantic analysis, "
            "conflict detection, resolution, and immutable provenance tracking."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Security: Setup rate limiting, security headers, exception handling
    setup_security(app)

    # CORS configuration: Allow local development frontend (SvelteKit default 5173, etc.)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
            "*",  # Permissive for local demo
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Attach API routes
    app.include_router(router)

    @app.get("/health", tags=["Health"])
    def health_check():
        return {"status": "ok", "service": "jnaara-api"}

    return app


app = create_app()

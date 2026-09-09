from contextlib import asynccontextmanager
import logging
import sys
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from jnaara.api.dependencies import get_configured_engine
from jnaara.api.routes import router
from jnaara.api.security import setup_security
from jnaara.config import get_settings

# Configure structured application-wide logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Ensure all jnaara loggers capture INFO level
logging.getLogger("jnaara").setLevel(logging.INFO)
logger = logging.getLogger("jnaara.api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs incoming API requests, HTTP status codes, and execution durations."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        path = request.url.path
        method = request.method

        if not path.startswith("/health"):
            logger.info("--> [HTTP] %s %s", method, path)

        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        if not path.startswith("/health"):
            logger.info(
                "<-- [HTTP] %s %s %d (%.1fms)",
                method,
                path,
                response.status_code,
                duration_ms,
            )

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown routines."""
    settings = get_settings()
    has_groq = bool(settings.groq_api_key and settings.groq_api_key.get_secret_value().strip())
    has_google = bool(settings.google_api_key and settings.google_api_key.get_secret_value().strip())

    logger.info("=" * 60)
    logger.info("  JNAARA DETERMINISTIC BELIEF ENGINE API")
    logger.info("  Database Path:        %s", settings.db_path)
    logger.info("  Active Strategy:      %s", settings.default_strategy)
    logger.info(
        "  Primary LLM:          %s (%s) [Key: %s]",
        settings.primary_llm,
        settings.primary_model,
        "CONFIGURED" if has_groq else "NOT SET (will fallback to mock)",
    )
    logger.info(
        "  Secondary LLM:        %s (%s) [Key: %s]",
        settings.secondary_llm,
        settings.secondary_model,
        "CONFIGURED" if has_google else "NOT SET (will fallback to mock)",
    )
    logger.info("=" * 60)

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

    # Attach request logging
    app.add_middleware(RequestLoggingMiddleware)

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

import logging
import time
from uuid import uuid4
from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Initialize rate limiter with client IP address key
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],
    headers_enabled=False,
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds essential HTTP security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


class ContentLengthLimitMiddleware(BaseHTTPMiddleware):
    """Enforces a maximum request body size (default 10 MB) to prevent denial of service."""

    def __init__(self, app, max_upload_size: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_upload_size = max_upload_size

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_upload_size:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "status": "error",
                            "message": f"Payload exceeds maximum allowed size of {self.max_upload_size // (1024 * 1024)}MB",
                        },
                    )
            except ValueError:
                pass
        return await call_next(request)


def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Standardized JSON response when a client breaches rate limits."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "status": "error",
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": f"Too many requests. Limit exceeded: {exc.detail}",
            "retry_after": getattr(exc, "retry_after", 60),
        },
    )


def custom_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Standardized JSON response for schema validation errors."""
    errors = []
    for err in exc.errors():
        field = " -> ".join(str(loc) for loc in err.get("loc", []))
        errors.append({
            "field": field,
            "message": err.get("msg"),
            "type": err.get("type"),
        })

    return JSONResponse(
        status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
        content={
            "status": "error",
            "error_code": "SCHEMA_VALIDATION_ERROR",
            "message": "Input validation failed. Please check your request payload.",
            "details": errors,
        },
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catches unhandled server errors, masks sensitive traces, and logs them."""
    error_id = str(uuid4())[:8]
    logger.exception("Unhandled error [%s] during request %s %s", error_id, request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred while processing your request.",
            "error_id": error_id,
        },
    )


def setup_security(app: FastAPI) -> None:
    """Attach security middlewares and exception handlers to the FastAPI app."""
    # Middlewares
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(ContentLengthLimitMiddleware)

    # State & Exception Handlers
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, custom_rate_limit_exceeded_handler)
    app.add_exception_handler(RequestValidationError, custom_validation_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

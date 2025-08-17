"""FastAPI middleware for request/response logging with basic redaction."""

import logging
from typing import Iterable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log requests and responses, redacting configured headers."""

    def __init__(self, app, redact_headers: Iterable[str] | None = None):
        super().__init__(app)
        self.logger = logging.getLogger("pc-reviewer")
        self.redact_headers = {h.lower() for h in (redact_headers or ("authorization",))}

    async def dispatch(self, request: Request, call_next):
        headers = {
            k: ("<redacted>" if k.lower() in self.redact_headers else v)
            for k, v in request.headers.items()
        }
        self.logger.info("request %s %s %s", request.method, request.url.path, headers)
        response = await call_next(request)
        self.logger.info("response %s %s", response.status_code, request.url.path)
        return response


def setup_logging(app) -> None:
    """Install the :class:`LoggingMiddleware` on the given app."""
    app.add_middleware(LoggingMiddleware)

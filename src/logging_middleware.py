"""FastAPI middleware for request/response logging with basic redaction."""

import logging
import os
from logging.handlers import RotatingFileHandler
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
    """Install the LoggingMiddleware and ensure the 'pc-reviewer' logger outputs INFO."""
    logger = logging.getLogger("pc-reviewer")

    # formatter used for both handlers
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    # add console handler if none
    if not logger.handlers:
        sh = logging.StreamHandler()
        sh.setLevel(logging.DEBUG)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

        # optional rotating file handler
        os.makedirs("logs", exist_ok=True)
        fh = RotatingFileHandler("logs/mcp.log", maxBytes=5 * 1024 * 1024, backupCount=3)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    logger.setLevel(logging.DEBUG)
    # avoid duplicate messages if uvicorn/root logger is configured
    logger.propagate = False

    app.add_middleware(LoggingMiddleware)

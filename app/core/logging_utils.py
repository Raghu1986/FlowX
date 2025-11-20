# app/core/logging_utils.py

import logging
import time
import socket
from typing import Optional, Dict, Any

from pythonjsonlogger import jsonlogger
from app.core.config import settings
from app.core.logging import correlation_id_ctx


# -----------------------------
#  Host info
# -----------------------------
HOSTNAME = socket.gethostname()
APP_NAME = settings.APP_NAME
ENV = settings.APP_ENV


# -----------------------------
#  Request-aware logger wrapper
# -----------------------------
class RequestLogger:
    """
    Wraps a base logger and automatically injects:
      - correlation_id
      - method
      - path
      - client_ip
      - response_time_ms
    """

    def __init__(self, base_logger: logging.Logger, request_meta: Dict[str, Any]):
        self._base_logger = base_logger
        self._request_meta = request_meta
        self.start_time = time.perf_counter()

    def _inject(self, extra: Optional[dict]):
        if extra is None:
            extra = {}

        elapsed = (time.perf_counter() - self.start_time) * 1000

        # Final enriched extra
        extra.update({
            "correlation_id": correlation_id_ctx.get(None),
            "method": self._request_meta.get("method"),
            "path": self._request_meta.get("path"),
            "client_ip": self._request_meta.get("client_ip"),
            "response_time_ms": round(elapsed, 2),
            "hostname": HOSTNAME,
            "environment": ENV,
            "app": APP_NAME,
        })
        return extra

    def _log(self, level, msg, *args, extra=None, **kwargs):
        enriched = self._inject(extra)
        self._base_logger.log(level, msg, *args, extra=enriched, **kwargs)

    # Standard log methods
    def debug(self, msg, *a, **kw): self._log(logging.DEBUG, msg, *a, **kw)
    def info(self, msg, *a, **kw): self._log(logging.INFO, msg, *a, **kw)
    def warning(self, msg, *a, **kw): self._log(logging.WARNING, msg, *a, **kw)
    def error(self, msg, *a, **kw): self._log(logging.ERROR, msg, *a, **kw)
    def exception(self, msg, *a, **kw): self._log(logging.ERROR, msg, *a, exc_info=True, **kw)


# -----------------------------
#  App-level logger for background tasks
# -----------------------------
class AppLogger:
    """
    For background tasks or functions that do not have a Request context.

    Injects:
      - correlation_id ("bg-<timestamp>" auto-generated)
      - hostname / environment / app
      - No request path/method/client_ip
    """

    def __init__(self, base_logger: logging.Logger, correlation_id: Optional[str] = None):
        self._base_logger = base_logger
        self.start_time = time.perf_counter()

        if correlation_id:
            self.correlation_id = correlation_id
        else:
            self.correlation_id = f"bg-{int(time.time())}"

    def _inject(self, extra: Optional[dict]):
        if extra is None:
            extra = {}

        elapsed = (time.perf_counter() - self.start_time) * 1000

        extra.update({
            "correlation_id": self.correlation_id,
            "hostname": HOSTNAME,
            "environment": ENV,
            "app": APP_NAME,
            "response_time_ms": round(elapsed, 2),
            "method": None,
            "path": None,
            "client_ip": None,
        })
        return extra

    def _log(self, level, msg, *args, extra=None, **kwargs):
        enriched = self._inject(extra)
        self._base_logger.log(level, msg, *args, extra=enriched, **kwargs)

    def debug(self, msg, *a, **kw): self._log(logging.DEBUG, msg, *a, **kw)
    def info(self, msg, *a, **kw): self._log(logging.INFO, msg, *a, **kw)
    def warning(self, msg, *a, **kw): self._log(logging.WARNING, msg, *a, **kw)
    def error(self, msg, *a, **kw): self._log(logging.ERROR, msg, *a, **kw)
    def exception(self, msg, *a, **kw): self._log(logging.ERROR, msg, *a, exc_info=True, **kw)


# -----------------------------
#  Logger Getters
# -----------------------------
def get_logger(request) -> RequestLogger:
    """
    Request-aware logger used inside route handlers.
    Automatically attaches:
      - method
      - path
      - client_ip
      - correlation_id (from middleware)
    """
    base_logger = logging.getLogger("excelvalidator")

    client_ip = request.client.host if request.client else "unknown"

    meta = {
        "method": request.method,
        "path": request.url.path,
        "client_ip": client_ip,
    }

    return RequestLogger(base_logger, meta)


def get_app_logger(correlation_id: Optional[str] = None) -> AppLogger:
    """
    Logger for background tasks or non-request contexts.
    """
    base_logger = logging.getLogger("excelvalidator")
    return AppLogger(base_logger, correlation_id)

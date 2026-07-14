"""Structured logging setup for the Sistema TAZZIN.

Every module calls :func:`get_logger` instead of touching the standard
``logging`` module directly, so log destination/format stays centralized.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from logging.handlers import RotatingFileHandler

from app.core.config import settings

_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    """Renders each log record as one JSON line (machine-parseable)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _configure_root() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings.log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("tazzin")
    root.setLevel(settings.log_level)
    root.propagate = False

    formatter: logging.Formatter
    if settings.log_format == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        settings.log_dir / "tazzin.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger (e.g. ``get_logger(__name__)``)."""
    _configure_root()
    return logging.getLogger(f"tazzin.{name}")


class timed_block:
    """Context manager that logs how long a block of code took.

    Usage::

        with timed_block(logger, "sales.monthly_revenue"):
            ...
    """

    def __init__(self, logger: logging.Logger, label: str):
        self.logger = logger
        self.label = label
        self._start = 0.0

    def __enter__(self) -> "timed_block":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        elapsed_ms = (time.perf_counter() - self._start) * 1000
        if exc_type is None:
            self.logger.debug("%s completed in %.1fms", self.label, elapsed_ms)
        else:
            self.logger.error("%s failed after %.1fms: %s", self.label, elapsed_ms, exc)

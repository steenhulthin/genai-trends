from __future__ import annotations

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key.startswith("_") or key in {
                "args",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
            }:
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True)


def _resolve_log_level() -> int:
    explicit = os.getenv("APP_LOG_LEVEL")
    if explicit:
        return getattr(logging, explicit.upper(), logging.INFO)
    app_env = os.getenv("APP_ENV", "").lower()
    if app_env == "prod":
        return logging.ERROR
    return logging.INFO


def _build_handler(path: Path, formatter: logging.Formatter) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(formatter)
    return handler


def configure_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    level = _resolve_log_level()

    app_logger = logging.getLogger("genai_trends")
    fetch_logger = logging.getLogger("genai_trends.fetch")
    if app_logger.handlers or fetch_logger.handlers:
        return

    app_logger.setLevel(level)
    fetch_logger.setLevel(level)
    app_logger.propagate = False
    fetch_logger.propagate = False

    app_logger.addHandler(_build_handler(LOG_DIR / "app.log", logging.Formatter(LOG_FORMAT)))
    fetch_logger.addHandler(_build_handler(LOG_DIR / "fetch.log", JsonFormatter()))


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)

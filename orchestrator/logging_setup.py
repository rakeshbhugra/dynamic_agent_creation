"""
Structured logging setup using structlog.

Logs JSON to logs/gateway.log and human-readable output to stdout.
Call setup_logging() once at app startup before importing any other gateway module.
"""

import logging
import sys
from pathlib import Path

import structlog

LOG_FILE = Path("logs/gateway.log")


def setup_logging(level: int = logging.DEBUG) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    file_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processor=structlog.processors.JSONRenderer(),
    )
    console_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processor=structlog.dev.ConsoleRenderer(colors=True),
    )

    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    root.setLevel(level)

    # Quieten noisy third-party loggers
    for noisy in ("httpx", "httpcore", "litellm", "openai", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

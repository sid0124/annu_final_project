"""
VTR-Agent: Logging Configuration

Structured logging configuration with JSON output and correlation IDs.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any

from vtr_agent.core.config import get_settings

# Settings
settings = get_settings()


class CorrelationIdFilter(logging.Filter):
    """Filter to add correlation ID to log records."""

    def __init__(self, correlation_id: str | None = None):
        super().__init__()
        self.correlation_id = correlation_id

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to log record."""
        record.correlation_id = self.correlation_id or "unknown"
        return True


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id

        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        if hasattr(record, "project_id"):
            log_data["project_id"] = record.project_id

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if record.stack_info:
            log_data["stack_trace"] = record.stack_info

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in [
                "args",
                "asctime",
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
                "socketName",
                "thread",
                "threadName",
                "traceback",
                "xcuration",
            ]:
                if not key.startswith("_"):
                    log_data[key] = value

        return json.dumps(log_data, default=str)


def setup_logging() -> None:
    """Configure structured logging for VTR-Agent."""
    # Create handlers
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
    console_handler.setFormatter(StructuredFormatter())

    # File handler
    import os

    log_dir = os.path.dirname(os.path.abspath(settings.LOG_FILE))
    os.makedirs(log_dir, exist_ok=True)

    file_handler = logging.FileHandler(settings.LOG_FILE)
    file_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
    file_handler.setFormatter(StructuredFormatter())

    # Configure root logger
    root_logger = logging.getLogger("vtr_agent")
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add new handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Configure specific loggers
    database_logger = logging.getLogger("vtr_agent.database")
    database_logger.setLevel(logging.WARNING)

    security_logger = logging.getLogger("vtr_agent.security")
    security_logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    ml_logger = logging.getLogger("vtr_agent.ml")
    ml_logger.setLevel(logging.WARNING)

    retrieval_logger = logging.getLogger("vtr_agent.retrieval")
    retrieval_logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    sandbox_logger = logging.getLogger("vtr_agent.sandbox")
    sandbox_logger.setLevel(logging.WARNING)

    # Log application startup
    root_logger.info(
        "VTR-Agent logging initialized",
        extra={
            "app_version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        },
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with correlation ID.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    logger = logging.getLogger(f"vtr_agent.{name}")

    # Add correlation ID if not already present
    if not any(
        isinstance(f, CorrelationIdFilter) for f in logger.filters
    ):
        logger.addFilter(CorrelationIdFilter())

    return logger


class StructuredLoggerAdapter:
    """Adapter for structured logging with extra fields."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def debug(
        self,
        msg: str,
        *,
        user_id: str | None = None,
        project_id: str | None = None,
        correlation_id: str | None = None,
        **kwargs,
    ) -> None:
        """Log debug message with structured context."""
        extra = {}
        if user_id:
            extra["user_id"] = user_id
        if project_id:
            extra["project_id"] = project_id
        if correlation_id:
            extra["correlation_id"] = correlation_id
        extra.update(kwargs)

        self.logger.debug(msg, extra=extra)

    def info(
        self,
        msg: str,
        *,
        user_id: str | None = None,
        project_id: str | None = None,
        correlation_id: str | None = None,
        **kwargs,
    ) -> None:
        """Log info message with structured context."""
        extra = {}
        if user_id:
            extra["user_id"] = user_id
        if project_id:
            extra["project_id"] = project_id
        if correlation_id:
            extra["correlation_id"] = correlation_id
        extra.update(kwargs)

        self.logger.info(msg, extra=extra)

    def warning(
        self,
        msg: str,
        *,
        user_id: str | None = None,
        project_id: str | None = None,
        correlation_id: str | None = None,
        **kwargs,
    ) -> None:
        """Log warning message with structured context."""
        extra = {}
        if user_id:
            extra["user_id"] = user_id
        if project_id:
            extra["project_id"] = project_id
        if correlation_id:
            extra["correlation_id"] = correlation_id
        extra.update(kwargs)

        self.logger.warning(msg, extra=extra)

    def error(
        self,
        msg: str,
        *,
        user_id: str | None = None,
        project_id: str | None = None,
        correlation_id: str | None = None,
        **kwargs,
    ) -> None:
        """Log error message with structured context."""
        extra = {}
        if user_id:
            extra["user_id"] = user_id
        if project_id:
            extra["project_id"] = project_id
        if correlation_id:
            extra["correlation_id"] = correlation_id
        extra.update(kwargs)

        self.logger.error(msg, extra=extra)

    def critical(
        self,
        msg: str,
        *,
        user_id: str | None = None,
        project_id: str | None = None,
        correlation_id: str | None = None,
        **kwargs,
    ) -> None:
        """Log critical message with structured context."""
        extra = {}
        if user_id:
            extra["user_id"] = user_id
        if project_id:
            extra["project_id"] = project_id
        if correlation_id:
            extra["correlation_id"] = correlation_id
        extra.update(kwargs)

        self.logger.critical(msg, extra=extra)

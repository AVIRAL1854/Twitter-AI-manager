"""Structured logging configuration and exception definitions."""

import logging
import sys
from typing import Any, Optional
from rich.console import Console
from rich.logging import RichHandler

console = Console()


# --- Exception Hierarchy ---


class AgentError(Exception):
    """Base exception for all agent errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class BrowserError(AgentError):
    """Raised when browser automation, launch, or navigation fails."""

    pass


class ExtractionError(AgentError):
    """Raised when extracting or parsing post elements fails."""

    pass


class PlanningError(AgentError):
    """Raised when AI planner fails to generate valid plans."""

    pass


class ValidationError(AgentError):
    """Raised when an action or post violates strict validation rules."""

    pass


class ExecutionError(AgentError):
    """Raised when executing an approved browser action fails."""

    pass


class PersistenceError(AgentError):
    """Raised when database or memory storage fails."""

    pass


# --- Structured Context Logger ---


class AgentLogger:
    """Wrapper around standard logger adding structured context like run_id."""

    def __init__(self, logger: logging.Logger, run_id: Optional[str] = None):
        self._logger = logger
        self.run_id = run_id

    def with_run_id(self, run_id: str) -> "AgentLogger":
        """Return a new logger with the attached run_id."""
        return AgentLogger(self._logger, run_id=run_id)

    def _format_msg(self, msg: str) -> str:
        if self.run_id:
            return f"[{self.run_id[:8]}] {msg}"
        return msg

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.debug(self._format_msg(msg), *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.info(self._format_msg(msg), *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.warning(self._format_msg(msg), *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.error(self._format_msg(msg), *args, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.critical(self._format_msg(msg), *args, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.exception(self._format_msg(msg), *args, **kwargs)


def setup_logging(level: int = logging.INFO) -> AgentLogger:
    """Configure structured logging with rich output."""
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                console=console,
                show_time=True,
                show_path=False,
            )
        ],
        force=True,
    )
    # Silence overly verbose external loggers
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    root_logger = logging.getLogger("x_agent")
    root_logger.setLevel(level)
    return AgentLogger(root_logger)


def get_logger(name: str = "x_agent", run_id: Optional[str] = None) -> AgentLogger:
    """Retrieve logger instance."""
    return AgentLogger(logging.getLogger(name), run_id=run_id)


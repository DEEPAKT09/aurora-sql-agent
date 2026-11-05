
"""
AURORA SQL Agent
Centralized Logging Configuration

Provides consistent application logging with console
and rotating file handlers.
"""

import logging
import logging.handlers
import os

from pathlib import Path
from typing import Optional


# ---------------------------------------------------------
# DEFAULT CONFIGURATION
# ---------------------------------------------------------

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_DIRECTORY = "logs"
DEFAULT_LOG_FILENAME = "aurora_sql_agent.log"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 5

LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | "
    "%(name)s | %(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ---------------------------------------------------------
# LOG DIRECTORY
# ---------------------------------------------------------

def create_log_directory(
    log_directory: str = DEFAULT_LOG_DIRECTORY,
) -> Path:
    """Create the logging directory if it does not exist."""

    directory = Path(log_directory)

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


# ---------------------------------------------------------
# LOG LEVEL
# ---------------------------------------------------------

def get_log_level(
    level: Optional[str] = None,
) -> int:
    """Convert a logging level name into its numeric value."""

    level = (
        level
        or os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL)
    ).upper()

    numeric_level = getattr(logging, level, None)

    if not isinstance(numeric_level, int):
        return logging.INFO

    return numeric_level


# ---------------------------------------------------------
# LOGGER CONFIGURATION
# ---------------------------------------------------------

def setup_logger(
    name: str = "aurora_sql_agent",
    log_level: Optional[str] = None,
    log_directory: str = DEFAULT_LOG_DIRECTORY,
    log_filename: str = DEFAULT_LOG_FILENAME,
    enable_console: bool = True,
    enable_file: bool = True,
) -> logging.Logger:
    """
    Configure and return an application logger.

    Supports:
        - Console logging
        - Rotating file logging
        - Configurable logging levels
        - Consistent formatting
    """

    logger = logging.getLogger(name)

    # Prevent duplicate handlers when Streamlit reruns.
    if getattr(logger, "_aurora_configured", False):
        return logger

    logger.setLevel(get_log_level(log_level))
    logger.propagate = False

    formatter = logging.Formatter(
        fmt=LOG_FORMAT,
        datefmt=DATE_FORMAT,
    )

    # Console handler.
    if enable_console:
        console_handler = logging.StreamHandler()

        console_handler.setLevel(
            get_log_level(log_level)
        )

        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

    # Rotating file handler.
    if enable_file:
        try:
            directory = create_log_directory(
                log_directory
            )

            log_path = directory / log_filename

            file_handler = logging.handlers.RotatingFileHandler(
                filename=log_path,
                maxBytes=DEFAULT_MAX_BYTES,
                backupCount=DEFAULT_BACKUP_COUNT,
                encoding="utf-8",
            )

            file_handler.setLevel(
                get_log_level(log_level)
            )

            file_handler.setFormatter(formatter)

            logger.addHandler(file_handler)

        except OSError as exc:
            # Keep console logging available if file logging
            # cannot be initialized.
            if not enable_console:
                raise

            logger.warning(
                "File logging could not be initialized: %s",
                exc,
            )

    logger._aurora_configured = True

    return logger


# ---------------------------------------------------------
# SHARED APPLICATION LOGGER
# ---------------------------------------------------------

logger = setup_logger()


# ---------------------------------------------------------
# LOGGING HELPERS
# ---------------------------------------------------------

def log_info(
    message: str,
    *args,
) -> None:
    """Record an informational message."""

    logger.info(message, *args)


def log_warning(
    message: str,
    *args,
) -> None:
    """Record a warning message."""

    logger.warning(message, *args)


def log_error(
    message: str,
    *args,
    exc_info: bool = False,
) -> None:
    """Record an error message."""

    logger.error(
        message,
        *args,
        exc_info=exc_info,
    )


def log_exception(
    message: str,
    *args,
) -> None:
    """Record an error with exception traceback."""

    logger.exception(message, *args)


def log_debug(
    message: str,
    *args,
) -> None:
    """Record a debug message."""

    logger.debug(message, *args)


# ---------------------------------------------------------
# AGENT LOGGING
# ---------------------------------------------------------

def log_agent_start(agent_name: str) -> None:
    """Record the start of an agent."""

    logger.info(
        "Agent started: %s",
        agent_name,
    )


def log_agent_success(agent_name: str) -> None:
    """Record successful agent execution."""

    logger.info(
        "Agent completed successfully: %s",
        agent_name,
    )


def log_agent_failure(
    agent_name: str,
    error: Exception,
) -> None:
    """Record agent execution failure."""

    logger.exception(
        "Agent failed: %s | Error: %s",
        agent_name,
        error,
    )


# ---------------------------------------------------------
# DATABASE LOGGING
# ---------------------------------------------------------

def log_database_connection(
    database_type: str,
    database_name: str,
) -> None:
    """Record a database connection event."""

    logger.info(
        "Database connection established | Type: %s | Database: %s",
        database_type,
        database_name,
    )


def log_database_disconnection(
    database_name: str,
) -> None:
    """Record a database disconnection event."""

    logger.info(
        "Database connection closed | Database: %s",
        database_name,
    )


def log_query_execution(
    execution_time: float,
    row_count: int,
) -> None:
    """
    Record SQL execution statistics.

    SQL text and database credentials are deliberately
    excluded from this log entry.
    """

    logger.info(
        "SQL query executed | Execution time: %.3f seconds | Rows: %d",
        execution_time,
        row_count,
    )


def log_query_failure(
    error: Exception,
) -> None:
    """Record SQL execution failure."""

    logger.exception(
        "SQL query execution failed: %s",
        error,
    )


# ---------------------------------------------------------
# WORKFLOW LOGGING
# ---------------------------------------------------------

def log_workflow_start() -> None:
    """Record workflow initialization."""

    logger.info("AURORA SQL Agent workflow started.")


def log_workflow_success() -> None:
    """Record successful workflow completion."""

    logger.info("AURORA SQL Agent workflow completed.")


def log_workflow_failure(
    error: Exception,
) -> None:
    """Record workflow execution failure."""

    logger.exception(
        "AURORA SQL Agent workflow failed: %s",
        error,
    )


"""
AURORA SQL Agent
Common Utility Helpers

Provides reusable helper functions for data conversion,
text processing, conversation history and application
state management.
"""

import json
import logging
import math
import re

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID


# ---------------------------------------------------------
# LOGGING
# ---------------------------------------------------------

logger = logging.getLogger("aurora_sql_agent")


# ---------------------------------------------------------
# DATA SERIALIZATION
# ---------------------------------------------------------

def serialize_value(value: Any) -> Any:
    """
    Convert Python values into JSON-compatible values.

    Handles datetime, Decimal, UUID, bytes and other
    commonly encountered database values.
    """

    if value is None:
        return None

    if isinstance(value, (datetime, date, time)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    if isinstance(value, float) and not math.isfinite(value):
        return None

    if isinstance(value, dict):
        return {
            str(key): serialize_value(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            serialize_value(item)
            for item in value
        ]

    # Handle NumPy and Pandas scalar values.
    if hasattr(value, "item") and callable(value.item):
        try:
            return serialize_value(value.item())
        except (ValueError, TypeError):
            pass

    return value


def to_json(
    data: Any,
    indent: Optional[int] = None,
) -> str:
    """
    Convert Python data into a JSON string.
    """

    try:
        return json.dumps(
            serialize_value(data),
            indent=indent,
            ensure_ascii=False,
        )

    except (TypeError, ValueError) as exc:
        logger.error("JSON serialization failed: %s", exc)
        raise ValueError(
            f"Unable to convert data into JSON: {exc}"
        ) from exc


def from_json(
    json_string: str,
    default: Any = None,
) -> Any:
    """
    Safely parse a JSON string.

    Returns the supplied default if parsing fails.
    """

    if not json_string:
        return default

    try:
        return json.loads(json_string)

    except (json.JSONDecodeError, TypeError):
        logger.warning("Invalid JSON received.")
        return default


# ---------------------------------------------------------
# TEXT PROCESSING
# ---------------------------------------------------------

def clean_text(text: Any) -> str:
    """
    Normalize text by removing unnecessary whitespace.
    """

    if text is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(text),
    ).strip()


def normalize_identifier(identifier: Any) -> str:
    """
    Normalize a database identifier for comparison.

    This function is for comparison and display only.
    It must not be used to construct executable SQL.
    """

    if identifier is None:
        return ""

    return str(identifier).strip().strip('`"[]').lower()


def truncate_text(
    text: Any,
    max_length: int = 500,
    suffix: str = "...",
) -> str:
    """
    Truncate text to a specified maximum length.
    """

    text = str(text or "")

    if max_length < 0:
        raise ValueError("max_length cannot be negative.")

    if len(text) <= max_length:
        return text

    if max_length <= len(suffix):
        return text[:max_length]

    return text[:max_length - len(suffix)] + suffix


def extract_sql_code(text: str) -> str:
    """
    Extract SQL from a Markdown code block.

    If no SQL code block exists, return the cleaned text.
    """

    if not text:
        return ""

    pattern = r"```(?:sql|postgres|postgresql|mysql)?\s*(.*?)```"

    matches = re.findall(
        pattern,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if matches:
        return matches[0].strip()

    return text.strip()


# ---------------------------------------------------------
# CONVERSATION HISTORY
# ---------------------------------------------------------

def format_conversation_history(
    history: Optional[list],
    max_messages: int = 10,
) -> list[dict]:
    """
    Normalize conversation history into a consistent format.

    Supports dictionaries containing role/content or
    Streamlit-style message records.
    """

    if not history:
        return []

    formatted_history = []

    for message in history[-max_messages:]:
        if not isinstance(message, dict):
            continue

        role = message.get("role", "user")
        content = message.get("content", "")

        if role not in ("user", "assistant", "system"):
            continue

        if not content:
            continue

        formatted_history.append({
            "role": role,
            "content": str(content),
        })

    return formatted_history


def add_conversation_message(
    history: Optional[list],
    role: str,
    content: str,
    max_messages: int = 20,
) -> list[dict]:
    """
    Add a message to conversation history.

    Returns a new list without modifying the original.
    """

    if role not in ("user", "assistant", "system"):
        raise ValueError("Invalid conversation role.")

    updated_history = list(history or [])

    updated_history.append({
        "role": role,
        "content": str(content or ""),
    })

    return updated_history[-max_messages:]


# ---------------------------------------------------------
# DATABASE RESULT HELPERS
# ---------------------------------------------------------

def normalize_database_records(
    records: Optional[list],
) -> list[dict]:
    """
    Normalize database records into JSON-compatible
    dictionaries.
    """

    if not records:
        return []

    normalized_records = []

    for record in records:
        if hasattr(record, "_mapping"):
            record = dict(record._mapping)

        elif not isinstance(record, dict):
            try:
                record = dict(record)
            except (TypeError, ValueError):
                logger.warning(
                    "Skipping unsupported database record."
                )
                continue

        normalized_records.append(
            serialize_value(record)
        )

    return normalized_records


def get_result_statistics(
    records: Optional[list],
) -> dict:
    """
    Generate basic statistics for query results.
    """

    normalized_records = normalize_database_records(records)

    if not normalized_records:
        return {
            "row_count": 0,
            "column_count": 0,
            "columns": [],
        }

    columns = list(normalized_records[0].keys())

    return {
        "row_count": len(normalized_records),
        "column_count": len(columns),
        "columns": columns,
    }


# ---------------------------------------------------------
# SCHEMA HELPERS
# ---------------------------------------------------------

def normalize_schema_metadata(
    metadata: Any,
) -> dict:
    """
    Ensure schema metadata has a dictionary structure.
    """

    if metadata is None:
        return {}

    if isinstance(metadata, dict):
        return metadata

    if hasattr(metadata, "model_dump"):
        return metadata.model_dump()

    if hasattr(metadata, "dict"):
        return metadata.dict()

    raise TypeError(
        "Schema metadata must be a dictionary or "
        "a supported model object."
    )


def get_schema_table_names(
    metadata: Optional[dict],
) -> list[str]:
    """
    Extract table names from schema metadata.
    """

    if not isinstance(metadata, dict):
        return []

    tables = metadata.get("tables", [])

    if isinstance(tables, dict):
        return list(tables.keys())

    table_names = []

    for table in tables:
        if isinstance(table, str):
            table_names.append(table)

        elif isinstance(table, dict):
            name = (
                table.get("table_name")
                or table.get("name")
            )

            if name:
                table_names.append(name)

    return table_names


# ---------------------------------------------------------
# APPLICATION STATE HELPERS
# ---------------------------------------------------------

def get_error_message(
    error: Any,
    default: str = "An unexpected error occurred.",
) -> str:
    """
    Convert an exception or error value into a
    user-friendly message.
    """

    if error is None:
        return default

    message = clean_text(error)

    return message or default


def is_valid_database_type(database_type: str) -> bool:
    """
    Check whether a database type is supported.
    """

    return (
        str(database_type).strip().lower()
        in ("postgresql", "postgres", "mysql")
    )


def get_database_dialect(database_type: str) -> str:
    """
    Convert a database type into its SQL dialect name.
    """

    database_type = str(database_type).strip().lower()

    dialect_mapping = {
        "postgresql": "postgres",
        "postgres": "postgres",
        "mysql": "mysql",
    }

    if database_type not in dialect_mapping:
        raise ValueError(
            f"Unsupported database type: {database_type}"
        )

    return dialect_mapping[database_type]


# ---------------------------------------------------------
# GENERAL HELPERS
# ---------------------------------------------------------

def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """Convert a value into an integer safely."""

    try:
        return int(value)

    except (ValueError, TypeError, OverflowError):
        return default


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Convert a value into a float safely."""

    try:
        result = float(value)

        if not math.isfinite(result):
            return default

        return result

    except (ValueError, TypeError, OverflowError):
        return default


def generate_display_title(
    text: str,
    max_length: int = 60,
) -> str:
    """
    Generate a short display title from user text.
    """

    cleaned = clean_text(text)

    if not cleaned:
        return "New Query"

    return truncate_text(
        cleaned,
        max_length=max_length,
    )

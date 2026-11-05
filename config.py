
"""
AURORA SQL Agent
Central application configuration.

Loads environment variables and provides configuration
for the LLM, database execution, security and application.
"""

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


# Load environment variables from .env
load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    """Centralized application settings."""

    # Application
    app_name: str = "AURORA SQL Agent"
    app_version: str = "1.0.0"
    environment: str = os.getenv("APP_ENV", "development")

    # Gemini LLM
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv(
        "GEMINI_MODEL",
        "gemini-3.5-flash-lite"
    )

    # LangSmith observability
    langsmith_tracing: bool = (
        os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
    )
    langsmith_api_key: str = os.getenv("LANGSMITH_API_KEY", "")
    langsmith_project: str = os.getenv(
        "LANGSMITH_PROJECT",
        "aurora-sql-agent"
    )
    langsmith_endpoint: str = os.getenv(
        "LANGSMITH_ENDPOINT",
        "https://api.smith.langchain.com"
    )

    # Database
    supported_databases: tuple = ("postgresql", "mysql")
    database_connection_timeout: int = 15

    # Query execution safety
    read_only_mode: bool = True
    max_rows: int = 1000
    query_timeout: int = 30
    max_retries: int = 2

    # SQL generation
    sql_dialect_default: str = "postgres"
    sql_generation_max_tokens: int = 4096

    # Conversation
    max_chat_history: int = 10

    # Visualization
    default_chart_height: int = 400

    # File export
    export_max_rows: int = 10000


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """
    Return a cached application configuration instance.
    """
    return AppConfig()


# Shared configuration instance
settings = get_config()


def validate_config() -> None:
    """
    Validate essential configuration before running the application.
    """

    if not settings.gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY is missing. "
            "Please configure it in your .env file."
        )

    if settings.max_rows <= 0:
        raise ValueError("MAX_ROWS must be greater than zero.")

    if settings.query_timeout <= 0:
        raise ValueError("QUERY_TIMEOUT must be greater than zero.")

    if settings.database_connection_timeout <= 0:
        raise ValueError(
            "DATABASE_CONNECTION_TIMEOUT must be greater than zero."
        )

    if settings.max_retries < 0:
        raise ValueError("MAX_RETRIES cannot be negative.")

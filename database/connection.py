
"""
AURORA SQL Agent
Database Connection Manager

Supports:
- PostgreSQL
- MySQL

Responsibilities:
- Build secure SQLAlchemy connection URLs.
- Create and manage database engines.
- Test database connectivity.
- Provide database connection contexts.
- Dispose database connections safely.
"""

from dataclasses import dataclass, field
from typing import Optional
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.exc import SQLAlchemyError

from config import settings


class DatabaseConnectionError(Exception):
    """Raised when a database connection operation fails."""


@dataclass
class DatabaseConnectionConfig:
    """Database connection parameters."""

    database_type: str
    host: str
    port: int
    database: str
    username: str
    password: str = field(repr=False)
    schema: Optional[str] = None
    ssl_mode: Optional[str] = None


class DatabaseManager:
    """Manages SQLAlchemy database connections."""

    SUPPORTED_DATABASES = {
        "postgresql": {
            "driver": "postgresql+psycopg",
            "default_port": 5432,
        },
        "mysql": {
            "driver": "mysql+pymysql",
            "default_port": 3306,
        },
    }

    def __init__(self):
        self.engine: Optional[Engine] = None
        self.connection_config: Optional[DatabaseConnectionConfig] = None

    @staticmethod
    def normalize_database_type(database_type: str) -> str:
        """Normalize and validate the database type."""

        normalized = database_type.strip().lower()

        aliases = {
            "postgres": "postgresql",
            "postgresql": "postgresql",
            "mysql": "mysql",
        }

        if normalized not in aliases:
            raise DatabaseConnectionError(
                f"Unsupported database type: {database_type}. "
                "Supported databases: PostgreSQL and MySQL."
            )

        return aliases[normalized]

    def build_connection_url(
        self,
        config: DatabaseConnectionConfig
    ) -> URL:
        """Build a SQLAlchemy URL without exposing credentials."""

        database_type = self.normalize_database_type(
            config.database_type
        )

        database_info = self.SUPPORTED_DATABASES[database_type]

        if not config.host.strip():
            raise DatabaseConnectionError("Database host is required.")

        if not config.database.strip():
            raise DatabaseConnectionError("Database name is required.")

        if not config.username.strip():
            raise DatabaseConnectionError("Database username is required.")

        if not config.password:
            raise DatabaseConnectionError("Database password is required.")

        if not 1 <= config.port <= 65535:
            raise DatabaseConnectionError("Invalid database port.")

        query = {}

        if config.ssl_mode:
            if database_type == "postgresql":
                query["sslmode"] = config.ssl_mode

            elif database_type == "mysql":
                query["ssl_mode"] = config.ssl_mode

        return URL.create(
            drivername=database_info["driver"],
            username=config.username,
            password=config.password,
            host=config.host.strip(),
            port=config.port,
            database=config.database.strip(),
            query=query,
        )

    def create_engine(
        self,
        config: DatabaseConnectionConfig
    ) -> Engine:
        """
        Create a SQLAlchemy engine.

        The engine uses connection health checks and a bounded
        connection pool.
        """

        connection_url = self.build_connection_url(config)

        try:
            engine = create_engine(
                connection_url,
                pool_pre_ping=True,
                pool_recycle=1800,
                pool_size=5,
                max_overflow=5,
                pool_timeout=settings.database_connection_timeout,
                connect_args={
    "connect_timeout": settings.database_connection_timeout
},
            )

            self.engine = engine
            self.connection_config = config

            return engine

        except SQLAlchemyError as exc:
            raise DatabaseConnectionError(
                "Unable to initialize the database engine. "
                "Please verify the connection details."
            ) from exc

    def test_connection(
        self,
        config: DatabaseConnectionConfig
    ) -> dict:
        """Test database connectivity using SELECT 1."""

        temporary_engine = None

        try:
            temporary_engine = create_engine(
                self.build_connection_url(config),
                pool_pre_ping=True,
                pool_size=1,
                max_overflow=0,
                pool_timeout=settings.database_connection_timeout,
                connect_args={
                    "connect_timeout": settings.database_connection_timeout
                },
            )

            with temporary_engine.connect() as connection:
                connection.execute(text("SELECT 1"))

            return {
                "success": True,
                "message": (
                    f"Successfully connected to "
                    f"{config.database_type} database."
                ),
                "database": config.database,
                "host": config.host,
                "database_type": self.normalize_database_type(
                    config.database_type
                ),
            }

        except Exception as exc:
            return {
                "success": False,
                "message": (
                    "Database connection failed. "
                    "Check the host, port, database name, "
                    "username, password and network access."
                ),
                "error_type": type(exc).__name__,
            }

        finally:
            if temporary_engine is not None:
                temporary_engine.dispose()

    def connect(
        self,
        config: DatabaseConnectionConfig
    ) -> Engine:
        """Create an engine and verify database connectivity."""

        self.close()

        engine = self.create_engine(config)

        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))

            return engine

        except SQLAlchemyError as exc:
            engine.dispose()
            self.engine = None
            self.connection_config = None

            raise DatabaseConnectionError(
                "Unable to connect to the selected database. "
                "Please verify your connection settings."
            ) from exc

    def get_engine(self) -> Engine:
        """Return the active database engine."""

        if self.engine is None:
            raise DatabaseConnectionError(
                "No active database connection. "
                "Please connect to a database first."
            )

        return self.engine

    @contextmanager
    def get_connection(self):
        """Provide a managed database connection context."""

        engine = self.get_engine()

        connection = engine.connect()

        try:
            yield connection

        finally:
            connection.close()

    def get_database_type(self) -> str:
        """Return the active database dialect."""

        if self.connection_config is None:
            raise DatabaseConnectionError(
                "No active database connection."
            )

        return self.normalize_database_type(
            self.connection_config.database_type
        )

    def get_database_name(self) -> str:
        """Return the connected database name."""

        if self.connection_config is None:
            raise DatabaseConnectionError(
                "No active database connection."
            )

        return self.connection_config.database

    def is_connected(self) -> bool:
        """Check whether the active connection is available."""

        if self.engine is None:
            return False

        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))

            return True

        except SQLAlchemyError:
            return False

    def close(self) -> None:
        """Dispose the active database engine."""

        if self.engine is not None:
            self.engine.dispose()

        self.engine = None
        self.connection_config = None


# Shared database manager instance
database_manager = DatabaseManager()


"""
AURORA SQL Agent
Database Connection Tests

Tests database configuration, connection URL generation,
engine creation, connectivity testing and connection management.
"""

import pytest

from unittest.mock import MagicMock, patch

from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

from database.connection import (
    DatabaseConnectionConfig,
    DatabaseConnectionError,
    DatabaseManager,
)


@pytest.fixture
def manager():
    return DatabaseManager()


@pytest.fixture
def postgres_config():
    return DatabaseConnectionConfig(
        database_type="postgresql",
        host="localhost",
        port=5432,
        database="test_db",
        username="test_user",
        password="test_password",
    )


@pytest.fixture
def mysql_config():
    return DatabaseConnectionConfig(
        database_type="mysql",
        host="localhost",
        port=3306,
        database="test_db",
        username="test_user",
        password="test_password",
    )


def mock_engine():
    """Create a mock SQLAlchemy engine with usable connections."""

    engine = MagicMock()
    connection = MagicMock()

    engine.connect.return_value.__enter__.return_value = connection

    return engine


# ---------------------------------------------------------
# Database type normalization
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "database_type, expected",
    [
        ("postgres", "postgresql"),
        ("postgresql", "postgresql"),
        ("POSTGRESQL", "postgresql"),
        ("mysql", "mysql"),
        ("MYSQL", "mysql"),
    ],
)
def test_normalize_database_type(
    manager,
    database_type,
    expected,
):
    result = manager.normalize_database_type(database_type)

    assert result == expected


def test_unsupported_database_type(manager):
    with pytest.raises(DatabaseConnectionError):
        manager.normalize_database_type("sqlite")


def test_database_type_with_whitespace(manager):
    assert (
        manager.normalize_database_type("  POSTGRES  ")
        == "postgresql"
    )


# ---------------------------------------------------------
# Connection URL generation
# ---------------------------------------------------------

def test_postgresql_connection_url(manager, postgres_config):
    url = manager.build_connection_url(postgres_config)

    assert isinstance(url, URL)
    assert url.drivername == "postgresql+psycopg"
    assert url.username == "test_user"
    assert url.host == "localhost"
    assert url.port == 5432
    assert url.database == "test_db"


def test_mysql_connection_url(manager, mysql_config):
    url = manager.build_connection_url(mysql_config)

    assert isinstance(url, URL)
    assert url.drivername == "mysql+pymysql"
    assert url.username == "test_user"
    assert url.host == "localhost"
    assert url.port == 3306
    assert url.database == "test_db"


def test_connection_url_preserves_special_password(manager):
    config = DatabaseConnectionConfig(
        database_type="postgresql",
        host="localhost",
        port=5432,
        database="test_db",
        username="test_user",
        password="p@ss/w:rd#123",
    )

    url = manager.build_connection_url(config)

    assert url.password == "p@ss/w:rd#123"


def test_missing_host_is_rejected(manager, postgres_config):
    postgres_config.host = ""

    with pytest.raises(DatabaseConnectionError):
        manager.build_connection_url(postgres_config)


def test_missing_database_is_rejected(manager, postgres_config):
    postgres_config.database = ""

    with pytest.raises(DatabaseConnectionError):
        manager.build_connection_url(postgres_config)


def test_missing_username_is_rejected(manager, postgres_config):
    postgres_config.username = ""

    with pytest.raises(DatabaseConnectionError):
        manager.build_connection_url(postgres_config)


def test_missing_password_is_rejected(manager, postgres_config):
    postgres_config.password = ""

    with pytest.raises(DatabaseConnectionError):
        manager.build_connection_url(postgres_config)


def test_invalid_port_is_rejected(manager, postgres_config):
    postgres_config.port = 70000

    with pytest.raises(DatabaseConnectionError):
        manager.build_connection_url(postgres_config)


# ---------------------------------------------------------
# Engine creation
# ---------------------------------------------------------

def test_create_engine_uses_sqlalchemy_url(
    manager,
    postgres_config,
):
    engine = mock_engine()

    with patch(
        "database.connection.create_engine",
        return_value=engine,
    ) as mocked_create_engine:

        result = manager.create_engine(postgres_config)

    assert result is engine
    assert manager.engine is engine
    assert manager.connection_config is postgres_config

    mocked_create_engine.assert_called_once()


def test_create_engine_failure(manager, postgres_config):
    with patch(
        "database.connection.create_engine",
        side_effect=SQLAlchemyError("Engine initialization failed"),
    ):
        with pytest.raises(DatabaseConnectionError):
            manager.create_engine(postgres_config)


# ---------------------------------------------------------
# Connection testing
# ---------------------------------------------------------

def test_test_connection_success(
    manager,
    postgres_config,
):
    engine = mock_engine()

    with patch(
        "database.connection.create_engine",
        return_value=engine,
    ):
        result = manager.test_connection(postgres_config)

    assert result["success"] is True
    assert result["database"] == "test_db"
    assert result["host"] == "localhost"
    assert result["database_type"] == "postgresql"

    engine.connect.assert_called_once()
    engine.dispose.assert_called_once()


def test_test_connection_failure(
    manager,
    postgres_config,
):
    with patch(
        "database.connection.create_engine",
        side_effect=SQLAlchemyError("Connection failed"),
    ):
        result = manager.test_connection(postgres_config)

    assert result["success"] is False
    assert "message" in result
    assert result["error_type"] == "SQLAlchemyError"


def test_test_connection_disposes_engine_on_failure(
    manager,
    postgres_config,
):
    engine = MagicMock()

    engine.connect.side_effect = SQLAlchemyError(
        "Connection failed"
    )

    with patch(
        "database.connection.create_engine",
        return_value=engine,
    ):
        result = manager.test_connection(postgres_config)

    assert result["success"] is False
    engine.dispose.assert_called_once()


# ---------------------------------------------------------
# Connection management
# ---------------------------------------------------------

def test_connect_stores_engine(
    manager,
    postgres_config,
):
    engine = mock_engine()

    with patch(
        "database.connection.create_engine",
        return_value=engine,
    ):
        result = manager.connect(postgres_config)

    assert result is engine
    assert manager.engine is engine
    assert manager.connection_config is postgres_config
    assert manager.is_connected() is True


def test_get_database_type_after_connection(
    manager,
    postgres_config,
):
    engine = mock_engine()

    with patch(
        "database.connection.create_engine",
        return_value=engine,
    ):
        manager.connect(postgres_config)

    assert manager.get_database_type() == "postgresql"


def test_get_database_name_after_connection(
    manager,
    postgres_config,
):
    engine = mock_engine()

    with patch(
        "database.connection.create_engine",
        return_value=engine,
    ):
        manager.connect(postgres_config)

    assert manager.get_database_name() == "test_db"


def test_get_engine_without_connection(manager):
    with pytest.raises(DatabaseConnectionError):
        manager.get_engine()


def test_close_connection(
    manager,
    postgres_config,
):
    engine = mock_engine()

    with patch(
        "database.connection.create_engine",
        return_value=engine,
    ):
        manager.connect(postgres_config)

    manager.close()

    engine.dispose.assert_called_once()

    assert manager.engine is None
    assert manager.connection_config is None
    assert manager.is_connected() is False


def test_close_without_connection(manager):
    manager.close()

    assert manager.engine is None
    assert manager.connection_config is None


def test_connect_failure_cleans_up(
    manager,
    postgres_config,
):
    engine = MagicMock()

    engine.connect.side_effect = SQLAlchemyError(
        "Unable to connect"
    )

    with patch(
        "database.connection.create_engine",
        return_value=engine,
    ):
        with pytest.raises(DatabaseConnectionError):
            manager.connect(postgres_config)

    engine.dispose.assert_called_once()

    assert manager.engine is None
    assert manager.connection_config is None


# ---------------------------------------------------------
# Connection context manager
# ---------------------------------------------------------

def test_get_connection_context(
    manager,
    postgres_config,
):
    engine = mock_engine()
    connection = engine.connect.return_value

    with patch(
        "database.connection.create_engine",
        return_value=engine,
    ):
        manager.connect(postgres_config)

    with manager.get_connection() as active_connection:
        assert active_connection is connection


    # One connection for connect() and one for get_connection().
    assert engine.connect.call_count == 2

    connection.close.assert_called_once()


def test_connection_context_without_engine(manager):
    with pytest.raises(DatabaseConnectionError):
        with manager.get_connection():
            pass


# ---------------------------------------------------------
# Connection status
# ---------------------------------------------------------

def test_is_connected_without_engine(manager):
    assert manager.is_connected() is False


def test_is_connected_with_engine(
    manager,
    postgres_config,
):
    engine = mock_engine()

    with patch(
        "database.connection.create_engine",
        return_value=engine,
    ):
        manager.connect(postgres_config)

    assert manager.is_connected() is True


def test_is_connected_when_database_fails(
    manager,
    postgres_config,
):
    engine = mock_engine()

    with patch(
        "database.connection.create_engine",
        return_value=engine,
    ):
        manager.connect(postgres_config)

    engine.connect.side_effect = SQLAlchemyError(
        "Connection lost"
    )

    assert manager.is_connected() is False


# ---------------------------------------------------------
# Database configuration
# ---------------------------------------------------------

def test_postgres_configuration(postgres_config):
    assert postgres_config.database_type == "postgresql"
    assert postgres_config.host == "localhost"
    assert postgres_config.port == 5432
    assert postgres_config.database == "test_db"


def test_mysql_configuration(mysql_config):
    assert mysql_config.database_type == "mysql"
    assert mysql_config.host == "localhost"
    assert mysql_config.port == 3306
    assert mysql_config.database == "test_db"

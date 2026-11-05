
"""
AURORA SQL Agent
Schema Discovery Tests

Tests schema inspection, tables, views, columns,
primary keys, foreign keys, indexes and schema summaries.
"""

import pytest
from unittest.mock import MagicMock, patch

from database.schema_discovery import (
    SchemaDiscovery,
    SchemaDiscoveryError,
)


@pytest.fixture
def mock_engine():
    """Create a mock PostgreSQL engine."""

    engine = MagicMock()
    engine.dialect.name = "postgresql"
    engine.url.database = "test_database"

    return engine


@pytest.fixture
def mock_inspector(mock_engine):
    """Create a mock SQLAlchemy inspector."""

    inspector = MagicMock()
    inspector.engine = mock_engine

    inspector.get_schema_names.return_value = [
        "public",
        "information_schema",
        "pg_catalog",
    ]

    inspector.get_table_names.return_value = [
        "customers",
        "orders",
        "products",
    ]

    inspector.get_view_names.return_value = [
        "customer_summary",
    ]

    inspector.get_columns.return_value = [
        {
            "name": "id",
            "type": "INTEGER",
            "nullable": False,
            "default": None,
            "autoincrement": True,
            "comment": None,
        },
        {
            "name": "name",
            "type": "VARCHAR(100)",
            "nullable": False,
            "default": None,
            "autoincrement": False,
            "comment": None,
        },
        {
            "name": "email",
            "type": "VARCHAR(150)",
            "nullable": True,
            "default": None,
            "autoincrement": False,
            "comment": None,
        },
    ]

    inspector.get_pk_constraint.return_value = {
        "constrained_columns": ["id"],
        "name": "customers_pkey",
    }

    inspector.get_foreign_keys.return_value = [
        {
            "name": "orders_customer_id_fkey",
            "constrained_columns": ["customer_id"],
            "referred_table": "customers",
            "referred_columns": ["id"],
            "referred_schema": "public",
        }
    ]

    inspector.get_indexes.return_value = [
        {
            "name": "ix_customers_email",
            "column_names": ["email"],
            "unique": True,
        }
    ]

    return inspector


@pytest.fixture
def discovery(mock_engine):
    """Create SchemaDiscovery with an injected engine."""

    return SchemaDiscovery(engine=mock_engine)


@pytest.fixture
def configured_discovery(discovery, mock_inspector):
    """Provide a discovery instance with a mocked inspector."""

    with patch.object(
        discovery,
        "get_inspector",
        return_value=mock_inspector,
    ):
        yield discovery


# ---------------------------------------------------------
# Initialization
# ---------------------------------------------------------

def test_schema_discovery_initialization(discovery, mock_engine):
    assert discovery is not None
    assert discovery.engine is mock_engine


def test_get_engine(discovery, mock_engine):
    assert discovery.get_engine() is mock_engine


# ---------------------------------------------------------
# Schema discovery
# ---------------------------------------------------------

def test_get_schemas(configured_discovery, mock_inspector):
    result = configured_discovery.get_schemas()

    assert isinstance(result, list)
    assert result == ["public"]

    assert "information_schema" not in result
    assert "pg_catalog" not in result

    mock_inspector.get_schema_names.assert_called_once()


def test_get_tables(configured_discovery, mock_inspector):
    result = configured_discovery.get_tables(schema="public")

    assert isinstance(result, list)
    assert result == ["customers", "orders", "products"]

    mock_inspector.get_table_names.assert_called_once_with(
        schema="public"
    )


def test_get_views(configured_discovery, mock_inspector):
    result = configured_discovery.get_views(schema="public")

    assert isinstance(result, list)
    assert result == ["customer_summary"]

    mock_inspector.get_view_names.assert_called_once_with(
        schema="public"
    )


# ---------------------------------------------------------
# Column metadata
# ---------------------------------------------------------

def test_get_columns(configured_discovery, mock_inspector):
    result = configured_discovery.get_columns(
        table_name="customers",
        schema="public",
    )

    assert isinstance(result, list)
    assert len(result) == 3

    assert result[0]["name"] == "id"
    assert result[1]["name"] == "name"
    assert result[2]["name"] == "email"

    mock_inspector.get_columns.assert_called_once_with(
        "customers",
        schema="public",
    )


def test_get_columns_returns_column_types(configured_discovery):
    result = configured_discovery.get_columns(
        table_name="customers",
        schema="public",
    )

    assert result[0]["type"] == "INTEGER"
    assert result[1]["type"] == "VARCHAR(100)"
    assert result[2]["type"] == "VARCHAR(150)"


def test_get_columns_preserves_nullable_values(configured_discovery):
    result = configured_discovery.get_columns(
        table_name="customers",
        schema="public",
    )

    assert result[0]["nullable"] is False
    assert result[1]["nullable"] is False
    assert result[2]["nullable"] is True


def test_get_columns_identifies_primary_key(configured_discovery):
    result = configured_discovery.get_columns(
        table_name="customers",
        schema="public",
    )

    assert result[0]["primary_key"] is True
    assert result[1]["primary_key"] is False
    assert result[2]["primary_key"] is False


# ---------------------------------------------------------
# Primary keys
# ---------------------------------------------------------

def test_get_primary_keys(configured_discovery, mock_inspector):
    result = configured_discovery.get_primary_keys(
        table_name="customers",
        schema="public",
    )

    assert isinstance(result, list)
    assert result == ["id"]

    mock_inspector.get_pk_constraint.assert_called_once_with(
        "customers",
        schema="public",
    )


# ---------------------------------------------------------
# Foreign keys
# ---------------------------------------------------------

def test_get_foreign_keys(configured_discovery, mock_inspector):
    result = configured_discovery.get_foreign_keys(
        table_name="orders",
        schema="public",
    )

    assert isinstance(result, list)
    assert len(result) == 1

    foreign_key = result[0]

    assert foreign_key["name"] == "orders_customer_id_fkey"
    assert foreign_key["constrained_columns"] == ["customer_id"]
    assert foreign_key["referred_table"] == "customers"
    assert foreign_key["referred_columns"] == ["id"]
    assert foreign_key["referred_schema"] == "public"

    mock_inspector.get_foreign_keys.assert_called_once_with(
        "orders",
        schema="public",
    )


# ---------------------------------------------------------
# Indexes
# ---------------------------------------------------------

def test_get_indexes(configured_discovery, mock_inspector):
    result = configured_discovery.get_indexes(
        table_name="customers",
        schema="public",
    )

    assert isinstance(result, list)
    assert len(result) == 1

    index = result[0]

    assert index["name"] == "ix_customers_email"
    assert index["columns"] == ["email"]
    assert index["unique"] is True

    mock_inspector.get_indexes.assert_called_once_with(
        "customers",
        schema="public",
    )


# ---------------------------------------------------------
# Complete table metadata
# ---------------------------------------------------------

def test_get_table_schema(configured_discovery):
    result = configured_discovery.get_table_schema(
        table_name="customers",
        schema="public",
    )

    assert isinstance(result, dict)

    assert result["table_name"] == "customers"
    assert result["schema"] == "public"

    assert "columns" in result
    assert "primary_keys" in result
    assert "foreign_keys" in result
    assert "indexes" in result

    assert len(result["columns"]) == 3
    assert result["primary_keys"] == ["id"]

    assert len(result["foreign_keys"]) == 1
    assert len(result["indexes"]) == 1


# ---------------------------------------------------------
# Complete schema discovery
# ---------------------------------------------------------

def test_discover_schema(configured_discovery):
    result = configured_discovery.discover_schema(
        schema="public",
        include_views=True,
    )

    assert isinstance(result, dict)

    assert result["database_type"] == "postgresql"
    assert result["database_name"] == "test_database"
    assert result["schema"] == "public"

    assert result["tables"] == [
        "customers",
        "orders",
        "products",
    ]

    assert result["views"] == ["customer_summary"]

    assert "customers" in result["table_details"]
    assert "orders" in result["table_details"]
    assert "products" in result["table_details"]

    assert "customer_summary" in result["view_details"]

    assert result["table_count"] == 3
    assert result["view_count"] == 1

    assert isinstance(result["relationships"], list)


def test_discover_schema_without_views(configured_discovery):
    result = configured_discovery.discover_schema(
        schema="public",
        include_views=False,
    )

    assert isinstance(result, dict)
    assert result["tables"] == [
        "customers",
        "orders",
        "products",
    ]

    assert result["views"] == []
    assert result["view_details"] == {}
    assert result["view_count"] == 0


def test_discover_schema_relationships(configured_discovery):
    result = configured_discovery.discover_schema(
        schema="public",
        include_views=True,
    )

    assert len(result["relationships"]) == 3

    relationship = result["relationships"][0]

    assert relationship["source_table"] == "customers"
    assert relationship["source_columns"] == ["customer_id"]
    assert relationship["target_table"] == "customers"
    assert relationship["target_schema"] == "public"
    assert relationship["target_columns"] == ["id"]


# ---------------------------------------------------------
# Schema summary
# ---------------------------------------------------------

def test_get_schema_summary(configured_discovery):
    schema_metadata = configured_discovery.discover_schema(
        schema="public",
        include_views=True,
    )

    result = configured_discovery.get_schema_summary(
        schema_metadata
    )

    assert isinstance(result, str)
    assert "Database Type: postgresql" in result
    assert "Database Name: test_database" in result
    assert "Table: customers" in result
    assert "id: INTEGER" in result
    assert "PRIMARY KEY" in result
    assert "DATABASE VIEWS" in result
    assert "View: customer_summary" in result


# ---------------------------------------------------------
# Empty schema handling
# ---------------------------------------------------------

def test_get_tables_empty_schema(discovery):
    inspector = MagicMock()
    inspector.engine = discovery.engine
    inspector.get_table_names.return_value = []

    with patch.object(
        discovery,
        "get_inspector",
        return_value=inspector,
    ):
        result = discovery.get_tables(schema="public")

    assert result == []


def test_get_views_empty_schema(discovery):
    inspector = MagicMock()
    inspector.engine = discovery.engine
    inspector.get_view_names.return_value = []

    with patch.object(
        discovery,
        "get_inspector",
        return_value=inspector,
    ):
        result = discovery.get_views(schema="public")

    assert result == []


def test_get_foreign_keys_without_relationships(discovery):
    inspector = MagicMock()
    inspector.get_foreign_keys.return_value = []

    with patch.object(
        discovery,
        "get_inspector",
        return_value=inspector,
    ):
        result = discovery.get_foreign_keys(
            table_name="customers",
            schema="public",
        )

    assert result == []


# ---------------------------------------------------------
# Error handling
# ---------------------------------------------------------

def test_schema_discovery_error_class():
    error = SchemaDiscoveryError("Schema discovery failed")

    assert isinstance(error, Exception)
    assert str(error) == "Schema discovery failed"

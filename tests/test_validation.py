
"""
AURORA SQL Agent
SQL Validation Tests

Tests the SQL parser and validator to ensure that
only permitted read-only SQL statements are accepted.
"""

import pytest

from tools.sql_validator import (
    SQLValidator,
    SQLValidationError,
)


# ---------------------------------------------------------
# TEST FIXTURES
# ---------------------------------------------------------

@pytest.fixture
def validator():
    """Create a fresh SQL validator for each test."""

    return SQLValidator()


# ---------------------------------------------------------
# VALID SELECT QUERIES
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "query,dialect",
    [
        (
            "SELECT * FROM customers",
            "postgres",
        ),
        (
            "SELECT id, name FROM customers",
            "postgres",
        ),
        (
            "SELECT COUNT(*) FROM orders",
            "postgres",
        ),
        (
            "SELECT * FROM customers WHERE city = 'Chennai'",
            "postgres",
        ),
        (
            "SELECT customer_id, COUNT(*) FROM orders "
            "GROUP BY customer_id",
            "postgres",
        ),
        (
            "SELECT * FROM customers LIMIT 10",
            "postgres",
        ),
        (
            "SELECT * FROM customers LIMIT 10",
            "mysql",
        ),
        (
            "SELECT c.name, o.total_amount "
            "FROM customers c "
            "JOIN orders o ON c.id = o.customer_id",
            "postgres",
        ),
        (
            "WITH recent_orders AS ("
            "SELECT * FROM orders WHERE order_date >= '2025-01-01'"
            ") SELECT * FROM recent_orders",
            "postgres",
        ),
    ],
)
def test_valid_select_queries(validator, query, dialect):
    """Valid read-only SELECT queries should pass."""

    result = validator.validate(
        query,
        dialect=dialect,
    )

    assert isinstance(result, dict)

    assert result.get(
        "is_valid",
        result.get("valid", False),
    ) is True


# ---------------------------------------------------------
# INVALID SQL QUERIES
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        "INSERT INTO customers (name) VALUES ('John')",
        "UPDATE customers SET name = 'John' WHERE id = 1",
        "DELETE FROM customers WHERE id = 1",
        "DROP TABLE customers",
        "ALTER TABLE customers ADD COLUMN age INT",
        "CREATE TABLE test_table (id INT)",
        "TRUNCATE TABLE customers",
        "MERGE INTO customers USING source_table "
        "ON customers.id = source_table.id "
        "WHEN MATCHED THEN UPDATE SET name = source_table.name",
    ],
)
def test_dangerous_queries_are_rejected(validator, query):
    """Data modification and schema modification must fail."""

    result = validator.validate(
        query,
        dialect="postgres",
    )

    assert isinstance(result, dict)

    assert result.get(
        "is_valid",
        result.get("valid", False),
    ) is False


# ---------------------------------------------------------
# INVALID SQL SYNTAX
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        "",
        "SELECT",
        "SELECT FROM customers",
        "SELECT * FORM customers",
        "SELEC * FROM customers",
    ],
)
def test_malformed_sql_is_rejected(validator, query):
    """Malformed SQL must not pass validation."""

    result = validator.validate(
        query,
        dialect="postgres",
    )

    assert isinstance(result, dict)

    assert result.get(
        "is_valid",
        result.get("valid", False),
    ) is False


# ---------------------------------------------------------
# MULTIPLE STATEMENTS
# ---------------------------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM customers; DROP TABLE customers",
        "SELECT * FROM customers; DELETE FROM customers",
        "SELECT * FROM customers; SELECT * FROM orders",
    ],
)
def test_multiple_statements_are_rejected(validator, query):
    """Only one SQL statement should be permitted."""

    result = validator.validate(
        query,
        dialect="postgres",
    )

    assert isinstance(result, dict)

    assert result.get(
        "is_valid",
        result.get("valid", False),
    ) is False


# ---------------------------------------------------------
# DIALECT TESTS
# ---------------------------------------------------------

def test_mysql_select_query(validator):
    """MySQL SELECT queries should be accepted."""

    result = validator.validate(
        "SELECT * FROM customers LIMIT 10",
        dialect="mysql",
    )

    assert result.get(
        "is_valid",
        result.get("valid", False),
    ) is True


def test_postgres_select_query(validator):
    """PostgreSQL SELECT queries should be accepted."""

    result = validator.validate(
        "SELECT * FROM customers LIMIT 10",
        dialect="postgres",
    )

    assert result.get(
        "is_valid",
        result.get("valid", False),
    ) is True


# ---------------------------------------------------------
# READ-ONLY VALIDATION
# ---------------------------------------------------------

def test_select_into_is_rejected(validator):
    """SELECT INTO must not be accepted."""

    result = validator.validate(
        "SELECT * INTO new_customers FROM customers",
        dialect="postgres",
    )

    assert result.get(
        "is_valid",
        result.get("valid", False),
    ) is False


def test_for_update_is_rejected(validator):
    """Locking SELECT statements must be rejected."""

    result = validator.validate(
        "SELECT * FROM customers FOR UPDATE",
        dialect="postgres",
    )

    assert result.get(
        "is_valid",
        result.get("valid", False),
    ) is False


# ---------------------------------------------------------
# VALIDATION REPORT TESTS
# ---------------------------------------------------------

def test_validation_returns_report(validator):
    """Validator should return a structured report."""

    result = validator.validate(
        "SELECT * FROM customers",
        dialect="postgres",
    )

    assert isinstance(result, dict)

    assert (
        "is_valid" in result
        or "valid" in result
    )


def test_validation_failure_contains_error(validator):
    """Invalid SQL should provide an error message."""

    result = validator.validate(
        "DROP TABLE customers",
        dialect="postgres",
    )

    assert result.get(
        "is_valid",
        result.get("valid", False),
    ) is False

    assert (
        result.get("error")
        or result.get("errors")
        or result.get("message")
    )


# ---------------------------------------------------------
# VALIDATE OR RAISE TESTS
# ---------------------------------------------------------

def test_validate_or_raise_accepts_valid_sql(validator):
    """validate_or_raise should accept safe SQL."""

    result = validator.validate_or_raise(
        "SELECT * FROM customers",
        dialect="postgres",
    )

    assert result is not None


def test_validate_or_raise_rejects_invalid_sql(validator):
    """validate_or_raise should reject dangerous SQL."""

    with pytest.raises(SQLValidationError):
        validator.validate_or_raise(
            "DROP TABLE customers",
            dialect="postgres",
        )


# ---------------------------------------------------------
# IS SAFE TESTS
# ---------------------------------------------------------

def test_is_safe_returns_true_for_select(validator):
    """Safe SELECT statements should return True."""

    assert validator.is_safe(
        "SELECT * FROM customers",
        dialect="postgres",
    ) is True


def test_is_safe_returns_false_for_delete(validator):
    """DELETE statements should return False."""

    assert validator.is_safe(
        "DELETE FROM customers",
        dialect="postgres",
    ) is False

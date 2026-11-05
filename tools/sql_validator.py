
"""
AURORA SQL Agent
SQL Validator

Responsibilities:
- Validate SQL syntax and dialect compatibility.
- Allow only read-only SELECT queries.
- Reject DML and DDL operations.
- Detect unsafe SQL expressions and functions.
- Reject multiple SQL statements.
- Reject SELECT statements without projections.
- Return structured validation reports.
"""

from typing import Any, Optional

from sqlglot import exp
from sqlglot.errors import ParseError

from tools.sql_parser import SQLParser, SQLParserError, sql_parser


class SQLValidationError(Exception):
    """Raised when SQL validation fails."""


class SQLValidator:
    """Validates SQL queries before database execution."""

    ALLOWED_STATEMENTS = {
        "SELECT",
    }

    FORBIDDEN_EXPRESSIONS = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Create,
        exp.Drop,
        exp.Alter,
        exp.Merge,
        exp.Command,
    )

    FORBIDDEN_FUNCTIONS = {
        "SLEEP",
        "PG_SLEEP",
        "LOAD_FILE",
        "BENCHMARK",
        "PG_READ_FILE",
        "PG_READ_BINARY_FILE",
        "PG_LS_DIR",
        "DBLINK",
        "LO_IMPORT",
        "LO_EXPORT",
    }

    def __init__(
        self,
        parser: Optional[SQLParser] = None,
    ):
        self.parser = parser or sql_parser

    @staticmethod
    def _check_statement_type(
        expression: exp.Expression,
    ) -> list[str]:
        """Ensure the root statement is a SELECT query."""

        errors = []

        if not isinstance(
            expression,
            (
                exp.Select,
                exp.Union,
                exp.Intersect,
                exp.Except,
            ),
        ):
            errors.append(
                "Only SELECT queries are permitted."
            )

        return errors

    @staticmethod
    def _check_select_projections(
        expression: exp.Expression,
    ) -> list[str]:
        """
        Ensure every SELECT statement contains at least
        one selected expression.

        This rejects incomplete queries such as:
            SELECT
            SELECT FROM customers
            SELECT id FROM customers UNION SELECT
        """

        errors = []

        select_statements = list(
            expression.find_all(exp.Select)
        )

        if not select_statements:
            errors.append(
                "The SQL query must contain a valid SELECT statement."
            )
            return errors

        for select_statement in select_statements:
            if not select_statement.expressions:
                errors.append(
                    "SELECT statements must contain at least "
                    "one selected column or expression."
                )

        return list(dict.fromkeys(errors))

    def _check_forbidden_expressions(
        self,
        expression: exp.Expression,
    ) -> list[str]:
        """Reject DML, DDL and other restricted SQL expressions."""

        errors = []

        for node in expression.walk():

            if isinstance(node, self.FORBIDDEN_EXPRESSIONS):
                errors.append(
                    f"Restricted SQL operation detected: "
                    f"{node.key.upper()}."
                )

            # SELECT INTO can create or modify database objects.
            if isinstance(node, exp.Into):
                errors.append(
                    "SELECT INTO operations are not permitted."
                )

            # Row-locking clauses are not permitted.
            if isinstance(node, exp.Lock):
                errors.append(
                    "Row-locking clauses are not permitted."
                )

        return list(dict.fromkeys(errors))

    def _check_functions(
        self,
        expression: exp.Expression,
    ) -> list[str]:
        """Reject potentially dangerous database functions."""

        errors = []

        for function in expression.find_all(exp.Func):
            try:
                function_name = function.sql_name().upper()
            except Exception:
                function_name = function.name.upper()

            if function_name in self.FORBIDDEN_FUNCTIONS:
                errors.append(
                    f"Restricted database function detected: "
                    f"{function_name}."
                )

        return list(dict.fromkeys(errors))

    @staticmethod
    def _check_multiple_statements(
        expressions: list[exp.Expression],
    ) -> list[str]:
        """Reject SQL containing multiple statements."""

        if len(expressions) != 1:
            return [
                "Only one SQL statement is permitted per request."
            ]

        return []

    def validate(
        self,
        sql: str,
        dialect: str = "postgres",
    ) -> dict[str, Any]:
        """
        Validate a SQL query.

        Returns:
            valid
            sql
            dialect
            statement_type
            tables
            columns
            errors
            warnings
            message
        """

        errors = []
        warnings = []

        if not sql or not sql.strip():
            return self._build_report(
                sql=sql,
                dialect=dialect,
                errors=["SQL query cannot be empty."],
            )

        try:
            normalized_dialect = self.parser.normalize_dialect(
                dialect
            )

            expressions = self.parser.parse(
                sql,
                normalized_dialect,
            )

            errors.extend(
                self._check_multiple_statements(expressions)
            )

            if errors:
                return self._build_report(
                    sql=sql,
                    dialect=normalized_dialect,
                    errors=errors,
                )

            expression = expressions[0]

            # Check the root statement type.
            errors.extend(
                self._check_statement_type(expression)
            )

            # Check that SELECT statements have projections.
            errors.extend(
                self._check_select_projections(expression)
            )

            # Reject restricted SQL operations.
            errors.extend(
                self._check_forbidden_expressions(expression)
            )

            # Reject dangerous database functions.
            errors.extend(
                self._check_functions(expression)
            )

            if expression.find(exp.Select) is None:
                warnings.append(
                    "The query does not contain a standard SELECT clause."
                )

            statement_type = (
                self.parser.get_statement_type(expression)
            )

            tables = (
                self.parser.extract_tables_from_expression(
                    expression
                )
            )

            columns = (
                self.parser.extract_columns_from_expression(
                    expression
                )
            )

            formatted_sql = expression.sql(
                dialect=normalized_dialect
            )

            errors = list(dict.fromkeys(errors))

            return {
                "valid": len(errors) == 0,
                "sql": formatted_sql,
                "dialect": normalized_dialect,
                "statement_type": statement_type,
                "tables": tables,
                "columns": columns,
                "errors": errors,
                "warnings": warnings,
                "message": (
                    "SQL validation successful."
                    if not errors
                    else "SQL validation failed."
                ),
            }

        except (SQLParserError, ParseError, ValueError) as exc:
            return self._build_report(
                sql=sql,
                dialect=dialect,
                errors=[str(exc)],
            )

        except Exception:
            return self._build_report(
                sql=sql,
                dialect=dialect,
                errors=[
                    "An unexpected error occurred during SQL validation."
                ],
            )

    @staticmethod
    def _build_report(
        sql: Optional[str],
        dialect: str,
        errors: list[str],
    ) -> dict[str, Any]:
        """Build a consistent validation response."""

        return {
            "valid": False,
            "sql": sql or "",
            "dialect": dialect,
            "statement_type": None,
            "tables": [],
            "columns": [],
            "errors": errors,
            "warnings": [],
            "message": "SQL validation failed.",
        }

    def validate_or_raise(
        self,
        sql: str,
        dialect: str = "postgres",
    ) -> dict[str, Any]:
        """Validate SQL and raise an exception if invalid."""

        report = self.validate(sql, dialect)

        if not report["valid"]:
            raise SQLValidationError(
                " ".join(report["errors"])
            )

        return report

    def is_safe(
        self,
        sql: str,
        dialect: str = "postgres",
    ) -> bool:
        """Return whether a SQL query passes validation."""

        return self.validate(sql, dialect)["valid"]


# Shared SQL validator instance
sql_validator = SQLValidator()

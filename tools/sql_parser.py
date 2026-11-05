
"""
AURORA SQL Agent
SQL Parser

Responsibilities:
- Parse SQL using SQLGlot.
- Identify SQL statement types.
- Detect multiple statements.
- Extract referenced tables and columns.
- Convert SQL between PostgreSQL and MySQL dialects.
- Provide structured SQL parsing information.
"""

from typing import Any, Optional

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError


class SQLParserError(Exception):
    """Raised when SQL parsing or inspection fails."""


class SQLParser:
    """SQL parsing and inspection utility."""

    SUPPORTED_DIALECTS = {
        "postgres": "postgres",
        "postgresql": "postgres",
        "mysql": "mysql",
    }

    def normalize_dialect(self, dialect: Optional[str]) -> str:
        """Normalize database dialect names."""

        if not dialect:
            return "postgres"

        normalized = dialect.strip().lower()

        if normalized not in self.SUPPORTED_DIALECTS:
            raise SQLParserError(
                f"Unsupported SQL dialect: {dialect}. "
                "Supported dialects are PostgreSQL and MySQL."
            )

        return self.SUPPORTED_DIALECTS[normalized]

    def parse(
        self,
        sql: str,
        dialect: Optional[str] = "postgres",
    ) -> list[exp.Expression]:
        """Parse SQL into SQLGlot expression objects."""

        if not sql or not sql.strip():
            raise SQLParserError("SQL query cannot be empty.")

        normalized_dialect = self.normalize_dialect(dialect)

        try:
            expressions = sqlglot.parse(
                sql,
                read=normalized_dialect,
            )

            expressions = [
                expression
                for expression in expressions
                if expression is not None
            ]

            if not expressions:
                raise SQLParserError(
                    "No valid SQL statement was found."
                )

            return expressions

        except ParseError as exc:
            raise SQLParserError(
                f"Unable to parse SQL: {exc}"
            ) from exc

    def parse_single(
        self,
        sql: str,
        dialect: Optional[str] = "postgres",
    ) -> exp.Expression:
        """Parse exactly one SQL statement."""

        expressions = self.parse(sql, dialect)

        if len(expressions) != 1:
            raise SQLParserError(
                "Only one SQL statement is supported at a time."
            )

        return expressions[0]

    @staticmethod
    def get_statement_type(
        expression: exp.Expression,
    ) -> str:
        """Identify the SQL statement type."""

        statement_types = {
            exp.Select: "SELECT",
            exp.Insert: "INSERT",
            exp.Update: "UPDATE",
            exp.Delete: "DELETE",
            exp.Create: "CREATE",
            exp.Drop: "DROP",
            exp.Alter: "ALTER",
            exp.Merge: "MERGE",
            exp.Command: "COMMAND",
        }

        for expression_type, statement_name in statement_types.items():
            if isinstance(expression, expression_type):
                return statement_name

        if isinstance(
            expression,
            (exp.Union, exp.Intersect, exp.Except),
        ):
            return "SELECT"

        return expression.key.upper()

    def get_statement_info(
        self,
        sql: str,
        dialect: Optional[str] = "postgres",
    ) -> dict[str, Any]:
        """Return structured information about a SQL statement."""

        normalized_dialect = self.normalize_dialect(dialect)

        expression = self.parse_single(
            sql,
            normalized_dialect,
        )

        return {
            "statement_type": self.get_statement_type(expression),
            "dialect": normalized_dialect,
            "is_select": self.is_select(expression),
            "has_cte": expression.args.get("with_") is not None,
            "has_limit": expression.args.get("limit") is not None,
            "tables": self.extract_tables_from_expression(expression),
            "columns": self.extract_columns_from_expression(expression),
            "sql": expression.sql(dialect=normalized_dialect),
        }

    @staticmethod
    def is_select(expression: exp.Expression) -> bool:
        """Check whether an expression represents a SELECT query."""

        return isinstance(
            expression,
            (
                exp.Select,
                exp.Union,
                exp.Intersect,
                exp.Except,
            ),
        )

    def extract_tables_from_expression(
        self,
        expression: exp.Expression,
    ) -> list[str]:
        """Extract unique table references from an expression."""

        tables = []

        for table in expression.find_all(exp.Table):
            table_name = table.sql()

            if table_name not in tables:
                tables.append(table_name)

        return tables

    def extract_columns_from_expression(
        self,
        expression: exp.Expression,
    ) -> list[str]:
        """Extract unique column references from an expression."""

        columns = []

        for column in expression.find_all(exp.Column):
            column_name = column.sql()

            if column_name not in columns:
                columns.append(column_name)

        return columns

    def extract_tables(
        self,
        sql: str,
        dialect: Optional[str] = "postgres",
    ) -> list[str]:
        """Extract referenced tables directly from SQL."""

        expression = self.parse_single(sql, dialect)

        return self.extract_tables_from_expression(expression)

    def extract_columns(
        self,
        sql: str,
        dialect: Optional[str] = "postgres",
    ) -> list[str]:
        """Extract referenced columns directly from SQL."""

        expression = self.parse_single(sql, dialect)

        return self.extract_columns_from_expression(expression)

    def convert_dialect(
        self,
        sql: str,
        source_dialect: str,
        target_dialect: str,
    ) -> str:
        """Convert SQL from one supported dialect to another."""

        source = self.normalize_dialect(source_dialect)
        target = self.normalize_dialect(target_dialect)

        expressions = self.parse(sql, source)

        if len(expressions) != 1:
            raise SQLParserError(
                "Dialect conversion supports one SQL statement at a time."
            )

        try:
            return expressions[0].sql(dialect=target)

        except Exception as exc:
            raise SQLParserError(
                f"SQL dialect conversion failed: {exc}"
            ) from exc

    def format_sql(
        self,
        sql: str,
        dialect: Optional[str] = "postgres",
        pretty: bool = True,
    ) -> str:
        """Format SQL for readable display."""

        normalized_dialect = self.normalize_dialect(dialect)

        expressions = self.parse(sql, normalized_dialect)

        if len(expressions) != 1:
            raise SQLParserError(
                "SQL formatting supports one statement at a time."
            )

        return expressions[0].sql(
            dialect=normalized_dialect,
            pretty=pretty,
        )

    def get_query_summary(
        self,
        sql: str,
        dialect: Optional[str] = "postgres",
    ) -> dict[str, Any]:
        """Generate a compact summary of a SQL query."""

        info = self.get_statement_info(sql, dialect)

        return {
            "statement_type": info["statement_type"],
            "is_select": info["is_select"],
            "tables_used": info["tables"],
            "columns_used": info["columns"],
            "uses_cte": info["has_cte"],
            "uses_limit": info["has_limit"],
        }


# Shared SQL parser instance
sql_parser = SQLParser()

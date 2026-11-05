
"""
AURORA SQL Agent
Database Query Executor

Responsibilities:
- Execute validated read-only SQL queries.
- Enforce SELECT-only execution.
- Apply row limits and query timeouts.
- Return structured query results.
- Capture execution time and row counts.
- Handle database errors safely.
"""

import re
import time

from typing import Any, Optional

import pandas as pd

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import Engine

from config import settings
from database.connection import (
    database_manager,
    DatabaseConnectionError,
)


class QueryExecutionError(Exception):
    """Raised when query execution fails."""


class QueryExecutor:
    """Executes safe, read-only SQL queries."""

    def __init__(
        self,
        engine: Optional[Engine] = None,
        max_rows: Optional[int] = None,
        query_timeout: Optional[int] = None,
    ):
        self.engine = engine

        self.max_rows = max_rows or settings.max_rows
        self.query_timeout = query_timeout or settings.query_timeout

    def get_engine(self) -> Engine:
        """Return the configured or active database engine."""

        if self.engine is not None:
            return self.engine

        return database_manager.get_engine()

    @staticmethod
    def _remove_comments(sql: str) -> str:
        """Remove SQL comments while preserving quoted strings."""

        result = []
        i = 0
        quote = None
        length = len(sql)

        while i < length:
            char = sql[i]

            if quote:
                result.append(char)

                if char == quote:
                    if i + 1 < length and sql[i + 1] == quote:
                        result.append(sql[i + 1])
                        i += 2
                        continue

                    quote = None

                elif char == "\\" and i + 1 < length:
                    result.append(sql[i + 1])
                    i += 2
                    continue

                i += 1
                continue

            if char in ("'", '"', "`"):
                quote = char
                result.append(char)
                i += 1
                continue

            if sql.startswith("--", i):
                while i < length and sql[i] != "\n":
                    i += 1
                continue

            if sql.startswith("/*", i):
                end = sql.find("*/", i + 2)

                if end == -1:
                    raise QueryExecutionError(
                        "Unterminated SQL comment."
                    )

                i = end + 2
                continue

            if char == "#":
                while i < length and sql[i] != "\n":
                    i += 1
                continue

            result.append(char)
            i += 1

        if quote:
            raise QueryExecutionError(
                "Unterminated SQL string or identifier."
            )

        return "".join(result)

    @staticmethod
    def _validate_single_statement(sql: str) -> None:
        """Prevent execution of multiple SQL statements."""

        statements = [
            statement.strip()
            for statement in sql.split(";")
            if statement.strip()
        ]

        if len(statements) != 1:
            raise QueryExecutionError(
                "Only one SQL statement can be executed at a time."
            )

    @staticmethod
    def _validate_read_only(sql: str) -> None:
        """
        Perform preliminary read-only checks.

        The SQL Validation Agent and database permissions provide
        additional security enforcement.
        """

        cleaned_sql = QueryExecutor._remove_comments(sql).strip()

        QueryExecutor._validate_single_statement(cleaned_sql)

        if not re.match(
            r"^(SELECT|WITH)\b",
            cleaned_sql,
            flags=re.IGNORECASE,
        ):
            raise QueryExecutionError(
                "Only SELECT queries and read-only CTE queries "
                "are permitted."
            )

        forbidden_patterns = [
            r"\bINSERT\b",
            r"\bUPDATE\b",
            r"\bDELETE\b",
            r"\bDROP\b",
            r"\bALTER\b",
            r"\bCREATE\b",
            r"\bTRUNCATE\b",
            r"\bREPLACE\b",
            r"\bMERGE\b",
            r"\bGRANT\b",
            r"\bREVOKE\b",
            r"\bCALL\b",
            r"\bEXEC(?:UTE)?\b",
            r"\bCOPY\b",
            r"\bVACUUM\b",
            r"\bANALYZE\b",
            r"\bLOCK\b",
            r"\bINTO\s+(?:OUTFILE|DUMPFILE)\b",
            r"\bFOR\s+(?:UPDATE|SHARE)\b",
            r"\bLOAD_FILE\s*\(",
        ]

        for pattern in forbidden_patterns:
            if re.search(
                pattern,
                cleaned_sql,
                flags=re.IGNORECASE,
            ):
                raise QueryExecutionError(
                    "The query contains a restricted SQL operation."
                )

    def _apply_row_limit(
        self,
        sql: str,
        dialect: str,
    ) -> str:
        """
        Apply a database-specific row limit when one is absent.

        Existing LIMIT or FETCH clauses are preserved.
        """

        sql = sql.strip().rstrip(";")

        if dialect == "postgresql":
            has_limit = re.search(
                r"\bLIMIT\b|\bFETCH\s+(?:FIRST|NEXT)\b",
                sql,
                flags=re.IGNORECASE,
            )

        elif dialect == "mysql":
            has_limit = re.search(
                r"\bLIMIT\b",
                sql,
                flags=re.IGNORECASE,
            )

        else:
            has_limit = re.search(
                r"\bLIMIT\b|\bFETCH\s+(?:FIRST|NEXT)\b",
                sql,
                flags=re.IGNORECASE,
            )

        if has_limit:
            return sql

        if dialect == "mysql":
            return f"{sql} LIMIT {self.max_rows}"

        return f"{sql} LIMIT {self.max_rows}"

    def _set_query_timeout(self, connection) -> None:
        """Apply database-specific statement timeouts."""

        dialect = connection.dialect.name

        if dialect == "postgresql":
            connection.execute(
                text(
                    "SELECT set_config("
                    "'statement_timeout', :timeout, true)"
                ),
                {
                    "timeout": f"{self.query_timeout * 1000}ms"
                },
            )

        elif dialect == "mysql":
            try:
                connection.execute(
                    text(
                        "SET SESSION MAX_EXECUTION_TIME = :timeout"
                    ),
                    {
                        "timeout": self.query_timeout * 1000
                    },
                )

            except SQLAlchemyError:
                raise QueryExecutionError(
                    "Unable to configure the MySQL query timeout."
                )

    def execute_query(
        self,
        sql: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Execute a read-only SQL query.

        Returns:
            success
            columns
            records
            dataframe
            row_count
            execution_time
            executed_sql
            error
        """

        if not sql or not sql.strip():
            raise QueryExecutionError(
                "SQL query cannot be empty."
            )

        if not settings.read_only_mode:
            raise QueryExecutionError(
                "Read-only execution must remain enabled "
                "in this application version."
            )

        self._validate_read_only(sql)

        engine = self.get_engine()

        params = params or {}

        started_at = time.perf_counter()

        try:
            with engine.connect() as connection:

                # Use a read-only transaction where supported.
                if engine.dialect.name == "postgresql":
                    connection.execute(
                        text("SET TRANSACTION READ ONLY")
                    )

                elif engine.dialect.name == "mysql":
                    connection.execute(
                        text("SET TRANSACTION READ ONLY")
                    )

                self._set_query_timeout(connection)

                executed_sql = self._apply_row_limit(
                    sql,
                    engine.dialect.name,
                )

                result = connection.execute(
                    text(executed_sql),
                    params,
                )

                columns = list(result.keys())

                records = [
                    dict(row._mapping)
                    for row in result.fetchmany(self.max_rows)
                ]

                execution_time = round(
                    time.perf_counter() - started_at,
                    4,
                )

                dataframe = pd.DataFrame(
                    records,
                    columns=columns,
                )

                return {
                    "success": True,
                    "columns": columns,
                    "records": records,
                    "dataframe": dataframe,
                    "row_count": len(records),
                    "execution_time": execution_time,
                    "executed_sql": executed_sql,
                    "database_type": engine.dialect.name,
                    "error": None,
                }

        except QueryExecutionError:
            raise

        except SQLAlchemyError as exc:
            raise QueryExecutionError(
                "Query execution failed. Please check the SQL syntax, "
                "table names, column names and database permissions."
            ) from exc

        except Exception as exc:
            raise QueryExecutionError(
                "An unexpected error occurred during query execution."
            ) from exc

    def execute_dataframe(
        self,
        sql: str,
        params: Optional[dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """Execute a query and return only its DataFrame."""

        result = self.execute_query(sql, params)

        return result["dataframe"]


# Shared query executor instance
query_executor = QueryExecutor()

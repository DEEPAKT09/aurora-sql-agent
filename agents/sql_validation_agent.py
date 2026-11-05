
"""
AURORA SQL Agent
SQL Validation Agent

Responsibilities:
- Validate generated SQL syntax.
- Verify database dialect compatibility.
- Enforce read-only SQL execution.
- Detect multiple SQL statements.
- Detect unsafe SQL operations.
- Return validation results to LangGraph.
- Support controlled SQL correction attempts.
"""

from typing import Any

import sqlglot
from sqlglot.errors import ParseError

from config import settings
from graph.state import SQLAgentState
from tools.sql_parser import sql_parser, SQLParserError
from tools.sql_validator import sql_validator, SQLValidationError


class SQLValidationAgentError(Exception):
    """Raised when SQL validation fails unexpectedly."""


class SQLValidationAgent:
    """Validates generated SQL before execution."""

    def __init__(self):
        self.validator = sql_validator
        self.parser = sql_parser

    # --------------------------------------------------
    # Dialect handling
    # --------------------------------------------------

    @staticmethod
    def _normalize_dialect(dialect: str) -> str:
        """Normalize database dialect names."""

        dialect = (dialect or "postgres").lower()

        mapping = {
            "postgres": "postgres",
            "postgresql": "postgres",
            "postgresql+psycopg": "postgres",
            "mysql": "mysql",
            "mysql+pymysql": "mysql",
        }

        if dialect not in mapping:
            raise SQLValidationAgentError(
                f"Unsupported SQL dialect: {dialect}"
            )

        return mapping[dialect]

    # --------------------------------------------------
    # SQL parsing
    # --------------------------------------------------

    def _parse_sql(
        self,
        sql: str,
        dialect: str,
    ) -> dict[str, Any]:
        """Parse SQL and check that it contains one statement."""

        try:
            expressions = sqlglot.parse(
                sql,
                read=dialect,
            )

            expressions = [
                expression
                for expression in expressions
                if expression is not None
            ]

            if not expressions:
                return {
                    "success": False,
                    "error": "The SQL query is empty or invalid.",
                    "statement_count": 0,
                    "statement_type": None,
                }

            if len(expressions) > 1:
                return {
                    "success": False,
                    "error": (
                        "Multiple SQL statements are not permitted. "
                        "Only one statement can be executed at a time."
                    ),
                    "statement_count": len(expressions),
                    "statement_type": None,
                }

            expression = expressions[0]

            statement_type = type(expression).__name__.upper()

            return {
                "success": True,
                "error": None,
                "statement_count": 1,
                "statement_type": statement_type,
                "expression": expression,
            }

        except ParseError as exc:
            return {
                "success": False,
                "error": f"SQL syntax error: {exc}",
                "statement_count": 0,
                "statement_type": None,
            }

        except Exception as exc:
            return {
                "success": False,
                "error": f"SQL parsing failed: {exc}",
                "statement_count": 0,
                "statement_type": None,
            }

    # --------------------------------------------------
    # Read-only checks
    # --------------------------------------------------

    @staticmethod
    def _check_select_only(expression: Any) -> dict[str, Any]:
        """
        Ensure that the parsed SQL contains only a SELECT query.

        Checking the complete expression tree prevents unsafe
        operations from being hidden inside nested queries or CTEs.
        """

        forbidden_types = {
            "INSERT",
            "UPDATE",
            "DELETE",
            "CREATE",
            "DROP",
            "ALTER",
            "TRUNCATE",
            "MERGE",
            "COMMAND",
            "COPY",
            "GRANT",
            "REVOKE",
        }

        for node in expression.walk():
            node_type = type(node).__name__.upper()

            if node_type in forbidden_types:
                return {
                    "success": False,
                    "error": (
                        f"Unsafe SQL operation detected: {node_type}. "
                        "Only read-only SELECT queries are permitted."
                    ),
                }

        if not expression.find(sqlglot.exp.Select):
            return {
                "success": False,
                "error": (
                    "Only SELECT queries are permitted "
                    "in read-only mode."
                ),
            }

        if expression.find(sqlglot.exp.Into):
            return {
                "success": False,
                "error": (
                    "SELECT INTO operations are not permitted."
                ),
            }

        if expression.find(sqlglot.exp.Lock):
            return {
                "success": False,
                "error": (
                    "Locking operations are not permitted."
                ),
            }

        return {
            "success": True,
            "error": None,
        }

    # --------------------------------------------------
    # Main validation
    # --------------------------------------------------

    def validate_sql(
        self,
        sql: str,
        dialect: str,
    ) -> dict[str, Any]:
        """Run complete SQL validation."""

        if not sql or not sql.strip():
            return {
                "is_valid": False,
                "syntax_valid": False,
                "read_only": False,
                "statement_count": 0,
                "dialect": dialect,
                "errors": ["SQL query cannot be empty."],
                "warnings": [],
            }

        normalized_dialect = self._normalize_dialect(dialect)

        errors = []
        warnings = []

        # 1. Parse SQL and check statement count.
        parse_result = self._parse_sql(
            sql,
            normalized_dialect,
        )

        if not parse_result["success"]:
            errors.append(parse_result["error"])

            return {
                "is_valid": False,
                "syntax_valid": False,
                "read_only": False,
                "statement_count": parse_result["statement_count"],
                "statement_type": parse_result.get("statement_type"),
                "dialect": normalized_dialect,
                "errors": errors,
                "warnings": warnings,
            }

        expression = parse_result["expression"]

        # 2. Check that the query is read-only.
        read_only_result = self._check_select_only(
            expression
        )

        if not read_only_result["success"]:
            errors.append(read_only_result["error"])

        # 3. Run the project's centralized SQL validator.
        try:
            validator_result = self.validator.validate(
                sql,
                dialect=normalized_dialect,
            )

            if isinstance(validator_result, dict):

                validator_errors = validator_result.get(
                    "errors",
                    [],
                )

                if isinstance(validator_errors, str):
                    validator_errors = [validator_errors]

                for error in validator_errors:
                    if error and str(error) not in errors:
                        errors.append(str(error))

                validator_warnings = validator_result.get(
                    "warnings",
                    [],
                )

                if isinstance(validator_warnings, str):
                    validator_warnings = [validator_warnings]

                for warning in validator_warnings:
                    if warning:
                        warnings.append(str(warning))

                if validator_result.get("is_valid") is False:
                    if not validator_errors:
                        errors.append(
                            "The centralized SQL validator rejected the query."
                        )

                if validator_result.get("valid") is False:
                    if not validator_errors:
                        errors.append(
                            "The centralized SQL validator rejected the query."
                        )

            elif validator_result is False:
                errors.append(
                    "The centralized SQL validator rejected the query."
                )

        except SQLValidationError as exc:
            errors.append(str(exc))

        except Exception as exc:
            errors.append(
                f"Centralized SQL validation failed: {exc}"
            )

        is_valid = len(errors) == 0

        return {
            "is_valid": is_valid,
            "syntax_valid": True,
            "read_only": read_only_result["success"],
            "statement_count": parse_result["statement_count"],
            "statement_type": parse_result["statement_type"],
            "dialect": normalized_dialect,
            "errors": errors,
            "warnings": warnings,
        }

    # --------------------------------------------------
    # Main agent execution
    # --------------------------------------------------

    def run(
        self,
        state: SQLAgentState,
    ) -> dict[str, Any]:
        """Validate generated SQL and update workflow state."""

        sql = state.get("generated_sql", "").strip()

        if not sql:
            return {
                "sql_valid": False,
                "validation_result": {
                    "is_valid": False,
                    "errors": ["No generated SQL query was provided."],
                    "warnings": [],
                },
                "validation_error": "No generated SQL query was provided.",
                "workflow_status": "failed",
                "current_agent": "sql_validation_agent",
            }

        try:
            dialect = (
                state.get("sql_dialect")
                or state.get("database_type")
                or settings.sql_dialect_default
            )

            result = self.validate_sql(
                sql,
                dialect,
            )

            if result["is_valid"]:
                return {
                    "sql_valid": True,
                    "validation_result": result,
                    "validation_error": None,
                    "validated_sql": sql,
                    "current_agent": "sql_validation_agent",
                    "workflow_status": "running",
                    "error": None,
                    "error_type": None,
                }

            error_message = "; ".join(
                result.get("errors", [])
            )

            return {
                "sql_valid": False,
                "validation_result": result,
                "validation_error": error_message,
                "validated_sql": None,
                "current_agent": "sql_validation_agent",
                "workflow_status": "running",
                "error": None,
                "error_type": None,
            }

        except SQLValidationAgentError as exc:
            return {
                "sql_valid": False,
                "validation_result": {
                    "is_valid": False,
                    "errors": [str(exc)],
                    "warnings": [],
                },
                "validation_error": str(exc),
                "current_agent": "sql_validation_agent",
                "workflow_status": "failed",
                "error": str(exc),
                "error_type": "SQLValidationAgentError",
            }

        except Exception:
            error_message = (
                "An unexpected error occurred during SQL validation."
            )

            return {
                "sql_valid": False,
                "validation_result": {
                    "is_valid": False,
                    "errors": [error_message],
                    "warnings": [],
                },
                "validation_error": error_message,
                "current_agent": "sql_validation_agent",
                "workflow_status": "failed",
                "error": error_message,
                "error_type": "SQLValidationAgentError",
            }


# --------------------------------------------------
# Shared agent instance
# --------------------------------------------------

sql_validation_agent = SQLValidationAgent()


def run(state: SQLAgentState) -> dict[str, Any]:
    """Entry point used by the LangGraph workflow."""

    return sql_validation_agent.run(state)

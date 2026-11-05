
"""
AURORA SQL Agent
Execution Agent

Responsibilities:
- Execute validated SQL queries.
- Enforce read-only execution.
- Apply query execution limits.
- Retrieve database records.
- Capture execution time and errors.
- Return structured results to LangGraph.
"""

from typing import Any

from config import settings
from database.query_executor import (
    query_executor,
    QueryExecutionError,
)
from graph.state import SQLAgentState


class ExecutionAgentError(Exception):
    """Raised when SQL execution fails."""


class ExecutionAgent:
    """Executes validated SQL against the connected database."""

    def __init__(self):
        self.executor = query_executor

    # --------------------------------------------------
    # Result normalization
    # --------------------------------------------------

    @staticmethod
    def _normalize_result(
        result: Any,
        sql: str,
        dialect: str,
    ) -> dict[str, Any]:
        """Normalize QueryExecutor output into a consistent structure."""

        if not isinstance(result, dict):
            raise ExecutionAgentError(
                "The query executor returned an unexpected result."
            )

        success = bool(result.get("success", False))

        if not success:
            return {
                "success": False,
                "columns": [],
                "records": [],
                "row_count": 0,
                "execution_time": result.get("execution_time", 0),
                "executed_sql": result.get("executed_sql", sql),
                "database_type": result.get(
                    "database_type",
                    dialect,
                ),
                "error": result.get(
                    "error",
                    "SQL execution failed.",
                ),
            }

        dataframe = result.get("dataframe")

        columns = result.get("columns", [])
        records = result.get("records", [])

        # Convert a returned DataFrame into records if necessary.
        if dataframe is not None:
            if not columns:
                columns = list(dataframe.columns)

            if not records:
                records = dataframe.to_dict(
                    orient="records"
                )

        # Ensure records are serializable and consistent.
        normalized_records = []

        for record in records:
            if isinstance(record, dict):
                normalized_records.append(record)

            elif hasattr(record, "_mapping"):
                normalized_records.append(
                    dict(record._mapping)
                )

            else:
                normalized_records.append(
                    dict(record)
                )

        return {
            "success": True,
            "columns": list(columns),
            "records": normalized_records,
            "row_count": result.get(
                "row_count",
                len(normalized_records),
            ),
            "execution_time": result.get(
                "execution_time",
                0,
            ),
            "executed_sql": result.get(
                "executed_sql",
                sql,
            ),
            "database_type": result.get(
                "database_type",
                dialect,
            ),
            "error": None,
        }

    # --------------------------------------------------
    # SQL execution
    # --------------------------------------------------

    def execute(
        self,
        sql: str,
        dialect: str,
    ) -> dict[str, Any]:
        """Execute a validated SQL query."""

        if not sql or not sql.strip():
            raise ExecutionAgentError(
                "Cannot execute an empty SQL query."
            )

        try:
            result = self.executor.execute_query(
                sql,
                dialect=dialect,
            )

        except TypeError:
            # Compatibility fallback for QueryExecutor versions
            # that accept only the SQL argument.
            result = self.executor.execute_query(sql)

        except QueryExecutionError as exc:
            raise ExecutionAgentError(
                f"Database query execution failed: {exc}"
            ) from exc

        except Exception as exc:
            raise ExecutionAgentError(
                f"Unexpected database execution error: {exc}"
            ) from exc

        return self._normalize_result(
            result,
            sql,
            dialect,
        )

    # --------------------------------------------------
    # Main agent execution
    # --------------------------------------------------

    def run(
        self,
        state: SQLAgentState,
    ) -> dict[str, Any]:
        """Execute validated SQL and update workflow state."""

        if not state.get("database_connected", False):
            return {
                "execution_success": False,
                "execution_result": None,
                "execution_error": "Database is not connected.",
                "workflow_status": "failed",
                "current_agent": "execution_agent",
                "error": "Database is not connected.",
                "error_type": "DatabaseConnectionError",
            }

        if not state.get("sql_valid", False):
            return {
                "execution_success": False,
                "execution_result": None,
                "execution_error": (
                    "SQL execution was blocked because "
                    "the validation agent did not approve the query."
                ),
                "workflow_status": "failed",
                "current_agent": "execution_agent",
                "error": (
                    "SQL execution was blocked because "
                    "the query has not passed validation."
                ),
                "error_type": "SQLValidationError",
            }

        sql = (
            state.get("validated_sql")
            or state.get("generated_sql")
            or ""
        ).strip()

        if not sql:
            return {
                "execution_success": False,
                "execution_result": None,
                "execution_error": "No validated SQL query was provided.",
                "workflow_status": "failed",
                "current_agent": "execution_agent",
                "error": "No validated SQL query was provided.",
                "error_type": "ExecutionAgentError",
            }

        try:
            dialect = (
                state.get("sql_dialect")
                or state.get("database_type")
                or settings.sql_dialect_default
            )

            result = self.execute(
                sql,
                dialect,
            )

            if not result["success"]:
                error_message = result.get(
                    "error",
                    "SQL execution failed.",
                )

                return {
                    "execution_success": False,
                    "execution_result": result,
                    "execution_error": error_message,
                    "execution_time": result.get(
                        "execution_time",
                        0,
                    ),
                    "current_agent": "execution_agent",
                    "workflow_status": "running",
                    "error": None,
                    "error_type": None,
                }

            return {
                "execution_success": True,
                "execution_result": result,
                "execution_error": None,
                "execution_time": result.get(
                    "execution_time",
                    0,
                ),
                "current_agent": "execution_agent",
                "workflow_status": "running",
                "error": None,
                "error_type": None,
            }

        except ExecutionAgentError as exc:
            error_message = str(exc)
            return {
                "execution_success": False,
                "execution_result": {
                    "success": False,
                    "columns": [],
                    "records": [],
                    "row_count": 0,
                    "execution_time": 0,
                    "executed_sql": sql,
                    "database_type": dialect,
                    "error": error_message,
                },
                "execution_error": error_message,
                "current_agent": "execution_agent",
                "workflow_status": "running",
                "error": None,
                "error_type": None,
            }

        except Exception as exc:
            error_message = (
                "An unexpected error occurred during SQL execution: "
                f"{exc}"
            )

            return {
                "execution_success": False,
                "execution_result": {
                    "success": False,
                    "columns": [],
                    "records": [],
                    "row_count": 0,
                    "execution_time": 0,
                    "executed_sql": sql,
                    "database_type": dialect,
                    "error": error_message,
                },
                "execution_error": error_message,
                "current_agent": "execution_agent",
                "workflow_status": "running",
                "error": None,
                "error_type": None,
            }


# --------------------------------------------------
# Shared execution agent instance
# --------------------------------------------------

execution_agent = ExecutionAgent()


def run(state: SQLAgentState) -> dict[str, Any]:
    """Entry point used by the LangGraph workflow."""

    return execution_agent.run(state)

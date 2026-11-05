
"""
AURORA SQL Agent
SQL Editor

Provides an interactive SQL workspace for reviewing,
editing, validating and executing SQL queries.
"""

import streamlit as st

from tools.sql_validator import sql_validator
from database.query_executor import (
    QueryExecutionError,
    query_executor,
)


def _initialize_sql_state():
    """Initialize SQL editor session state."""

    defaults = {
        "generated_sql": "",
        "edited_sql": "",
        "sql_dialect": "postgres",
        "sql_validation_result": None,
        "sql_execution_result": None,
        "sql_editor_message": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _get_dialect():
    """Return the active database SQL dialect."""

    database_type = st.session_state.get("database_type")

    if database_type == "mysql":
        return "mysql"

    return "postgres"


def _validate_sql(sql, dialect):
    """Validate SQL using the centralized SQL validator."""

    try:
        result = sql_validator.validate(
            sql,
            dialect=dialect,
        )

        if isinstance(result, dict):
            return result

        return {
            "is_valid": bool(result),
            "message": (
                "SQL validation successful."
                if result
                else "SQL validation failed."
            ),
        }

    except Exception as exc:
        return {
            "is_valid": False,
            "message": str(exc),
            "errors": [str(exc)],
        }


def _is_validation_successful(result):
    """Normalize validation response status."""

    if not isinstance(result, dict):
        return False

    return bool(
        result.get(
            "is_valid",
            result.get(
                "valid",
                result.get("success", False),
            ),
        )
    )


def _render_validation_result(result):
    """Display SQL validation feedback."""

    if not isinstance(result, dict):
        st.error("Invalid validation response.")
        return

    if _is_validation_successful(result):
        st.success(
            result.get(
                "message",
                "SQL validation successful.",
            )
        )
    else:
        st.error(
            result.get(
                "message",
                "SQL validation failed.",
            )
        )

    errors = result.get("errors", [])

    if errors:
        with st.expander("Validation Details"):
            for error in errors:
                st.write(f"- {error}")

    warnings = result.get("warnings", [])

    if warnings:
        with st.expander("Validation Warnings"):
            for warning in warnings:
                st.write(f"- {warning}")


def _execute_sql(sql, dialect):
    """Execute validated read-only SQL."""

    if not st.session_state.get("database_connected", False):
        st.error("Please connect to a database first.")
        return

    validation_result = _validate_sql(sql, dialect)

    st.session_state.sql_validation_result = validation_result

    if not _is_validation_successful(validation_result):
        st.error("Query execution blocked because validation failed.")
        _render_validation_result(validation_result)
        return

    try:
        # The QueryExecutor detects the dialect from its connected engine.
        result = query_executor.execute_query(sql)

        st.session_state.sql_execution_result = result

        if isinstance(result, dict):
            if result.get("success", False):
                st.success("Query executed successfully.")
            else:
                st.error(
                    result.get(
                        "error",
                        "Query execution failed.",
                    )
                )
        else:
            st.success("Query execution completed.")

    except QueryExecutionError as exc:
        st.session_state.sql_execution_result = {
            "success": False,
            "error": str(exc),
        }
        st.error(f"Query execution failed: {exc}")

    except Exception as exc:
        st.session_state.sql_execution_result = {
            "success": False,
            "error": str(exc),
        }
        st.error(f"Unexpected execution error: {exc}")


def _render_execution_result():
    """Display the most recent SQL execution result."""

    result = st.session_state.get("sql_execution_result")

    if not result:
        return

    st.divider()
    st.markdown("### Execution Result")

    if not isinstance(result, dict):
        st.write(result)
        return

    if not result.get("success", False):
        st.error(
            result.get(
                "error",
                "Query execution failed.",
            )
        )
        return

    columns = result.get("columns", [])
    records = result.get("records", [])

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Rows Returned",
            result.get("row_count", len(records)),
        )

    with col2:
        st.metric(
            "Execution Time",
            f"{result.get('execution_time', 0):.3f} sec",
        )

    if records:
        st.dataframe(
            records,
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("The query returned no records.")

    if columns:
        st.caption(
            "Columns: " + ", ".join(map(str, columns))
        )


def render_sql_editor():
    """
    Render the SQL editor and execution workspace.

    Returns:
        str: The current SQL query.
    """

    _initialize_sql_state()

    st.title("SQL Workspace")

    st.caption(
        "Review generated SQL, make changes, validate "
        "and execute read-only database queries."
    )

    if not st.session_state.get("database_connected", False):
        st.warning(
            "Connect to a database before executing SQL queries."
        )

    dialect = _get_dialect()

    st.session_state.sql_dialect = dialect

    # SQL editor header.
    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown("### SQL Editor")

    with col2:
        st.caption(
            f"Dialect: {dialect.upper()}"
        )

    generated_sql = st.session_state.get("generated_sql", "")

    if (
        generated_sql
        and not st.session_state.get("edited_sql")
    ):
        st.session_state.edited_sql = generated_sql

    if not st.session_state.get("edited_sql"):
        st.info(
            "Your generated SQL will appear here. "
            "You can also enter a SQL query manually."
        )

    # SQL editor.
    edited_sql = st.text_area(
        "SQL Query",
        value=st.session_state.edited_sql,
        height=300,
        placeholder=(
            "SELECT * FROM your_table LIMIT 100;"
        ),
        key="sql_editor_input",
    )

    st.session_state.edited_sql = edited_sql

    st.divider()

    # Editor actions.
    validate_col, execute_col, reset_col = st.columns(3)

    with validate_col:
        validate_clicked = st.button(
            "Validate SQL",
            width="stretch",
        )

    with execute_col:
        execute_clicked = st.button(
            "Run Query",
            type="primary",
            width="stretch",
            disabled=not st.session_state.database_connected,
        )

    with reset_col:
        reset_clicked = st.button(
            "Reset SQL",
            width="stretch",
        )

    if reset_clicked:
        st.session_state.edited_sql = generated_sql
        st.session_state.sql_validation_result = None
        st.session_state.sql_execution_result = None
        st.session_state.pop("sql_editor_input", None)
        st.rerun()

    if validate_clicked:

        if not edited_sql.strip():
            st.warning("Please enter a SQL query.")

        else:
            validation_result = _validate_sql(
                edited_sql,
                dialect,
            )

            st.session_state.sql_validation_result = (
                validation_result
            )

    if execute_clicked:

        if not edited_sql.strip():
            st.warning("Please enter a SQL query.")

        else:
            _execute_sql(
                edited_sql,
                dialect,
            )

    # Validation feedback.
    validation_result = st.session_state.get(
        "sql_validation_result"
    )

    if validation_result:
        st.divider()
        st.markdown("### SQL Validation")
        _render_validation_result(validation_result)

    # Execution feedback and results.
    _render_execution_result()

    return edited_sql

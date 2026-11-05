
"""
Tests for the AURORA SQL Agent execution agent.

The database executor is mocked, so these tests do not
require an active PostgreSQL or MySQL connection.
"""

import pytest
from unittest.mock import MagicMock, patch

from agents.execution_agent import ExecutionAgent


@pytest.fixture
def agent():
    return ExecutionAgent()


@pytest.fixture
def valid_state():
    return {
        "user_question": "Show all customers",
        "database_connected": True,
        "database_type": "postgresql",
        "sql_valid": True,
        "generated_sql": "SELECT * FROM customers",
        "sql_dialect": "postgres",
    }


@pytest.fixture
def mock_query_result():
    return {
        "success": True,
        "columns": ["id", "name"],
        "records": [
            {"id": 1, "name": "John"},
            {"id": 2, "name": "Jane"},
        ],
        "row_count": 2,
        "execution_time": 0.05,
        "executed_sql": "SELECT * FROM customers",
        "database_type": "postgresql",
        "error": None,
    }


def test_agent_initialization(agent):
    assert agent is not None


@patch("agents.execution_agent.query_executor.execute_query")
def test_execute_query_success(
    mock_execute,
    agent,
    valid_state,
    mock_query_result,
):
    mock_execute.return_value = mock_query_result

    result = agent.run(valid_state)

    mock_execute.assert_called_once()

    assert result["execution_success"] is True
    assert result["execution_result"]["success"] is True
    assert result["execution_result"]["row_count"] == 2
    assert len(result["execution_result"]["records"]) == 2


@patch("agents.execution_agent.query_executor.execute_query")
def test_execute_query_passes_generated_sql(
    mock_execute,
    agent,
    valid_state,
    mock_query_result,
):
    mock_execute.return_value = mock_query_result

    agent.run(valid_state)

    args, kwargs = mock_execute.call_args

    assert args[0] == valid_state["generated_sql"]


@patch("agents.execution_agent.query_executor.execute_query")
def test_execute_query_passes_dialect(
    mock_execute,
    agent,
    valid_state,
    mock_query_result,
):
    mock_execute.return_value = mock_query_result

    agent.run(valid_state)

    _, kwargs = mock_execute.call_args

    if "dialect" in kwargs:
        assert kwargs["dialect"] == "postgres"


@patch("agents.execution_agent.query_executor.execute_query")
def test_execution_failure(
    mock_execute,
    agent,
    valid_state,
):
    mock_execute.return_value = {
        "success": False,
        "columns": [],
        "records": [],
        "row_count": 0,
        "execution_time": 0,
        "error": "Database execution failed",
    }

    result = agent.run(valid_state)

    assert result["execution_success"] is False
    assert result["execution_result"]["success"] is False


@patch("agents.execution_agent.query_executor.execute_query")
def test_execution_exception(
    mock_execute,
    agent,
    valid_state,
):
    mock_execute.side_effect = Exception("Database connection error")

    result = agent.run(valid_state)

    assert result["execution_success"] is False
    assert result["execution_result"]["success"] is False
    assert "error" in result["execution_result"]


@patch("agents.execution_agent.query_executor.execute_query")
def test_execution_skipped_without_database_connection(
    mock_execute,
    agent,
    valid_state,
):
    valid_state["database_connected"] = False

    result = agent.run(valid_state)

    mock_execute.assert_not_called()
    assert result["execution_success"] is False


@patch("agents.execution_agent.query_executor.execute_query")
def test_execution_skipped_when_sql_is_invalid(
    mock_execute,
    agent,
    valid_state,
):
    valid_state["sql_valid"] = False

    result = agent.run(valid_state)

    mock_execute.assert_not_called()
    assert result["execution_success"] is False


@patch("agents.execution_agent.query_executor.execute_query")
def test_execution_skipped_when_sql_is_empty(
    mock_execute,
    agent,
    valid_state,
):
    valid_state["generated_sql"] = ""

    result = agent.run(valid_state)

    mock_execute.assert_not_called()
    assert result["execution_success"] is False


@patch("agents.execution_agent.query_executor.execute_query")
def test_execution_result_contains_records(
    mock_execute,
    agent,
    valid_state,
    mock_query_result,
):
    mock_execute.return_value = mock_query_result

    result = agent.run(valid_state)

    execution_result = result["execution_result"]

    assert "columns" in execution_result
    assert "records" in execution_result
    assert "row_count" in execution_result
    assert "execution_time" in execution_result


@patch("agents.execution_agent.query_executor.execute_query")
def test_execution_result_handles_empty_records(
    mock_execute,
    agent,
    valid_state,
):
    mock_execute.return_value = {
        "success": True,
        "columns": ["id", "name"],
        "records": [],
        "row_count": 0,
        "execution_time": 0.02,
        "executed_sql": valid_state["generated_sql"],
        "database_type": "postgresql",
        "error": None,
    }

    result = agent.run(valid_state)

    assert result["execution_success"] is True
    assert result["execution_result"]["records"] == []
    assert result["execution_result"]["row_count"] == 0


def test_execution_agent_error_class():
    from agents.execution_agent import ExecutionAgentError

    error = ExecutionAgentError("Test execution error")

    assert str(error) == "Test execution error"

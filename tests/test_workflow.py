
"""
Tests for AURORA SQL Agent LangGraph workflow orchestration.

Agent functions and graph execution are mocked where appropriate.
No live database or Gemini API connection is required.
"""

import pytest
from unittest.mock import MagicMock

from graph.workflow import (
    SQLAgentWorkflow,
    WorkflowError,
)


@pytest.fixture
def workflow():
    return SQLAgentWorkflow()


@pytest.fixture
def sample_state():
    return {
        "user_question": "Show all customers",
        "database_connected": True,
        "database_type": "postgresql",
        "database_name": "test_db",
        "sql_dialect": "postgres",
        "schema_metadata": {},
        "generated_sql": "SELECT * FROM customers",
        "validated_sql": "SELECT * FROM customers",
        "sql_valid": True,
        "validation_error": None,
        "execution_success": False,
        "execution_result": {},
        "execution_error": None,
        "retry_count": 0,
        "max_retries": 2,
        "workflow_trace": [],
        "errors": [],
        "workflow_status": "running",
    }


def test_workflow_initialization(workflow):
    assert workflow.graph is None
    assert workflow.compiled_graph is None
    assert workflow.agents == {}


def test_load_agents(workflow):
    workflow._load_agents()

    expected_agents = {
        "supervisor",
        "schema_agent",
        "sql_generation_agent",
        "sql_validation_agent",
        "execution_agent",
        "result_analysis_agent",
        "visualization_agent",
    }

    assert set(workflow.agents.keys()) == expected_agents


def test_create_agent_node_success(workflow, sample_state):
    agent_function = MagicMock(
        return_value={
            "generated_sql": "SELECT * FROM customers",
            "sql_generation_success": True,
        }
    )

    workflow.agents["sql_generation_agent"] = agent_function

    node = workflow._create_agent_node("sql_generation_agent")
    result = node(sample_state)

    assert result["generated_sql"] == "SELECT * FROM customers"
    assert result["sql_generation_success"] is True
    assert result["current_agent"] == "sql_generation_agent"
    assert "sql_generation_agent" in result["workflow_trace"]


def test_create_agent_node_invalid_return(workflow, sample_state):
    agent_function = MagicMock(return_value="invalid result")

    workflow.agents["test_agent"] = agent_function

    node = workflow._create_agent_node("test_agent")
    result = node(sample_state)

    assert result["workflow_status"] == "failed"
    assert result["current_agent"] == "test_agent"
    assert "error" in result
    assert result["errors"]


def test_create_agent_node_handles_exception(workflow, sample_state):
    agent_function = MagicMock(
        side_effect=RuntimeError("Agent execution failed")
    )

    workflow.agents["test_agent"] = agent_function

    node = workflow._create_agent_node("test_agent")
    result = node(sample_state)

    assert result["workflow_status"] == "failed"
    assert result["current_agent"] == "test_agent"
    assert "Agent execution failed" in result["error"]
    assert result["errors"][0]["agent"] == "test_agent"


def test_prepare_validation_retry(workflow, sample_state):
    sample_state["validation_error"] = "Invalid SQL syntax"
    sample_state["retry_count"] = 0

    result = workflow._prepare_validation_retry(sample_state)

    assert result["retry_count"] == 1
    assert result["sql_generation_success"] is False
    assert result["sql_generation_error"] == "Invalid SQL syntax"
    assert result["execution_success"] is False
    assert result["workflow_status"] == "running"
    assert result["current_agent"] == "sql_generation_agent"


def test_prepare_execution_retry(workflow, sample_state):
    sample_state["execution_error"] = "Unknown column: customer_name"
    sample_state["retry_count"] = 0

    result = workflow._prepare_execution_retry(sample_state)

    assert result["retry_count"] == 1
    assert result["sql_generation_success"] is False
    assert result["sql_generation_error"] == (
        "Unknown column: customer_name"
    )
    assert result["sql_valid"] is False
    assert result["validated_sql"] is None
    assert result["validation_error"] is None
    assert result["execution_result"]["error"] == (
        "Unknown column: customer_name"
    )
    assert result["workflow_status"] == "running"
    assert result["current_agent"] == "sql_generation_agent"


def test_prepare_validation_retry_preserves_validation_error(
    workflow,
    sample_state,
):
    sample_state["validation_error"] = "SELECT statement is invalid"

    result = workflow._prepare_validation_retry(sample_state)

    # SQLGenerationAgent reads validation_error when correcting SQL.
    assert result.get("validation_error") == (
        "SELECT statement is invalid"
    )


def test_prepare_execution_retry_preserves_execution_error(
    workflow,
    sample_state,
):
    sample_state["execution_error"] = "Table does not exist"

    result = workflow._prepare_execution_retry(sample_state)

    # SQLGenerationAgent reads execution_result["error"].
    assert result["execution_result"]["error"] == "Table does not exist"


def test_build_workflow_compiles_graph(workflow):
    compiled_graph = workflow.build()

    assert compiled_graph is not None
    assert workflow.graph is not None
    assert workflow.compiled_graph is not None


def test_run_builds_graph_when_not_compiled(workflow, sample_state):
    mock_compiled_graph = MagicMock()
    mock_compiled_graph.invoke.return_value = {
        **sample_state,
        "workflow_status": "completed",
    }

    workflow.build = MagicMock(return_value=mock_compiled_graph)
    workflow.compiled_graph = None

    result = workflow.run(sample_state)

    workflow.build.assert_called_once()
    mock_compiled_graph.invoke.assert_called_once()
    assert result["workflow_status"] == "completed"


def test_run_uses_supplied_recursion_limit(workflow, sample_state):
    mock_compiled_graph = MagicMock()
    mock_compiled_graph.invoke.return_value = sample_state

    workflow.compiled_graph = mock_compiled_graph

    workflow.run(sample_state, recursion_limit=50)

    _, kwargs = mock_compiled_graph.invoke.call_args

    assert kwargs["config"]["recursion_limit"] == 50


def test_run_wraps_graph_execution_error(workflow, sample_state):
    mock_compiled_graph = MagicMock()
    mock_compiled_graph.invoke.side_effect = RuntimeError(
        "Graph execution failed"
    )

    workflow.compiled_graph = mock_compiled_graph

    with pytest.raises(WorkflowError, match="Workflow execution failed"):
        workflow.run(sample_state)


def test_get_graph_visualization_handles_error(workflow):
    workflow.compiled_graph = MagicMock()
    workflow.compiled_graph.get_graph.side_effect = RuntimeError(
        "Visualization unavailable"
    )

    result = workflow.get_graph_visualization()

    assert result is None


def test_get_workflow_nodes(workflow):
    workflow.agents = {
        "supervisor": MagicMock(),
        "schema_agent": MagicMock(),
        "sql_generation_agent": MagicMock(),
    }

    result = workflow.get_workflow_nodes()

    assert result == [
        "supervisor",
        "schema_agent",
        "sql_generation_agent",
    ]

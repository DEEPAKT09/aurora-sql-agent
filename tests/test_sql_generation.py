
"""
AURORA SQL Agent
SQL Generation Agent Tests

Tests natural-language-to-SQL generation using a mocked LLM.
"""

import pytest
from unittest.mock import MagicMock, patch

from agents.sql_generation_agent import (
    SQLGenerationAgent,
    SQLGenerationError,
)


@pytest.fixture
def mock_llm():
    """Create a mocked Gemini LLM."""

    llm = MagicMock()
    llm.invoke.return_value = MagicMock(
        content="SELECT id, name FROM customers;"
    )

    return llm


@pytest.fixture
def agent(mock_llm):
    """Create SQL generation agent with mocked Gemini."""

    with patch(
        "agents.sql_generation_agent.ChatGoogleGenerativeAI",
        return_value=mock_llm,
    ):
        instance = SQLGenerationAgent()

    return instance


@pytest.fixture
def sample_state():
    """Provide representative workflow state."""

    return {
        "user_question": "Show all customer names",
        "database_connected": True,
        "database_type": "postgresql",
        "database_name": "test_database",
        "schema_context": """
        Table: customers
        Columns:
        - id: INTEGER
        - name: VARCHAR(100)
        - email: VARCHAR(150)
        """,
        "conversation_history": [],
        "retry_count": 0,
    }


# ---------------------------------------------------------
# Initialization
# ---------------------------------------------------------

def test_agent_initialization(agent):
    assert agent is not None


# ---------------------------------------------------------
# SQL generation
# ---------------------------------------------------------

def test_generate_sql_success(
    agent,
    mock_llm,
    sample_state,
):
    result = agent.run(sample_state)

    assert isinstance(result, dict)
    assert result["sql_generation_success"] is True
    assert "SELECT" in result["generated_sql"].upper()
    assert "customers" in result["generated_sql"].lower()

    mock_llm.invoke.assert_called_once()


def test_generate_sql_uses_user_question(
    agent,
    mock_llm,
    sample_state,
):
    agent.run(sample_state)

    prompt = str(mock_llm.invoke.call_args)

    assert "Show all customer names" in prompt


def test_generate_sql_uses_schema_context(
    agent,
    mock_llm,
    sample_state,
):
    agent.run(sample_state)

    prompt = str(mock_llm.invoke.call_args)

    assert "customers" in prompt
    assert "VARCHAR(100)" in prompt


def test_generate_sql_uses_database_dialect(
    agent,
    mock_llm,
    sample_state,
):
    agent.run(sample_state)

    prompt = str(mock_llm.invoke.call_args)

    assert "postgres" in prompt.lower()


def test_generate_sql_supports_mysql(
    agent,
    mock_llm,
    sample_state,
):
    sample_state["database_type"] = "mysql"

    result = agent.run(sample_state)

    assert result["sql_generation_success"] is True
    assert result["sql_dialect"] == "mysql"


def test_generate_sql_supports_postgresql(
    agent,
    mock_llm,
    sample_state,
):
    result = agent.run(sample_state)

    assert result["sql_generation_success"] is True
    assert result["sql_dialect"] == "postgres"


# ---------------------------------------------------------
# SQL response handling
# ---------------------------------------------------------

def test_generate_sql_removes_markdown_code_fence(
    agent,
    mock_llm,
    sample_state,
):
    mock_llm.invoke.return_value = MagicMock(
        content="```sql\nSELECT * FROM customers;\n```"
    )

    result = agent.run(sample_state)

    assert result["sql_generation_success"] is True
    assert "```" not in result["generated_sql"]
    assert "SELECT" in result["generated_sql"].upper()


def test_generate_sql_preserves_query(
    agent,
    mock_llm,
    sample_state,
):
    expected_sql = (
        "SELECT name FROM customers WHERE id = 10;"
    )

    mock_llm.invoke.return_value = MagicMock(
        content=expected_sql
    )

    result = agent.run(sample_state)

    assert result["generated_sql"].strip() == expected_sql


# ---------------------------------------------------------
# Conversation context
# ---------------------------------------------------------

def test_generate_sql_uses_conversation_history(
    agent,
    mock_llm,
    sample_state,
):
    sample_state["conversation_history"] = [
        {
            "role": "user",
            "content": "Show customers from Chennai",
        },
        {
            "role": "assistant",
            "content": "Here are the Chennai customers.",
        },
    ]

    agent.run(sample_state)

    prompt = str(mock_llm.invoke.call_args)

    assert "Chennai" in prompt


# ---------------------------------------------------------
# Retry and correction context
# ---------------------------------------------------------

def test_generate_sql_uses_previous_validation_error(
    agent,
    mock_llm,
    sample_state,
):
    sample_state["validation_error"] = (
        "Previous SQL failed validation"
    )

    agent.run(sample_state)

    prompt = str(mock_llm.invoke.call_args)

    assert "Previous SQL failed validation" in prompt


def test_generate_sql_uses_execution_error(
    agent,
    mock_llm,
    sample_state,
):
    sample_state["execution_result"] = {
         "error": "Unknown column 'customer_name'"
    }

    agent.run(sample_state)

    prompt = str(mock_llm.invoke.call_args)

    assert "Unknown column" in prompt


# ---------------------------------------------------------
# Error handling
# ---------------------------------------------------------

def test_generate_sql_handles_llm_error(
    agent,
    mock_llm,
    sample_state,
):
    mock_llm.invoke.side_effect = Exception(
        "Gemini API unavailable"
    )

    result = agent.run(sample_state)

    assert isinstance(result, dict)
    assert result["sql_generation_success"] is False


def test_generate_sql_handles_empty_response(
    agent,
    mock_llm,
    sample_state,
):
    mock_llm.invoke.return_value = MagicMock(content="")

    result = agent.run(sample_state)

    assert isinstance(result, dict)
    assert result["sql_generation_success"] is False


def test_sql_generation_error_class():
    error = SQLGenerationError("SQL generation failed")

    assert isinstance(error, Exception)
    assert str(error) == "SQL generation failed"

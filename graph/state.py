
"""
AURORA SQL Agent
LangGraph Shared State

Defines the shared state structure used by all agents
and workflow nodes.
"""

from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph.message import add_messages


class SQLAgentState(TypedDict, total=False):
    """Shared state for the AURORA multi-agent workflow."""

    # -----------------------------------------------------
    # Conversation
    # -----------------------------------------------------

    messages: Annotated[list, add_messages]
    user_question: str
    conversation_history: list[dict[str, Any]]
    final_response: Optional[str]

    # -----------------------------------------------------
    # Supervisor
    # -----------------------------------------------------

    supervisor_decision: dict[str, Any]
    user_intent: str
    requires_database: bool
    supervisor_reasoning: str
    clarification_needed: bool
    clarification_question: Optional[str]

    # -----------------------------------------------------
    # Database connection
    # -----------------------------------------------------

    database_connected: bool
    database_type: Optional[str]
    database_name: Optional[str]
    database_schema: Optional[str]
    database_config: Any

    # -----------------------------------------------------
    # Schema discovery
    # -----------------------------------------------------

    schema_metadata: dict[str, Any]
    schema_discovered: bool
    relevant_schema: dict[str, Any]
    schema_context: str
    relevant_tables: list[str]
    relevant_columns: list[str]
    schema_error: Optional[str]

    # -----------------------------------------------------
    # SQL generation
    # -----------------------------------------------------

    generated_sql: Optional[str]
    sql_dialect: str
    sql_generation_success: bool
    sql_generation_error: Optional[str]

    # -----------------------------------------------------
    # SQL validation
    # -----------------------------------------------------

    validation_result: dict[str, Any]
    sql_valid: bool
    validated_sql: Optional[str]
    validation_error: Optional[str]

    # -----------------------------------------------------
    # Query optimization
    # -----------------------------------------------------

    optimization_result: dict[str, Any]
    optimized_sql: Optional[str]
    optimization_warnings: list[str]

    # -----------------------------------------------------
    # SQL execution
    # -----------------------------------------------------

    execution_result: dict[str, Any]
    execution_success: bool
    execution_error: Optional[str]

    # -----------------------------------------------------
    # Result analysis
    # -----------------------------------------------------

    result_analysis: Any
    analysis_success: bool
    analysis_error: Optional[str]

    # -----------------------------------------------------
    # Visualization
    # -----------------------------------------------------

    visualization_requested: bool
    visualization_result: Any
    visualization_success: bool
    visualization_error: Optional[str]

    # -----------------------------------------------------
    # Workflow control
    # -----------------------------------------------------

    workflow_status: str
    current_agent: Optional[str]
    next_agent: Optional[str]
    retry_count: int
    max_retries: int
    error: Optional[str]
    errors: list[dict[str, Any]]
    workflow_trace: list[str]


def create_initial_state(
    user_question: str,
    database_connected: bool = False,
    database_type: Optional[str] = None,
    database_name: Optional[str] = None,
    database_schema: Optional[str] = None,
    conversation_history: Optional[list] = None,
    database_config: Any = None,
) -> SQLAgentState:
    """
    Create the initial state for a new workflow execution.

    Args:
        user_question: Natural-language question from the user.
        database_connected: Whether a database is connected.
        database_type: PostgreSQL or MySQL.
        database_name: Connected database name.
        database_schema: Selected database schema.
        conversation_history: Previous conversation messages.
        database_config: Database connection configuration.

    Returns:
        SQLAgentState: Initialized workflow state.
    """

    return {
        # Conversation
        "messages": [],
        "user_question": user_question,
        "conversation_history": conversation_history or [],
        "final_response": None,

        # Supervisor
        "supervisor_decision": {},
        "user_intent": "unknown",
        "requires_database": True,
        "supervisor_reasoning": "",
        "clarification_needed": False,
        "clarification_question": None,

        # Database
        "database_connected": database_connected,
        "database_type": database_type,
        "database_name": database_name,
        "database_schema": database_schema,
        "database_config": database_config,

        # Schema
        "schema_metadata": {},
        "schema_discovered": False,
        "relevant_schema": {},
        "schema_context": "",
        "relevant_tables": [],
        "relevant_columns": [],
        "schema_error": None,

        # SQL generation
        "generated_sql": None,
        "sql_dialect": (
            "mysql" if database_type == "mysql" else "postgres"
        ),
        "sql_generation_success": False,
        "sql_generation_error": None,

        # Validation
        "validation_result": {},
        "sql_valid": False,
        "validated_sql": None,
        "validation_error": None,

        # Optimization
        "optimization_result": {},
        "optimized_sql": None,
        "optimization_warnings": [],

        # Execution
        "execution_result": {},
        "execution_success": False,
        "execution_error": None,

        # Analysis
        "result_analysis": None,
        "analysis_success": False,
        "analysis_error": None,

        # Visualization
        "visualization_requested": False,
        "visualization_result": None,
        "visualization_success": False,
        "visualization_error": None,

        # Workflow
        "workflow_status": "initialized",
        "current_agent": None,
        "next_agent": None,
        "retry_count": 0,
        "max_retries": 2,
        "error": None,
        "errors": [],
        "workflow_trace": [],
    }


def update_workflow_status(
    state: SQLAgentState,
    status: str,
    current_agent: Optional[str] = None,
    next_agent: Optional[str] = None,
) -> dict[str, Any]:
    """
    Build a workflow status update.

    Returns:
        Dictionary containing the updated workflow fields.
    """

    return {
        "workflow_status": status,
        "current_agent": current_agent,
        "next_agent": next_agent,
    }


def add_workflow_error(
    state: SQLAgentState,
    agent_name: str,
    error_message: str,
) -> dict[str, Any]:
    """
    Record an agent error in the shared workflow state.

    Returns:
        Dictionary containing the error update.
    """

    existing_errors = list(
        state.get("errors", [])
    )

    error_entry = {
        "agent": agent_name,
        "message": str(error_message),
    }

    existing_errors.append(error_entry)

    existing_trace = list(
        state.get("workflow_trace", [])
    )

    existing_trace.append(
        f"{agent_name}: error"
    )

    return {
        "error": str(error_message),
        "errors": existing_errors,
        "workflow_trace": existing_trace,
        "workflow_status": "failed",
        "current_agent": agent_name,
    }


def increment_retry_count(
    state: SQLAgentState,
) -> dict[str, Any]:
    """
    Increment the workflow retry counter.

    Returns:
        Dictionary containing the updated retry count.
    """

    current_count = state.get("retry_count", 0)

    return {
        "retry_count": current_count + 1,
    }


def add_workflow_trace(
    state: SQLAgentState,
    agent_name: str,
) -> dict[str, Any]:
    """
    Append an agent name to the workflow execution trace.

    Returns:
        Dictionary containing the updated workflow trace.
    """

    trace = list(
        state.get("workflow_trace", [])
    )

    trace.append(agent_name)

    return {
        "workflow_trace": trace,
        "current_agent": agent_name,
    }

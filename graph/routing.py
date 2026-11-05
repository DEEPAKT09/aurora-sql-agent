
"""
AURORA SQL Agent
LangGraph Workflow Routing

Controls the movement between agents based on
workflow state, validation results and execution status.
"""


# ---------------------------------------------------------
# AGENT NODE NAMES
# ---------------------------------------------------------

SUPERVISOR_AGENT = "supervisor"
SCHEMA_AGENT = "schema_agent"
SQL_GENERATION_AGENT = "sql_generation_agent"
SQL_VALIDATION_AGENT = "sql_validation_agent"
EXECUTION_AGENT = "execution_agent"
RESULT_ANALYSIS_AGENT = "result_analysis_agent"
VISUALIZATION_AGENT = "visualization_agent"

END_NODE = "__end__"


# ---------------------------------------------------------
# WORKFLOW STATUS
# ---------------------------------------------------------

STATUS_INITIALIZED = "initialized"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CLARIFICATION_REQUIRED = "clarification_required"
STATUS_UNSUPPORTED_REQUEST = "unsupported_request"


# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def _get_retry_count(state):
    """Return the current retry count."""

    return int(state.get("retry_count", 0) or 0)


def _get_max_retries(state):
    """Return the configured maximum retry count."""

    return int(state.get("max_retries", 2) or 0)


def _can_retry(state):
    """Check whether another retry is permitted."""

    return _get_retry_count(state) < _get_max_retries(state)


def _get_validation_status(state):
    """Extract SQL validation status."""

    validation = state.get("validation_result", {})

    if isinstance(validation, dict):
        return bool(
            validation.get(
                "is_valid",
                validation.get(
                    "valid",
                    validation.get("success", False),
                ),
            )
        )

    return bool(state.get("sql_valid", False))


def _get_execution_status(state):
    """Extract SQL execution status."""

    execution = state.get("execution_result", {})

    if isinstance(execution, dict):
        return bool(
            execution.get(
                "success",
                state.get("execution_success", False),
            )
        )

    return bool(state.get("execution_success", False))


def _has_execution_result(state):
    """Check whether execution returned a result."""

    execution = state.get("execution_result")

    return (
        isinstance(execution, dict)
        and bool(execution)
    )


def _has_schema_metadata(state):
    """Check whether schema discovery produced metadata."""

    metadata = state.get("schema_metadata")

    return (
        isinstance(metadata, dict)
        and bool(metadata)
    )


# ---------------------------------------------------------
# SUPERVISOR ROUTING
# ---------------------------------------------------------

def route_after_supervisor(state):
    """
    Decide where to route after supervisor execution.

    Possible destinations:
        - END_NODE
        - SCHEMA_AGENT
    """

    status = state.get("workflow_status")

    # Stop immediately for terminal workflow states.
    if status in (
        STATUS_FAILED,
        STATUS_CLARIFICATION_REQUIRED,
        STATUS_UNSUPPORTED_REQUEST,
    ):
        return END_NODE

    if state.get("error"):
        return END_NODE

    # Requests that do not require database access
    # should not enter the SQL workflow.
    if not state.get("requires_database", True):
        return END_NODE

    # Database connection is mandatory for SQL requests.
    if not state.get("database_connected", False):
        return END_NODE

    return SCHEMA_AGENT


# ---------------------------------------------------------
# SCHEMA AGENT ROUTING
# ---------------------------------------------------------

def route_after_schema_discovery(state):
    """
    Decide where to route after schema discovery.

    Possible destinations:
        - SQL_GENERATION_AGENT
        - END_NODE
    """

    if state.get("error"):
        return END_NODE

    if state.get("workflow_status") == STATUS_FAILED:
        return END_NODE

    if not _has_schema_metadata(state):
        return END_NODE

    return SQL_GENERATION_AGENT


# ---------------------------------------------------------
# SQL GENERATION ROUTING
# ---------------------------------------------------------

def route_after_sql_generation(state):
    """
    Decide where to route after SQL generation.

    Possible destinations:
        - SQL_VALIDATION_AGENT
        - END_NODE
    """

    if state.get("error"):
        return END_NODE

    if not state.get("sql_generation_success", False):
        return END_NODE

    if not state.get("generated_sql"):
        return END_NODE

    return SQL_VALIDATION_AGENT


# ---------------------------------------------------------
# SQL VALIDATION ROUTING
# ---------------------------------------------------------

def route_after_validation(state):
    """
    Decide where to route after SQL validation.

    Possible destinations:
        - EXECUTION_AGENT
        - SQL_GENERATION_AGENT
        - END_NODE
    """

    if state.get("error"):
        return END_NODE

    if _get_validation_status(state):
        return EXECUTION_AGENT

    # Retry SQL generation when validation fails.
    if _can_retry(state):
        return SQL_GENERATION_AGENT

    return END_NODE


# ---------------------------------------------------------
# SQL EXECUTION ROUTING
# ---------------------------------------------------------

def route_after_execution(state):
    """
    Decide where to route after SQL execution.

    Possible destinations:
        - RESULT_ANALYSIS_AGENT
        - SQL_GENERATION_AGENT
        - END_NODE
    """

    if _get_execution_status(state):
        return RESULT_ANALYSIS_AGENT

    # Retry only when an execution result exists
    # and the retry limit has not been reached.
    if _has_execution_result(state) and _can_retry(state):
        return SQL_GENERATION_AGENT

    return END_NODE


# ---------------------------------------------------------
# RESULT ANALYSIS ROUTING
# ---------------------------------------------------------

def route_after_analysis(state):
    """
    Decide where to route after result analysis.

    Possible destinations:
        - VISUALIZATION_AGENT
        - END_NODE
    """

    if state.get("error"):
        return END_NODE

    if not state.get("analysis_success", False):
        return END_NODE

    if state.get("visualization_requested", False):
        return VISUALIZATION_AGENT

    return END_NODE


# ---------------------------------------------------------
# VISUALIZATION ROUTING
# ---------------------------------------------------------

def route_after_visualization(state):
    """
    Decide where to route after visualization.

    The visualization agent is the final processing stage.
    """

    return END_NODE

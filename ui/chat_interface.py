
"""
AURORA SQL Agent
Chat Interface

Provides the main conversational interface for interacting
with the multi-agent natural-language-to-SQL workflow.
"""

import uuid

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from graph.state import create_initial_state
from graph.workflow import run_workflow


def _initialize_chat_state():
    """Initialize chat-related session state."""

    defaults = {
        "chat_messages": [],
        "conversation_history": [],
        "generated_sql": "",
        "edited_sql": "",
        "sql_validation_result": None,
        "sql_execution_result": None,
        "result_analysis": None,
        "visualization_figure": None,
        "workflow_running": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _get_response(state):
    """Extract a user-facing response from workflow state."""

    if not isinstance(state, dict):
        return "AURORA could not complete the request."

    response = state.get("final_response")
    if response:
        return str(response)

    status = state.get("workflow_status")

    if status == "clarification_required":
        return state.get(
            "clarification_question",
            "Could you clarify your question?",
        )

    if status == "unsupported_request":
        return (
            "I couldn't process this request because it is "
            "outside the supported SQL Agent functionality."
        )

    execution = state.get("execution_result", {})

    if isinstance(execution, dict) and execution.get("success"):
        return (
            "Your query was executed successfully. "
            f"{execution.get('row_count', 0)} record(s) returned."
        )

    if state.get("error"):
        return f"An error occurred: {state['error']}"

    return "The workflow completed, but no final response was generated."


def _build_conversation_history():
    """Return recent conversation history for the agents."""

    history = st.session_state.get("conversation_history", [])
    return history[-10:]


def _prepare_workflow_state(question):
    """Prepare the initial state for the LangGraph workflow."""

    return create_initial_state(
        user_question=question,
        database_connected=st.session_state.get(
            "database_connected", False
        ),
        database_type=st.session_state.get("database_type"),
        database_name=st.session_state.get("database_name"),
        database_schema=st.session_state.get("database_schema"),
        conversation_history=_build_conversation_history(),
        database_config=st.session_state.get("database_config"),
    )


def _sync_workflow_results(state):
    """Synchronize workflow outputs with Streamlit session state."""

    if not isinstance(state, dict):
        return

    generated_sql = state.get("generated_sql")
    if generated_sql:
        st.session_state.generated_sql = generated_sql
        st.session_state.edited_sql = generated_sql

    validation_result = state.get("validation_result")
    if validation_result is not None:
        st.session_state.sql_validation_result = validation_result

    execution_result = state.get("execution_result")
    if execution_result is not None:
        st.session_state.sql_execution_result = execution_result

    result_analysis = state.get("result_analysis")
    if result_analysis is not None:
        st.session_state.result_analysis = result_analysis

    visualization = state.get("visualization_result")
    if visualization is not None:
        if isinstance(visualization, dict):
            st.session_state.visualization_figure = (
                visualization.get("figure")
                or visualization.get("visualization")
            )
        else:
            st.session_state.visualization_figure = visualization


def _run_agent_workflow(question):
    """Execute the complete multi-agent workflow."""

    if not st.session_state.get("database_connected", False):
        return (
            "Please connect to your PostgreSQL or MySQL database "
            "before submitting a data query.",
            None,
        )

    try:
        st.session_state.workflow_running = True

        initial_state = _prepare_workflow_state(question)
        final_state = run_workflow(initial_state)

        _sync_workflow_results(final_state)

        return _get_response(final_state), final_state

    except Exception as exc:
        return f"Unable to process your request: {exc}", None

    finally:
        st.session_state.workflow_running = False


def _render_sql_section(state):
    """Display generated SQL and validation information."""

    sql = state.get("generated_sql") if isinstance(state, dict) else None
    if not sql:
        return

    with st.expander("Generated SQL", expanded=True):
        st.code(sql, language="sql")

        validation = state.get("validation_result", {})
        if isinstance(validation, dict):
            is_valid = validation.get(
                "is_valid",
                validation.get(
                    "valid",
                    validation.get("success", False),
                ),
            )

            if is_valid:
                st.success("SQL validation successful.")
            else:
                st.warning(
                    validation.get(
                        "message",
                        "Review the SQL validation result.",
                    )
                )


def _render_query_results(state, message_id):
    """Display query execution results."""

    if not isinstance(state, dict):
        return

    result = state.get("execution_result")
    if not isinstance(result, dict):
        return

    if not result.get("success", False):
        error = result.get("error")
        if error:
            st.error(f"Query execution failed: {error}")
        return

    records = result.get("records", [])
    columns = result.get("columns", [])

    if isinstance(records, pd.DataFrame):
        dataframe = records.copy()
    elif records:
        dataframe = pd.DataFrame(records, columns=columns or None)
    else:
        dataframe = pd.DataFrame(columns=columns)

    with st.expander("Query Results", expanded=True):
        col1, col2 = st.columns(2)

        col1.metric(
            "Rows Returned",
            result.get("row_count", len(dataframe)),
        )

        col2.metric(
            "Execution Time",
            f"{result.get('execution_time', 0):.3f} sec",
        )

        if dataframe.empty:
            st.info("The query returned no records.")
        else:
            st.dataframe(
                dataframe,
                width="stretch",
                hide_index=True,
            )

            csv_data = dataframe.to_csv(index=False).encode("utf-8")

            st.download_button(
                "Download Results as CSV",
                data=csv_data,
                file_name="aurora_query_results.csv",
                mime="text/csv",
                key=f"chat_results_csv_{message_id}",
            )


def _render_analysis(state):
    """Display AI-generated or fallback result analysis."""

    if not isinstance(state, dict):
        return

    analysis = state.get("result_analysis")
    if not analysis:
        analysis = state.get("analysis_fallback")

    if not analysis:
        analysis_error = state.get("analysis_error")
        if analysis_error:
            st.caption(
                "AI explanation was unavailable. "
                "The query results are still available above."
            )
        return

    with st.expander("Result Analysis", expanded=True):
        if isinstance(analysis, dict):
            summary = (
                analysis.get("summary")
                or analysis.get("analysis")
                or analysis.get("explanation")
            )

            if summary:
                st.write(summary)

            insights = analysis.get("insights", [])
            if isinstance(insights, list):
                for insight in insights:
                    st.markdown(f"- {insight}")
        else:
            st.write(str(analysis))


def _render_visualization(state):
    """Display the visualization generated by the agent."""

    if not isinstance(state, dict):
        return

    visualization = state.get("visualization_result")
    if not visualization:
        return

    if isinstance(visualization, dict):
        figure = (
            visualization.get("figure")
            or visualization.get("visualization")
        )
    else:
        figure = visualization

    if figure is None:
        return

    with st.expander("Data Visualization", expanded=True):
        try:
            if isinstance(figure, (go.Figure, dict)):
                st.plotly_chart(
                    figure,
                    width="stretch",
                    key=f"chat_chart_{uuid.uuid4().hex}",
                )
            else:
                st.info("The visualization output is not supported.")
        except Exception as exc:
            st.warning(f"Unable to display chart: {exc}")


def _render_message_details(message):
    """Render workflow outputs associated with an assistant message."""

    state = message.get("state")
    if not isinstance(state, dict):
        return

    message_id = message.get("id") or uuid.uuid4().hex

    _render_sql_section(state)
    _render_query_results(state, message_id)
    _render_analysis(state)
    _render_visualization(state)


def _render_chat_history():
    """Render all messages from the persistent session history."""

    for message in st.session_state.chat_messages:
        role = message.get("role", "assistant")

        with st.chat_message(role):
            st.markdown(message.get("content", ""))

            if role == "assistant":
                _render_message_details(message)


def _process_user_question(question):
    """Store a user question, run the workflow, and store its response."""

    question = question.strip()
    if not question:
        return

    # Prevent accidental duplicate submissions.
    if st.session_state.get("workflow_running", False):
        return

    user_message = {
        "id": uuid.uuid4().hex,
        "role": "user",
        "content": question,
    }

    # Store the user message before running the workflow.
    st.session_state.chat_messages.append(user_message)
    st.session_state.conversation_history.append({
        "role": "user",
        "content": question,
    })

    with st.spinner("AURORA is analyzing your question..."):
        response, final_state = _run_agent_workflow(question)

    assistant_message = {
        "id": uuid.uuid4().hex,
        "role": "assistant",
        "content": response,
        "state": final_state,
    }

    # Store the assistant response exactly once.
    st.session_state.chat_messages.append(assistant_message)
    st.session_state.conversation_history.append({
        "role": "assistant",
        "content": response,
    })

    # The next render displays both messages from the same history.
    st.rerun()


def render_chat_interface():
    """Render the main AURORA SQL Agent chat interface."""

    _initialize_chat_state()

    st.title("AURORA SQL Agent")

    st.caption(
        "Ask questions about your database in plain English. "
        "AURORA will generate SQL, validate it and retrieve your data."
    )

    if st.session_state.get("database_connected", False):
        database_name = st.session_state.get(
            "database_name",
            "Connected Database",
        )
        database_type = st.session_state.get(
            "database_type",
            "Database",
        )

        st.success(
            f"Connected to {database_name} ({database_type.upper()})"
        )
    else:
        st.warning(
            "No database connected. Open Database Connection "
            "from the sidebar to get started."
        )

    st.divider()

    if not st.session_state.chat_messages:
        st.markdown("### Welcome to AURORA!")

        st.write(
            "You can ask questions about your database "
            "without writing SQL manually."
        )

        st.markdown("**Example questions:**")

        examples = [
            "Show me the first 10 records from the customers table.",
            "How many orders were placed this month?",
            "Find the top 5 products by sales.",
            "Compare monthly revenue for the last year.",
        ]

        for example in examples:
            st.markdown(f"- {example}")

        st.divider()

    # Always render the conversation from one persistent message list.
    _render_chat_history()

    question = st.chat_input(
        "Ask AURORA anything about your database...",
        disabled=st.session_state.get("workflow_running", False),
    )

    if question:
        _process_user_question(question)


"""
AURORA SQL Agent
LangGraph Workflow Orchestration

Connects all agents and manages the complete
natural-language-to-SQL workflow.
"""

from typing import Any, Optional

from langgraph.graph import StateGraph, START, END

from config import settings
from graph.state import (
    SQLAgentState,
    increment_retry_count,
    add_workflow_trace,
)


class WorkflowError(Exception):
    """Raised when workflow construction or execution fails."""


class SQLAgentWorkflow:
    """
    Builds and executes the AURORA multi-agent workflow.
    """

    def __init__(self):
        self.graph = None
        self.compiled_graph = None
        self.agents = {}

    # -----------------------------------------------------
    # LOAD AGENTS
    # -----------------------------------------------------

    def _load_agents(self) -> None:
        """Import and register all agent functions."""

        try:
            from agents.supervisor import run as supervisor_run
            from agents.schema_agent import run as schema_run
            from agents.sql_generation_agent import run as sql_generation_run
            from agents.sql_validation_agent import run as sql_validation_run
            from agents.execution_agent import run as execution_run
            from agents.result_analysis_agent import run as analysis_run
            from agents.visualization_agent import run as visualization_run

            self.agents = {
                "supervisor": supervisor_run,
                "schema_agent": schema_run,
                "sql_generation_agent": sql_generation_run,
                "sql_validation_agent": sql_validation_run,
                "execution_agent": execution_run,
                "result_analysis_agent": analysis_run,
                "visualization_agent": visualization_run,
            }

        except ImportError as exc:
            raise WorkflowError(
                f"Unable to load workflow agents: {exc}"
            ) from exc

    # -----------------------------------------------------
    # RETRY PREPARATION
    # -----------------------------------------------------

    
    def _prepare_validation_retry(
        self,
        state: SQLAgentState,
    ) -> dict[str, Any]:
        """
        Prepare state before regenerating SQL after
        a validation failure.
        """

        updates = increment_retry_count(state)

        updates.update(
            add_workflow_trace(
                state,
                "sql_generation_retry",
            )
        )

        validation_error = (
            state.get("validation_error")
            or "SQL validation failed."
        )

        updates.update({
            "sql_generation_success": False,
            "sql_generation_error": validation_error,

            # SQLGenerationAgent reads this field.
            "validation_error": validation_error,

            "execution_success": False,
            "execution_result": {},
            "execution_error": None,

            "error": None,
            "workflow_status": "running",
            "current_agent": "sql_generation_agent",
        })

        return updates


    def _prepare_execution_retry(
        self,
        state: SQLAgentState,
    ) -> dict[str, Any]:
        """
        Prepare state before regenerating SQL after
        an execution failure.
        """

        updates = increment_retry_count(state)

        updates.update(
            add_workflow_trace(
                state,
                "sql_generation_retry",
            )
        )

        execution_error = (
            state.get("execution_error")
            or "SQL execution failed."
        )

        updates.update({
            "sql_generation_success": False,
            "sql_generation_error": execution_error,

            "sql_valid": False,
            "validated_sql": None,
            "validation_result": {},
            "validation_error": None,

            "execution_success": False,
            "execution_result": {
                "error": execution_error
            },
            "execution_error": None,

            "error": None,
            "workflow_status": "running",
            "current_agent": "sql_generation_agent",
        })

        return updates

    # -----------------------------------------------------
    # NODE WRAPPERS
    # -----------------------------------------------------

    def _create_agent_node(self, agent_name: str):
        """
        Create a workflow node for an agent.

        Adds workflow trace information while preserving
        the state updates returned by the agent.
        """

        agent_function = self.agents[agent_name]

        def agent_node(state: SQLAgentState):
            try:
                result = agent_function(state)

                if not isinstance(result, dict):
                    raise WorkflowError(
                        f"{agent_name} must return a dictionary."
                    )

                updates = dict(result)

                trace = list(
                    updates.get(
                        "workflow_trace",
                        state.get("workflow_trace", []),
                    )
                )

                trace.append(agent_name)

                updates["workflow_trace"] = trace
                updates["current_agent"] = agent_name

                return updates

            except Exception as exc:
                errors = list(state.get("errors", []))
                errors.append({
                    "agent": agent_name,
                    "message": str(exc),
                })

                trace = list(state.get("workflow_trace", []))
                trace.append(f"{agent_name}: error")

                return {
                    "error": str(exc),
                    "errors": errors,
                    "workflow_trace": trace,
                    "workflow_status": "failed",
                    "current_agent": agent_name,
                    "final_response": (
                        f"The {agent_name.replace('_', ' ')} "
                        f"encountered an error: {exc}"
                    ),
                }

        return agent_node

    # -----------------------------------------------------
    # BUILD WORKFLOW
    # -----------------------------------------------------

    def build(self):
        """Construct and compile the LangGraph workflow."""

        try:
            self._load_agents()

            workflow = StateGraph(SQLAgentState)

            # Register agent nodes.
            for agent_name in self.agents:
                workflow.add_node(
                    agent_name,
                    self._create_agent_node(agent_name),
                )

            # Register retry preparation nodes.
            workflow.add_node(
                "prepare_validation_retry",
                self._prepare_validation_retry,
            )

            workflow.add_node(
                "prepare_execution_retry",
                self._prepare_execution_retry,
            )

            # Entry point.
            workflow.add_edge(START, "supervisor")

            # Supervisor routing.
            from graph.routing import (
                route_after_supervisor,
                route_after_schema_discovery,
                route_after_sql_generation,
                route_after_validation,
                route_after_execution,
                route_after_analysis,
                END_NODE,
                SCHEMA_AGENT,
                SQL_GENERATION_AGENT,
                SQL_VALIDATION_AGENT,
                EXECUTION_AGENT,
                RESULT_ANALYSIS_AGENT,
                VISUALIZATION_AGENT,
            )

            workflow.add_conditional_edges(
                "supervisor",
                route_after_supervisor,
                {
                    SCHEMA_AGENT: SCHEMA_AGENT,
                    END_NODE: END,
                },
            )

            # Schema discovery.
            workflow.add_conditional_edges(
                "schema_agent",
                route_after_schema_discovery,
                {
                    SQL_GENERATION_AGENT: SQL_GENERATION_AGENT,
                    END_NODE: END,
                },
            )

            # SQL generation.
            workflow.add_conditional_edges(
                "sql_generation_agent",
                route_after_sql_generation,
                {
                    SQL_VALIDATION_AGENT: SQL_VALIDATION_AGENT,
                    END_NODE: END,
                },
            )

            # SQL validation and retry.
            def validation_router(state):
                destination = route_after_validation(state)

                if destination == SQL_GENERATION_AGENT:
                    return "retry"

                if destination == EXECUTION_AGENT:
                    return "execute"

                return "end"

            workflow.add_conditional_edges(
                "sql_validation_agent",
                validation_router,
                {
                    "retry": "prepare_validation_retry",
                    "execute": EXECUTION_AGENT,
                    "end": END,
                },
            )

            workflow.add_edge(
                "prepare_validation_retry",
                "sql_generation_agent",
            )

            # SQL execution and retry.
            def execution_router(state):
                destination = route_after_execution(state)

                if destination == SQL_GENERATION_AGENT:
                    return "retry"

                if destination == RESULT_ANALYSIS_AGENT:
                    return "analyze"

                return "end"

            workflow.add_conditional_edges(
                "execution_agent",
                execution_router,
                {
                    "retry": "prepare_execution_retry",
                    "analyze": RESULT_ANALYSIS_AGENT,
                    "end": END,
                },
            )

            workflow.add_edge(
                "prepare_execution_retry",
                "sql_generation_agent",
            )

            # Result analysis.
            workflow.add_conditional_edges(
                "result_analysis_agent",
                route_after_analysis,
                {
                    VISUALIZATION_AGENT: VISUALIZATION_AGENT,
                    END_NODE: END,
                },
            )

            # Visualization is the final agent.
            workflow.add_edge(
                "visualization_agent",
                END,
            )

            self.graph = workflow
            self.compiled_graph = workflow.compile()

            return self.compiled_graph

        except Exception as exc:
            raise WorkflowError(
                f"Failed to build workflow: {exc}"
            ) from exc

    # -----------------------------------------------------
    # EXECUTE WORKFLOW
    # -----------------------------------------------------

    def run(
        self,
        initial_state: SQLAgentState,
        recursion_limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """Execute the compiled workflow."""

        if self.compiled_graph is None:
            self.compiled_graph = self.build()

        try:
            limit = recursion_limit or (
                settings.max_retries * 5 + 25
            )

            result = self.compiled_graph.invoke(
                initial_state,
                config={
                    "recursion_limit": limit,
                },
            )

            return result

        except Exception as exc:
            raise WorkflowError(
                f"Workflow execution failed: {exc}"
            ) from exc

    # -----------------------------------------------------
    # WORKFLOW INFORMATION
    # -----------------------------------------------------

    def get_graph(self):
        """Return the compiled workflow graph."""

        if self.compiled_graph is None:
            self.build()

        return self.compiled_graph

    def get_graph_visualization(self) -> Optional[bytes]:
        """Return a PNG representation of the workflow."""

        try:
            graph = self.get_graph()
            return graph.get_graph().draw_mermaid_png()

        except Exception:
            return None

    def get_workflow_nodes(self) -> list[str]:
        """Return the registered workflow node names."""

        return list(self.agents.keys())


# ---------------------------------------------------------
# SHARED WORKFLOW INSTANCE
# ---------------------------------------------------------

sql_agent_workflow = SQLAgentWorkflow()


# ---------------------------------------------------------
# PUBLIC HELPER FUNCTIONS
# ---------------------------------------------------------

def build_workflow():
    """Build and return the compiled workflow."""

    return sql_agent_workflow.build()


def run_workflow(
    initial_state: SQLAgentState,
    recursion_limit: Optional[int] = None,
) -> dict[str, Any]:
    """Run the AURORA SQL Agent workflow."""

    return sql_agent_workflow.run(
        initial_state=initial_state,
        recursion_limit=recursion_limit,
    )

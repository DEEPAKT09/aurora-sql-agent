
"""
AURORA SQL Agent
Visualization Agent

Responsibilities:
- Determine whether query results benefit from visualization.
- Recommend suitable chart types.
- Generate Plotly visualizations.
- Support bar, line, pie, scatter and histogram charts.
- Avoid visualizing empty or unsuitable results.
- Return visualization information to LangGraph.
"""

from typing import Any

import pandas as pd

from config import settings
from graph.state import SQLAgentState
from tools.visualization_tools import (
    visualization_tools,
    VisualizationError,
)


class VisualizationAgentError(Exception):
    """Raised when visualization generation fails."""


class VisualizationAgent:
    """Creates visualizations from SQL query results."""

    def __init__(self):
        self.visualizer = visualization_tools

    # --------------------------------------------------
    # Data preparation
    # --------------------------------------------------

    @staticmethod
    def _prepare_dataframe(
        execution_result: dict[str, Any],
    ) -> pd.DataFrame:
        """Convert SQL execution results into a DataFrame."""

        if not isinstance(execution_result, dict):
            raise VisualizationAgentError(
                "Invalid SQL execution result."
            )

        dataframe = execution_result.get("dataframe")

        if isinstance(dataframe, pd.DataFrame):
            return dataframe.copy()

        records = execution_result.get("records", [])

        if records:
            return pd.DataFrame(records)

        columns = execution_result.get("columns", [])

        if columns:
            return pd.DataFrame(columns=columns)

        return pd.DataFrame()

    # --------------------------------------------------
    # Visualization decision
    # --------------------------------------------------

    @staticmethod
    def _should_visualize(
        state: SQLAgentState,
        dataframe: pd.DataFrame,
    ) -> tuple[bool, str]:
        """Determine whether the query results are suitable for a chart."""

        if dataframe.empty:
            return False, "No records are available to visualize."

        if len(dataframe.columns) == 0:
            return False, "The query returned no usable columns."

        user_question = state.get(
            "user_question",
            "",
        ).lower()

        visualization_keywords = (
            "chart",
            "graph",
            "plot",
            "visualize",
            "visualise",
            "visualization",
            "visualisation",
            "trend",
            "distribution",
            "compare",
            "comparison",
            "breakdown",
        )

        explicitly_requested = any(
            keyword in user_question
            for keyword in visualization_keywords
        )

        # A single numeric value generally does not need a chart.
        numeric_columns = dataframe.select_dtypes(
            include="number"
        ).columns.tolist()

        if not numeric_columns:
            return (
                False,
                "The results do not contain numeric columns "
                "suitable for the supported charts.",
            )

        if len(dataframe) < 2 and not explicitly_requested:
            return (
                False,
                "The query returned too few records for a useful chart.",
            )

        return True, (
            "Visualization requested by the user."
            if explicitly_requested
            else "Query results contain data suitable for visualization."
        )

    # --------------------------------------------------
    # Chart recommendation
    # --------------------------------------------------

    def _recommend_chart(
        self,
        dataframe: pd.DataFrame,
    ) -> dict[str, Any]:
        """Recommend a chart based on the returned DataFrame."""

        try:
            recommendation = self.visualizer.suggest_chart_type(
                dataframe
            )

            if isinstance(recommendation, dict):
                return recommendation

            if isinstance(recommendation, str):
                return {
                    "chart_type": recommendation,
                }

            return {}

        except Exception:
            # Chart recommendation is optional. The visualization
            # helper can still select a chart automatically.
            return {}

    # --------------------------------------------------
    # Chart generation
    # --------------------------------------------------

    def _create_visualization(
        self,
        dataframe: pd.DataFrame,
        recommendation: dict[str, Any],
        question: str,
    ) -> Any:
        """Generate a Plotly chart using the visualization tools."""

        chart_type = (
            recommendation.get("chart_type")
            or recommendation.get("type")
        )

        x_column = (
            recommendation.get("x_column")
            or recommendation.get("x")
        )

        y_column = (
            recommendation.get("y_column")
            or recommendation.get("y")
        )

        title = (
            recommendation.get("title")
            or "Query Results Visualization"
        )

        # Use automatic chart selection when no chart type
        # has been recommended.
        if not chart_type:
            return self.visualizer.create_recommended_chart(
                dataframe,
                title=title,
            )

        return self.visualizer.create_chart(
            dataframe=dataframe,
            chart_type=chart_type,
            x_column=x_column,
            y_column=y_column,
            title=title,
        )

    # --------------------------------------------------
    # Main agent execution
    # --------------------------------------------------

    def run(
        self,
        state: SQLAgentState,
    ) -> dict[str, Any]:
        """Generate a visualization and update workflow state."""

        if not state.get("execution_success", False):
            return {
                "visualization": None,
                "visualization_success": False,
                "visualization_skipped": True,
                "visualization_reason": (
                    "Visualization skipped because SQL execution failed."
                ),
                "current_agent": "visualization_agent",
                "workflow_status": "completed",
            }

        execution_result = state.get("execution_result")

        if not isinstance(execution_result, dict):
            return {
                "visualization": None,
                "visualization_success": False,
                "visualization_skipped": True,
                "visualization_reason": (
                    "No valid execution results are available."
                ),
                "current_agent": "visualization_agent",
                "workflow_status": "completed",
            }

        try:
            dataframe = self._prepare_dataframe(
                execution_result
            )

            should_visualize, reason = self._should_visualize(
                state,
                dataframe,
            )

            if not should_visualize:
                return {
                    "visualization": None,
                    "visualization_success": False,
                    "visualization_skipped": True,
                    "visualization_reason": reason,
                    "visualization_dataframe": dataframe,
                    "current_agent": "visualization_agent",
                    "workflow_status": "completed",
                    "error": None,
                    "error_type": None,
                }

            recommendation = self._recommend_chart(
                dataframe
            )

            figure = self._create_visualization(
                dataframe=dataframe,
                recommendation=recommendation,
                question=state.get("user_question", ""),
            )

            if figure is None:
                raise VisualizationAgentError(
                    "The visualization tool did not return a chart."
                )

            chart_type = (
                recommendation.get("chart_type")
                or recommendation.get("type")
                or "automatic"
            )

            return {
                "visualization": figure,
                "visualization_success": True,
                "visualization_skipped": False,
                "visualization_reason": reason,
                "visualization_type": chart_type,
                "visualization_dataframe": dataframe,
                "visualization_recommendation": recommendation,
                "current_agent": "visualization_agent",
                "workflow_status": "completed",
                "error": None,
                "error_type": None,
            }

        except VisualizationError as exc:
            return {
                "visualization": None,
                "visualization_success": False,
                "visualization_skipped": True,
                "visualization_reason": str(exc),
                "current_agent": "visualization_agent",
                "workflow_status": "completed",
                "error": None,
                "error_type": None,
            }

        except Exception:
            return {
                "visualization": None,
                "visualization_success": False,
                "visualization_skipped": True,
                "visualization_reason": (
                    "The SQL query succeeded, but chart generation "
                    "failed. The query results are still available."
                ),
                "current_agent": "visualization_agent",
                "workflow_status": "completed",
                "error": None,
                "error_type": None,
            }


# --------------------------------------------------
# Shared visualization agent instance
# --------------------------------------------------

visualization_agent = VisualizationAgent()


def run(state: SQLAgentState) -> dict[str, Any]:
    """Entry point used by the LangGraph workflow."""

    return visualization_agent.run(state)

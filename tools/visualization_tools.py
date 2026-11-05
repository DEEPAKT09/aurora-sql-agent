
"""
AURORA SQL Agent
Visualization Tools

Responsibilities:
- Analyze query result DataFrames.
- Recommend suitable chart types.
- Generate interactive Plotly charts.
- Support bar, line, pie, scatter and histogram charts.
- Handle missing and unsuitable visualization data.
"""

from typing import Any, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


class VisualizationError(Exception):
    """Raised when visualization generation fails."""


class VisualizationTools:
    """Creates interactive visualizations from SQL query results."""

    SUPPORTED_CHARTS = {
        "bar",
        "line",
        "pie",
        "scatter",
        "histogram",
    }

    def __init__(self, default_height: int = 400):
        self.default_height = default_height

    @staticmethod
    def _validate_dataframe(
        dataframe: pd.DataFrame,
    ) -> None:
        """Validate the input DataFrame."""

        if dataframe is None:
            raise VisualizationError(
                "No query result data was provided."
            )

        if not isinstance(dataframe, pd.DataFrame):
            raise VisualizationError(
                "Visualization input must be a pandas DataFrame."
            )

        if dataframe.empty:
            raise VisualizationError(
                "The query returned no records to visualize."
            )

        if len(dataframe.columns) == 0:
            raise VisualizationError(
                "The query result contains no columns."
            )

    @staticmethod
    def _get_numeric_columns(
        dataframe: pd.DataFrame,
    ) -> list[str]:
        """Return numeric columns suitable for chart values."""

        return dataframe.select_dtypes(
            include="number"
        ).columns.tolist()

    @staticmethod
    def _get_categorical_columns(
        dataframe: pd.DataFrame,
    ) -> list[str]:
        """Return non-numeric columns suitable for categories."""

        return dataframe.select_dtypes(
            exclude="number"
        ).columns.tolist()

    def suggest_chart_type(
        self,
        dataframe: pd.DataFrame,
    ) -> dict[str, Any]:
        """
        Recommend a chart type based on result structure.

        Returns:
            recommended_chart
            category_column
            value_column
            numeric_columns
            categorical_columns
            explanation
        """

        self._validate_dataframe(dataframe)

        numeric_columns = self._get_numeric_columns(dataframe)
        categorical_columns = self._get_categorical_columns(dataframe)

        recommendation = {
            "recommended_chart": None,
            "category_column": None,
            "value_column": None,
            "numeric_columns": numeric_columns,
            "categorical_columns": categorical_columns,
            "explanation": "",
        }

        if len(dataframe.columns) == 1:
            column = dataframe.columns[0]

            if column in numeric_columns:
                recommendation.update({
                    "recommended_chart": "histogram",
                    "value_column": column,
                    "explanation": (
                        "A histogram is suitable for examining "
                        "the distribution of a numeric column."
                    ),
                })
            else:
                recommendation.update({
                    "recommended_chart": "bar",
                    "category_column": column,
                    "explanation": (
                        "A bar chart can show the frequency "
                        "of each category."
                    ),
                })

            return recommendation

        if numeric_columns and categorical_columns:
            category = categorical_columns[0]
            value = numeric_columns[0]

            if (
                len(dataframe) <= 8
                and dataframe[category].nunique() <= 8
            ):
                chart_type = "pie"
                explanation = (
                    "A pie chart can illustrate the proportional "
                    "distribution of a small number of categories."
                )
            else:
                chart_type = "bar"
                explanation = (
                    "A bar chart is suitable for comparing numeric "
                    "values across categories."
                )

            recommendation.update({
                "recommended_chart": chart_type,
                "category_column": category,
                "value_column": value,
                "explanation": explanation,
            })

            return recommendation

        if len(numeric_columns) >= 2:
            recommendation.update({
                "recommended_chart": "scatter",
                "category_column": numeric_columns[0],
                "value_column": numeric_columns[1],
                "explanation": (
                    "A scatter plot can reveal relationships "
                    "between two numeric columns."
                ),
            })

            return recommendation

        if categorical_columns:
            recommendation.update({
                "recommended_chart": "bar",
                "category_column": categorical_columns[0],
                "explanation": (
                    "A bar chart can display the frequency "
                    "of categorical values."
                ),
            })

            return recommendation

        recommendation["explanation"] = (
            "The result structure does not provide enough "
            "information for an automatic chart recommendation."
        )

        return recommendation

    def create_chart(
        self,
        dataframe: pd.DataFrame,
        chart_type: str,
        x_column: Optional[str] = None,
        y_column: Optional[str] = None,
        color_column: Optional[str] = None,
        title: Optional[str] = None,
        height: Optional[int] = None,
    ) -> go.Figure:
        """
        Generate an interactive Plotly chart.

        Args:
            dataframe: Query result DataFrame.
            chart_type: bar, line, pie, scatter or histogram.
            x_column: Category or X-axis column.
            y_column: Numeric Y-axis column.
            color_column: Optional grouping column.
            title: Optional chart title.
            height: Optional chart height.
        """

        self._validate_dataframe(dataframe)

        chart_type = chart_type.strip().lower()

        if chart_type not in self.SUPPORTED_CHARTS:
            raise VisualizationError(
                f"Unsupported chart type: {chart_type}. "
                f"Supported types: {', '.join(sorted(self.SUPPORTED_CHARTS))}."
            )

        columns = dataframe.columns.tolist()

        if x_column and x_column not in columns:
            raise VisualizationError(
                f"Column '{x_column}' does not exist in the query results."
            )

        if y_column and y_column not in columns:
            raise VisualizationError(
                f"Column '{y_column}' does not exist in the query results."
            )

        if color_column and color_column not in columns:
            raise VisualizationError(
                f"Column '{color_column}' does not exist in the query results."
            )

        chart_height = height or self.default_height
        chart_title = title or "AURORA SQL Agent Visualization"

        try:
            if chart_type == "bar":
                if not x_column:
                    raise VisualizationError(
                        "A category column is required for a bar chart."
                    )

                chart_data = dataframe.copy()

                if not y_column:
                    chart_data = (
                        chart_data[x_column]
                        .value_counts()
                        .reset_index()
                    )

                    chart_data.columns = [
                        x_column,
                        "count",
                    ]

                    y_column = "count"

                figure = px.bar(
                    chart_data,
                    x=x_column,
                    y=y_column,
                    color=color_column,
                    title=chart_title,
                    height=chart_height,
                    labels={
                        x_column: x_column,
                        y_column: y_column,
                    },
                )

            elif chart_type == "line":
                if not x_column or not y_column:
                    raise VisualizationError(
                        "Both X and Y columns are required for a line chart."
                    )

                figure = px.line(
                    dataframe,
                    x=x_column,
                    y=y_column,
                    color=color_column,
                    markers=True,
                    title=chart_title,
                    height=chart_height,
                )

            elif chart_type == "pie":
                if not x_column:
                    raise VisualizationError(
                        "A category column is required for a pie chart."
                    )

                if not y_column:
                    chart_data = (
                        dataframe[x_column]
                        .value_counts()
                        .reset_index()
                    )

                    chart_data.columns = [
                        x_column,
                        "count",
                    ]

                    y_column = "count"

                else:
                    chart_data = dataframe

                figure = px.pie(
                    chart_data,
                    names=x_column,
                    values=y_column,
                    title=chart_title,
                    height=chart_height,
                )

            elif chart_type == "scatter":
                if not x_column or not y_column:
                    raise VisualizationError(
                        "Both X and Y columns are required "
                        "for a scatter plot."
                    )

                figure = px.scatter(
                    dataframe,
                    x=x_column,
                    y=y_column,
                    color=color_column,
                    title=chart_title,
                    height=chart_height,
                )

            else:
                if not x_column:
                    x_column = (
                        self._get_numeric_columns(dataframe) or [None]
                    )[0]

                if not x_column:
                    raise VisualizationError(
                        "A numeric column is required for a histogram."
                    )

                if x_column not in self._get_numeric_columns(dataframe):
                    raise VisualizationError(
                        "Histogram requires a numeric column."
                    )

                figure = px.histogram(
                    dataframe,
                    x=x_column,
                    color=color_column,
                    title=chart_title,
                    height=chart_height,
                )

            figure.update_layout(
                template="plotly_white",
                height=chart_height,
                margin={
                    "l": 40,
                    "r": 30,
                    "t": 65,
                    "b": 40,
                },
                legend_title_text="",
            )

            return figure

        except VisualizationError:
            raise

        except Exception as exc:
            raise VisualizationError(
                f"Unable to generate the requested chart: {exc}"
            ) from exc

    def create_recommended_chart(
        self,
        dataframe: pd.DataFrame,
        chart_type: Optional[str] = None,
        title: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Automatically recommend and generate a chart.

        An optional chart_type allows the user to override
        the automatically recommended chart.
        """

        recommendation = self.suggest_chart_type(dataframe)

        selected_chart = (
            chart_type or recommendation["recommended_chart"]
        )

        if not selected_chart:
            return {
                "success": False,
                "chart": None,
                "recommendation": recommendation,
                "error": recommendation["explanation"],
            }

        try:
            figure = self.create_chart(
                dataframe=dataframe,
                chart_type=selected_chart,
                x_column=recommendation["category_column"],
                y_column=recommendation["value_column"],
                title=title,
            )

            return {
                "success": True,
                "chart": figure,
                "chart_type": selected_chart,
                "recommendation": recommendation,
                "error": None,
            }

        except VisualizationError as exc:
            return {
                "success": False,
                "chart": None,
                "chart_type": selected_chart,
                "recommendation": recommendation,
                "error": str(exc),
            }


# Shared visualization tools instance
visualization_tools = VisualizationTools()

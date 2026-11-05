
"""
AURORA SQL Agent
Schema Agent

Discovers database metadata and identifies relevant tables and columns.
Uses deterministic fallback when Gemini analysis is unavailable.
"""

import json
import re
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI

from config import settings
from database.schema_discovery import (
    schema_discovery,
    SchemaDiscoveryError,
)
from database.metadata import metadata_manager
from graph.state import SQLAgentState


class SchemaAgentError(Exception):
    """Raised when schema discovery fails."""


class SchemaAgent:
    """Discovers and analyzes database schema information."""

    def __init__(self):
        self.model = None

        if settings.gemini_api_key:
            self.model = ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                google_api_key=settings.gemini_api_key,
                max_retries=settings.max_retries,
            )

    # --------------------------------------------------
    # Response handling
    # --------------------------------------------------

    @staticmethod
    def _extract_content(response: Any) -> str:
        """Extract text from a LangChain model response."""

        content = getattr(response, "content", response)

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts = []

            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and item.get("text"):
                    parts.append(item["text"])

            return "\n".join(parts).strip()

        return str(content).strip()

    @staticmethod
    def _parse_json(response_text: str) -> dict[str, Any]:
        """
        Parse Gemini JSON output.

        strict=False permits unescaped control characters inside
        JSON strings, a common cause of Gemini parsing failures.
        """

        if not isinstance(response_text, str) or not response_text.strip():
            raise SchemaAgentError("Gemini returned an empty response.")

        cleaned = response_text.strip()

        cleaned = re.sub(
            r"^\s*```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)

        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start == -1 or end == -1 or end <= start:
            raise SchemaAgentError(
                "Gemini did not return a valid JSON object."
            )

        candidate = cleaned[start:end + 1]

        try:
            result = json.loads(candidate, strict=False)
        except json.JSONDecodeError as exc:
            raise SchemaAgentError(
                "Gemini returned malformed schema analysis JSON."
            ) from exc

        if not isinstance(result, dict):
            raise SchemaAgentError(
                "Schema analysis must return a JSON object."
            )

        # Validate and normalize the expected fields.
        for key in (
            "relevant_tables",
            "relevant_columns",
            "relationships",
        ):
            value = result.get(key, [])
            if not isinstance(value, list):
                result[key] = []

        if not isinstance(result.get("reasoning", ""), str):
            result["reasoning"] = str(result.get("reasoning", ""))

        if not isinstance(result.get("clarification_needed", False), bool):
            result["clarification_needed"] = False

        if not isinstance(result.get("clarification_question", ""), str):
            result["clarification_question"] = ""

        return result

    # --------------------------------------------------
    # Schema discovery
    # --------------------------------------------------

    @staticmethod
    def _discover_schema(state: SQLAgentState) -> dict[str, Any]:
        """Retrieve database schema metadata."""

        schema_name = state.get("database_schema")

        try:
            metadata = metadata_manager.get_schema_metadata(
                schema=schema_name,
                include_views=True,
            )

            if metadata:
                return metadata

        except TypeError:
            try:
                metadata = metadata_manager.get_schema_metadata()
                if metadata:
                    return metadata
            except Exception:
                pass

        except Exception:
            pass

        try:
            metadata = schema_discovery.discover_schema(
                schema=schema_name,
                include_views=True,
            )

            if not metadata:
                raise SchemaAgentError(
                    "No schema metadata was returned by the database."
                )

            return metadata

        except SchemaDiscoveryError as exc:
            raise SchemaAgentError(
                f"Database schema discovery failed: {exc}"
            ) from exc

    # --------------------------------------------------
    # Schema normalization
    # --------------------------------------------------

    @staticmethod
    def _extract_table_names(metadata: Any) -> list[str]:
        """Extract table names from different metadata structures."""

        names = []

        def walk(value):
            if isinstance(value, dict):
                tables = value.get("tables", [])

                if isinstance(tables, dict):
                    names.extend(str(name) for name in tables)

                elif isinstance(tables, list):
                    for table in tables:
                        if isinstance(table, str):
                            names.append(table)
                        elif isinstance(table, dict):
                            name = (
                                table.get("name")
                                or table.get("table_name")
                            )
                            if name:
                                names.append(str(name))

                for key, nested in value.items():
                    if key != "tables":
                        walk(nested)

            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(metadata)
        return list(dict.fromkeys(names))

    @staticmethod
    def _extract_columns(metadata: Any) -> list[str]:
        """Extract fully qualified table.column references."""

        columns = []

        def walk(value, parent_table=""):
            if isinstance(value, dict):
                table = (
                    value.get("name")
                    or value.get("table_name")
                    or parent_table
                )

                column_items = value.get("columns", [])

                if isinstance(column_items, dict):
                    column_items = [
                        {"name": name} for name in column_items
                    ]

                if isinstance(column_items, list):
                    for column in column_items:
                        if isinstance(column, str):
                            name = column
                        elif isinstance(column, dict):
                            name = (
                                column.get("name")
                                or column.get("column_name")
                            )
                        else:
                            continue

                        if name:
                            reference = (
                                f"{table}.{name}" if table else str(name)
                            )
                            columns.append(reference)

                for key, nested in value.items():
                    if key != "columns":
                        walk(
                            nested,
                            str(table) if table else parent_table,
                        )

            elif isinstance(value, list):
                for item in value:
                    walk(item, parent_table)

        walk(metadata)
        return list(dict.fromkeys(columns))

    @staticmethod
    def _build_schema_context(
        metadata: dict[str, Any],
        relevant_tables: list[str],
    ) -> dict[str, Any]:
        """Build schema context while retaining metadata relationships."""

        if not isinstance(metadata, dict):
            return {"schema_metadata": metadata}

        tables = metadata.get("tables")

        if isinstance(tables, dict):
            selected = {
                name: details
                for name, details in tables.items()
                if name in relevant_tables
                or any(
                    str(name).endswith(f".{table}")
                    for table in relevant_tables
                )
            }

            if selected:
                return {
                    **{
                        key: value
                        for key, value in metadata.items()
                        if key != "tables"
                    },
                    "tables": selected,
                }

        if isinstance(tables, list):
            selected = []

            for table in tables:
                if isinstance(table, str):
                    name = table
                elif isinstance(table, dict):
                    name = table.get("name") or table.get("table_name")
                else:
                    continue

                if name and (
                    name in relevant_tables
                    or any(
                        str(name).endswith(f".{item}")
                        for item in relevant_tables
                    )
                ):
                    selected.append(table)

            if selected:
                return {
                    **{
                        key: value
                        for key, value in metadata.items()
                        if key != "tables"
                    },
                    "tables": selected,
                }

        return metadata

    # --------------------------------------------------
    # Deterministic fallback
    # --------------------------------------------------

    @staticmethod
    def _fallback_analysis(
        question: str,
        available_tables: list[str],
        available_columns: list[str],
    ) -> dict[str, Any]:
        """Select schema objects without relying on Gemini."""

        question_lower = question.lower()

        relevant_tables = []
        relevant_columns = []

        for table in available_tables:
            table_name = table.split(".")[-1].lower()

            if re.search(
                rf"(?<!\w){re.escape(table_name)}(?!\w)",
                question_lower,
            ):
                relevant_tables.append(table)

        for column in available_columns:
            table_name, separator, column_name = column.rpartition(".")

            if not separator:
                column_name = column
                table_name = ""

            if table_name and table_name in relevant_tables:
                relevant_columns.append(column)
            elif re.search(
                rf"(?<!\w){re.escape(column_name.lower())}(?!\w)",
                question_lower,
            ):
                relevant_columns.append(column)

        if not relevant_tables:
            relevant_tables = available_tables

        if not relevant_columns:
            relevant_columns = available_columns

        return {
            "relevant_tables": relevant_tables,
            "relevant_columns": relevant_columns,
            "relationships": [],
            "reasoning": (
                "Schema selection used discovered database metadata "
                "because AI schema analysis was unavailable."
            ),
            "clarification_needed": False,
            "clarification_question": "",
        }

    # --------------------------------------------------
    # Gemini schema analysis
    # --------------------------------------------------

    def _build_analysis_prompt(
        self,
        question: str,
        metadata: dict[str, Any],
    ) -> str:

        schema_json = json.dumps(
            metadata,
            indent=2,
            default=str,
            ensure_ascii=False,
        )

        return f"""
You are the Schema Analysis Agent of AURORA SQL Agent.

Identify the database tables and columns needed to answer the question.

USER QUESTION:
{question}

AVAILABLE DATABASE SCHEMA:
{schema_json}

Rules:
1. Use only existing tables and columns.
2. Include all tables needed for joins.
3. Identify relevant columns.
4. Do not generate SQL.
5. Do not invent schema objects.
6. For aggregate questions, identify the relevant numeric column.
7. Return one valid JSON object only.
8. Do not include Markdown fences or additional text.
9. Do not insert literal line breaks inside JSON string values.

Required JSON structure:
{{
  "relevant_tables": [],
  "relevant_columns": [],
  "relationships": [],
  "reasoning": "",
  "clarification_needed": false,
  "clarification_question": ""
}}
"""

    def _analyze_schema(
        self,
        question: str,
        metadata: dict[str, Any],
        available_tables: list[str],
        available_columns: list[str],
    ) -> dict[str, Any]:
        """Use Gemini, falling back safely if its response is invalid."""

        try:
            if self.model is None:
                raise SchemaAgentError(
                    "Gemini API key is not configured."
                )

            prompt = self._build_analysis_prompt(question, metadata)
            response = self.model.invoke(prompt)

            return self._parse_json(
                self._extract_content(response)
            )

        except Exception as exc:
            print(
                "Schema Agent: Gemini analysis unavailable. "
                f"Using deterministic fallback. Details: {exc}"
            )

            return self._fallback_analysis(
                question,
                available_tables,
                available_columns,
            )

    # --------------------------------------------------
    # Schema filtering
    # --------------------------------------------------

    @staticmethod
    def _filter_relevant_tables(
        selected_tables: list,
        available_tables: list[str],
    ) -> list[str]:

        valid = []

        for table in selected_tables:
            if not isinstance(table, str):
                continue

            if table in available_tables:
                valid.append(table)
                continue

            matches = [
                available
                for available in available_tables
                if available.split(".")[-1] == table.split(".")[-1]
            ]

            if len(matches) == 1:
                valid.append(matches[0])

        return list(dict.fromkeys(valid))

    @staticmethod
    def _filter_relevant_columns(
        selected_columns: list,
        available_columns: list[str],
    ) -> list[str]:

        valid = []

        for column in selected_columns:
            if not isinstance(column, str):
                continue

            if column in available_columns:
                valid.append(column)
                continue

            matches = [
                available
                for available in available_columns
                if available.split(".")[-1] == column.split(".")[-1]
            ]

            if len(matches) == 1:
                valid.append(matches[0])

        return list(dict.fromkeys(valid))

    # --------------------------------------------------
    # Main execution
    # --------------------------------------------------

    def run(self, state: SQLAgentState) -> dict[str, Any]:

        if not state.get("database_connected", False):
            return {
                "error": "Database is not connected.",
                "error_type": "DatabaseConnectionError",
                "workflow_status": "failed",
                "current_agent": "schema_agent",
            }

        try:
            question = state.get("user_question", "").strip()

            metadata = self._discover_schema(state)

            available_tables = self._extract_table_names(metadata)
            available_columns = self._extract_columns(metadata)

            if not available_tables:
                raise SchemaAgentError(
                    "No tables or views were discovered "
                    "in the connected database."
                )

            analysis = self._analyze_schema(
                question,
                metadata,
                available_tables,
                available_columns,
            )

            if analysis.get("clarification_needed", False):
                clarification = str(
                    analysis.get("clarification_question", "")
                ).strip()

                if not clarification:
                    clarification = (
                        "Could you clarify which data or tables "
                        "you want to query?"
                    )

                return {
                    "schema_metadata": metadata,
                    "clarification_needed": True,
                    "clarification_question": clarification,
                    "final_response": clarification,
                    "workflow_status": "clarification_required",
                    "current_agent": "schema_agent",
                }

            relevant_tables = self._filter_relevant_tables(
                analysis.get("relevant_tables", []),
                available_tables,
            )

            relevant_columns = self._filter_relevant_columns(
                analysis.get("relevant_columns", []),
                available_columns,
            )

            if not relevant_tables:
                relevant_tables = available_tables

            relevant_schema = self._build_schema_context(
                metadata,
                relevant_tables,
            )

            return {
                "schema_metadata": metadata,
                "relevant_schema": relevant_schema,
                "relevant_tables": relevant_tables,
                "relevant_columns": relevant_columns,
                "schema_context": json.dumps(
                    relevant_schema,
                    indent=2,
                    default=str,
                ),
                "schema_reasoning": str(
                    analysis.get("reasoning", "")
                ),
                "current_agent": "schema_agent",
                "workflow_status": "running",
                "error": None,
                "error_type": None,
            }

        except SchemaAgentError as exc:
            return {
                "error": str(exc),
                "error_type": "SchemaAgentError",
                "workflow_status": "failed",
                "current_agent": "schema_agent",
            }

        except Exception as exc:
            print(f"Schema Agent error: {exc}")

            return {
                "error": f"Schema Agent failed: {exc}",
                "error_type": "SchemaAgentError",
                "workflow_status": "failed",
                "current_agent": "schema_agent",
            }


# Shared schema agent instance
schema_agent = SchemaAgent()


def run(state: SQLAgentState) -> dict[str, Any]:
    """Entry point used by LangGraph."""

    return schema_agent.run(state)


"""
AURORA SQL Agent
Query Optimizer

Responsibilities:
- Analyze SQL query structure.
- Identify potential performance issues.
- Recommend indexing opportunities.
- Detect SELECT * usage.
- Identify missing row limits.
- Inspect joins and filtering conditions.
- Generate optimization recommendations.

Note:
This module provides recommendations only.
It does not automatically modify or execute SQL.
"""

from typing import Any, Optional

from sqlglot import exp

from tools.sql_parser import SQLParser, SQLParserError, sql_parser


class QueryOptimizationError(Exception):
    """Raised when query optimization analysis fails."""


class QueryOptimizer:
    """Analyzes SQL queries and generates optimization suggestions."""

    def __init__(
        self,
        parser: Optional[SQLParser] = None,
    ):
        self.parser = parser or sql_parser

    def analyze(
        self,
        sql: str,
        dialect: str = "postgres",
    ) -> dict[str, Any]:
        """
        Analyze SQL and return optimization recommendations.

        Returns:
            success
            dialect
            tables
            issues
            recommendations
            optimization_score
            summary
        """

        if not sql or not sql.strip():
            raise QueryOptimizationError(
                "SQL query cannot be empty."
            )

        try:
            normalized_dialect = self.parser.normalize_dialect(
                dialect
            )

            expression = self.parser.parse_single(
                sql,
                normalized_dialect,
            )

            issues = []

            self._check_select_star(expression, issues)
            self._check_missing_limit(expression, issues)
            self._check_joins(expression, issues)
            self._check_filter_conditions(expression, issues)
            self._check_nested_queries(expression, issues)
            self._check_distinct_usage(expression, issues)
            self._check_order_by(expression, issues)
            self._check_functions_in_conditions(expression, issues)

            tables = (
                self.parser.extract_tables_from_expression(
                    expression
                )
            )

            recommendations = [
                issue["recommendation"]
                for issue in issues
            ]

            score = self._calculate_score(issues)

            return {
                "success": True,
                "dialect": normalized_dialect,
                "tables": tables,
                "issues": issues,
                "recommendations": recommendations,
                "optimization_score": score,
                "summary": self._generate_summary(
                    issues,
                    score,
                ),
            }

        except SQLParserError as exc:
            raise QueryOptimizationError(
                f"Unable to analyze SQL: {exc}"
            ) from exc

        except QueryOptimizationError:
            raise

        except Exception as exc:
            raise QueryOptimizationError(
                "An unexpected error occurred during query analysis."
            ) from exc

    @staticmethod
    def _add_issue(
        issues: list[dict[str, str]],
        severity: str,
        category: str,
        message: str,
        recommendation: str,
    ) -> None:
        """Add a structured optimization issue."""

        issues.append(
            {
                "severity": severity,
                "category": category,
                "message": message,
                "recommendation": recommendation,
            }
        )

    def _check_select_star(
        self,
        expression: exp.Expression,
        issues: list[dict[str, str]],
    ) -> None:
        """Identify SELECT * usage."""

        for select in expression.find_all(exp.Select):
            for projection in select.expressions:
                if isinstance(projection, exp.Star):
                    self._add_issue(
                        issues,
                        "medium",
                        "SELECT *",
                        "The query retrieves all columns.",
                        (
                            "Select only the columns required by the "
                            "application to reduce data transfer."
                        ),
                    )
                    return

                if isinstance(projection, exp.Column):
                    if isinstance(projection.this, exp.Star):
                        self._add_issue(
                            issues,
                            "medium",
                            "SELECT *",
                            "The query retrieves all columns.",
                            (
                                "Select only the columns required by the "
                                "application to reduce data transfer."
                            ),
                        )
                        return

    def _check_missing_limit(
        self,
        expression: exp.Expression,
        issues: list[dict[str, str]],
    ) -> None:
        """Identify queries without an explicit row limit."""

        if not expression.find(exp.Limit):
            self._add_issue(
                issues,
                "low",
                "Missing LIMIT",
                "The query does not specify a row limit.",
                (
                    "Consider adding LIMIT to restrict the number "
                    "of returned records, especially for large tables."
                ),
            )

    def _check_joins(
        self,
        expression: exp.Expression,
        issues: list[dict[str, str]],
    ) -> None:
        """Inspect JOIN operations."""

        joins = list(expression.find_all(exp.Join))

        for join in joins:
            join_type = (
                join.args.get("kind")
                or join.args.get("side")
                or "JOIN"
            )

            if join.args.get("on") is None and join.args.get("using") is None:
                self._add_issue(
                    issues,
                    "high",
                    "JOIN condition",
                    (
                        f"The {join_type} operation does not contain "
                        "an explicit ON or USING condition."
                    ),
                    (
                        "Review the join carefully. Ensure that the "
                        "relationship between the tables is intentional."
                    ),
                )

    def _check_filter_conditions(
        self,
        expression: exp.Expression,
        issues: list[dict[str, str]],
    ) -> None:
        """Identify queries without filtering conditions."""

        selects = list(expression.find_all(exp.Select))

        for select in selects:
            if (
                select.args.get("where") is None
                and select.args.get("limit") is None
            ):
                self._add_issue(
                    issues,
                    "low",
                    "Missing filter",
                    (
                        "A SELECT statement has no WHERE condition "
                        "or explicit LIMIT."
                    ),
                    (
                        "Consider filtering records using WHERE "
                        "or restricting the returned rows."
                    ),
                )

                return

    def _check_nested_queries(
        self,
        expression: exp.Expression,
        issues: list[dict[str, str]],
    ) -> None:
        """Identify deeply nested subqueries."""

        subqueries = list(expression.find_all(exp.Subquery))

        if len(subqueries) >= 3:
            self._add_issue(
                issues,
                "medium",
                "Nested subqueries",
                (
                    f"The query contains {len(subqueries)} "
                    "nested or embedded subquery expressions."
                ),
                (
                    "Review whether some subqueries can be simplified "
                    "using JOINs or common table expressions."
                ),
            )

    def _check_distinct_usage(
        self,
        expression: exp.Expression,
        issues: list[dict[str, str]],
    ) -> None:
        """Identify DISTINCT operations for review."""

        for select in expression.find_all(exp.Select):
            if select.args.get("distinct") is not None:
                self._add_issue(
                    issues,
                    "low",
                    "DISTINCT operation",
                    (
                        "The query uses DISTINCT, which may require "
                        "additional sorting or hashing."
                    ),
                    (
                        "Confirm that duplicate removal is necessary. "
                        "Remove DISTINCT if the underlying query "
                        "already produces unique records."
                    ),
                )
                return

    def _check_order_by(
        self,
        expression: exp.Expression,
        issues: list[dict[str, str]],
    ) -> None:
        """Identify ORDER BY operations without a row limit."""

        for select in expression.find_all(exp.Select):
            if (
                select.args.get("order") is not None
                and select.args.get("limit") is None
            ):
                self._add_issue(
                    issues,
                    "low",
                    "ORDER BY without LIMIT",
                    (
                        "The query sorts records without restricting "
                        "the number of returned rows."
                    ),
                    (
                        "Consider combining ORDER BY with LIMIT "
                        "when only the top or latest records are needed."
                    ),
                )
                return

    def _check_functions_in_conditions(
        self,
        expression: exp.Expression,
        issues: list[dict[str, str]],
    ) -> None:
        """Identify function calls inside WHERE conditions."""

        for where in expression.find_all(exp.Where):
            functions = list(where.find_all(exp.Func))

            if functions:
                self._add_issue(
                    issues,
                    "medium",
                    "Functions in WHERE",
                    (
                        "The WHERE condition contains function calls. "
                        "Some function-based predicates may prevent "
                        "ordinary index usage."
                    ),
                    (
                        "Check the query execution plan. Where "
                        "appropriate, consider rewriting the predicate "
                        "or creating a suitable expression index."
                    ),
                )
                return

    @staticmethod
    def _calculate_score(
        issues: list[dict[str, str]],
    ) -> int:
        """
        Calculate a heuristic optimization score.

        This is an advisory score, not a measured performance metric.
        """

        score = 100

        deductions = {
            "high": 20,
            "medium": 10,
            "low": 5,
        }

        for issue in issues:
            score -= deductions.get(
                issue["severity"],
                0,
            )

        return max(0, min(100, score))

    @staticmethod
    def _generate_summary(
        issues: list[dict[str, str]],
        score: int,
    ) -> str:
        """Generate a readable optimization summary."""

        if not issues:
            return (
                "No common SQL optimization concerns were detected. "
                "This does not guarantee optimal query performance."
            )

        return (
            f"Identified {len(issues)} potential optimization "
            f"concern(s). The heuristic optimization score is "
            f"{score}/100. Review the recommendations before "
            "changing the query."
        )

    def get_recommendations(
        self,
        sql: str,
        dialect: str = "postgres",
    ) -> list[str]:
        """Return only optimization recommendations."""

        result = self.analyze(sql, dialect)

        return result["recommendations"]


# Shared query optimizer instance
query_optimizer = QueryOptimizer()

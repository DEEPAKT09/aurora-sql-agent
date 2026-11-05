
"""
AURORA SQL Agent
Evaluation Metrics

Calculates performance metrics for natural-language-to-SQL
generation, validation, execution and result evaluation.
"""

from typing import Any, Optional

import math
import re


# ---------------------------------------------------------
# GENERAL METRIC HELPERS
# ---------------------------------------------------------

def safe_percentage(
    numerator: int,
    denominator: int,
) -> float:
    """Calculate a percentage safely."""

    if denominator <= 0:
        return 0.0

    return round(
        (numerator / denominator) * 100,
        2,
    )


def safe_average(values: list[float]) -> float:
    """Calculate the average of numeric values."""

    valid_values = []

    for value in values:
        try:
            number = float(value)

            if math.isfinite(number):
                valid_values.append(number)

        except (TypeError, ValueError, OverflowError):
            continue

    if not valid_values:
        return 0.0

    return round(
        sum(valid_values) / len(valid_values),
        4,
    )


# ---------------------------------------------------------
# SQL GENERATION METRICS
# ---------------------------------------------------------

def calculate_exact_match_accuracy(
    generated_queries: list[str],
    expected_queries: list[str],
) -> dict[str, Any]:
    """
    Calculate exact SQL string match accuracy.

    Note:
        This is a strict string comparison. Queries that
        are semantically equivalent but formatted differently
        may not count as exact matches.
    """

    if len(generated_queries) != len(expected_queries):
        raise ValueError(
            "Generated and expected query lists "
            "must have equal lengths."
        )

    total = len(expected_queries)

    if total == 0:
        return {
            "total": 0,
            "correct": 0,
            "accuracy": 0.0,
        }

    correct = sum(
        1
        for generated, expected in zip(
            generated_queries,
            expected_queries,
        )
        if normalize_sql(generated) == normalize_sql(expected)
    )

    return {
        "total": total,
        "correct": correct,
        "accuracy": safe_percentage(correct, total),
    }


def normalize_sql(sql: Optional[str]) -> str:
    """
    Normalize SQL for basic textual comparison.

    Removes surrounding whitespace, normalizes case
    and collapses repeated whitespace.

    This does not establish SQL semantic equivalence.
    """

    if not sql:
        return ""

    normalized = str(sql).strip().rstrip(";")
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.lower()


# ---------------------------------------------------------
# SQL VALIDATION METRICS
# ---------------------------------------------------------

def calculate_validation_metrics(
    validation_results: list[dict],
) -> dict[str, Any]:
    """Calculate SQL validation success and failure rates."""

    total = len(validation_results)

    valid_count = sum(
        1
        for result in validation_results
        if result.get(
            "is_valid",
            result.get("valid", False),
        )
    )

    invalid_count = total - valid_count

    return {
        "total": total,
        "valid": valid_count,
        "invalid": invalid_count,
        "validation_success_rate": safe_percentage(
            valid_count,
            total,
        ),
        "validation_failure_rate": safe_percentage(
            invalid_count,
            total,
        ),
    }


# ---------------------------------------------------------
# SQL EXECUTION METRICS
# ---------------------------------------------------------

def calculate_execution_metrics(
    execution_results: list[dict],
) -> dict[str, Any]:
    """
    Calculate SQL execution success rate and performance.

    Expected result fields:
        success
        execution_time
        row_count
    """

    total = len(execution_results)

    successful = [
        result
        for result in execution_results
        if result.get("success", False)
    ]

    failed = total - len(successful)

    execution_times = [
        result.get("execution_time", 0)
        for result in successful
    ]

    row_counts = [
        result.get("row_count", 0)
        for result in successful
    ]

    return {
        "total_queries": total,
        "successful_queries": len(successful),
        "failed_queries": failed,
        "execution_success_rate": safe_percentage(
            len(successful),
            total,
        ),
        "execution_failure_rate": safe_percentage(
            failed,
            total,
        ),
        "average_execution_time": safe_average(
            execution_times
        ),
        "average_rows_returned": safe_average(
            row_counts
        ),
    }


# ---------------------------------------------------------
# RESULT CORRECTNESS METRICS
# ---------------------------------------------------------

def calculate_result_accuracy(
    actual_results: list[Any],
    expected_results: list[Any],
) -> dict[str, Any]:
    """
    Compare actual query results with expected results.

    Comparison is order-sensitive by default.

    Values are normalized for common Python/database
    serialization differences.
    """

    if len(actual_results) != len(expected_results):
        raise ValueError(
            "Actual and expected result lists "
            "must have equal lengths."
        )

    total = len(expected_results)

    if total == 0:
        return {
            "total": 0,
            "correct": 0,
            "accuracy": 0.0,
        }

    correct = 0

    for actual, expected in zip(
        actual_results,
        expected_results,
    ):
        if normalize_result(actual) == normalize_result(expected):
            correct += 1

    return {
        "total": total,
        "correct": correct,
        "accuracy": safe_percentage(correct, total),
    }


def normalize_result(value: Any) -> Any:
    """Normalize values for result comparison."""

    if isinstance(value, dict):
        return {
            str(key): normalize_result(item)
            for key, item in sorted(
                value.items(),
                key=lambda pair: str(pair[0]),
            )
        }

    if isinstance(value, (list, tuple)):
        return [
            normalize_result(item)
            for item in value
        ]

    if isinstance(value, float):
        if not math.isfinite(value):
            return None

        return round(value, 8)

    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except (ValueError, TypeError):
            pass

    if hasattr(value, "item") and callable(value.item):
        try:
            return normalize_result(value.item())
        except (ValueError, TypeError):
            pass

    return value


# ---------------------------------------------------------
# LATENCY METRICS
# ---------------------------------------------------------

def calculate_latency_metrics(
    execution_times: list[float],
) -> dict[str, Any]:
    """
    Calculate average, minimum and maximum query latency.
    """

    valid_times = []

    for value in execution_times:
        try:
            number = float(value)

            if math.isfinite(number) and number >= 0:
                valid_times.append(number)

        except (TypeError, ValueError, OverflowError):
            continue

    if not valid_times:
        return {
            "count": 0,
            "average": 0.0,
            "minimum": 0.0,
            "maximum": 0.0,
        }

    return {
        "count": len(valid_times),
        "average": safe_average(valid_times),
        "minimum": round(min(valid_times), 4),
        "maximum": round(max(valid_times), 4),
    }


# ---------------------------------------------------------
# OVERALL PERFORMANCE METRICS
# ---------------------------------------------------------

def calculate_overall_metrics(
    generated_queries: Optional[list[str]] = None,
    expected_queries: Optional[list[str]] = None,
    validation_results: Optional[list[dict]] = None,
    execution_results: Optional[list[dict]] = None,
    actual_results: Optional[list[Any]] = None,
    expected_results: Optional[list[Any]] = None,
) -> dict[str, Any]:
    """
    Calculate a consolidated evaluation report.

    Only metrics for which input data is provided
    are included.
    """

    report = {}

    if (
        generated_queries is not None
        and expected_queries is not None
    ):
        report["sql_generation"] = (
            calculate_exact_match_accuracy(
                generated_queries,
                expected_queries,
            )
        )

    if validation_results is not None:
        report["sql_validation"] = (
            calculate_validation_metrics(
                validation_results
            )
        )

    if execution_results is not None:
        report["sql_execution"] = (
            calculate_execution_metrics(
                execution_results
            )
        )

    if (
        actual_results is not None
        and expected_results is not None
    ):
        report["result_accuracy"] = (
            calculate_result_accuracy(
                actual_results,
                expected_results,
            )
        )

    return report


# ---------------------------------------------------------
# EVALUATION SUMMARY
# ---------------------------------------------------------

def generate_evaluation_summary(
    metrics: dict[str, Any],
) -> str:
    """Generate a readable evaluation summary."""

    if not metrics:
        return "No evaluation metrics are available."

    lines = [
        "AURORA SQL Agent - Evaluation Summary",
        "=" * 42,
    ]

    for category, values in metrics.items():
        lines.append("")
        lines.append(
            category.replace("_", " ").title()
        )

        if not isinstance(values, dict):
            lines.append(str(values))
            continue

        for metric_name, metric_value in values.items():
            label = metric_name.replace("_", " ").title()

            if isinstance(metric_value, float):
                display_value = f"{metric_value:.2f}"
            else:
                display_value = str(metric_value)

            lines.append(
                f"{label}: {display_value}"
            )

    return "\n".join(lines)

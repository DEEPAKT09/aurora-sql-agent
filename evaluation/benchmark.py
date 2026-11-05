
"""
AURORA SQL Agent
Benchmark Runner

Runs predefined natural-language-to-SQL test cases
through the multi-agent workflow and evaluates performance.

Expected test case structure:

{
    "id": "TC001",
    "question": "Show all customers",
    "expected_sql": "SELECT * FROM customers",
    "expected_results": [
        {"id": 1, "name": "John"}
    ]
}
"""

import json
import logging

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from evaluation.metrics import (
    calculate_exact_match_accuracy,
    calculate_execution_metrics,
    calculate_result_accuracy,
    calculate_validation_metrics,
    generate_evaluation_summary,
)

from graph.state import create_initial_state
from graph.workflow import run_workflow


logger = logging.getLogger("aurora_sql_agent.benchmark")


# ---------------------------------------------------------
# BENCHMARK CONFIGURATION
# ---------------------------------------------------------

DEFAULT_TEST_CASES_PATH = (
    Path(__file__).parent / "test_cases.json"
)

DEFAULT_RESULTS_DIRECTORY = (
    Path(__file__).parent / "results"
)


# ---------------------------------------------------------
# BENCHMARK ERRORS
# ---------------------------------------------------------

class BenchmarkError(Exception):
    """Raised when benchmark execution fails."""


# ---------------------------------------------------------
# BENCHMARK RUNNER
# ---------------------------------------------------------

class BenchmarkRunner:
    """
    Executes benchmark test cases against AURORA SQL Agent.

    The caller must provide an active database configuration.
    The benchmark uses the existing LangGraph workflow.
    """

    def __init__(
        self,
        database_type: str,
        database_name: str,
        database_config: Any,
        database_schema: Optional[str] = None,
        test_cases_path: Optional[str] = None,
        results_directory: Optional[str] = None,
    ):
        self.database_type = database_type
        self.database_name = database_name
        self.database_config = database_config
        self.database_schema = database_schema

        self.test_cases_path = Path(
            test_cases_path or DEFAULT_TEST_CASES_PATH
        )

        self.results_directory = Path(
            results_directory or DEFAULT_RESULTS_DIRECTORY
        )

        self.results: list[dict[str, Any]] = []

    # -----------------------------------------------------
    # LOAD TEST CASES
    # -----------------------------------------------------

    def load_test_cases(self) -> list[dict[str, Any]]:
        """
        Load benchmark test cases from a JSON file.
        """

        if not self.test_cases_path.exists():
            raise BenchmarkError(
                f"Test cases file not found: "
                f"{self.test_cases_path}"
            )

        try:
            with self.test_cases_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                test_cases = json.load(file)

        except json.JSONDecodeError as exc:
            raise BenchmarkError(
                f"Invalid test cases JSON: {exc}"
            ) from exc

        except OSError as exc:
            raise BenchmarkError(
                f"Unable to read test cases file: {exc}"
            ) from exc

        if not isinstance(test_cases, list):
            raise BenchmarkError(
                "The test cases file must contain a JSON list."
            )

        for index, test_case in enumerate(test_cases):
            if not isinstance(test_case, dict):
                raise BenchmarkError(
                    f"Test case at index {index} must be an object."
                )

            if not test_case.get("question"):
                raise BenchmarkError(
                    f"Test case at index {index} "
                    "is missing its question."
                )

        return test_cases

    # -----------------------------------------------------
    # RUN SINGLE TEST CASE
    # -----------------------------------------------------

    def run_test_case(
        self,
        test_case: dict[str, Any],
        conversation_history: Optional[list] = None,
    ) -> dict[str, Any]:
        """
        Execute one benchmark test case.

        Returns generated SQL, validation information,
        execution information and optional accuracy metrics.
        """

        test_id = test_case.get(
            "id",
            "UNKNOWN",
        )

        question = test_case["question"]

        logger.info(
            "Running benchmark test case: %s",
            test_id,
        )

        initial_state = create_initial_state(
            user_question=question,
            database_connected=True,
            database_type=self.database_type,
            database_name=self.database_name,
            database_schema=self.database_schema,
            conversation_history=conversation_history or [],
            database_config=self.database_config,
        )

        started_at = datetime.now()

        try:
            workflow_result = run_workflow(
                initial_state=initial_state
            )

            elapsed_time = (
                datetime.now() - started_at
            ).total_seconds()

            generated_sql = (
                workflow_result.get("generated_sql")
                or ""
            )

            validation_result = (
                workflow_result.get("validation_result")
                or {}
            )

            execution_result = (
                workflow_result.get("execution_result")
                or {}
            )

            actual_records = (
                execution_result.get("records")
                or []
            )

            result = {
                "test_id": test_id,
                "question": question,
                "status": workflow_result.get(
                    "workflow_status",
                    "unknown",
                ),
                "generated_sql": generated_sql,
                "expected_sql": test_case.get("expected_sql"),
                "sql_valid": workflow_result.get(
                    "sql_valid",
                    False,
                ),
                "validation_result": validation_result,
                "execution_success": execution_result.get(
                    "success",
                    workflow_result.get(
                        "execution_success",
                        False,
                    ),
                ),
                "execution_time": execution_result.get(
                    "execution_time",
                    0,
                ),
                "row_count": execution_result.get(
                    "row_count",
                    len(actual_records),
                ),
                "actual_results": actual_records,
                "expected_results": test_case.get(
                    "expected_results"
                ),
                "total_workflow_time": round(
                    elapsed_time,
                    4,
                ),
                "error": (
                    workflow_result.get("error")
                    or execution_result.get("error")
                ),
                "workflow_trace": workflow_result.get(
                    "workflow_trace",
                    [],
                ),
            }

            # Exact SQL comparison.
            expected_sql = test_case.get("expected_sql")

            if expected_sql is not None:
                result["sql_exact_match"] = (
                    calculate_exact_match_accuracy(
                        [generated_sql],
                        [expected_sql],
                    )
                )

            # Result comparison.
            expected_results = test_case.get(
                "expected_results"
            )

            if expected_results is not None:
                result["result_accuracy"] = (
                    calculate_result_accuracy(
                        actual_records,
                        expected_results,
                    )
                )

            logger.info(
                "Benchmark test case completed: %s",
                test_id,
            )

            return result

        except Exception as exc:
            elapsed_time = (
                datetime.now() - started_at
            ).total_seconds()

            logger.exception(
                "Benchmark test case failed: %s",
                test_id,
            )

            return {
                "test_id": test_id,
                "question": question,
                "status": "failed",
                "generated_sql": "",
                "expected_sql": test_case.get("expected_sql"),
                "sql_valid": False,
                "execution_success": False,
                "execution_time": 0,
                "row_count": 0,
                "actual_results": [],
                "expected_results": test_case.get(
                    "expected_results"
                ),
                "total_workflow_time": round(
                    elapsed_time,
                    4,
                ),
                "error": str(exc),
                "workflow_trace": [],
            }

    # -----------------------------------------------------
    # RUN COMPLETE BENCHMARK
    # -----------------------------------------------------

    def run_benchmark(
        self,
        test_cases: Optional[list[dict]] = None,
    ) -> dict[str, Any]:
        """
        Execute all benchmark test cases.

        If test_cases is not provided, load them from
        the configured JSON file.
        """

        cases = (
            test_cases
            if test_cases is not None
            else self.load_test_cases()
        )

        if not cases:
            raise BenchmarkError(
                "No benchmark test cases were provided."
            )

        self.results = []

        logger.info(
            "Starting benchmark with %d test cases.",
            len(cases),
        )

        for test_case in cases:
            result = self.run_test_case(test_case)
            self.results.append(result)

        report = self.generate_report()

        logger.info(
            "Benchmark completed. Total cases: %d",
            len(self.results),
        )

        return report

    # -----------------------------------------------------
    # GENERATE EVALUATION REPORT
    # -----------------------------------------------------

    def generate_report(self) -> dict[str, Any]:
        """
        Generate consolidated benchmark metrics.
        """

        total = len(self.results)

        if total == 0:
            raise BenchmarkError(
                "No benchmark results are available."
            )

        generated_queries = [
            result.get("generated_sql", "")
            for result in self.results
            if result.get("expected_sql") is not None
        ]

        expected_queries = [
            result.get("expected_sql", "")
            for result in self.results
            if result.get("expected_sql") is not None
        ]

        validation_results = [
            {
                "is_valid": result.get(
                    "sql_valid",
                    False,
                )
            }
            for result in self.results
        ]

        execution_results = [
            {
                "success": result.get(
                    "execution_success",
                    False,
                ),
                "execution_time": result.get(
                    "execution_time",
                    0,
                ),
                "row_count": result.get(
                    "row_count",
                    0,
                ),
            }
            for result in self.results
        ]

        # Only compare results for test cases that
        # explicitly provide expected results.
        result_pairs = [
            result
            for result in self.results
            if result.get("expected_results") is not None
        ]

        metrics = {
            "total_test_cases": total,
            "passed_execution": sum(
                1
                for result in self.results
                if result.get("execution_success")
            ),
            "failed_execution": sum(
                1
                for result in self.results
                if not result.get("execution_success")
            ),
            "workflow_success_rate": round(
                (
                    sum(
                        1
                        for result in self.results
                        if result.get("status") == "completed"
                    ) / total
                ) * 100,
                2,
            ),
            "validation": calculate_validation_metrics(
                validation_results
            ),
            "execution": calculate_execution_metrics(
                execution_results
            ),
            "total_workflow_time": round(
                sum(
                    result.get("total_workflow_time", 0)
                    for result in self.results
                ),
                4,
            ),
        }

        if generated_queries:
            metrics["sql_generation"] = (
                calculate_exact_match_accuracy(
                    generated_queries,
                    expected_queries,
                )
            )

        if result_pairs:
            metrics["result_accuracy"] = (
                calculate_result_accuracy(
                    [
                        result.get("actual_results", [])
                        for result in result_pairs
                    ],
                    [
                        result.get("expected_results", [])
                        for result in result_pairs
                    ],
                )
            )

        return {
            "benchmark_name": "AURORA SQL Agent Benchmark",
            "generated_at": datetime.now().isoformat(),
            "metrics": metrics,
            "summary": generate_evaluation_summary(metrics),
            "test_results": self.results,
        }

    # -----------------------------------------------------
    # SAVE BENCHMARK REPORT
    # -----------------------------------------------------

    def save_report(
        self,
        report: Optional[dict] = None,
        filename: Optional[str] = None,
    ) -> str:
        """
        Save benchmark results as a JSON report.

        Returns the saved report path.
        """

        report = report or self.generate_report()

        self.results_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        if filename is None:
            timestamp = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )

            filename = (
                f"benchmark_report_{timestamp}.json"
            )

        output_path = (
            self.results_directory / filename
        )

        try:
            with output_path.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    report,
                    file,
                    indent=4,
                    ensure_ascii=False,
                    default=str,
                )

        except OSError as exc:
            raise BenchmarkError(
                f"Unable to save benchmark report: {exc}"
            ) from exc

        logger.info(
            "Benchmark report saved: %s",
            output_path,
        )

        return str(output_path)

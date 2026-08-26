from __future__ import annotations

import unittest

from evaluate import (
    classify_failure,
    compare_result_sets,
    metric_contract,
    merge_runs,
    read_json,
    validate_case_contract,
    M6_DIR,
)


class M6EvaluateTest(unittest.TestCase):

    def test_versioned_case_contract_has_required_category_counts(self) -> None:
        validate_case_contract(read_json(M6_DIR / "cases.json"))

    def test_result_comparison_ignores_aliases_order_and_decimal_scale(self) -> None:
        actual = {
            "columns": ["generated_name", "generated_amount"],
            "rows": [
                {"generated_name": "华东一部", "generated_amount": "100.000000"},
                {"generated_name": "华南一部", "generated_amount": "80"},
            ],
        }
        expected = {
            "columns": ["department_name", "sales_amount"],
            "rows": [
                {"department_name": "华南一部", "sales_amount": "80.00"},
                {"department_name": "华东一部", "sales_amount": "100.00"},
            ],
        }

        self.assertTrue(compare_result_sets(actual, expected)["passed"])

    def test_result_comparison_rejects_partial_rows(self) -> None:
        actual = {"columns": ["value"], "rows": [{"value": "1"}]}
        expected = {"columns": ["value"], "rows": [{"value": "1"}, {"value": "2"}]}

        comparison = compare_result_sets(actual, expected)

        self.assertFalse(comparison["passed"])
        self.assertEqual("row_count_mismatch", comparison["reason"])

    def test_result_comparison_allows_extra_derived_columns(self) -> None:
        actual = {
            "columns": ["department_name", "sales_amount", "sales_rank"],
            "rows": [
                {"department_name": "华东一部", "sales_amount": "100.00", "sales_rank": "1"}
            ],
        }
        expected = {
            "columns": ["department_name", "sales_amount"],
            "rows": [{"department_name": "华东一部", "sales_amount": "100.00"}],
        }

        self.assertTrue(compare_result_sets(actual, expected)["passed"])

    def test_early_clean_termination_is_a_distinct_failure(self) -> None:
        run = {"complete": True, "sql": [], "resultSets": [], "errors": [], "streamError": None}

        self.assertEqual("early_clean_termination", classify_failure(run))

    def test_metric_contract_requires_every_concept_group(self) -> None:
        case = {"conceptGroups": [["sum"], ["total_amount"], ["approved"]]}

        self.assertTrue(
            metric_contract(
                case,
                ["SELECT SUM(total_amount) FROM sales_order WHERE status = 'APPROVED'"],
            )["passed"]
        )
        self.assertFalse(metric_contract(case, ["SELECT SUM(total_amount) FROM sales_order"])["passed"])

    def test_merge_runs_keeps_complete_base_and_replaces_improved_rerun(self) -> None:
        base = [
            {"id": "Q1", "passed": False, "metricCorrect": False, "resultCorrect": False,
             "sqlExecutable": False, "nodes": []},
            {"id": "Q2", "passed": True, "metricCorrect": False, "resultCorrect": True,
             "sqlExecutable": True, "nodes": [{}]},
        ]
        rerun = [
            {"id": "Q1", "passed": True, "metricCorrect": True, "resultCorrect": True,
             "sqlExecutable": True, "nodes": [{}]},
        ]

        merged = merge_runs(base, rerun)

        self.assertEqual(["Q1", "Q2"], [run["id"] for run in merged])
        self.assertTrue(merged[0]["passed"])


if __name__ == "__main__":
    unittest.main()

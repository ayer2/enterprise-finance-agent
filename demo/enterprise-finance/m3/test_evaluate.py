from __future__ import annotations

import unittest

from evaluate import analysis_run_passed, merge_analysis_runs


def run(case_id: str, *, report: str = "", complete: bool = True) -> dict:
    return {
        "id": case_id,
        "complete": complete,
        "errors": [],
        "streamError": None,
        "sql": ["SELECT 1"],
        "resultSets": [{"rowCount": 1}],
        "report": report,
        "nodes": [{"nodeName": "SqlExecuteNode"}],
    }


class EvaluateTest(unittest.TestCase):

    def test_analysis_requires_report_evidence_contract(self) -> None:
        self.assertFalse(analysis_run_passed(run("Q1", report="# 结果")))
        self.assertTrue(analysis_run_passed(run("Q1", report="# 结果\n## 数据口径与查询依据")))
        self.assertTrue(analysis_run_passed(run("Q1", report="# 结果\n##数据口径与查询依据")))

    def test_merge_keeps_prior_complete_trace_when_rerun_fails_early(self) -> None:
        completed = run("Q1", report="# 结果\n## 数据口径与查询依据")
        quota_failure = {
            "id": "Q1",
            "complete": False,
            "errors": ["credits limit"],
            "streamError": None,
            "sql": [],
            "resultSets": [],
            "report": "",
            "nodes": [{"nodeName": "QueryEnhanceNode"}],
        }

        merged = merge_analysis_runs([completed], [quota_failure])

        self.assertEqual("SELECT 1", merged[0]["sql"][0])
        self.assertTrue(merged[0]["passed"])


if __name__ == "__main__":
    unittest.main()

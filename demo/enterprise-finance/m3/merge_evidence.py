#!/usr/bin/env python3
"""Merge M3 evidence artifacts while retaining the best trace for every case."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluate import merge_analysis_runs, read_json


def best_intent_runs(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        for item in artifact.get("intentRuns", []):
            current = merged.get(item["id"])
            if current is None or (item.get("passed") and not current.get("passed")):
                merged[item["id"]] = item
    return sorted(merged.values(), key=lambda item: item["id"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    artifacts = [read_json(path) for path in args.inputs]
    core_runs: list[dict[str, Any]] = []
    followup_runs: list[dict[str, Any]] = []
    for artifact in artifacts:
        core_runs = merge_analysis_runs(core_runs, artifact.get("coreRuns", []))
        followup_runs = merge_analysis_runs(followup_runs, artifact.get("multiTurnRuns", []))
    intent_runs = best_intent_runs(artifacts)
    html_export = next(
        (
            artifact.get("summary", {}).get("htmlExport")
            for artifact in artifacts
            if artifact.get("summary", {}).get("htmlExport", {}).get("passed")
        ),
        {"passed": False},
    )
    chart_runs = sum(item.get("hasChart", False) for item in core_runs + followup_runs)
    all_runs = core_runs + followup_runs + intent_runs
    summary = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "agentId": artifacts[0].get("summary", {}).get("agentId"),
        "corePassed": sum(item["passed"] for item in core_runs),
        "coreTotal": len(core_runs),
        "followupPassed": sum(item["passed"] for item in followup_runs),
        "followupTotal": len(followup_runs),
        "intentPassed": sum(item["passed"] for item in intent_runs),
        "intentTotal": len(intent_runs),
        "chartRuns": chart_runs,
        "retryRuns": sum(bool(item.get("retryMessages")) for item in core_runs + followup_runs),
        "htmlExport": html_export,
        "passed": all(item["passed"] for item in all_runs) and html_export["passed"] and chart_runs > 0,
    }
    result = {
        "summary": summary,
        "coreRuns": core_runs,
        "multiTurnRuns": followup_runs,
        "intentRuns": intent_runs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

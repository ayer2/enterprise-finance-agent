#!/usr/bin/env python3
"""Run and preserve the M3 live end-to-end acceptance suite."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


M3_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = M3_DIR.parent / "knowledge"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def api_json(base_url: str, method: str, path: str, payload: Any | None = None) -> Any:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json; charset=utf-8", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        content = response.read().decode("utf-8")
    return json.loads(content) if content else None


def install_report_contract(base_url: str, agent_id: int) -> None:
    config = read_json(M3_DIR / "report-optimization.json")
    payload = {
        **config,
        "agentId": agent_id,
        "enabled": True,
        "description": "M3 reports must expose metric definitions and query evidence",
        "creator": "M3 acceptance",
        "priority": 100,
        "displayOrder": 1,
    }
    response = api_json(base_url, "POST", "/api/prompt-config/save", payload)
    if not response.get("success"):
        raise RuntimeError(f"failed to install report contract: {response}")


def stop_stream(base_url: str, conversation_id: str) -> None:
    query = urllib.parse.urlencode({"conversationId": conversation_id})
    request = urllib.request.Request(base_url.rstrip("/") + f"/api/stream/stop?{query}", method="POST")
    try:
        urllib.request.urlopen(request, timeout=10).close()
    except Exception:
        pass


def ordered_nodes(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nodes: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for event in events:
        step_id = event.get("stepId")
        if step_id and step_id not in nodes:
            nodes[step_id] = {
                "stepId": step_id,
                "nodeName": event.get("nodeName"),
                "attempt": event.get("attempt"),
            }
    return list(nodes.values())


def grouped_text(events: list[dict[str, Any]], text_type: str, node_name: str | None = None) -> list[str]:
    groups: OrderedDict[str, list[str]] = OrderedDict()
    for event in events:
        if event.get("textType") != text_type:
            continue
        if node_name and event.get("nodeName") != node_name:
            continue
        key = event.get("stepId") or event.get("nodeName") or "unknown"
        groups.setdefault(key, []).append(event.get("text") or "")
    return ["".join(chunks).strip() for chunks in groups.values() if "".join(chunks).strip()]


def parse_result_sets(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parsed = []
    for event in events:
        if event.get("textType") != "RESULT_SET" or not event.get("text"):
            continue
        payload = event["text"].strip()
        try:
            value = json.loads(payload)
        except json.JSONDecodeError:
            continue
        result_set = value.get("resultSet") or {}
        rows = result_set.get("data") or []
        parsed.append(
            {
                "columns": result_set.get("column") or result_set.get("columns") or [],
                "rowCount": len(rows),
                "rows": rows,
                "sampleRows": rows[:3],
                "displayStyle": value.get("displayStyle") or {},
            }
        )
    return parsed


def has_chart(result_sets: list[dict[str, Any]], report: str) -> bool:
    return any((item.get("displayStyle") or {}).get("type") not in (None, "", "table") for item in result_sets) \
        or "```echarts" in report


def analysis_run_passed(result: dict[str, Any]) -> bool:
    return (
        result.get("complete")
        and not result.get("errors")
        and not result.get("streamError")
        and bool(result.get("sql"))
        and bool(result.get("resultSets"))
        and bool(result.get("report"))
        and bool(re.search(r"##\s*数据口径与查询依据", result.get("report", "")))
    )


def run_progress_score(result: dict[str, Any]) -> tuple[int, int, int, int, int, int]:
    """Prefer the most complete trace when a rerun fails before the prior run did."""
    return (
        int(analysis_run_passed(result)),
        int(bool(result.get("complete"))),
        int(bool(result.get("sql"))),
        int(bool(result.get("resultSets"))),
        int(bool(result.get("report"))),
        len(result.get("nodes") or []),
    )


def merge_analysis_runs(
    base_runs: list[dict[str, Any]], new_runs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged = {item["id"]: item for item in base_runs}
    for item in new_runs:
        current = merged.get(item["id"])
        if current is None or run_progress_score(item) >= run_progress_score(current):
            merged[item["id"]] = item
    for item in merged.values():
        item["passed"] = analysis_run_passed(item)
    return sorted(merged.values(), key=lambda item: item["id"])


def execute_run(
    base_url: str,
    agent_id: int,
    case: dict[str, Any],
    conversation_id: str,
    nl2sql_only: bool = False,
) -> dict[str, Any]:
    started = time.monotonic()
    params = urllib.parse.urlencode(
        {
            "agentId": agent_id,
            "conversationId": conversation_id,
            "threadId": "m3-" + uuid.uuid4().hex,
            "query": case["question"],
            "nl2sqlOnly": str(nl2sql_only).lower(),
        }
    )
    events: list[dict[str, Any]] = []
    stream_error = None
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + f"/api/stream/search?{params}", timeout=360) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[5:])
                events.append(event)
    except Exception as error:
        stream_error = f"{type(error).__name__}: {error}"
        stop_stream(base_url, conversation_id)

    sql = list(OrderedDict.fromkeys(grouped_text(events, "SQL")))
    reports = grouped_text(events, "MARK_DOWN", "ReportGeneratorNode")
    report = "\n".join(reports).strip()
    result_sets = parse_result_sets(events)
    errors = [event.get("text") for event in events if event.get("error")]
    retry_messages = [
        event.get("text", "").strip()
        for event in events
        if event.get("text") and any(word in event["text"] for word in ("重试", "SQL执行失败", "校验未通过"))
    ]
    evidence = [
        event.get("text", "").strip()
        for event in events
        if event.get("nodeName") == "EvidenceRecallNode" and event.get("text", "").startswith("证据")
    ]
    complete = any(event.get("complete") for event in events)
    final_answers = [event.get("text", "") for event in events if event.get("eventType") == "FINAL_ANSWER"]

    if nl2sql_only:
        passed = complete and not errors and bool(sql) and bool(result_sets)
    else:
        passed = analysis_run_passed(
            {
                "complete": complete,
                "errors": errors,
                "streamError": stream_error,
                "sql": sql,
                "resultSets": result_sets,
                "report": report,
            }
        )
    return {
        "id": case["id"],
        "question": case["question"],
        "category": case.get("category") or case.get("metric"),
        "conversationId": conversation_id,
        "passed": passed,
        "durationSeconds": round(time.monotonic() - started, 3),
        "complete": complete,
        "streamError": stream_error,
        "errors": errors,
        "nodes": ordered_nodes(events),
        "evidence": evidence,
        "sql": sql,
        "resultSets": result_sets,
        "retryMessages": retry_messages,
        "report": report,
        "finalAnswer": "\n".join(final_answers).strip(),
        "hasChart": has_chart(result_sets, report),
    }


def run_intent_case(base_url: str, agent_id: int, case: dict[str, Any]) -> dict[str, Any]:
    result = execute_run(base_url, agent_id, case, "m3-intent-" + case["id"], nl2sql_only=True)
    node_names = {node["nodeName"] for node in result["nodes"]}
    expected_data = case["expected"] == "data"
    classified_as_data = "EvidenceRecallNode" in node_names
    result["expected"] = case["expected"]
    result["classifiedAsData"] = classified_as_data
    result["passed"] = classified_as_data == expected_data and result["complete"] and not result["errors"]
    if not expected_data:
        result["passed"] = result["passed"] and not result["sql"] and not result["resultSets"]
    return result


def verify_html_export(base_url: str, report: str) -> dict[str, Any]:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/sessions/m3-acceptance/reports/html",
        data=report.encode("utf-8"),
        method="POST",
        headers={"Content-Type": "text/plain; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8")
        content_type = response.headers.get("Content-Type", "")
    return {
        "passed": "text/html" in content_type and "marked.min.js" in html and "echarts.min.js" in html,
        "contentType": content_type,
        "bytes": len(html.encode("utf-8")),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8065")
    parser.add_argument("--agent-id", required=True, type=int)
    parser.add_argument("--workers", default=2, type=int)
    parser.add_argument("--output", type=Path, default=M3_DIR / "evidence" / "latest.json")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", help="comma-separated core/follow-up IDs to rerun")
    parser.add_argument("--merge-base", type=Path, help="replace rerun cases in an existing evidence artifact")
    args = parser.parse_args()

    standard = read_json(KNOWLEDGE_DIR / "标准问答.json")
    config = read_json(M3_DIR / "questions.json")
    core = [
        {
            "id": item["id"],
            "question": item["question"],
            "metric": item["metric"],
            "category": "核心指标查询",
            "expectChart": item["id"] in {"M2-Q02", "M2-Q03", "M2-Q06", "M2-Q07", "M2-Q10", "M2-Q12", "M2-Q13", "M2-Q15", "M2-Q16", "M2-Q17"},
        }
        for item in standard
    ] + config["additionalCoreQuestions"]
    selected_ids = {value.strip() for value in args.ids.split(",")} if args.ids else None
    selected_followups = [
        case for case in config["multiTurnQuestions"] if not selected_ids or case["id"] in selected_ids
    ]
    if selected_ids:
        required_base_ids = {case["baseQuestionId"] for case in selected_followups}
        core = [case for case in core if case["id"] in selected_ids or case["id"] in required_base_ids]
    if args.limit:
        core = core[: args.limit]

    install_report_contract(args.base_url, args.agent_id)
    conversations = {case["id"]: "m3-core-" + case["id"] for case in core}
    for followup in config["multiTurnQuestions"]:
        base_id = followup["baseQuestionId"]
        if base_id in conversations:
            conversations[base_id] = "m3-drilldown-" + base_id

    core_results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(execute_run, args.base_url, args.agent_id, case, conversations[case["id"]]): case
            for case in core
        }
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            core_results.append(result)
            print(json.dumps({"id": result["id"], "passed": result["passed"], "seconds": result["durationSeconds"]}, ensure_ascii=False), flush=True)
    core_results.sort(key=lambda item: item["id"])

    followup_results = []
    if not args.limit:
        for case in selected_followups:
            conversation_id = conversations[case["baseQuestionId"]]
            result = execute_run(args.base_url, args.agent_id, case, conversation_id)
            followup_results.append(result)
            print(json.dumps({"id": result["id"], "passed": result["passed"], "seconds": result["durationSeconds"]}, ensure_ascii=False), flush=True)

    intent_results = []
    if not args.limit and not selected_ids:
        for case in config["intentQuestions"]:
            result = run_intent_case(args.base_url, args.agent_id, case)
            intent_results.append(result)

    if args.merge_base:
        base_artifact = read_json(args.merge_base)

        core_results = merge_analysis_runs(base_artifact.get("coreRuns", []), core_results)
        followup_results = merge_analysis_runs(base_artifact.get("multiTurnRuns", []), followup_results)
        if not intent_results:
            intent_results = base_artifact.get("intentRuns", [])

    report_for_export = next((item["report"] for item in core_results if item["report"]), "# M3 empty report")
    html_export = verify_html_export(args.base_url, report_for_export)
    all_runs = core_results + followup_results + intent_results
    summary = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "agentId": args.agent_id,
        "corePassed": sum(item["passed"] for item in core_results),
        "coreTotal": len(core_results),
        "followupPassed": sum(item["passed"] for item in followup_results),
        "followupTotal": len(followup_results),
        "intentPassed": sum(item["passed"] for item in intent_results),
        "intentTotal": len(intent_results),
        "chartRuns": sum(item.get("hasChart", False) for item in core_results + followup_results),
        "retryRuns": sum(bool(item.get("retryMessages")) for item in core_results + followup_results),
        "htmlExport": html_export,
        "passed": all(item["passed"] for item in all_runs)
        and html_export["passed"]
        and sum(item.get("hasChart", False) for item in core_results + followup_results) > 0,
    }
    artifact = {
        "summary": summary,
        "coreRuns": core_results,
        "multiTurnRuns": followup_results,
        "intentRuns": intent_results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

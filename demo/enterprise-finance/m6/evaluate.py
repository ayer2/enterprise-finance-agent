#!/usr/bin/env python3
"""Run the M6 reproducible evaluation suite against a live DataAgent instance."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


M6_DIR = Path(__file__).resolve().parent
DEMO_DIR = M6_DIR.parent
REPO_DIR = DEMO_DIR.parent.parent
M3_EVALUATOR = DEMO_DIR / "m3" / "evaluate.py"
SECURITY_RESULT = REPO_DIR / "data-agent-management" / "target" / "m6-security-evaluation.json"


def load_m3_module() -> Any:
    spec = importlib.util.spec_from_file_location("enterprise_finance_m3_evaluate", M3_EVALUATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load M3 evaluator: {M3_EVALUATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M3 = load_m3_module()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mysql_reference_result(
    case: dict[str, Any],
    *,
    reference_mode: str,
    mysql_bin: str,
    host: str,
    port: int,
    user: str,
    password_env: str,
) -> dict[str, Any]:
    env = os.environ.copy()
    password = env.get(password_env)
    if reference_mode == "docker":
        command = [
            "docker",
            "compose",
            "-f",
            str(DEMO_DIR / "docker-compose.yml"),
            "exec",
            "-T",
            "mysql",
            "sh",
            "-c",
            'MYSQL_PWD="$ENTERPRISE_DEMO_READONLY_PASSWORD" exec mysql --user=enterprise_agent_ro '
            "--database=enterprise_demo --default-character-set=utf8mb4 --batch --raw",
        ]
    else:
        if password is not None:
            env["MYSQL_PWD"] = password
        command = [
            mysql_bin,
            "--protocol=tcp",
            f"--host={host}",
            f"--port={port}",
            f"--user={user}",
            "--database=enterprise_demo",
            "--default-character-set=utf8mb4",
            "--batch",
            "--raw",
        ]
    completed = subprocess.run(
        command,
        cwd=REPO_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        input=case["sql"],
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip()
        if password:
            message = message.replace(password, "***")
        raise RuntimeError(f"standard SQL failed for {case['id']}: {message}")
    lines = completed.stdout.splitlines()
    if not lines:
        return {"columns": [], "rows": [], "rowCount": 0}
    columns = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        values = line.split("\t")
        rows.append({column: None if value == "NULL" else value for column, value in zip(columns, values)})
    return {"columns": columns, "rows": rows, "rowCount": len(rows)}


def result_matrix(result_set: dict[str, Any]) -> list[list[Any]]:
    columns = result_set.get("columns") or []
    rows = result_set.get("rows") or result_set.get("sampleRows") or []
    return [[row.get(column) for column in columns] for row in rows]


def as_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def values_equal(actual: Any, expected: Any) -> bool:
    if actual is None or expected is None:
        return actual is None and expected is None
    actual_number = as_decimal(actual)
    expected_number = as_decimal(expected)
    if actual_number is not None and expected_number is not None:
        tolerance = max(Decimal("0.01"), abs(expected_number) * Decimal("0.000001"))
        return abs(actual_number - expected_number) <= tolerance
    return str(actual).strip() == str(expected).strip()


def row_signature(row: list[Any]) -> str:
    return json.dumps([None if value is None else str(value).strip() for value in row], ensure_ascii=False)


def compare_result_sets(actual: dict[str, Any] | None, expected: dict[str, Any]) -> dict[str, Any]:
    if actual is None:
        return {"passed": False, "reason": "missing_result_set"}
    actual_columns = actual.get("columns") or []
    expected_columns = expected.get("columns") or []
    actual_column_lookup = {str(column).lower(): column for column in actual_columns}
    if expected_columns and all(str(column).lower() in actual_column_lookup for column in expected_columns):
        projected_columns = [actual_column_lookup[str(column).lower()] for column in expected_columns]
        actual_rows = [
            [row.get(column) for column in projected_columns]
            for row in (actual.get("rows") or actual.get("sampleRows") or [])
        ]
    else:
        actual_rows = result_matrix(actual)
    expected_rows = result_matrix(expected)
    if len(actual_rows) != len(expected_rows):
        return {
            "passed": False,
            "reason": "row_count_mismatch",
            "actualRowCount": len(actual_rows),
            "expectedRowCount": len(expected_rows),
        }
    if actual_rows and expected_rows and len(actual_rows[0]) != len(expected_rows[0]):
        return {
            "passed": False,
            "reason": "column_count_mismatch",
            "actualColumnCount": len(actual_rows[0]),
            "expectedColumnCount": len(expected_rows[0]),
        }

    unmatched = list(actual_rows)
    for expected_row in expected_rows:
        match_index = next(
            (
                index
                for index, actual_row in enumerate(unmatched)
                if len(actual_row) == len(expected_row)
                and all(values_equal(actual_value, expected_value) for actual_value, expected_value in zip(actual_row, expected_row))
            ),
            None,
        )
        if match_index is None:
            return {
                "passed": False,
                "reason": "value_mismatch",
                "missingExpectedRow": row_signature(expected_row),
                "actualSample": [row_signature(row) for row in unmatched[:3]],
            }
        unmatched.pop(match_index)
    return {"passed": True, "reason": None}


def metric_contract(case: dict[str, Any], sql: list[str]) -> dict[str, Any]:
    combined = "\n".join(sql).lower()
    checks = []
    for alternatives in case.get("conceptGroups", []):
        matched = any(str(term).lower() in combined for term in alternatives)
        checks.append({"alternatives": alternatives, "matched": matched})
    return {"passed": bool(checks) and all(item["matched"] for item in checks), "checks": checks}


def classify_failure(run: dict[str, Any]) -> str | None:
    if run.get("streamError"):
        return "stream_error"
    if run.get("errors"):
        return "workflow_error"
    if run.get("complete") and (not run.get("sql") or not run.get("resultSets")):
        return "early_clean_termination"
    if not run.get("complete"):
        return "incomplete_stream"
    return None


def enrich_run(run: dict[str, Any], case: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    executable = (
        bool(run.get("complete"))
        and not run.get("streamError")
        and not run.get("errors")
        and bool(run.get("sql"))
        and bool(run.get("resultSets"))
    )
    actual = next((item for item in run.get("resultSets", []) if item.get("rows") is not None), None)
    comparison = compare_result_sets(actual, expected) if executable else {"passed": False, "reason": "sql_not_executable"}
    metric = metric_contract(case, run.get("sql") or []) if case["category"] == "metric_definition" else None
    run.update(
        {
            "expected": expected,
            "sqlExecutable": executable,
            "resultCorrect": bool(comparison["passed"]),
            "resultComparison": comparison,
            "metricCorrect": bool(metric and metric["passed"] and comparison["passed"]),
            "metricContract": metric,
            "failureType": classify_failure(run),
        }
    )
    run["passed"] = executable and run["resultCorrect"] and (
        case["category"] != "metric_definition" or run["metricCorrect"]
    )
    return run


def run_score(run: dict[str, Any]) -> tuple[int, int, int, int, int]:
    return (
        int(bool(run.get("passed"))),
        int(bool(run.get("metricCorrect"))),
        int(bool(run.get("resultCorrect"))),
        int(bool(run.get("sqlExecutable"))),
        len(run.get("nodes") or []),
    )


def merge_runs(base_runs: list[dict[str, Any]], new_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {run["id"]: run for run in base_runs}
    for run in new_runs:
        current = merged.get(run["id"])
        if current is None or run_score(run) >= run_score(current):
            merged[run["id"]] = run
    return sorted(merged.values(), key=lambda item: item["id"])


def rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)
    return round(ordered[index], 3)


def run_security_evaluation() -> dict[str, Any]:
    wrapper = REPO_DIR / ("mvnw.cmd" if os.name == "nt" else "mvnw")
    completed = subprocess.run(
        [str(wrapper), "-pl", "data-agent-management", "-Dtest=M6SqlSecurityEvaluationTest", "test"],
        cwd=REPO_DIR,
        timeout=600,
        check=False,
    )
    if not SECURITY_RESULT.exists():
        raise RuntimeError(f"security evaluation did not create {SECURITY_RESULT}")
    result = read_json(SECURITY_RESULT)
    result["testExitCode"] = completed.returncode
    return result


def build_summary(
    config: dict[str, Any],
    analysis_runs: list[dict[str, Any]],
    multi_turn_runs: list[dict[str, Any]],
    security: dict[str, Any],
) -> dict[str, Any]:
    runs = analysis_runs + multi_turn_runs
    metric_runs = [run for run in runs if run["category"] == "metric_definition"]
    durations = [float(run["durationSeconds"]) for run in runs]
    sql_rate = rate(sum(run["sqlExecutable"] for run in runs), len(runs))
    result_rate = rate(sum(run["resultCorrect"] for run in runs), len(runs))
    metric_rate = rate(sum(run["metricCorrect"] for run in metric_runs), len(metric_runs))
    block_rate = security.get("dangerousRequestBlockRate")
    thresholds = config["thresholds"]
    category_counts = Counter(run["category"] for run in runs)
    threshold_checks = {
        "sqlExecutableRate": sql_rate is not None and sql_rate >= thresholds["sqlExecutableRate"],
        "resultAccuracyRate": result_rate is not None and result_rate >= thresholds["resultAccuracyRate"],
        "metricAccuracyRate": metric_rate is not None and metric_rate >= thresholds["metricAccuracyRate"],
        "dangerousRequestBlockRate": block_rate is not None
        and block_rate >= thresholds["dangerousRequestBlockRate"],
    }
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "dataset": config["dataset"],
        "caseCounts": dict(sorted(category_counts.items())),
        "analysisTotal": len(runs),
        "sqlExecutableRate": sql_rate,
        "resultAccuracyRate": result_rate,
        "metricAccuracyRate": metric_rate,
        "dangerousRequestBlockRate": block_rate,
        "durationSeconds": {
            "total": round(sum(durations), 3),
            "mean": round(statistics.mean(durations), 3) if durations else None,
            "p50": percentile(durations, 0.50),
            "p95": percentile(durations, 0.95),
        },
        "failureTypes": dict(sorted(Counter(run["failureType"] for run in runs if run["failureType"]).items())),
        "thresholds": thresholds,
        "thresholdChecks": threshold_checks,
        "passed": all(threshold_checks.values()) and security.get("testExitCode") == 0,
    }


def markdown_report(artifact: dict[str, Any]) -> str:
    summary = artifact["summary"]

    def percent(value: float | None) -> str:
        return "N/A" if value is None else f"{value * 100:.2f}%"

    failed = [run for run in artifact["analysisRuns"] + artifact["multiTurnRuns"] if not run["passed"]]
    lines = [
        "# M6 自动评测报告",
        "",
        f"- 生成时间（UTC）：`{summary['generatedAt']}`",
        f"- 数据集：`{summary['dataset']['name']}`，固定种子 `{summary['dataset']['seed']}`",
        f"- 题集指纹：`{artifact['provenance']['casesSha256']}`",
        f"- 总体结论：`{'通过' if summary['passed'] else '未通过'}`",
        "",
        "## 核心指标",
        "",
        "| 指标 | 实际值 | 目标值 | 结果 |",
        "|---|---:|---:|---|",
        f"| SQL 可执行率 | {percent(summary['sqlExecutableRate'])} | >= {percent(summary['thresholds']['sqlExecutableRate'])} | {'通过' if summary['thresholdChecks']['sqlExecutableRate'] else '未通过'} |",
        f"| 查询结果正确率 | {percent(summary['resultAccuracyRate'])} | >= {percent(summary['thresholds']['resultAccuracyRate'])} | {'通过' if summary['thresholdChecks']['resultAccuracyRate'] else '未通过'} |",
        f"| 指标口径正确率 | {percent(summary['metricAccuracyRate'])} | >= {percent(summary['thresholds']['metricAccuracyRate'])} | {'通过' if summary['thresholdChecks']['metricAccuracyRate'] else '未通过'} |",
        f"| 危险请求拦截率 | {percent(summary['dangerousRequestBlockRate'])} | = {percent(summary['thresholds']['dangerousRequestBlockRate'])} | {'通过' if summary['thresholdChecks']['dangerousRequestBlockRate'] else '未通过'} |",
        "",
        "## 耗时",
        "",
        f"- 平均：`{summary['durationSeconds']['mean']}` 秒",
        f"- P50：`{summary['durationSeconds']['p50']}` 秒",
        f"- P95：`{summary['durationSeconds']['p95']}` 秒",
        f"- 所有题累计：`{summary['durationSeconds']['total']}` 秒",
        "",
        "## 失败明细",
        "",
    ]
    if not failed:
        lines.append("无。")
    else:
        lines.extend(["| ID | 类别 | 失败类型 | 结果比对 |", "|---|---|---|---|"])
        for run in failed:
            lines.append(
                f"| {run['id']} | {run['category']} | {run.get('failureType') or '-'} | {run['resultComparison'].get('reason') or '-'} |"
            )
    lines.extend(
        [
            "",
            "## 解释边界",
            "",
            "- SQL 可执行率的分母为 32 道独立业务题与 4 道多轮追问，共 36 次被评测回答。",
            "- 结果正确率使用同一固定种子数据库实时执行标准 SQL，并对结果逐行逐值比对；不以 SQL 文本相同作为正确标准。",
            "- 指标口径正确率只统计 8 道指标口径题，必须同时满足结果正确和关键公式要素完整。",
            "- 工作流发送完成事件但没有 SQL 或结果集时，单独标记为 `early_clean_termination`，不会计为成功。",
            "- 危险请求拦截率由应用层 SQL AST、安全白名单、数据范围及人工确认边界直接执行得到，不依赖模型自行拒绝。",
            "",
        ]
    )
    return "\n".join(lines)


def validate_case_contract(config: dict[str, Any]) -> None:
    expected = {"single_table": 8, "multi_table": 10, "metric_definition": 8, "trend_anomaly": 6}
    counts = Counter(case["category"] for case in config["analysisCases"])
    if counts != Counter(expected):
        raise ValueError(f"analysis case counts must be {expected}, got {dict(counts)}")
    if len(config["multiTurnCases"]) != 4:
        raise ValueError("multiTurnCases must contain exactly 4 cases")
    all_cases = config["analysisCases"] + config["multiTurnCases"]
    ids = [case["id"] for case in all_cases]
    if len(ids) != len(set(ids)):
        raise ValueError("case IDs must be unique")
    base_ids = {case["id"] for case in config["analysisCases"]}
    missing_bases = [case["baseQuestionId"] for case in config["multiTurnCases"] if case["baseQuestionId"] not in base_ids]
    if missing_bases:
        raise ValueError(f"multi-turn base questions not found: {missing_bases}")
    for case in config["analysisCases"]:
        if case["category"] == "metric_definition" and not case.get("conceptGroups"):
            raise ValueError(f"metric case {case['id']} has no conceptGroups")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8065")
    parser.add_argument("--agent-id", required=True, type=int)
    parser.add_argument("--workers", default=2, type=int)
    parser.add_argument("--mysql-bin", default=shutil.which("mysql") or "mysql")
    parser.add_argument("--reference-mode", choices=("docker", "tcp"), default="docker")
    parser.add_argument("--mysql-host", default="127.0.0.1")
    parser.add_argument("--mysql-port", default=3307, type=int)
    parser.add_argument("--mysql-user", default="enterprise_agent_ro")
    parser.add_argument("--mysql-password-env", default="ENTERPRISE_DEMO_READONLY_PASSWORD")
    parser.add_argument("--ids", help="comma-separated IDs for a diagnostic subset")
    parser.add_argument("--output", type=Path, default=M6_DIR / "evidence" / "latest.json")
    parser.add_argument("--report", type=Path, default=M6_DIR / "evidence" / "latest.md")
    parser.add_argument("--skip-security", action="store_true")
    parser.add_argument("--references-only", action="store_true")
    parser.add_argument("--merge-base", type=Path, help="merge selected reruns into a complete prior artifact")
    args = parser.parse_args()

    cases_path = M6_DIR / "cases.json"
    config = read_json(cases_path)
    validate_case_contract(config)
    selected_ids = {item.strip() for item in args.ids.split(",")} if args.ids else None
    analysis_cases = [case for case in config["analysisCases"] if not selected_ids or case["id"] in selected_ids]
    followups = [case for case in config["multiTurnCases"] if not selected_ids or case["id"] in selected_ids]
    required_bases = {case["baseQuestionId"] for case in followups}
    if required_bases:
        known = {case["id"] for case in analysis_cases}
        analysis_cases.extend(
            case for case in config["analysisCases"] if case["id"] in required_bases and case["id"] not in known
        )

    all_selected = analysis_cases + followups
    expected = {
        case["id"]: mysql_reference_result(
            case,
            reference_mode=args.reference_mode,
            mysql_bin=args.mysql_bin,
            host=args.mysql_host,
            port=args.mysql_port,
            user=args.mysql_user,
            password_env=args.mysql_password_env,
        )
        for case in all_selected
    }
    if args.references_only:
        artifact = {
            "dataset": config["dataset"],
            "provenance": {
                "casesSha256": sha256(cases_path),
                "generatorConfigSha256": sha256(DEMO_DIR / "config.json"),
            },
            "referenceResults": expected,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"referenceCases": len(expected), "output": str(args.output)}, ensure_ascii=False))
        return

    conversations = {case["id"]: "m6-" + case["id"].lower() for case in analysis_cases}
    analysis_runs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(M3.execute_run, args.base_url, args.agent_id, case, conversations[case["id"]], True): case
            for case in analysis_cases
        }
        for future in concurrent.futures.as_completed(futures):
            case = futures[future]
            run = enrich_run(future.result(), case, expected[case["id"]])
            analysis_runs.append(run)
            print(
                json.dumps(
                    {
                        "id": run["id"],
                        "sqlExecutable": run["sqlExecutable"],
                        "resultCorrect": run["resultCorrect"],
                        "metricCorrect": run["metricCorrect"],
                        "seconds": run["durationSeconds"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    analysis_runs.sort(key=lambda item: item["id"])

    multi_turn_runs = []
    for case in followups:
        run = M3.execute_run(
            args.base_url,
            args.agent_id,
            case,
            conversations[case["baseQuestionId"]],
            True,
        )
        multi_turn_runs.append(enrich_run(run, case, expected[case["id"]]))

    base_artifact = read_json(args.merge_base) if args.merge_base else None
    if base_artifact:
        analysis_runs = merge_runs(base_artifact.get("analysisRuns", []), analysis_runs)
        multi_turn_runs = merge_runs(base_artifact.get("multiTurnRuns", []), multi_turn_runs)
    if args.skip_security:
        security = (
            base_artifact.get("securityEvaluation")
            if base_artifact
            else {"skipped": True, "dangerousRequestBlockRate": None, "testExitCode": None}
        )
    else:
        security = run_security_evaluation()
    summary = build_summary(config, analysis_runs, multi_turn_runs, security)
    artifact = {
        "summary": summary,
        "provenance": {
            "casesSha256": sha256(cases_path),
            "generatorConfigSha256": sha256(DEMO_DIR / "config.json"),
            "evaluator": str(Path(__file__).relative_to(REPO_DIR)).replace("\\", "/"),
        },
        "analysisRuns": analysis_runs,
        "multiTurnRuns": multi_turn_runs,
        "securityEvaluation": security,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(markdown_report(artifact), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    if selected_ids and not args.merge_base:
        print("diagnostic subset completed; thresholds are only authoritative for the full suite", flush=True)
    elif not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

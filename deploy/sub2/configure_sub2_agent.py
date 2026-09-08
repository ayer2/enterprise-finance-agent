#!/usr/bin/env python3
"""Idempotently configure a Sub2 PostgreSQL data source and DataAgent.

Run this on the server where the DataAgent backend is exposed. Secrets are read
from SUB2_DB_PASSWORD or an interactive prompt and are never printed.
"""

from __future__ import annotations

import getpass
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_API = "http://127.0.0.1:8066"
DEFAULT_AGENT = "Sub2 数据问答助手"
DEFAULT_TABLES = {
    "users",
    "groups",
    "accounts",
    "api_keys",
    "account_groups",
    "usage_logs",
    "channels",
    "channel_groups",
    "channel_model_pricing",
    "channel_monitors",
    "channel_monitor_histories",
    "ops_error_logs",
    "ops_system_metrics",
}


class ApiError(RuntimeError):
    pass


def request(base: str, method: str, path: str, payload: object | None = None) -> object:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    url = base.rstrip("/") + path
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read()
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        detail = exc.read().decode("utf-8", "replace") if isinstance(exc, urllib.error.HTTPError) else str(exc)
        raise ApiError(f"{method} {path} failed: {detail}") from exc
    try:
        return json.loads(raw.decode("utf-8")) if raw else None
    except json.JSONDecodeError as exc:
        raise ApiError(f"{method} {path} returned invalid JSON") from exc


def unwrap(value: object, label: str) -> object:
    if isinstance(value, dict) and "success" in value:
        if not value.get("success"):
            raise ApiError(f"{label}: {value.get('message', 'unknown error')}")
        return value.get("data")
    return value


def find_exact(items: object, key: str, expected: str) -> dict | None:
    if not isinstance(items, list):
        raise ApiError("backend returned an unexpected list response")
    return next((item for item in items if isinstance(item, dict) and item.get(key) == expected), None)


def main() -> int:
    api = os.environ.get("DATA_AGENT_URL", DEFAULT_API)
    agent_name = os.environ.get("SUB2_AGENT_NAME", DEFAULT_AGENT)
    db_password = os.environ.get("SUB2_DB_PASSWORD") or getpass.getpass("Sub2 dataagent_ro password: ")
    requested_tables = {
        table.strip()
        for table in os.environ.get("SUB2_TABLES", "").split(",")
        if table.strip()
    }

    print(f"Checking DataAgent at {api} ...")
    ready = unwrap(request(api, "GET", "/api/model-config/check-ready"), "model readiness")
    if isinstance(ready, dict) and not ready.get("ready"):
        raise ApiError("chat or embedding model is not active; configure both models first")

    datasources = request(api, "GET", "/api/datasource")
    datasource = find_exact(datasources, "name", "sub2api")
    if datasource is None:
        print("Creating PostgreSQL data source sub2api ...")
        datasource = request(
            api,
            "POST",
            "/api/datasource",
            {
                "name": "sub2api",
                "type": "postgresql",
                "host": os.environ.get("SUB2_DB_HOST", "sub2api-postgres"),
                "port": int(os.environ.get("SUB2_DB_PORT", "5432")),
                "databaseName": os.environ.get("SUB2_DB_NAME", "sub2api"),
                "username": os.environ.get("SUB2_DB_USER", "dataagent_ro"),
                "password": db_password,
                "status": "active",
                "description": "Sub2API read-only PostgreSQL data source",
            },
        )
    datasource_id = datasource.get("id") if isinstance(datasource, dict) else None
    if not isinstance(datasource_id, int):
        raise ApiError("could not resolve sub2api datasource id")
    unwrap(request(api, "POST", f"/api/datasource/{datasource_id}/test"), "datasource test")
    print(f"Datasource ready: id={datasource_id}")

    tables = request(api, "GET", f"/api/datasource/{datasource_id}/tables")
    if not isinstance(tables, list):
        raise ApiError("backend returned an unexpected table list")
    table_names = {str(table) for table in tables}
    selected = requested_tables or (table_names & DEFAULT_TABLES)
    selected &= table_names
    if not selected:
        available = ", ".join(sorted(table_names))
        raise ApiError(f"no safe Sub2 tables found; set SUB2_TABLES=...; available: {available}")

    agents = request(api, "GET", "/api/agent/list")
    agent = find_exact(agents, "name", agent_name)
    if agent is None:
        print(f"Creating agent {agent_name} ...")
        agent = request(
            api,
            "POST",
            "/api/agent",
            {
                "name": agent_name,
                "description": "只读查询 Sub2API 运行数据并生成中文分析回答",
                "category": "数据问答",
                "tags": "Sub2API,数据分析,只读",
                "status": "draft",
                "prompt": (
                    "你是 Sub2API 数据分析助手。只能查询已授权的 Sub2 数据库，"
                    "只允许执行只读 SELECT 查询，不得执行任何写操作；不要输出 API Key、密码、"
                    "账号凭据或完整请求体。回答时说明时间范围、数据来源和关键指标。"
                ),
            },
        )
    agent_id = agent.get("id") if isinstance(agent, dict) else None
    if not isinstance(agent_id, int):
        raise ApiError("could not resolve agent id")

    agent_datasources = unwrap(request(api, "GET", f"/api/agent/{agent_id}/datasources"), "agent datasources")
    active = next(
        (
            item
            for item in agent_datasources
            if isinstance(item, dict) and item.get("isActive") in (1, True)
        ),
        None,
    ) if isinstance(agent_datasources, list) else None
    if not isinstance(active, dict) or active.get("datasourceId") != datasource_id:
        unwrap(
            request(api, "POST", f"/api/agent/{agent_id}/datasources/{datasource_id}"),
            "bind datasource",
        )
    unwrap(
        request(
            api,
            "POST",
            f"/api/agent/{agent_id}/datasources/tables",
            {"datasourceId": datasource_id, "tables": sorted(selected)},
        ),
        "select tables",
    )
    unwrap(request(api, "POST", f"/api/agent/{agent_id}/datasources/init"), "schema initialization")
    if os.environ.get("SUB2_PUBLISH", "1").lower() not in {"0", "false", "no"}:
        request(api, "POST", f"/api/agent/{agent_id}/publish")

    print(f"Agent ready: id={agent_id}, tables={','.join(sorted(selected))}")
    print("Next: open Data Q&A and select this agent, then ask a read-only Sub2 question.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ApiError, KeyboardInterrupt) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

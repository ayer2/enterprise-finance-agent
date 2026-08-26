#!/usr/bin/env python3
"""Idempotently import M2 semantic models and knowledge through management APIs."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        payload: Any | None = None,
        content_type: str = "application/json; charset=utf-8",
    ) -> Any:
        data = None
        if payload is not None:
            data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": content_type, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} failed: HTTP {error.code}: {detail}") from error
        return json.loads(body) if body else None

    def multipart(self, path: str, fields: dict[str, str]) -> Any:
        boundary = "----M2Knowledge" + uuid.uuid4().hex
        chunks: list[bytes] = []
        for name, value in fields.items():
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode(),
                    f'Content-Disposition: form-data; name="{name}"\r\n'.encode(),
                    b"Content-Type: text/plain; charset=utf-8\r\n\r\n",
                    value.encode("utf-8"),
                    b"\r\n",
                ]
            )
        chunks.append(f"--{boundary}--\r\n".encode())
        return self.request(
            "POST",
            path,
            b"".join(chunks),
            f"multipart/form-data; boundary={boundary}",
        )


def load_json(name: str) -> Any:
    return json.loads((BASE_DIR / name).read_text(encoding="utf-8"))


def response_data(response: Any) -> Any:
    if isinstance(response, dict) and response.get("success") is False:
        raise RuntimeError(response.get("message", "API returned success=false"))
    if isinstance(response, dict) and "data" in response:
        return response["data"]
    return response


def import_semantic_models(client: ApiClient, agent_id: int) -> int:
    models = load_json("semantic-models.json")
    result = response_data(
        client.request("POST", "/api/semantic-model/batch-import", {"agentId": agent_id, "items": models})
    )
    if result.get("failCount", 0):
        raise RuntimeError(f"semantic model import failed: {result}")
    return result["successCount"]


def import_business_knowledge(client: ApiClient, agent_id: int) -> int:
    desired = load_json("business-knowledge.json")
    query = urllib.parse.urlencode({"agentId": agent_id})
    existing = response_data(client.request("GET", f"/api/business-knowledge?{query}")) or []
    by_term = {item["businessTerm"]: item for item in existing}

    for item in desired:
        payload = {**item, "agentId": agent_id, "isRecall": True}
        current = by_term.get(item["businessTerm"])
        if current:
            client.request("PUT", f"/api/business-knowledge/{current['id']}", payload)
            client.request("POST", f"/api/business-knowledge/recall/{current['id']}?isRecall=true")
        else:
            client.request("POST", "/api/business-knowledge", payload)

    client.request("POST", f"/api/business-knowledge/refresh-vector-store?agentId={agent_id}")
    return len(desired)


def qa_content(item: dict[str, Any]) -> str:
    columns = ", ".join(item["expectedColumns"])
    return f"指标：{item['metric']}\n标准 SQL：\n{item['sql']}\n期望列：{columns}"


def import_standard_qa(client: ApiClient, agent_id: int) -> int:
    desired = load_json("标准问答.json")
    page = response_data(
        client.request(
            "POST",
            "/api/agent-knowledge/query/page",
            {"agentId": agent_id, "pageNum": 1, "pageSize": 500},
        )
    )
    existing = page if isinstance(page, list) else []
    by_question = {item.get("question"): item for item in existing if item.get("question")}

    for item in desired:
        current = by_question.get(item["question"])
        title = f"{item['id']} {item['metric']}标准问答"
        content = qa_content(item)
        if current:
            client.request("PUT", f"/api/agent-knowledge/recall/{current['id']}?isRecall=true")
            if current.get("title") != title or current.get("content") != content:
                client.request("PUT", f"/api/agent-knowledge/{current['id']}", {"title": title, "content": content})
                client.request("POST", f"/api/agent-knowledge/retry-embedding/{current['id']}")
        else:
            client.multipart(
                "/api/agent-knowledge/create",
                {
                    "agentId": str(agent_id),
                    "title": title,
                    "type": "QA",
                    "question": item["question"],
                    "content": content,
                },
            )
    return len(desired)


def wait_for_embeddings(client: ApiClient, agent_id: int, timeout: int) -> tuple[int, int]:
    deadline = time.monotonic() + timeout
    retry_counts: dict[tuple[str, int], int] = {}
    while True:
        business = response_data(
            client.request("GET", f"/api/business-knowledge?agentId={agent_id}")
        ) or []
        qa_response = client.request(
            "POST",
            "/api/agent-knowledge/query/page",
            {"agentId": agent_id, "pageNum": 1, "pageSize": 500},
        )
        qa = response_data(qa_response) or []
        tracked_business = [item for item in business if item.get("businessTerm") in {
            row["businessTerm"] for row in load_json("business-knowledge.json")
        }]
        tracked_questions = {row["question"] for row in load_json("标准问答.json")}
        tracked_qa = [item for item in qa if item.get("question") in tracked_questions]
        failed_business = [item for item in tracked_business if item.get("embeddingStatus") == "FAILED"]
        failed_qa = [item for item in tracked_qa if item.get("embeddingStatus") == "FAILED"]
        for kind, items, endpoint in (
            ("business", failed_business, "/api/business-knowledge/retry-embedding/"),
            ("qa", failed_qa, "/api/agent-knowledge/retry-embedding/"),
        ):
            for item in items:
                key = (kind, int(item["id"]))
                attempts = retry_counts.get(key, 0)
                if attempts >= 3:
                    raise RuntimeError(f"embedding failed after 3 retries: {kind} id={item['id']}")
                client.request("POST", endpoint + str(item["id"]))
                retry_counts[key] = attempts + 1
        complete = [item for item in tracked_business + tracked_qa if item.get("embeddingStatus") == "COMPLETED"]
        expected = len(tracked_business) + len(tracked_qa)
        if expected and len(complete) == expected:
            return len(tracked_business), len(tracked_qa)
        if time.monotonic() >= deadline:
            raise TimeoutError(f"embedding timeout: {len(complete)}/{expected} completed")
        time.sleep(3 if failed_business or failed_qa else 2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8065")
    parser.add_argument("--agent-id", required=True, type=int)
    parser.add_argument("--wait-seconds", default=180, type=int)
    args = parser.parse_args()

    client = ApiClient(args.base_url)
    semantic_count = import_semantic_models(client, args.agent_id)
    business_count = import_business_knowledge(client, args.agent_id)
    qa_count = import_standard_qa(client, args.agent_id)
    embedded_business, embedded_qa = wait_for_embeddings(client, args.agent_id, args.wait_seconds)
    print(
        json.dumps(
            {
                "agentId": args.agent_id,
                "semanticModels": semantic_count,
                "businessKnowledge": business_count,
                "standardQa": qa_count,
                "embeddedBusinessKnowledge": embedded_business,
                "embeddedStandardQa": embedded_qa,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

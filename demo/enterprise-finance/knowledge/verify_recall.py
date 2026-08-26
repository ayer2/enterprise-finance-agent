#!/usr/bin/env python3
"""Verify representative M2 business terms through the live evidence-recall node."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
import uuid


CASES = [
    ("销售收入按什么口径统计？", "2025年全年销售额是多少？"),
    ("收款率怎么计算？", "2025年新产生应收的整体回款率是多少？"),
    ("预算使用率怎么算？", "2025年12月各部门预算执行率是多少？"),
    ("到期未回款怎么统计？", "截至2025年12月31日逾期应收余额是多少？"),
    ("指标达成率怎么算？", "2025年第四季度各部门各项KPI完成率是多少？"),
]


def stop_stream(base_url: str, conversation_id: str) -> None:
    query = urllib.parse.urlencode({"conversationId": conversation_id})
    request = urllib.request.Request(f"{base_url}/api/stream/stop?{query}", method="POST")
    try:
        urllib.request.urlopen(request, timeout=10).close()
    except Exception:
        pass


def recall(base_url: str, agent_id: int, question: str) -> list[str]:
    conversation_id = "m2-recall-" + uuid.uuid4().hex
    params = urllib.parse.urlencode(
        {
            "agentId": agent_id,
            "conversationId": conversation_id,
            "threadId": conversation_id,
            "query": question,
            "nl2sqlOnly": "true",
        }
    )
    evidence: list[str] = []
    in_evidence_node = False
    try:
        with urllib.request.urlopen(f"{base_url}/api/stream/search?{params}", timeout=120) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[5:])
                node = event.get("nodeName")
                if node == "EvidenceRecallNode":
                    in_evidence_node = True
                    text = event.get("text") or ""
                    if text.startswith("证据"):
                        evidence.append(text.strip())
                elif in_evidence_node:
                    break
    finally:
        stop_stream(base_url, conversation_id)
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8065")
    parser.add_argument("--agent-id", required=True, type=int)
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    results = []
    for question, expected in CASES:
        evidence = recall(base_url, args.agent_id, question)
        matched = any(expected in item for item in evidence)
        results.append(
            {
                "question": question,
                "expectedEvidence": expected,
                "matched": matched,
                "evidenceCount": len(evidence),
            }
        )
        if not matched:
            raise RuntimeError(
                f"recall mismatch for {question!r}; expected {expected!r}; evidence={evidence!r}"
            )

    print(json.dumps({"passed": len(results), "total": len(CASES), "cases": results}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""AstrBot bridge for the Sub2 DataAgent SSE workflow."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

import aiohttp
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register


@register("sub2_data_agent", "ayer2", "查询 Sub2API 数据并返回分析结果", "1.0.0")
class Sub2DataAgentPlugin(Star):
    """Route /sub2 questions to the published Sub2 DataAgent."""

    def __init__(self, context: Context):
        super().__init__(context)
        self.base_url = os.getenv("SUB2_DATA_AGENT_URL", "http://sub2-data-agent-backend:8065").rstrip("/")
        self.agent_id = os.getenv("SUB2_DATA_AGENT_ID", "1")
        self.timeout_seconds = float(os.getenv("SUB2_DATA_AGENT_TIMEOUT", "180"))
        data_dir = Path(os.getenv("ASTRBOT_DATA_DIR", "/AstrBot/data"))
        self.mapping_path = data_dir / "plugin_data" / "sub2_data_agent" / "conversations.json"
        self.conversations = self._load_conversations()

    @filter.command("sub2", priority=1000)
    async def sub2_command(self, event: AstrMessageEvent):
        """Handle AstrBot's parsed /sub2 command."""
        raw = self._message_text(event).strip()
        query = self._extract_query(raw)
        # Some adapters pass only the text after a parsed command.
        if not query and raw and not raw.startswith("/"):
            query = raw
        logger.info("[Sub2] command handler matched")
        event.stop_event()
        async for result in self._respond(event, query):
            yield result

    @filter.event_message_type(filter.EventMessageType.ALL, priority=999)
    async def sub2_message_fallback(self, event: AstrMessageEvent):
        """Catch adapters that do not expose slash commands to command handlers."""
        raw = self._message_text(event).strip()
        if "/sub2" not in raw.lower():
            return
        logger.info("[Sub2] message fallback matched")
        event.stop_event()
        async for result in self._respond(event, self._extract_query(raw)):
            yield result

    @staticmethod
    def _extract_query(raw: str) -> str:
        command_index = raw.lower().find("/sub2")
        if command_index < 0:
            return ""
        return raw[command_index + 5 :].strip()

    async def _respond(self, event: AstrMessageEvent, query: str):
        if not query:
            yield event.plain_result("用法：/sub2 查询最近1小时失败率最高的模型，并说明失败原因")
            return

        origin = event.unified_msg_origin
        if query in {"新会话", "新对话", "重置", "清空上下文"}:
            self.conversations[origin] = f"astrbot:{uuid4().hex}"
            self._save_conversations()
            yield event.plain_result("已开启新的 Sub2 会话，之前的上下文不会带入。")
            return

        conversation_id = self.conversations.setdefault(origin, f"astrbot:{uuid4().hex}")
        self._save_conversations()
        try:
            answer = await self._query(conversation_id, query)
        except Exception as exc:  # pragma: no cover - runtime/network failure path
            yield event.plain_result(f"Sub2 数据查询失败：{exc}")
            return
        yield event.plain_result(answer)

    @staticmethod
    def _message_text(event: AstrMessageEvent) -> str:
        """Read plain text across AstrBot versions and message adapters."""
        getter = getattr(event, "get_message_str", None)
        if callable(getter):
            try:
                value = getter()
            except Exception:  # pragma: no cover - adapter-specific fallback
                value = ""
            if value:
                return str(value)
        return str(getattr(event, "message_str", "") or "")

    def _load_conversations(self) -> dict[str, str]:
        try:
            value = json.loads(self.mapping_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}

    def _save_conversations(self) -> None:
        self.mapping_path.parent.mkdir(parents=True, exist_ok=True)
        self.mapping_path.write_text(
            json.dumps(self.conversations, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    async def _query(self, conversation_id: str, query: str) -> str:
        params = urlencode(
            {
                "agentId": self.agent_id,
                "conversationId": conversation_id,
                "query": query,
                "humanFeedback": "false",
                "rejectedPlan": "false",
                "nl2sqlOnly": "false",
            }
        )
        url = f"{self.base_url}/api/stream/search?{params}"
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        final_answer = ""
        report_parts: list[str] = []
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers={"Accept": "text/event-stream"}) as response:
                if response.status != 200:
                    detail = (await response.text())[:300]
                    raise RuntimeError(f"HTTP {response.status}: {detail}")
                async for raw_line in response.content:
                    line = raw_line.decode("utf-8", "replace").rstrip("\r\n")
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    try:
                        item: dict[str, Any] = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    event_type = item.get("eventType")
                    text = str(item.get("text") or "")
                    if event_type == "FINAL_ANSWER":
                        final_answer = text.strip()
                    elif item.get("nodeName") == "ReportGeneratorNode" and item.get("textType") == "MARK_DOWN":
                        report_parts.append(text)

        answer = final_answer or "".join(report_parts).strip()
        return answer or "Sub2 未返回可用回答，请查看 DataAgent 后端日志。"

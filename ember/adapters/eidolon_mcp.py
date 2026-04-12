"""
Eidolon MCP Server adapter for EMBER.

Connects to an eidolon-mcp-server instance via MCP HTTP protocol.
The server handles fact extraction (via `remember`) and retrieval (via `recall`).

Requirements:
    pip install ember-benchmark[eidolon]

Usage:
    adapter = EidolonMCPAdapter(server_url="http://localhost:3456")
    results = await ember.run(adapter)

The server must be running before tests start. Use setup() to verify connectivity.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from ember.adapter import MemoryAdapter
from ember.types import ExtractedFact, Message, SearchResult, SeededFact


class EidolonMCPAdapter(MemoryAdapter):
    """
    Adapter for eidolon-mcp-server (https://github.com/your-org/eidolon-mcp-server).

    Talks to the MCP server via HTTP JSON-RPC. The server handles:
    - Fact extraction: via `remember` tool (stores user_said + i_said + extracted facts)
    - Fact retrieval: via `recall` tool (search by query, type, limit)
    - Fact seeding: via `remember` with pre-formatted facts_learned
    - Reset: via `correct` tool to delete all facts
    """

    def __init__(
        self,
        server_url: str = "http://localhost:3456",
        user_id: str = "ember-eval-user",
        timeout: float = 30.0,
    ):
        self.server_url = server_url.rstrip("/")
        self.endpoint = f"{self.server_url}/mcp"
        self.user_id = user_id
        self.timeout = timeout
        self._session_id: str | None = None
        self._req_id = 0
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "Eidolon MCP Server"

    @property
    def supports_two_way_memory(self) -> bool:
        return True  # eidolon stores companion-expressed facts

    @property
    def supports_graceful_omission(self) -> bool:
        return False  # eidolon doesn't filter by emotional context yet

    # ------------------------------------------------------------------
    # MCP transport
    # ------------------------------------------------------------------

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    async def _post(self, payload: dict) -> dict:
        """Send JSON-RPC over HTTP, handle SSE responses."""
        assert self._client is not None
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["mcp-session-id"] = self._session_id

        resp = await self._client.post(self.endpoint, json=payload, headers=headers)

        if "mcp-session-id" in resp.headers:
            self._session_id = resp.headers["mcp-session-id"]

        if resp.status_code == 202 or not resp.content.strip():
            return {}

        content_type = resp.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return self._parse_sse(resp.text)
        return resp.json()

    @staticmethod
    def _parse_sse(sse_text: str) -> dict:
        for line in sse_text.splitlines():
            if line.startswith("data:"):
                data = line[5:].strip()
                if data and data != "[DONE]":
                    try:
                        return json.loads(data)
                    except json.JSONDecodeError:
                        pass
        return {}

    async def _call_tool(self, tool_name: str, arguments: dict | None = None) -> str:
        """Call an MCP tool and return text content."""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments or {}},
            "id": self._next_id(),
        }
        result = await self._post(payload)
        if "error" in result:
            raise RuntimeError(f"MCP tool '{tool_name}' error: {result['error']}")
        content = result.get("result", {}).get("content", [])
        return content[0].get("text", "") if content else ""

    # ------------------------------------------------------------------
    # MemoryAdapter implementation
    # ------------------------------------------------------------------

    async def setup(self) -> None:
        self._client = httpx.AsyncClient(timeout=self.timeout)
        # MCP initialize handshake
        payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ember-benchmark", "version": "0.1.0"},
            },
            "id": self._next_id(),
        }
        await self._post(payload)
        await self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        # Set eval user
        await self._call_tool("set_user", {"user_id": self.user_id})

    async def teardown(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def ingest_conversation(self, messages: list[Message]) -> None:
        """Feed conversation turns via eidolon's `remember` tool."""
        # Group into user/assistant pairs
        i = 0
        while i < len(messages):
            user_msg = ""
            asst_msg = ""
            if i < len(messages) and messages[i].role == "user":
                user_msg = messages[i].content
                i += 1
            if i < len(messages) and messages[i].role == "assistant":
                asst_msg = messages[i].content
                i += 1

            if user_msg or asst_msg:
                await self._call_tool("remember", {
                    "user_said": user_msg,
                    "i_said": asst_msg,
                })

    async def wait_for_extraction(self, timeout_seconds: float = 60) -> None:
        # eidolon's remember() extracts synchronously inline
        pass

    async def get_extracted_facts(self) -> list[ExtractedFact]:
        """Retrieve all stored facts via `recall` with type=fact."""
        text = await self._call_tool("recall", {"type": "fact", "limit": 200})
        return self._parse_facts_text(text)

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search via eidolon's `recall` tool."""
        text = await self._call_tool("recall", {
            "query": query,
            "type": "fact",
            "limit": limit,
        })
        facts = self._parse_facts_text(text)
        return [
            SearchResult(
                fact=f.fact,
                score=f.confidence,
                predicate=f.predicate,
            )
            for f in facts
        ]

    async def seed_facts(self, facts: list[SeededFact]) -> None:
        """Seed facts by calling `remember` with pre-formatted facts_learned."""
        # Format facts in eidolon's PREDICATE:category:reasoning:text:confidence format
        # Include temporal data in metadata if supported by eidolon
        formatted = []
        for f in facts:
            base = f"{f.predicate}:{f.category}:explicit:{f.fact}:{f.importance}"
            # Append ISO timestamp if present (eidolon can optionally parse this)
            if f.created_at:
                base += f"|created_at={f.created_at.isoformat()}"
            if f.updated_at:
                base += f"|updated_at={f.updated_at.isoformat()}"
            formatted.append(base)

        # Batch into groups to avoid huge payloads
        batch_size = 5
        for i in range(0, len(formatted), batch_size):
            batch = formatted[i:i + batch_size]
            facts_str = "; ".join(batch)
            await self._call_tool("remember", {
                "user_said": "[EMBER seed: eval facts pre-loaded]",
                "i_said": "[acknowledged]",
                "facts_learned": facts_str,
            })

    async def reset(self) -> None:
        """Delete all facts for the eval user."""
        # Use correct tool to diagnose and delete all
        try:
            diagnosis = await self._call_tool("correct", {
                "description": "all facts",
                "action": "diagnose",
            })
            ids = re.findall(r"id=([a-f0-9-]{8,})", diagnosis)
            for fact_id in ids:
                await self._call_tool("correct", {
                    "action": "delete",
                    "target_id": fact_id,
                })
        except RuntimeError:
            pass  # No facts to delete

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_facts_text(text: str) -> list[ExtractedFact]:
        """
        Parse eidolon's recall output format into ExtractedFact objects.

        Eidolon returns facts formatted like:
            • [PREDICATE] fact text here (confidence: 0.9, category: personal)
        """
        facts = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("No ") or line.startswith("---"):
                continue

            # Try to parse structured format: [PREDICATE] text (confidence: X, ...)
            match = re.match(
                r'[•\-*]?\s*\[(\w+)\]\s+(.+?)(?:\s*\(confidence:\s*([\d.]+))?',
                line,
            )
            if match:
                facts.append(ExtractedFact(
                    fact=match.group(2).rstrip(" ("),
                    predicate=match.group(1),
                    confidence=float(match.group(3)) if match.group(3) else 1.0,
                ))
            elif len(line) > 5:
                # Fallback: treat as plain text fact
                facts.append(ExtractedFact(fact=line))

        return facts

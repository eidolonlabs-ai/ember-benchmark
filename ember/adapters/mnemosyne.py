"""
Mnemosyne MCP adapter for EMBER.

Connects to a running Mnemosyne server (http://localhost:3100) via the
MCP streamable-http transport.  Mnemosyne is a multi-layer cognitive
companion memory platform that stores facts as a knowledge graph with
pgvector embeddings.

Requirements:
    pip install httpx

Usage:
    adapter = MnemosyneAdapter(server_url="http://localhost:3100")
    results = await ember.run(adapter)

The Mnemosyne server must already be running (docker compose up) before
tests start. See mnemosyne/README.md for setup instructions.
"""

from __future__ import annotations

import json
import secrets
from typing import Any

import httpx

from ember.adapter import MemoryAdapter
from ember.types import ExtractedFact, Message, SearchResult, SeededFact


class MnemosyneAdapter(MemoryAdapter):
    """
    Adapter for the Mnemosyne companion memory platform.

    Talks to the MCP streamable-http server via JSON-RPC.  The server
    handles:
    - Fact extraction : extract_session_facts (LLM-driven, post-session)
    - Fact storage    : store_fact (direct, structured write)
    - Fact retrieval  : search_memory (hybrid semantic + recency + importance)
    - Reset           : fresh user + companion on every reset()

    Supports two-way memory (scope='shared') and graceful omission
    (emotional intent filtering via the 'intent' parameter).
    """

    def __init__(
        self,
        server_url: str = "http://localhost:3100",
        timeout: float = 300.0,
    ):
        self.server_url = server_url.rstrip("/")
        self.endpoint = f"{self.server_url}/mcp"
        self.timeout = timeout

        self._session_id: str | None = None
        self._api_key: str | None = None
        self._companion_id: str | None = None
        self._req_id = 0
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "Mnemosyne"

    @property
    def supports_two_way_memory(self) -> bool:
        # Mnemosyne has scope='shared' on MemoryEdge
        return True

    @property
    def supports_graceful_omission(self) -> bool:
        # search_memory intent='casual' gates HIGH-salience content
        return True

    # ------------------------------------------------------------------
    # MCP transport (mirrors EidolonMCPAdapter pattern)
    # ------------------------------------------------------------------

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    async def _post(self, payload: dict) -> dict:
        """Send a JSON-RPC request; handle SSE responses."""
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

        # 202 Accepted or empty body → notification was ACKed, no result
        if resp.status_code == 202 or not resp.content.strip():
            return {}

        content_type = resp.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return self._parse_sse(resp.text)
        return resp.json()

    @staticmethod
    def _parse_sse(sse_text: str) -> dict:
        """Extract the first JSON object from an SSE stream."""
        for line in sse_text.splitlines():
            if line.startswith("data:"):
                data = line[5:].strip()
                if data and data != "[DONE]":
                    try:
                        return json.loads(data)
                    except json.JSONDecodeError:
                        pass
        return {}

    async def _call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> Any:
        """Call an MCP tool and return the parsed text content (always dict or list)."""
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
        text = content[0].get("text", "") if content else ""
        if not text:
            return {}
        # FastMCP wraps tool errors in content text starting with "Error executing tool"
        if text.startswith("Error executing tool"):
            raise RuntimeError(f"MCP tool '{tool_name}' failed: {text[:200]}")
        try:
            parsed = json.loads(text)
            # If the JSON decodes to a plain string, try one more level
            if isinstance(parsed, str):
                try:
                    return json.loads(parsed)
                except json.JSONDecodeError:
                    return {}
            return parsed
        except json.JSONDecodeError:
            return {}

    # ------------------------------------------------------------------
    # MemoryAdapter lifecycle
    # ------------------------------------------------------------------

    async def setup(self) -> None:
        """Open HTTP client, complete MCP handshake, provision user + companion."""
        self._client = httpx.AsyncClient(timeout=self.timeout)

        # 1. MCP initialize handshake
        await self._post(
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "ember-benchmark", "version": "0.1.0"},
                },
                "id": self._next_id(),
            }
        )
        await self._post(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        )

        # 2. Provision a fresh user for this eval run (random email avoids unique constraint)
        run_id = secrets.token_hex(8)
        user_data = await self._call_tool(
            "provision_user",
            {"email": f"ember-eval-{run_id}@example.com", "timezone": "UTC"},
        )
        self._api_key = user_data["api_key"]

        # 3. Create a companion (facts are scoped per companion)
        companion_data = await self._call_tool(
            "create_companion",
            {
                "api_key": self._api_key,
                "name": "Ember Eval Companion",
                "persona": "A neutral, empathetic companion used for benchmark evaluation.",
                "personality_traits": "empathetic,curious",
            },
        )
        self._companion_id = companion_data["companion_id"]

    async def teardown(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # MemoryAdapter interface
    # ------------------------------------------------------------------

    async def ingest_conversation(self, messages: list[Message]) -> None:
        """
        Feed a conversation into Mnemosyne via extract_session_facts.

        Formats the message list as 'User: ...\nAssistant: ...' text and
        calls the LLM-backed extraction tool.
        """
        lines = []
        for msg in messages:
            role = "User" if msg.role == "user" else "Assistant"
            lines.append(f"{role}: {msg.content}")
        conversation_text = "\n".join(lines)

        try:
            await self._call_tool(
                "extract_session_facts",
                {
                    "api_key": self._api_key,
                    "companion_id": self._companion_id,
                    "conversation_text": conversation_text,
                },
            )
        except RuntimeError:
            # LLM or DB errors during extraction are non-fatal;
            # get_extracted_facts will simply return empty results.
            pass

    async def wait_for_extraction(self, timeout_seconds: float = 60) -> None:
        """No-op: extract_session_facts is synchronous (blocks until LLM finishes)."""
        pass

    async def get_extracted_facts(self) -> list[ExtractedFact]:
        """
        Retrieve all extracted facts via a set of broad search_memory queries.

        Mnemosyne has no 'list all' endpoint, so we probe with several
        high-coverage queries and deduplicate by fact text.
        """
        probe_queries = [
            "user life personal history",
            "feelings emotions mental health anxiety grief loss",
            "work job career layoff burnout identity",
            "family relationships friends partner breakup",
            "location city moved home",
            "health condition diagnosis therapy",
            "belief values faith spiritual",
            "companion values preferences conversations honesty",
            "pet dog cat animal",
            "hobby interest past activity painting",
            "shame guilt relief anger identity reframe",
            "financial money savings plans",
        ]
        seen: dict[str, ExtractedFact] = {}
        for query in probe_queries:
            try:
                result = await self._call_tool(
                    "search_memory",
                    {
                        "api_key": self._api_key,
                        "companion_id": self._companion_id,
                        "query": query,
                        "intent": "recall",
                        "limit": 50,
                    },
                )
                if not isinstance(result, dict):
                    continue
                for f in result.get("facts", []):
                    key = f["fact_text"].strip().lower()
                    if key not in seen:
                        seen[key] = ExtractedFact(
                            fact=f["fact_text"],
                            predicate=f.get("predicate", ""),
                            category=f.get("category", ""),
                            importance=f.get("importance", 0.5),
                            confidence=f.get("confidence", 1.0),
                            scope=f.get("scope", "user"),
                        )
            except RuntimeError:
                continue  # tool error — skip this probe
        return list(seen.values())

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search Mnemosyne using hybrid semantic retrieval."""
        result = await self._call_tool(
            "search_memory",
            {
                "api_key": self._api_key,
                "companion_id": self._companion_id,
                "query": query,
                "intent": "factual",
                "limit": limit,
            },
        )
        if not isinstance(result, dict):
            return []
        return [
            SearchResult(
                fact=f["fact_text"],
                score=f.get("score", 0.0),
                predicate=f.get("predicate", ""),
                metadata={
                    "category": f.get("category", ""),
                    "emotional_salience": f.get("emotional_salience", "LOW"),
                    "emotional_context": f.get("emotional_context"),
                },
            )
            for f in result.get("facts", [])
        ]

    async def seed_facts(self, facts: list[SeededFact]) -> None:
        """Pre-load facts by calling store_fact for each SeededFact."""
        for f in facts:
            # Split fact_text into a simple subject→object form for the graph
            # store_fact needs subject / predicate / obj — derive from SeededFact
            subject = "user"
            obj = f.fact  # put the full fact text as the object
            await self._call_tool(
                "store_fact",
                {
                    "api_key": self._api_key,
                    "companion_id": self._companion_id,
                    "subject": subject,
                    "predicate": f.predicate,
                    "obj": obj,
                    "fact_text": f.fact,
                    "category": f.category or "",
                    "importance": f.importance,
                    "confidence": f.confidence,
                    "emotional_salience": f.emotional_salience.value
                    if hasattr(f.emotional_salience, "value")
                    else str(f.emotional_salience),
                    "scope": f.scope.value
                    if hasattr(f.scope, "value")
                    else str(f.scope),
                },
            )

    async def reset(self) -> None:
        """
        Reset state by provisioning a fresh user + companion.

        This guarantees complete isolation between test runs without needing
        a 'delete all' endpoint.
        """
        run_id = secrets.token_hex(8)
        user_data = await self._call_tool(
            "provision_user",
            {"email": f"ember-reset-{run_id}@example.com", "timezone": "UTC"},
        )
        self._api_key = user_data["api_key"]

        companion_data = await self._call_tool(
            "create_companion",
            {
                "api_key": self._api_key,
                "name": "Ember Eval Companion",
                "persona": "A neutral, empathetic companion used for benchmark evaluation.",
                "personality_traits": "empathetic,curious",
            },
        )
        self._companion_id = companion_data["companion_id"]

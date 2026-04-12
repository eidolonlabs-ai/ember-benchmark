"""
Adapter ABC — the contract between EMBER and any memory system.

To benchmark a memory system, implement a subclass of MemoryAdapter
with 5 methods. That's it. EMBER handles everything else.

Example:
    class MyMemoryAdapter(MemoryAdapter):
        async def ingest_conversation(self, messages):
            # Feed messages into your system
            ...

        async def get_extracted_facts(self):
            # Return whatever your system extracted
            ...

    adapter = MyMemoryAdapter()
    results = await ember.run(adapter)
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ember.types import ExtractedFact, Message, SearchResult, SeededFact


class MemoryAdapter(ABC):
    """
    Abstract interface that any memory system must implement to be
    benchmarked by EMBER.

    Design principles:
    - Minimal surface area (5 methods)
    - Async-first (companion systems are typically async)
    - No opinion on storage format, embedding model, or extraction method
    - Adapters can be thin wrappers around MCP clients, direct DB access,
      REST APIs, or in-process function calls
    """

    @abstractmethod
    async def ingest_conversation(self, messages: list[Message]) -> None:
        """
        Feed a conversation into the memory system for fact extraction.

        The system should process these messages however it normally would —
        LLM extraction, NLP parsing, rule-based matching, etc.

        For systems with async/background extraction (like ai-companions'
        ARQ workers), call this and then use wait_for_extraction().
        """

    @abstractmethod
    async def wait_for_extraction(self, timeout_seconds: float = 60) -> None:
        """
        Wait for extraction to complete.

        For synchronous systems, this can be a no-op.
        For async systems (background workers, queues), poll until ready
        or raise TimeoutError.
        """

    @abstractmethod
    async def get_extracted_facts(self) -> list[ExtractedFact]:
        """
        Return all facts the system extracted from ingested conversations.

        Called after ingest_conversation + wait_for_extraction to evaluate
        extraction quality (Tier 1).
        """

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """
        Search memory with a natural language query.

        This is the core retrieval operation tested by Tier 2.
        The system should return results ranked by relevance.
        """

    @abstractmethod
    async def seed_facts(self, facts: list[SeededFact]) -> None:
        """
        Pre-load facts into the system for retrieval testing (Tier 2).

        This bypasses extraction entirely — facts are injected directly
        so retrieval can be tested in isolation.

        **CRITICAL**: Respect the `created_at` and `updated_at` timestamps
        on each SeededFact. If the adapter uses recency in ranking (common for
        hybrid scoring), these timestamps control the age of facts and thus
        their ranking. If a fact has `created_at` = 30 days ago, the system
        must store it as if it was created 30 days ago, not "now".

        If the adapter doesn't support custom timestamps, raise NotImplementedError.
        """

    @abstractmethod
    async def reset(self) -> None:
        """
        Clear all memory state for a clean test run.

        Called between test cases to ensure isolation.
        Must remove all facts, embeddings, and conversation history
        for the test user/session.
        """

    # ------------------------------------------------------------------
    # Optional hooks (override if your system supports them)
    # ------------------------------------------------------------------

    async def setup(self) -> None:
        """Called once before any tests. Connect, authenticate, etc."""

    async def teardown(self) -> None:
        """Called once after all tests. Disconnect, cleanup, etc."""

    @property
    def name(self) -> str:
        """Human-readable name for reports."""
        return self.__class__.__name__

    @property
    def supports_two_way_memory(self) -> bool:
        """Whether the system stores companion-expressed facts (scope=shared)."""
        return False

    @property
    def supports_graceful_omission(self) -> bool:
        """Whether the system can suppress sensitive content for casual queries."""
        return False

"""
AI Companions adapter for EMBER.

Connects directly to ai-companions' Python services (VectorMemoryService,
fact extraction) for in-process evaluation. Requires the ai-companions
backend to be importable (add it to PYTHONPATH or install).

Requirements:
    pip install ember-benchmark[ai-companions]

Usage:
    adapter = AICompanionsAdapter(db_url="postgresql+asyncpg://...")
    results = await ember.run(adapter)

For cloud testing, point db_url at your Fly.io/Neon PostgreSQL instance.
"""

from __future__ import annotations

import uuid
from typing import Any

from ember.adapter import MemoryAdapter
from ember.types import ExtractedFact, Message, SearchResult, SeededFact


class AICompanionsAdapter(MemoryAdapter):
    """
    Adapter for ai-companions backend (direct Python import).

    Uses:
    - Fact extraction: calls the same extraction pipeline as ARQ workers
    - Retrieval: calls VectorMemoryService.search_memories()
    - Seeding: inserts directly into memory_items via SQLAlchemy
    - Reset: deletes all memory_items for the test user

    Requires ai-companions backend on PYTHONPATH.
    """

    def __init__(
        self,
        db_url: str | None = None,
        user_id: str | None = None,
        character_id: str | None = None,
    ):
        self.db_url = db_url
        self.user_id = user_id or str(uuid.uuid4())
        self.character_id = character_id or str(uuid.uuid4())
        self._db_session = None
        self._vector_service = None

    @property
    def name(self) -> str:
        return "AI Companions (pgvector)"

    @property
    def supports_two_way_memory(self) -> bool:
        return True  # has scope=shared on MemoryEdge

    @property
    def supports_graceful_omission(self) -> bool:
        return False  # not yet implemented in VectorMemoryService

    # ------------------------------------------------------------------
    # MemoryAdapter implementation (stubs — wire to real services)
    # ------------------------------------------------------------------

    async def setup(self) -> None:
        """
        Initialize DB connection and services.

        TODO: Wire to real ai-companions imports:
            from app.db.session import get_async_engine
            from app.services.vector_memory import VectorMemoryService
        """
        # Lazy import to avoid hard dependency
        try:
            from app.db.session import async_session_factory
            from app.services.vector_memory import VectorMemoryService

            self._db_session = async_session_factory()
            self._vector_service = VectorMemoryService(self._db_session)
        except ImportError:
            raise ImportError(
                "ai-companions backend not found on PYTHONPATH. "
                "Run from the ai-companions repo or set PYTHONPATH=backend"
            )

    async def teardown(self) -> None:
        if self._db_session:
            await self._db_session.close()

    async def ingest_conversation(self, messages: list[Message]) -> None:
        """
        Run fact extraction on messages.

        TODO: Wire to real extraction:
            from app.services.fact_extraction import extract_facts_from_messages
        """
        raise NotImplementedError(
            "Wire to app.services.fact_extraction.extract_facts_from_messages()"
        )

    async def wait_for_extraction(self, timeout_seconds: float = 60) -> None:
        # ai-companions uses background workers, but for eval we'd call
        # extraction synchronously. No wait needed.
        pass

    async def get_extracted_facts(self) -> list[ExtractedFact]:
        """
        Query memory_items table for extracted facts.

        TODO: Wire to real query:
            from app.models.memory import MemoryEdge
            stmt = select(MemoryEdge).where(MemoryEdge.user_id == self.user_id)
        """
        raise NotImplementedError(
            "Wire to SQLAlchemy query on MemoryEdge table"
        )

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """
        Search via VectorMemoryService.search_memories().

        TODO: Wire to real search:
            results = await self._vector_service.search_memories(
                query=query, user_id=self.user_id, limit=limit,
                track_retrieval=False  # don't pollute retrieval counts during eval
            )
        """
        raise NotImplementedError(
            "Wire to VectorMemoryService.search_memories()"
        )

    async def seed_facts(self, facts: list[SeededFact]) -> None:
        """
        Insert facts directly into memory_items + generate embeddings.

        **CRITICAL**: Respect the `created_at` and `updated_at` timestamps on each fact.
        These are used by Tier 2b (recency bias) to test temporal ranking.

        TODO: Wire to real insert:
            from app.models.memory import MemoryEdge
            for f in facts:
                edge = MemoryEdge(
                    user_id=self.user_id,
                    fact_text=f.fact,
                    predicate=f.predicate,
                    importance=f.importance,
                    emotional_salience=f.emotional_salience.value,  # Store as string
                    scope=f.scope.value,
                    created_at=f.created_at or datetime.utcnow(),  # Respect provided timestamp
                    updated_at=f.updated_at or (f.created_at or datetime.utcnow()),
                )
                db.add(edge)
            await db.commit()
            
            # Then generate embeddings for each fact
            # This is critical for retrieval ranking to include recency
        """
        raise NotImplementedError(
            "Wire to direct MemoryEdge insert + embedding generation with timestamp preservation"
        )

    async def reset(self) -> None:
        """
        Delete all memory_items for the test user.

        TODO: Wire to real delete:
            await db.execute(
                delete(MemoryEdge).where(MemoryEdge.user_id == self.user_id)
            )
            await db.commit()
        """
        raise NotImplementedError(
            "Wire to DELETE FROM memory_items WHERE user_id = ..."
        )

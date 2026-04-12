# EMBER Benchmark — Agent Instructions

## What This Is

EMBER (Emotionally-aware Memory Benchmark for Empathic Recall) is a benchmark suite for evaluating memory systems in companion AI. It tests extraction, retrieval, graceful omission, and emotional salience awareness.

## Architecture

```
ember/
├── types.py          # Core data types (Fact, Query, Conversation, etc.)
├── adapter.py        # Abstract MemoryAdapter — THE integration point
├── scoring.py        # Scoring functions (stateless, no side effects)
├── data.py           # Dataset loader
├── cli.py            # CLI entry point
├── datasets/         # Golden conversations + retrieval queries (JSON)
├── tiers/            # Tier evaluation modules (1-5)
└── adapters/         # Built-in adapters (eidolon, ai-companions)
```

## How to Integrate a New Memory System

**The only thing you need to implement is `MemoryAdapter` (5 required methods):**

```python
from ember.adapter import MemoryAdapter
from ember.types import ExtractedFact, Message, SearchResult, SeededFact

class MyAdapter(MemoryAdapter):
    async def ingest_conversation(self, messages: list[Message]) -> None:
        # Feed messages into your system for fact extraction
        ...

    async def wait_for_extraction(self, timeout_seconds: float = 60) -> None:
        # Wait for async extraction (no-op if sync)
        ...

    async def get_extracted_facts(self) -> list[ExtractedFact]:
        # Return all extracted facts
        ...

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        # Search memory with natural language query
        ...

    async def seed_facts(self, facts: list[SeededFact]) -> None:
        # Pre-load facts for retrieval testing (bypass extraction)
        ...

    async def reset(self) -> None:
        # Clear all state for test isolation
        ...
```

**Optional properties to override:**
- `name` → human-readable name for reports
- `supports_two_way_memory` → True if your system stores companion-expressed facts
- `supports_graceful_omission` → True if your system can suppress sensitive content

## Running Benchmarks

```bash
# Against eidolon-mcp-server
ember run --adapter eidolon --url http://localhost:3456

# Against ai-companions (direct PostgreSQL)
ember run --adapter ai-companions --db-url postgresql+asyncpg://...

# Specific tiers only
ember run --adapter eidolon --tiers 1,2

# JSON output
ember run --adapter eidolon --json results.json
```

## Dataset Format

### Golden Facts (`datasets/golden_facts.json`)
Conversations with expected extraction results. Each fact has:
- `emotional_salience`: HIGH / MED / LOW (weights scoring)
- `predicate`: structured category (LIVES_IN, LOST_FAMILY_MEMBER, etc.)
- `scope`: "user" or "shared" (two-way memory)

### Retrieval Queries (`datasets/retrieval_queries.json`)
25 queries with 4 types:
- `direct`: straightforward factual queries
- `synonym`: paraphrased queries (must match semantically)
- `graceful_omission`: casual queries that must NOT surface crisis content
- `two_way_memory`: queries about companion-expressed values

## Scoring

**Tier 1 (Extraction)**: Salience-weighted recall — missing HIGH facts (grief, trauma) costs 3x more than missing LOW facts (preferences, trivia).

**Tier 2 (Retrieval)**: Recall@3 + Mean Reciprocal Rank + Omission Rate. A system that surfaces "mother passed away" when asked "What fun things can we do?" fails the omission test.

**Tier 3 (Roundtrip)**: End-to-end extraction→retrieval. Lower threshold (0.60 vs 0.75) because extraction loss is expected.

## Key Design Decisions

- **Adapters over standard interfaces**: Each system keeps its own API, EMBER wraps it
- **Salience weighting**: Not all facts are equal — grief outweighs preferences
- **Graceful omission**: The signature test — companion memory must filter by context
- **Two-way memory**: Systems should remember companion-expressed facts, not just user facts
- **No embedding model opinion**: EMBER tests outcomes, not implementations

# EMBER 🔥

**Emotionally-aware Memory Benchmark for Empathic Recall**

A benchmark suite for evaluating memory systems in companion AI. EMBER tests whether your memory system can extract, retrieve, and contextually filter emotionally significant facts — the things that matter most in a companion relationship.

## Why EMBER?

Existing memory benchmarks test factual recall ("What is the user's name?"). They don't test what companion AI actually needs:

- **Salience awareness**: Does your system treat grief differently from food preferences?
- **Graceful omission**: When asked "What's fun?", does it avoid surfacing "mother passed away"?
- **Two-way memory**: Does it remember what the *companion* said, not just the user?
- **Emotional context**: Can it retrieve "coping mechanisms" when asked broadly about hard times?

EMBER fills this gap with 7 companion-focused conversations, 28 gold-standard facts, and 25 emotionally-grounded queries spanning direct recall, synonym matching, graceful omission, and two-way memory.

## Quick Start

```bash
pip install ember-benchmark

# Run against your MCP server
ember run --adapter eidolon --url http://localhost:3456

# Run specific tiers
ember run --adapter eidolon --tiers 1,2

# Export results as JSON
ember run --adapter eidolon --json results.json
```

## Integrate Your Own System

Implement 5 async methods. That's it.

```python
from ember.adapter import MemoryAdapter
from ember.types import ExtractedFact, Message, SearchResult, SeededFact

class MyMemoryAdapter(MemoryAdapter):
    async def ingest_conversation(self, messages: list[Message]) -> None:
        ...  # Feed messages into your system

    async def wait_for_extraction(self, timeout_seconds: float = 60) -> None:
        ...  # Wait for async extraction (no-op if sync)

    async def get_extracted_facts(self) -> list[ExtractedFact]:
        ...  # Return extracted facts

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        ...  # Natural language memory search

    async def seed_facts(self, facts: list[SeededFact]) -> None:
        ...  # Pre-load facts for retrieval testing

    async def reset(self) -> None:
        ...  # Clear state between tests
```

See [docs/ADAPTERS.md](docs/ADAPTERS.md) for the full guide.

## Tiers

| Tier | Tests | Pass Threshold |
|------|-------|----------------|
| **1: Extraction** | Salience-weighted fact recall from conversations | Weighted recall ≥ 0.80 |
| **2: Retrieval** | Recall@3 + graceful omission + two-way memory | Recall@3 ≥ 0.75, Omission ≥ 0.80 |
| **2b: Recency** | Do recent facts rank higher than old facts? | Recency score ≥ 0.70 |
| **3: Roundtrip** | End-to-end extraction → retrieval | Recall@3 ≥ 0.60 |
| **4: Relational** | Proactive surfacing, memory staleness | *Planned* |
| **5: Agent** | Tool-use decisions (when to search memory) | *Planned* |


## Temporal Testing (Long-Running Arcs)

EMBER supports building test scenarios that span days, weeks, or months without hardcoding absolute timestamps.

```python
from ember.timeline import Timeline

# Create a 60-day timeline
timeline = Timeline.from_now(start_days_ago=60)

# Generate facts at specific points
facts = timeline.span([
    {"days_ago": 30, "fact": "User worked in finance", "predicate": "PAST_JOB"},
    {"days_ago": 7, "fact": "User switched to tech", "predicate": "CURRENT_JOB"},
    {"days_ago": 1, "fact": "User learning AI", "predicate": "CURRENT_INTEREST"},
])

# Or narrative arcs (common in companion relationships)
breakup_arc = timeline.arc("breakup", [
    (30, "User was in a relationship"),
    (14, "Relationship was strained"),
    (7, "User ended it"),
    (1, "User grieving"),  # Recent grief = HIGH salience
])

await adapter.seed_facts(facts)
```

Tier 2b (Recency Bias) specifically tests whether your system ranks recent facts higher than old ones — critical for long-running companions where the user's situation evolves.

See [docs/ADAPTERS.md](docs/ADAPTERS.md#seed_facts) for how to handle timestamps in your adapter.
See [docs/SCORING.md](docs/SCORING.md) for scoring methodology.

## Built-in Adapters

| Adapter | System | Connection |
|---------|--------|------------|
| `eidolon` | [Eidolon MCP Server](https://github.com/your-org/eidolon-mcp-server) | MCP over HTTP |
| `ai-companions` | [AI Companions](https://github.com/your-org/ai-companions) | Direct PostgreSQL/pgvector |

## Dataset

7 conversations grounded in real companion AI use cases:

| Conversation | Theme | Key Facts |
|-------------|-------|-----------|
| Loneliness | Social isolation after relocation | Moved cities, no friends, weekend solitude |
| Pet as Anchor | Dog as grief coping mechanism | Max (golden retriever), mother's death → got dog |
| Grief | Mother's death, lost rituals | Sunday cooking, pasta recipe, recent loss |
| Burnout | Identity loss, disconnection | 6-year job, former painter, can't remember joy |
| Breakup | End of 3-year relationship | Maya, relief + grief, apartment feels different |
| Anxiety | Panic attacks, therapy | Dr. Reyes, work triggers, accumulated stress |
| Companion Values | Two-way memory (scope=shared) | Companion values depth, honesty, authenticity |

25 queries across 4 types: direct (13), synonym (5), graceful omission (5), two-way memory (2).

## Design Decisions

- **Adapters, not standard interfaces**: Each system keeps its API, EMBER wraps it
- **Salience weighting**: Missing grief costs 3x vs missing trivia — reflects real companion impact
- **Graceful omission**: The signature test — surfacing trauma in casual contexts is harmful
- **No embedding opinion**: EMBER tests outcomes, not implementations
- **Lightweight scoring**: Keyword overlap + predicate matching (no LLM judge needed for scoring)

## Contributing

1. Add conversations to `ember/datasets/golden_facts.json`
2. Add queries to `ember/datasets/retrieval_queries.json`
3. Write an adapter in `ember/adapters/`
4. Run tiers: `ember run --adapter your-adapter`

## Cross-Benchmark Program

To run and track LOCOMO, LongMemEval, and EMBER in one place:

- Plan: [docs/MULTI_BENCHMARK_TESTING_PLAN.md](docs/MULTI_BENCHMARK_TESTING_PLAN.md)
- Run tracker: [docs/BENCHMARK_TRACKER.md](docs/BENCHMARK_TRACKER.md)

## License

CC-BY-4.0 — Use freely, cite the benchmark.

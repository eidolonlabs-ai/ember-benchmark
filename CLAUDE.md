# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**EMBER** (Emotionally-aware Memory Benchmark for Empathic Recall) is a benchmark suite for evaluating memory systems in companion AI. It tests whether memory systems can extract, retrieve, and contextually filter emotionally significant facts—the things that matter most in a companion relationship.

Unlike traditional memory benchmarks (which test factual recall), EMBER tests:
- **Salience awareness**: Does the system treat grief differently from food preferences?
- **Graceful omission**: Does it avoid surfacing trauma when asked casual questions?
- **Two-way memory**: Does it remember what the *companion* said, not just the user?
- **Temporal awareness**: Do recent facts rank higher than old ones?

## Development Commands

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install adapter-specific dependencies
pip install -e ".[ai-companions,eidolon]"

# Run full benchmark against an adapter
ember run --adapter eidolon --url http://localhost:3456
ember run --adapter eidolon --tiers 1,2

# Export results as JSON
ember run --adapter eidolon --json results.json

# Run tests
pytest tests/ -v
pytest tests/ -k "tier1" -v              # Single tier
pytest tests/ -m "llm_eval" --skip-slow  # Skip slow LLM evaluations

# Linting
ruff check ember/
ruff format ember/

# Build distribution
pip install build
python -m build
```

## Architecture

### Core Structure

```
ember/
├── adapter.py           # Abstract MemoryAdapter base class (THE integration point)
├── types.py             # Pydantic models (Message, Conversation, Fact, Query, etc.)
├── cli.py               # argparse entry point (ember run --adapter ...)
├── scoring.py           # Stateless scoring functions (salience-weighted recall, Recall@k, etc.)
├── data.py              # Dataset loader (golden_facts.json, retrieval_queries.json)
├── timeline.py          # Temporal test data generation (Timeline.from_now(), arc())
├── tiers/               # Tier evaluation modules
│   ├── tier1_extraction.py      # Salience-weighted fact extraction scoring
│   ├── tier2_retrieval.py       # Recall@3 + Omission + Two-way memory
│   ├── tier2b_recency.py        # Recency bias (recent facts ranked higher)
│   └── tier3_roundtrip.py       # End-to-end extraction→retrieval
├── adapters/            # Built-in memory system adapters
│   ├── eidolon_mcp.py           # Eidolon via MCP/HTTP
│   ├── eidolon_agent_memory.py  # Eidolon Agent Memory (multi-layer cognitive)
│   └── ai_companions.py         # AI Companions (direct PostgreSQL + pgvector)
└── datasets/            # Golden facts + queries (JSON)
    ├── golden_facts.json        # 7 conversations, 28 gold facts
    └── retrieval_queries.json   # 25 queries (direct, synonym, omission, two-way)
```

### Adapter Pattern (Key Integration Point)

Every memory system is benchmarked by implementing `MemoryAdapter` with **5 required async methods**:

```python
class MemoryAdapter(ABC):
    # Feed a conversation into the system for fact extraction
    async def ingest_conversation(self, messages: list[Message]) -> None: ...
    
    # Wait for async extraction to complete (no-op for sync systems)
    async def wait_for_extraction(self, timeout_seconds: float = 60) -> None: ...
    
    # Return all extracted facts (used by Tier 1 scoring)
    async def get_extracted_facts(self) -> list[ExtractedFact]: ...
    
    # Search memory with natural language query (used by Tier 2 scoring)
    async def search(self, query: str, limit: int = 10) -> list[SearchResult]: ...
    
    # Pre-load facts directly (bypass extraction, used by isolated retrieval testing)
    async def seed_facts(self, facts: list[SeededFact]) -> None: ...
    
    # Clear all state between test cases
    async def reset(self) -> None: ...
```

Optional properties to override: `name`, `supports_two_way_memory`, `supports_graceful_omission`.

See `docs/ADAPTERS.md` for detailed guidance.

### Scoring Philosophy

**Not all facts are equal:**

| Salience | Weight | Examples |
|----------|--------|----------|
| HIGH | 3x | Mother's death, panic attacks, breakup grief |
| MED | 2x | Coping mechanisms, therapy, past hobbies |
| LOW | 1x | City, job tenure, pet breed |

**Salience-Weighted Recall** (Tier 1):
$$\text{Score} = \frac{\sum(\text{found} \times \text{weight})}{\sum(\text{total} \times \text{weight})}$$

Missing a grief fact costs 3x more than missing a trivia fact. Pass threshold: ≥ 0.80.

**Graceful Omission** (Tier 2): When asked "What fun things can we do?", the system must NOT surface "mother passed away". Tests emotional awareness in context filtering.

**Recall@3** (Tier 2): For each query, does the top-3 contain the expected keywords? Reflects typical companion context injection (top-3 facts into the prompt).

### Dataset Format

#### Golden Facts (`ember/datasets/golden_facts.json`)
Conversations with expected extraction results. Each fact has:
- `fact`: Human-readable text
- `predicate`: Structured category (e.g., `LOST_FAMILY_MEMBER`, `LIVES_IN`)
- `emotional_salience`: HIGH / MED / LOW (weights scoring)
- `scope`: "user" or "shared" (for two-way memory tests)

#### Retrieval Queries (`ember/datasets/retrieval_queries.json`)
25 queries across 4 types:
- `direct`: Straightforward factual queries
- `synonym`: Paraphrased queries (must match semantically)
- `graceful_omission`: Casual queries that must NOT surface crisis content
- `two_way_memory`: Queries about companion-expressed values

### Tiers (Evaluation Levels)

| Tier | Tests | Pass Threshold |
|------|-------|----------------|
| **1: Extraction** | Salience-weighted recall from conversations | ≥ 0.80 |
| **2: Retrieval** | Recall@3 + graceful omission + two-way memory | Recall@3 ≥ 0.75, Omission ≥ 0.80 |
| **2b: Recency** | Do recent facts rank higher? | ≥ 0.70 |
| **3: Roundtrip** | End-to-end extraction → retrieval | ≥ 0.60 |

## Key Design Decisions

1. **Adapters, not standard interfaces** — Each system keeps its own API; EMBER wraps it. This maximizes adoption and avoids forcing architectures.

2. **Salience weighting** — Missing grief costs 3x more than missing trivia. Reflects real companion impact.

3. **Graceful omission** — The signature test. Surfacing trauma in casual contexts is harmful; systems must filter by emotional intent.

4. **No embedding opinion** — EMBER tests outcomes, not implementations. Scoring uses keyword overlap + predicate matching (no embeddings).

5. **Lightweight scoring** — Simple enough to understand and debug. No LLM judge needed.

6. **Temporal testing** — `Timeline` API allows building scenarios across days/weeks/months without hardcoding timestamps. Critical for testing recency bias.

7. **Two-way memory** — Systems should remember companion-expressed facts, not just user facts. Tests whether companions are treated as full participants.

## Common Tasks

### Adding a New Adapter

1. Create a subclass of `MemoryAdapter` in `ember/adapters/your_adapter.py`
2. Implement 5 methods: `ingest_conversation`, `wait_for_extraction`, `get_extracted_facts`, `search`, `seed_facts`, `reset`
3. Register in `cli.py` `_create_adapter()` function
4. Test: `ember run --adapter your-adapter`

See `ember/adapters/eidolon_agent_memory.py` for a full example (MCP, async extraction, timestamp handling).

### Enriching the Dataset

1. Add a new conversation to `ember/datasets/golden_facts.json`
2. Each conversation should have:
   - 3-5 HIGH salience facts (grief, trauma, identity)
   - 2-3 MED salience facts (relationships, coping)
   - 1-2 LOW salience facts (trivia, preferences)
   - Use varied predicates (not just location/pet)
   - Consider two-way memory: what would the companion express about values?

See `scripts/README.md` for dataset analysis and enrichment guidance.

### Running a Single Tier

```bash
ember run --adapter eidolon --tiers 1          # Tier 1 only
ember run --adapter eidolon --tiers 1,2,2b     # Tier 1, 2, 2b
```

### Debugging Extraction

Set environment variables to get verbose output:
```bash
EMBER_DEBUG=1 ember run --adapter eidolon --tiers 1 -v
```

Check `ember/adapters/` for adapter-specific logging.

### Testing Locally with Timeline

```python
from ember.timeline import Timeline

# Create a 60-day timeline
timeline = Timeline.from_now(start_days_ago=60)

# Generate facts at specific points
facts = timeline.span([
    {"days_ago": 30, "fact": "User worked in finance", "predicate": "PAST_JOB"},
    {"days_ago": 7, "fact": "User switched to tech", "predicate": "CURRENT_JOB"},
])

# Or narrative arcs
breakup_arc = timeline.arc("breakup", [
    (30, "User was in a relationship"),
    (7, "Relationship ended"),
    (1, "User grieving"),
])
```

## Active Development Areas

Based on recent commits:
- **EidolonAgentMemoryAdapter**: Multi-layer cognitive memory with improved error handling and logging (see commits c48ebbe, ec47c67)
- **Multi-benchmark tracking**: Integration with LOCOMO, LongMemEval (see docs/MULTI_BENCHMARK_TESTING_PLAN.md)
- **Cross-adapter testing**: Comparing different memory implementations

## Gotchas & Important Details

1. **Timestamps in `seed_facts`**: If your adapter supports recency-based ranking, you MUST respect the `created_at`/`updated_at` timestamps from `SeededFact`. Tier 2b tests this explicitly.

2. **Graceful omission requires intentional design**: It's not automatic. Your system must either:
   - Have an emotional intent parameter (e.g., `intent="casual"` suppresses crisis content)
   - Or implement context-aware filtering logic
   - If not supported, set `supports_graceful_omission=False`

3. **Predicate matching is strict**: Scoring requires exact predicate match (e.g., `LOST_FAMILY_MEMBER`). If your system doesn't use predicates, use empty string and rely on keyword overlap.

4. **Async-first design**: All adapters are async. Synchronous systems can have `wait_for_extraction()` as a no-op, but extraction still must be awaitable.

5. **Test isolation**: `reset()` is called between test cases. It must clear ALL state—conversations, facts, embeddings, everything.

6. **Two-way memory is optional**: Set `supports_two_way_memory=False` if your system only tracks user facts. Queries with `scope="shared"` will be skipped.

## Related Documentation

- **docs/ADAPTERS.md** — Complete adapter implementation guide with patterns
- **docs/SCORING.md** — Detailed scoring methodology and formulas
- **.github/copilot-instructions.md** — Agent-specific guidance (overlaps with this file)
- **README.md** — User-facing benchmark overview
- **scripts/README.md** — Dataset enrichment and analysis scripts

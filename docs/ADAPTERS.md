# EMBER Adapter Guide

## Writing a New Adapter

To benchmark your memory system with EMBER, implement a subclass of `MemoryAdapter`. This document explains each method and common patterns.

## Required Methods

### `ingest_conversation(messages: list[Message]) -> None`
Feed a conversation into your system. Messages alternate user/assistant roles.

**Patterns:**
- **MCP/REST systems**: POST each message pair to your API
- **Direct DB systems**: Call your extraction function in-process
- **Queue-based systems**: Enqueue messages, then use `wait_for_extraction()`

```python
# MCP adapter example
async def ingest_conversation(self, messages):
    for i in range(0, len(messages), 2):
        user_msg = messages[i].content if i < len(messages) else ""
        asst_msg = messages[i+1].content if i+1 < len(messages) else ""
        await self.mcp_client.remember(user_msg, asst_msg)
```

### `wait_for_extraction(timeout_seconds: float) -> None`
Wait for async extraction to complete. No-op for synchronous systems.

```python
# Background worker pattern (e.g., ai-companions ARQ)
async def wait_for_extraction(self, timeout_seconds=60):
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        count = await self.db.scalar(select(func.count()).where(...))
        if count > 0:
            return
        await asyncio.sleep(1)
    raise TimeoutError("Extraction did not complete")
```

### `get_extracted_facts() -> list[ExtractedFact]`
Return everything your system extracted. Map to `ExtractedFact`:
- `fact`: human-readable text
- `predicate`: category tag (optional but helps scoring)
- `importance`: 0-1 system-assigned importance
- `confidence`: 0-1 extraction confidence

### `search(query: str, limit: int) -> list[SearchResult]`
Natural language search. Return results ranked by relevance.
- `fact`: the fact text
- `score`: relevance score (0-1, used for ranking)

### `seed_facts(facts: list[SeededFact]) -> None`
Inject facts directly (bypass extraction) for isolated retrieval testing.

**This is critical** — Tier 2 tests retrieval in isolation by pre-loading known facts. If your system doesn't support direct insertion, simulate it by wrapping facts in synthetic conversations.

**⚠️ CRITICAL: Timestamps**

Each `SeededFact` has optional `created_at` and `updated_at` fields. If your system uses recency in ranking (hybrid scoring typical), you **must** respect these timestamps:

```python
async def seed_facts(self, facts: list[SeededFact]):
    for f in facts:
        # Store with the provided timestamps, NOT "now"
        await db.insert_memory_item(
            fact=f.fact,
            created_at=f.created_at or datetime.utcnow(),  # OK to default
            updated_at=f.updated_at,
        )
```

If you can't preserve timestamps (no DB support), raise `NotImplementedError` — this disables Tier 2b (recency bias testing) for your adapter, which is fine.

**How to generate temporal test data:**

Use `ember.timeline.Timeline` to easily create multi-temporal scenarios:

```python
from ember.timeline import Timeline

timeline = Timeline.from_now(start_days_ago=60)
facts = timeline.span([
    {"days_ago": 30, "fact": "User worked in finance", "predicate": "PAST_JOB"},
    {"days_ago": 7, "fact": "User switched to tech", "predicate": "CURRENT_JOB"},
    {"days_ago": 1, "fact": "User learning AI", "predicate": "CURRENT_INTEREST"},
])

# Or narrative arcs
breakup_arc = timeline.arc("breakup", [
    (30, "User was in a relationship"),
    (7, "Relationship ended"),
    (1, "User grieving"),
])
```

### `reset() -> None`
Delete all memory state for test isolation. Called between test cases.

## Optional Properties

```python
@property
def supports_two_way_memory(self) -> bool:
    """Return True if your system stores companion-expressed facts (scope=shared)."""
    return False  # Two-way memory queries are skipped if False

@property
def supports_graceful_omission(self) -> bool:
    """Return True if your system filters sensitive content for casual queries."""
    return False  # Omission tests still run but won't affect pass/fail
```

## Example: Minimal HTTP Adapter

```python
import httpx
from ember.adapter import MemoryAdapter
from ember.types import ExtractedFact, Message, SearchResult, SeededFact

class MyHTTPAdapter(MemoryAdapter):
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = None

    async def setup(self):
        self.client = httpx.AsyncClient(base_url=self.base_url)

    async def teardown(self):
        await self.client.aclose()

    async def ingest_conversation(self, messages):
        await self.client.post("/ingest", json={
            "messages": [{"role": m.role, "content": m.content} for m in messages]
        })

    async def wait_for_extraction(self, timeout_seconds=60):
        pass  # sync system

    async def get_extracted_facts(self):
        resp = await self.client.get("/facts")
        return [ExtractedFact(fact=f["text"], predicate=f.get("type", ""))
                for f in resp.json()]

    async def search(self, query, limit=10):
        resp = await self.client.get("/search", params={"q": query, "limit": limit})
        return [SearchResult(fact=r["text"], score=r["score"])
                for r in resp.json()]

    async def seed_facts(self, facts):
        await self.client.post("/facts/seed", json=[
            {"text": f.fact, "type": f.predicate, "importance": f.importance}
            for f in facts
        ])

    async def reset(self):
        await self.client.delete("/facts")
```

## Testing Your Adapter

```bash
# Run just Tier 2 (retrieval) to start — doesn't need LLM calls
ember run --adapter my-adapter --tiers 2

# Then add extraction tests
ember run --adapter my-adapter --tiers 1,2,3
```

## Common Issues

| Issue | Solution |
|-------|----------|
| `seed_facts` not supported | Wrap facts in synthetic conversations and call `ingest_conversation` |
| Async extraction timeout | Increase `wait_for_extraction` timeout or poll more frequently |
| Low recall on synonym queries | Your embedding model may not handle paraphrases well — this is what EMBER tests |
| Omission failures | Your system needs context-aware filtering — the core companion memory challenge |

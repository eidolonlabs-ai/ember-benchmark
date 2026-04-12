"""
Tier 3: End-to-End Roundtrip

Tests the full pipeline: conversation → extraction → retrieval.
No seeding — the system must extract facts from conversations and then
find them via queries. This catches integration issues between extraction
and retrieval that Tier 1 and Tier 2 miss in isolation.

Input: Golden conversations ingested → queries fired against extracted facts
"""

from __future__ import annotations

from ember.adapter import MemoryAdapter
from ember.data import load_golden_conversations, load_retrieval_queries
from ember.scoring import retrieval_recall_at_k, aggregate_retrieval_scores
from ember.types import QueryType, TierResult


async def run_tier3(
    adapter: MemoryAdapter,
    k: int = 3,
    verbose: bool = False,
) -> TierResult:
    """
    Run Tier 3 end-to-end roundtrip evaluation.

    1. Reset adapter state
    2. Ingest ALL golden conversations (extraction)
    3. Wait for extraction
    4. Run retrieval queries against extracted facts (no seeding)
    5. Score retrieval quality
    """
    conversations = load_golden_conversations()
    queries, _ = load_retrieval_queries()  # ignore seeded facts

    # Reset and ingest all conversations
    await adapter.reset()
    for conv in conversations:
        await adapter.ingest_conversation(conv.messages)
    await adapter.wait_for_extraction()

    # Run retrieval queries against whatever was extracted
    per_query = []
    for query in queries:
        if query.test_type == QueryType.TWO_WAY_MEMORY and not adapter.supports_two_way_memory:
            continue

        results = await adapter.search(query.query, limit=k)
        recall = retrieval_recall_at_k(results, query, k)
        per_query.append({
            "query_id": query.id,
            "test_type": query.test_type.value,
            **recall,
        })

    aggregated = aggregate_retrieval_scores(per_query)

    # Tier 3 threshold is lower — extraction loss is expected
    threshold = 0.60  # vs 0.75 for Tier 2
    passed = aggregated["mean_recall_at_k"] >= threshold

    return TierResult(
        tier="Tier 3: End-to-End Roundtrip",
        passed=passed,
        score=aggregated["mean_recall_at_k"],
        details={
            **aggregated,
            "threshold": threshold,
            "conversations_ingested": len(conversations),
            "k": k,
        },
        per_item=per_query,
    )

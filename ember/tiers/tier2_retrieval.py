"""
Tier 2: Retrieval Quality

Tests whether a memory system can find relevant facts given natural language
queries. Evaluates three capabilities:

- Direct recall: Can it find facts when asked directly?
- Synonym/paraphrase: Can it match semantically similar queries?
- Graceful omission: Does it suppress sensitive content for casual queries?
- Two-way memory: Can it retrieve companion-expressed facts?

Input: Seeded facts pre-loaded → queries fired → compare results
"""

from __future__ import annotations

from ember.adapter import MemoryAdapter
from ember.data import load_retrieval_queries, get_pass_thresholds
from ember.scoring import (
    aggregate_retrieval_scores,
    graceful_omission_score,
    retrieval_recall_at_k,
)
from ember.types import QueryType, TierResult


async def run_tier2(
    adapter: MemoryAdapter,
    k: int = 3,
    verbose: bool = False,
) -> TierResult:
    """
    Run Tier 2 retrieval quality evaluation.

    1. Reset adapter state
    2. Seed facts (bypass extraction)
    3. For each query, search and score
    4. Aggregate results
    """
    queries, seeded_facts = load_retrieval_queries()
    thresholds = get_pass_thresholds()["tier2"]

    await adapter.reset()
    await adapter.seed_facts(seeded_facts)

    per_query = []

    for query in queries:
        # Skip two-way memory tests if adapter doesn't support it
        if query.test_type == QueryType.TWO_WAY_MEMORY and not adapter.supports_two_way_memory:
            continue

        results = await adapter.search(query.query, limit=k * 2)  # fetch extra for omission check

        if query.test_type == QueryType.GRACEFUL_OMISSION:
            omission = graceful_omission_score(results, query)
            # Also check positive recall for omission queries that have should_return
            recall = retrieval_recall_at_k(results[:k], query, k) if query.should_return else {}
            per_query.append({
                "query_id": query.id,
                "test_type": query.test_type.value,
                **recall,
                **omission,
            })
        else:
            recall = retrieval_recall_at_k(results[:k], query, k)
            per_query.append({
                "query_id": query.id,
                "test_type": query.test_type.value,
                **recall,
            })

    aggregated = aggregate_retrieval_scores(per_query)

    # Pass if recall@k and omission both meet thresholds
    recall_pass = aggregated["mean_recall_at_k"] >= thresholds.get("recall_at_3", 0.75)
    omission_pass = aggregated["omission_rate"] >= thresholds.get("omission_rate", 0.80)
    passed = recall_pass and omission_pass

    return TierResult(
        tier="Tier 2: Retrieval Quality",
        passed=passed,
        score=aggregated["mean_recall_at_k"],
        details={
            **aggregated,
            "thresholds": thresholds,
            "recall_pass": recall_pass,
            "omission_pass": omission_pass,
            "k": k,
        },
        per_item=per_query,
    )

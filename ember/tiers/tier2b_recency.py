"""
Tier 2b: Recency Bias

Tests whether a memory system correctly weights recent facts over old ones.
This is critical for long-running companion relationships where facts evolve
over time.

If the system uses recency in ranking (standard for hybrid scoring), this
tier verifies the recency weight is meaningful.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ember.adapter import MemoryAdapter
from ember.types import SearchResult, SeededFact, TierResult


async def run_tier2b(adapter: MemoryAdapter, verbose: bool = False) -> TierResult:
    """
    Run Tier 2b recency bias evaluation.

    Scenario: Seed facts at different ages (30d, 7d, 1d old).
    Query with a broad semantic match.
    Verify: Recent facts rank higher than old facts.
    """
    now = datetime.utcnow()

    # Create a set of facts spanning time
    facts_old = SeededFact(
        fact="User used to work in finance",
        predicate="PAST_JOB",
        importance=0.7,
        created_at=now - timedelta(days=30),
    )
    facts_medium = SeededFact(
        fact="User is now working in tech",
        predicate="CURRENT_JOB",
        importance=0.8,
        created_at=now - timedelta(days=7),
    )
    facts_recent = SeededFact(
        fact="User just started learning AI",
        predicate="CURRENT_INTEREST",
        importance=0.6,
        created_at=now - timedelta(days=1),
    )

    await adapter.reset()
    await adapter.seed_facts([facts_old, facts_medium, facts_recent])

    # Query that matches all three semantically but should rank by recency
    results = await adapter.search("What have you been up to lately?", limit=10)

    # Score: how well does recency order the results?
    ranks = {}
    for i, result in enumerate(results):
        for label, fact in [("old", facts_old), ("medium", facts_medium), ("recent", facts_recent)]:
            if fact.fact.lower() in result.fact.lower() or result.fact.lower() in fact.fact.lower():
                ranks[label] = i
                break

    # Ideally: recent < medium < old (lower rank is better)
    recency_score = 1.0
    if "recent" in ranks and "medium" in ranks and "old" in ranks:
        if ranks["recent"] <= ranks["medium"] <= ranks["old"]:
            recency_score = 1.0
        elif ranks["recent"] <= ranks["old"] < ranks["medium"]:
            recency_score = 0.8  # Medium not ranked last, but recent still first
        elif ranks["recent"] < ranks["medium"] or ranks["recent"] < ranks["old"]:
            recency_score = 0.5  # Recent at least ranks before some older facts
        else:
            recency_score = 0.0  # Recent not ranked first

    passed = recency_score >= 0.7

    return TierResult(
        tier="Tier 2b: Recency Bias",
        passed=passed,
        score=recency_score,
        details={
            "ranks": ranks,
            "threshold": 0.7,
            "message": (
                "Recency score measures whether recent facts (1d old) rank higher "
                "than older facts (7d, 30d old) for a broad query. "
                "Score = 1.0 if recent < medium < old; 0.5 if recent ranks before any older facts."
            ),
        },
        per_item=[
            {
                "fact": facts_old.fact,
                "age_days": 30,
                "rank": ranks.get("old", -1),
            },
            {
                "fact": facts_medium.fact,
                "age_days": 7,
                "rank": ranks.get("medium", -1),
            },
            {
                "fact": facts_recent.fact,
                "age_days": 1,
                "rank": ranks.get("recent", -1),
            },
        ],
    )

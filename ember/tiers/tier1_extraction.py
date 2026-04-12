"""
Tier 1: Extraction Quality

Tests whether a memory system correctly extracts facts from conversations.
Scores both flat recall and salience-weighted recall (missing HIGH-salience
facts like grief or trauma is penalized more heavily).

Input: Golden conversations → system extracts → compare to expected facts
"""

from __future__ import annotations

from ember.adapter import MemoryAdapter
from ember.data import load_golden_conversations, get_pass_thresholds
from ember.scoring import extraction_recall
from ember.types import TierResult


async def run_tier1(adapter: MemoryAdapter, verbose: bool = False) -> TierResult:
    """
    Run Tier 1 extraction quality evaluation.

    For each golden conversation:
    1. Reset adapter state
    2. Ingest conversation messages
    3. Wait for extraction to complete
    4. Compare extracted facts to gold standard
    5. Score with salience weighting
    """
    conversations = load_golden_conversations()
    thresholds = get_pass_thresholds()["tier1"]

    per_conv = []
    all_matched = 0
    all_total = 0

    # Accumulate for overall weighted recall
    from ember.types import Salience
    salience_total = {s: 0 for s in Salience}
    salience_found = {s: 0 for s in Salience}

    for conv in conversations:
        await adapter.reset()
        await adapter.ingest_conversation(conv.messages)
        await adapter.wait_for_extraction()

        extracted = await adapter.get_extracted_facts()
        result = extraction_recall(extracted, conv.expected_facts)

        per_conv.append({
            "conversation_id": conv.id,
            "flat_recall": result["flat_recall"],
            "weighted_recall": result["weighted_recall"],
            "matched": len(result["matched"]),
            "total": len(conv.expected_facts),
            "missing": [f.fact for f in result["missing"]],
        })

        all_matched += len(result["matched"])
        all_total += len(conv.expected_facts)

        for s in Salience:
            salience_total[s] += result["salience_breakdown"][s.value]["total"]
            salience_found[s] += result["salience_breakdown"][s.value]["found"]

    # Overall scores
    flat_recall = all_matched / all_total if all_total > 0 else 1.0
    weighted_num = sum(salience_found[s] * s.weight for s in Salience)
    weighted_den = sum(salience_total[s] * s.weight for s in Salience)
    weighted_recall = weighted_num / weighted_den if weighted_den > 0 else 1.0

    passed = weighted_recall >= thresholds.get("weighted_recall", 0.80)

    return TierResult(
        tier="Tier 1: Extraction Quality",
        passed=passed,
        score=weighted_recall,
        details={
            "flat_recall": flat_recall,
            "weighted_recall": weighted_recall,
            "threshold": thresholds.get("weighted_recall", 0.80),
            "conversations": len(conversations),
            "total_gold_facts": all_total,
            "total_matched": all_matched,
            "salience_breakdown": {
                s.value: {"found": salience_found[s], "total": salience_total[s]}
                for s in Salience
            },
        },
        per_item=per_conv,
    )

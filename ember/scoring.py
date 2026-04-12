"""
Scoring functions for EMBER tiers.

All scores are 0-1. Higher is better. Functions are stateless and
operate on EMBER types — no adapter or system knowledge needed.
"""

from __future__ import annotations

from ember.types import (
    ExtractedFact,
    GoldFact,
    RetrievalQuery,
    Salience,
    SearchResult,
)


# ---------------------------------------------------------------------------
# Tier 1: Extraction scoring
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "of", "in", "at", "to",
    "for", "and", "or", "user", "has", "have", "had", "been", "be", "their",
    "they", "it", "that", "this", "with", "from", "companion",
})


def _tokenize(text: str) -> set[str]:
    """Lowercase split + stopword removal."""
    return {w for w in text.lower().split() if w not in _STOPWORDS}


def fact_matches_gold(
    extracted: ExtractedFact,
    gold: GoldFact,
    threshold: float = 0.4,
) -> bool:
    """
    Check whether an extracted fact semantically covers a gold fact.
    Uses predicate match + keyword overlap. Lightweight — no embeddings.
    """
    # Predicate must match (if gold has one)
    if gold.predicate:
        if extracted.predicate.upper() != gold.predicate.upper():
            return False

    # Keyword overlap
    ext_words = _tokenize(extracted.fact)
    gold_words = _tokenize(gold.fact)

    if not gold_words:
        return True

    overlap = ext_words & gold_words
    return len(overlap) / len(gold_words) >= threshold


def extraction_recall(
    extracted: list[ExtractedFact],
    gold_facts: list[GoldFact],
    match_threshold: float = 0.4,
) -> dict:
    """
    Compute flat recall and salience-weighted recall.

    Returns dict with:
        flat_recall: simple fraction of gold facts found
        weighted_recall: salience-weighted (missing HIGH hurts 3x)
        matched: list of (gold_fact, matched_extracted_fact) tuples
        missing: list of unmatched gold facts
    """
    matched = []
    missing = []

    salience_total = {s: 0 for s in Salience}
    salience_found = {s: 0 for s in Salience}

    for gold in gold_facts:
        salience_total[gold.emotional_salience] += 1
        found = False
        for ext in extracted:
            if fact_matches_gold(ext, gold, match_threshold):
                matched.append((gold, ext))
                found = True
                break
        if not found:
            missing.append(gold)
        else:
            salience_found[gold.emotional_salience] += 1

    flat_recall = len(matched) / len(gold_facts) if gold_facts else 1.0

    # Salience-weighted recall
    weighted_num = sum(salience_found[s] * s.weight for s in Salience)
    weighted_den = sum(salience_total[s] * s.weight for s in Salience)
    weighted_recall = weighted_num / weighted_den if weighted_den > 0 else 1.0

    return {
        "flat_recall": flat_recall,
        "weighted_recall": weighted_recall,
        "matched": matched,
        "missing": missing,
        "salience_breakdown": {
            s.value: {"found": salience_found[s], "total": salience_total[s]}
            for s in Salience
        },
    }


# ---------------------------------------------------------------------------
# Tier 2: Retrieval scoring
# ---------------------------------------------------------------------------

def _result_contains_keyword(results: list[SearchResult], keyword: str) -> int | None:
    """Return the rank (0-indexed) of the first result containing keyword, or None."""
    kw = keyword.lower()
    for i, r in enumerate(results):
        if kw in r.fact.lower():
            return i
    return None


def retrieval_recall_at_k(
    results: list[SearchResult],
    query: RetrievalQuery,
    k: int = 3,
) -> dict:
    """
    Compute recall@k and reciprocal rank for a single query.

    Returns dict with:
        recall_at_k: fraction of should_return keywords found in top-k
        reciprocal_rank: 1/rank of first relevant result (0 if none)
        found_keywords: keywords found in top-k
        missing_keywords: keywords not found in top-k
    """
    top_k = results[:k]

    found = []
    missing = []
    first_rank = None

    for kw in query.should_return:
        rank = _result_contains_keyword(top_k, kw)
        if rank is not None:
            found.append(kw)
            if first_rank is None or rank < first_rank:
                first_rank = rank
        else:
            missing.append(kw)

    recall = len(found) / len(query.should_return) if query.should_return else 1.0
    mrr = 1.0 / (first_rank + 1) if first_rank is not None else 0.0

    return {
        "recall_at_k": recall,
        "reciprocal_rank": mrr,
        "found_keywords": found,
        "missing_keywords": missing,
    }


def graceful_omission_score(
    results: list[SearchResult],
    query: RetrievalQuery,
) -> dict:
    """
    For graceful_omission queries: check that sensitive content is NOT returned.

    Returns dict with:
        omission_pass: True if no omit_keywords appear in results
        leaked_keywords: keywords that should have been omitted but appeared
    """
    leaked = []
    for kw in query.omit_keywords:
        if _result_contains_keyword(results, kw) is not None:
            leaked.append(kw)

    return {
        "omission_pass": len(leaked) == 0,
        "leaked_keywords": leaked,
    }


def aggregate_retrieval_scores(per_query: list[dict]) -> dict:
    """
    Aggregate per-query retrieval results into overall scores.

    Returns dict with:
        mean_recall_at_k: average recall@k across all queries
        mean_mrr: mean reciprocal rank
        omission_rate: fraction of omission queries that passed
    """
    recalls = [q["recall_at_k"] for q in per_query if "recall_at_k" in q]
    mrrs = [q["reciprocal_rank"] for q in per_query if "reciprocal_rank" in q]
    omissions = [q for q in per_query if "omission_pass" in q]

    mean_recall = sum(recalls) / len(recalls) if recalls else 0.0
    mean_mrr = sum(mrrs) / len(mrrs) if mrrs else 0.0
    omission_rate = (
        sum(1 for o in omissions if o["omission_pass"]) / len(omissions)
        if omissions else 1.0
    )

    return {
        "mean_recall_at_k": mean_recall,
        "mean_mrr": mean_mrr,
        "omission_rate": omission_rate,
        "total_queries": len(per_query),
    }

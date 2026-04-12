"""Dataset loader for EMBER."""

from __future__ import annotations

import json
from pathlib import Path

from ember.types import (
    Conversation,
    GoldFact,
    Message,
    RetrievalQuery,
    SeededFact,
)

_DATA_DIR = Path(__file__).parent / "datasets"


def load_golden_conversations() -> list[Conversation]:
    """Load the golden facts dataset (Tier 1)."""
    raw = json.loads((_DATA_DIR / "golden_facts.json").read_text("utf-8"))
    conversations = []
    for conv in raw["conversations"]:
        conversations.append(Conversation(
            id=conv["id"],
            description=conv.get("description", ""),
            messages=[Message(**m) for m in conv["messages"]],
            expected_facts=[GoldFact(**f) for f in conv["expected_facts"]],
        ))
    return conversations


def load_retrieval_queries() -> tuple[list[RetrievalQuery], list[SeededFact]]:
    """Load the retrieval query dataset (Tier 2). Returns (queries, seeded_facts)."""
    raw = json.loads((_DATA_DIR / "retrieval_queries.json").read_text("utf-8"))
    queries = [RetrievalQuery(**q) for q in raw["queries"]]
    seeded = [SeededFact(**f) for f in raw["seeded_facts"]]
    return queries, seeded


def get_pass_thresholds() -> dict:
    """Load pass/fail thresholds from both datasets."""
    golden = json.loads((_DATA_DIR / "golden_facts.json").read_text("utf-8"))
    retrieval = json.loads((_DATA_DIR / "retrieval_queries.json").read_text("utf-8"))
    return {
        "tier1": golden.get("pass_threshold", {}),
        "tier2": retrieval.get("pass_threshold", {}),
    }

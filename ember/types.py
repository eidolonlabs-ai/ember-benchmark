"""
Core data types for EMBER.

These types define the contract between EMBER's test harness and any
memory system adapter. They are intentionally minimal — a memory system
only needs to map its internal representations to/from these types.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Salience(str, Enum):
    """Emotional salience of a fact — how much it matters in a companion context."""
    HIGH = "HIGH"   # Grief, trauma, major life events, acute distress
    MED = "MED"     # Relationships, coping mechanisms, ongoing situations
    LOW = "LOW"     # Biographical trivia, casual preferences

    @property
    def weight(self) -> int:
        return {"HIGH": 3, "MED": 2, "LOW": 1}[self.value]


class Scope(str, Enum):
    """Who the fact is about."""
    USER = "user"       # About the human user
    SHARED = "shared"   # About the companion (two-way memory)


class QueryType(str, Enum):
    """What the query is testing."""
    DIRECT = "direct"
    SYNONYM = "synonym"
    GRACEFUL_OMISSION = "graceful_omission"
    TWO_WAY_MEMORY = "two_way_memory"


# ---------------------------------------------------------------------------
# Conversation data (input to extraction)
# ---------------------------------------------------------------------------

class Message(BaseModel):
    """A single turn in a conversation."""
    role: str = Field(description="'user' or 'assistant'")
    content: str


class Conversation(BaseModel):
    """A conversation with expected extraction results."""
    id: str
    description: str = ""
    messages: list[Message]
    expected_facts: list[GoldFact] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Facts (what a memory system should extract and store)
# ---------------------------------------------------------------------------

class GoldFact(BaseModel):
    """A ground-truth fact expected to be extracted from a conversation."""
    fact: str
    predicate: str
    category: str = ""
    importance_min: float = 0.0
    emotional_salience: Salience = Salience.MED
    scope: Scope = Scope.USER


class ExtractedFact(BaseModel):
    """A fact as returned by a memory system's extraction."""
    fact: str
    predicate: str = ""
    category: str = ""
    importance: float = 0.0
    confidence: float = 1.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    scope: Scope = Scope.USER
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Retrieval (search queries and results)
# ---------------------------------------------------------------------------

class RetrievalQuery(BaseModel):
    """A test query for retrieval evaluation."""
    id: str
    query: str
    test_type: QueryType = QueryType.DIRECT
    should_return: list[str] = Field(default_factory=list)
    should_not_return: list[str] = Field(default_factory=list)
    omit_keywords: list[str] = Field(default_factory=list)
    emotional_salience: Salience = Salience.MED
    notes: str = ""


class SearchResult(BaseModel):
    """A single result from a memory search."""
    fact: str
    score: float = 0.0
    predicate: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SeededFact(BaseModel):
    """A fact pre-loaded into the system for retrieval testing."""
    fact: str
    predicate: str
    category: str = ""
    created_at: Optional[datetime] = None  # When fact was created. None = "now"
    updated_at: Optional[datetime] = None  # When fact was last updated. None = same as created_at
    importance: float = 0.5
    emotional_salience: Salience = Salience.MED
    scope: Scope = Scope.USER


# ---------------------------------------------------------------------------
# Scoring results
# ---------------------------------------------------------------------------

class TierResult(BaseModel):
    """Result of running one tier of evaluation."""
    tier: str
    passed: bool
    score: float = Field(description="Primary score (0-1)")
    details: dict[str, Any] = Field(default_factory=dict)
    per_item: list[dict[str, Any]] = Field(default_factory=list)

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.tier}: {self.score:.3f}"


# Forward reference resolution
Conversation.model_rebuild()

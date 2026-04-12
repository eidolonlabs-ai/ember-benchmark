"""
Timeline helpers for creating temporal test scenarios.

Useful for populating golden datasets or seeded facts that span days/weeks/months
without hardcoding absolute timestamps.

Example:
    timeline = Timeline.from_now(start_days_ago=60)
    facts = [
        timeline.fact_at(days_ago=30, fact="User got promoted"),
        timeline.fact_at(days_ago=7, fact="User went on vacation"),
        timeline.fact_at(days_ago=1, fact="User started therapy"),
    ]
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from ember.types import SeededFact, Salience, Scope


class Timeline:
    """
    Helper for creating time-distributed facts relative to a reference point.

    Usage:
        timeline = Timeline.from_now(start_days_ago=60)  # 60 days ago to now
        facts = timeline.span([
            {"days_ago": 30, "fact": "...", "predicate": "..."},
            {"days_ago": 7, "fact": "...", "predicate": "..."},
        ])
    """

    def __init__(self, now: datetime, start_days_ago: int = 60):
        """
        Create a timeline.

        Args:
            now: Reference point (typically datetime.utcnow())
            start_days_ago: How far back the timeline spans (for context)
        """
        self.now = now
        self.start_days_ago = start_days_ago
        self.start_time = now - timedelta(days=start_days_ago)

    @classmethod
    def from_now(cls, start_days_ago: int = 60) -> Timeline:
        """Create a timeline starting from the current time."""
        return cls(datetime.utcnow(), start_days_ago)

    def fact_at(
        self,
        days_ago: int,
        fact: str,
        predicate: str = "",
        category: str = "",
        importance: float = 0.5,
        emotional_salience: Salience = Salience.MED,
        scope: Scope = Scope.USER,
    ) -> SeededFact:
        """
        Create a fact at a specific point in the past.

        Args:
            days_ago: How many days ago (relative to Timeline.now)
            fact: Fact text
            predicate: Predicate tag
            ... other SeededFact fields
        """
        created_at = self.now - timedelta(days=days_ago)
        return SeededFact(
            fact=fact,
            predicate=predicate,
            category=category,
            importance=importance,
            emotional_salience=emotional_salience,
            scope=scope,
            created_at=created_at,
        )

    def span(self, specs: list[dict]) -> list[SeededFact]:
        """
        Create multiple facts from a list of specs.

        Each spec is a dict with "days_ago", "fact", "predicate", etc.

        Example:
            facts = timeline.span([
                {"days_ago": 30, "fact": "...", "predicate": "..."},
                {"days_ago": 7, "fact": "...", "predicate": "..."},
            ])
        """
        facts = []
        for spec in specs:
            days_ago = spec.pop("days_ago", 0)
            fact = spec.pop("fact", "")
            fact_obj = self.fact_at(days_ago=days_ago, fact=fact, **spec)
            facts.append(fact_obj)
        return facts

    def arc(self, label: str, stages: list[tuple[int, str]]) -> list[SeededFact]:
        """
        Create a narrative arc of related facts over time.

        Useful for representing character development or situation evolution.

        Args:
            label: Narrative label (e.g., "relationship_end")
            stages: List of (days_ago, fact_text) tuples representing stages

        Example:
            arc = timeline.arc("breakup", [
                (30, "User was in a relationship with Alex"),
                (14, "Relationship was strained"),
                (7, "Arguments increased"),
                (1, "User ended the relationship"),
            ])
        """
        predicates = {
            "relationship": "HAS_RELATIONSHIP",
            "breakup": "LOST_RELATIONSHIP",
            "health": "HEALTH_STATUS",
            "job": "JOB_STATUS",
            "mood": "EMOTIONAL_STATE",
        }
        predicate = predicates.get(label, label.upper())

        facts = []
        for i, (days_ago, fact_text) in enumerate(stages):
            # Earlier stages are lower importance, later stages are higher
            importance = 0.3 + (i / len(stages)) * 0.6
            salience = Salience.MED if i < len(stages) - 1 else Salience.HIGH
            facts.append(
                self.fact_at(
                    days_ago=days_ago,
                    fact=fact_text,
                    predicate=predicate,
                    importance=importance,
                    emotional_salience=salience,
                )
            )
        return facts

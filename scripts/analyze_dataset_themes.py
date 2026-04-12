#!/usr/bin/env python3
"""
Analyze themes and categories from ai-companions production database.

Queries memory_items table to identify high-frequency categories, predicates,
and emotional patterns that could improve golden_facts.json dataset coverage.

Usage:
    python3 scripts/analyze_dataset_themes.py

Requires:
    - Fly CLI installed and authenticated
    - Database connection via: fly mpg connect -a ai-companions-dev
"""

import asyncio
import json
from typing import Any
import asyncpg
import os
from datetime import datetime


async def get_database_connection() -> asyncpg.Connection:
    """Connect to Fly.io PostgreSQL database."""
    # Connection via Fly.io — assumes user has already authenticated
    # Fly injects PG* environment variables in prod, we'll build connection manually
    
    # For local testing, you can set DATABASE_URL or use Fly proxy
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("❌ DATABASE_URL not set. Set it to connect to cloud database.")
        print("   From terminal, run: fly ssh console -a ai-companions-dev")
        print("   Then in the console, Python can access DATABASE_URL via env var")
        raise ValueError("DATABASE_URL required")
    
    try:
        conn = await asyncpg.connect(db_url)
        return conn
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        raise


async def analyze_categories(conn: asyncpg.Connection) -> dict[str, Any]:
    """Analyze fact distribution by category."""
    query = """
        SELECT 
            category,
            COUNT(*) as count,
            AVG(importance) as avg_importance,
            MAX(importance) as max_importance,
            MIN(created_at) as earliest_created,
            MAX(created_at) as most_recent
        FROM memory_items
        WHERE deleted_at IS NULL
        GROUP BY category
        ORDER BY count DESC
    """
    
    rows = await conn.fetch(query)
    results = {}
    
    for row in rows:
        results[row["category"] or "(null)"] = {
            "count": row["count"],
            "avg_importance": float(row["avg_importance"]) if row["avg_importance"] else 0,
            "max_importance": float(row["max_importance"]) if row["max_importance"] else 0,
            "earliest_created": row["earliest_created"].isoformat() if row["earliest_created"] else None,
            "most_recent": row["most_recent"].isoformat() if row["most_recent"] else None,
        }
    
    return results


async def analyze_predicates(conn: asyncpg.Connection) -> dict[str, Any]:
    """Analyze fact distribution by predicate."""
    query = """
        SELECT 
            predicate,
            COUNT(*) as count,
            AVG(importance) as avg_importance,
            scope
        FROM memory_items
        WHERE deleted_at IS NULL AND predicate IS NOT NULL
        GROUP BY predicate, scope
        ORDER BY count DESC
        LIMIT 50
    """
    
    rows = await conn.fetch(query)
    results = {}
    
    for row in rows:
        key = f"{row['predicate']} ({row['scope']})"
        results[key] = {
            "count": row["count"],
            "avg_importance": float(row["avg_importance"]) if row["avg_importance"] else 0,
            "scope": row["scope"],
        }
    
    return results


async def analyze_emotional_context(conn: asyncpg.Connection) -> dict[str, Any]:
    """Analyze distributions by emotional context."""
    query = """
        SELECT 
            emotional_context,
            COUNT(*) as count,
            AVG(importance) as avg_importance,
            COUNT(DISTINCT category) as unique_categories
        FROM memory_items
        WHERE deleted_at IS NULL AND emotional_context IS NOT NULL
        GROUP BY emotional_context
        ORDER BY count DESC
    """
    
    rows = await conn.fetch(query)
    results = {}
    
    for row in rows:
        results[row["emotional_context"]] = {
            "count": row["count"],
            "avg_importance": float(row["avg_importance"]) if row["avg_importance"] else 0,
            "unique_categories": row["unique_categories"],
        }
    
    return results


async def analyze_temporal_types(conn: asyncpg.Connection) -> dict[str, Any]:
    """Analyze distributions by temporal classification."""
    query = """
        SELECT 
            temporal_type,
            COUNT(*) as count,
            AVG(importance) as avg_importance,
            COUNT(DISTINCT category) as unique_categories
        FROM memory_items
        WHERE deleted_at IS NULL
        GROUP BY temporal_type
        ORDER BY count DESC
    """
    
    rows = await conn.fetch(query)
    results = {}
    
    for row in rows:
        results[row["temporal_type"]] = {
            "count": row["count"],
            "avg_importance": float(row["avg_importance"]) if row["avg_importance"] else 0,
            "unique_categories": row["unique_categories"],
        }
    
    return results


async def get_underrepresented_facts(conn: asyncpg.Connection, limit: int = 20) -> list[dict]:
    """Find facts from underrepresented categories."""
    query = """
        SELECT 
            category,
            predicate,
            fact,
            importance,
            emotional_context,
            temporal_type,
            scope
        FROM memory_items
        WHERE deleted_at IS NULL
        AND category NOT IN ('personal', 'preference', 'history')
        AND importance > 0.5  -- High importance facts
        ORDER BY created_at DESC
        LIMIT $1
    """
    
    rows = await conn.fetch(query, limit)
    results = []
    
    for row in rows:
        results.append({
            "category": row["category"],
            "predicate": row["predicate"],
            "fact": row["fact"],
            "importance": float(row["importance"]) if row["importance"] else 0,
            "emotional_context": row["emotional_context"],
            "temporal_type": row["temporal_type"],
            "scope": row["scope"],
        })
    
    return results


async def get_high_salience_facts(conn: asyncpg.Connection, limit: int = 30) -> list[dict]:
    """Get high-importance facts that could be templates for golden dataset."""
    query = """
        SELECT 
            category,
            predicate,
            fact,
            importance,
            emotional_context,
            temporal_type,
            scope
        FROM memory_items
        WHERE deleted_at IS NULL
        AND importance >= 0.7  -- HIGH salience
        ORDER BY created_at DESC
        LIMIT $1
    """
    
    rows = await conn.fetch(query, limit)
    results = []
    
    for row in rows:
        results.append({
            "category": row["category"],
            "predicate": row["predicate"],
            "fact": row["fact"],
            "importance": float(row["importance"]) if row["importance"] else 0,
            "emotional_context": row["emotional_context"],
            "temporal_type": row["temporal_type"],
            "scope": row["scope"],
        })
    
    return results


async def main():
    """Run full analysis."""
    conn = await get_database_connection()
    
    try:
        print("📊 Analyzing database themes for golden dataset enrichment...\n")
        
        # Category analysis
        print("=" * 60)
        print("CATEGORY DISTRIBUTION")
        print("=" * 60)
        categories = await analyze_categories(conn)
        for cat, stats in sorted(categories.items(), key=lambda x: x[1]["count"], reverse=True):
            print(f"  {cat:20s} | count: {stats['count']:4d} | avg_importance: {stats['avg_importance']:.2f}")
        
        # Predicate analysis
        print("\n" + "=" * 60)
        print("TOP PREDICATES (by frequency)")
        print("=" * 60)
        predicates = await analyze_predicates(conn)
        for pred, stats in sorted(predicates.items(), key=lambda x: x[1]["count"], reverse=True)[:15]:
            print(f"  {pred:40s} | count: {stats['count']:4d}")
        
        # Emotional context
        print("\n" + "=" * 60)
        print("EMOTIONAL CONTEXT")
        print("=" * 60)
        emotions = await analyze_emotional_context(conn)
        for emotion, stats in sorted(emotions.items(), key=lambda x: x[1]["count"], reverse=True):
            print(f"  {emotion:20s} | count: {stats['count']:4d} | avg_importance: {stats['avg_importance']:.2f}")
        
        # Temporal types
        print("\n" + "=" * 60)
        print("TEMPORAL TYPES")
        print("=" * 60)
        temporal = await analyze_temporal_types(conn)
        for ttype, stats in sorted(temporal.items(), key=lambda x: x[1]["count"], reverse=True):
            print(f"  {ttype:20s} | count: {stats['count']:4d} | avg_importance: {stats['avg_importance']:.2f}")
        
        # Underrepresented facts
        print("\n" + "=" * 60)
        print("UNDERREPRESENTED HIGH-IMPORTANCE FACTS (samples)")
        print("=" * 60)
        underrep = await get_underrepresented_facts(conn, limit=10)
        for fact in underrep:
            print(f"\n  📌 {fact['fact'][:60]}...")
            print(f"     Category: {fact['category']} | Predicate: {fact['predicate']}")
            print(f"     Importance: {fact['importance']:.2f} | Emotional: {fact['emotional_context']}")
        
        # High salience facts for templates
        print("\n" + "=" * 60)
        print("HIGH-SALIENCE FACTS (potential dataset additions)")
        print("=" * 60)
        high = await get_high_salience_facts(conn, limit=15)
        groupings = {}
        for fact in high:
            cat = fact["category"] or "(uncategorized)"
            if cat not in groupings:
                groupings[cat] = []
            groupings[cat].append(fact)
        
        for cat, facts in groupings.items():
            print(f"\n  📂 {cat} ({len(facts)} facts)")
            for fact in facts[:3]:  # Show first 3 per category
                print(f"     • {fact['fact'][:55]}...")
        
        # Summary recommendations
        print("\n" + "=" * 60)
        print("RECOMMENDATIONS FOR GOLDEN DATASET")
        print("=" * 60)
        
        total_facts = sum(s["count"] for s in categories.values())
        print(f"\nTotal facts in database: {total_facts}")
        print(f"Current golden dataset: 7 conversations (typical ~25-35 facts)")
        
        print("\n✅ Well-covered in current dataset:")
        print("   • Loneliness/isolation (personal)")
        print("   • Pet as emotional anchor (family, relationships)")
        print("   • Grief over loss (HIGH salience)")
        print("   • Burnout and identity crisis (personal)")
        print("   • Breakup and desire for connection (relationships)")
        print("   • Anxiety and panic attacks (health)")
        print("   • Companion values/self-expression (two-way memory)")
        
        gaps = [cat for cat in categories.keys() if categories[cat]["count"] < total_facts * 0.05 and cat != "(null)"]
        if gaps:
            print(f"\n⚠️  Underrepresented categories ({len(gaps)}):")
            for gap in gaps:
                print(f"   • {gap} ({categories[gap]['count']} facts)")
        
        print("\n💡 Recommended new conversations to add:")
        print("   1. Financial stress / money anxiety")
        print("   2. Career transitions / job loss")
        print("   3. Health concerns / chronic conditions")
        print("   4. Family conflict / estrangement")
        print("   5. Relationship milestone (engagement, marriage)")
        print("   6. Academic struggles / learning challenges")
        print("   7. Digital detox / internet addiction")
        print("   8. Toxic friendship / social boundary-setting")
        
        # Export suggestions
        suggestions = {
            "timestamp": datetime.now().isoformat(),
            "total_facts": total_facts,
            "categories": categories,
            "top_predicates": dict(sorted(predicates.items(), key=lambda x: x[1]["count"], reverse=True)[:20]),
            "underrepresented_samples": underrep[:10],
            "high_salience_samples": high[:20],
        }
        
        with open("analysis_results.json", "w") as f:
            json.dump(suggestions, f, indent=2, default=str)
        
        print("\n✅ Full analysis exported to: analysis_results.json")
    
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())

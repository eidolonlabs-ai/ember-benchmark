#!/usr/bin/env python3
"""
Quick analysis script to run ON Fly.io server.

Usage:
    fly ssh console -a ai-companions-dev -C "python3 <<'EOF'
    < paste this file's contents >
    EOF"

Or copy to server and run:
    fly ssh sftp shell -a ai-companions-dev
    # put /path/to/this/file /tmp/analyze.py
    fly ssh console -a ai-companions-dev -C "python3 /tmp/analyze.py"
"""

import os
import asyncpg
from datetime import datetime
from collections import Counter

async def main():
    # On Fly.io, DATABASE_URL is set automatically
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL not found. This script must run on Fly.io server.")
        return
    
    conn = await asyncpg.connect(db_url)
    
    try:
        print("\n📊 AI Companions Memory Item Analysis")
        print("=" * 70)
        
        # Category distribution
        print("\n📂 CATEGORY DISTRIBUTION")
        print("-" * 70)
        cat_rows = await conn.fetch("""
            SELECT category, COUNT(*) as count, AVG(importance) as avg_imp
            FROM memory_items WHERE deleted_at IS NULL
            GROUP BY category ORDER BY count DESC
        """)
        
        total = sum(r["count"] for r in cat_rows)
        for r in cat_rows:
            pct = (r["count"] / total * 100) if total > 0 else 0
            cat_name = r["category"] or "(no category)"
            print(f"  {cat_name:25s} {r['count']:4d} facts ({pct:5.1f}%) | avg importance: {r['avg_imp']:.2f}")
        
        # Predicate distribution (top 15)
        print("\n🔑 TOP PREDICATES")
        print("-" * 70)
        pred_rows = await conn.fetch("""
            SELECT predicate, COUNT(*) as count, scope
            FROM memory_items WHERE deleted_at IS NULL AND predicate IS NOT NULL
            GROUP BY predicate, scope ORDER BY count DESC LIMIT 15
        """)
        
        for r in pred_rows:
            scope_tag = f"[{r['scope']}]" if r["scope"] != "user" else ""
            print(f"  {r['predicate']:30s} {r['count']:4d} {scope_tag}")
        
        # Emotional context
        print("\n😊 EMOTIONAL CONTEXT")
        print("-" * 70)
        emot_rows = await conn.fetch("""
            SELECT emotional_context, COUNT(*) as count, AVG(importance) as avg_imp
            FROM memory_items WHERE deleted_at IS NULL AND emotional_context IS NOT NULL
            GROUP BY emotional_context ORDER BY count DESC
        """)
        
        for r in emot_rows:
            print(f"  {r['emotional_context']:25s} {r['count']:4d} facts | avg importance: {r['avg_imp']:.2f}")
        
        # Temporal types
        print("\n⏱️  TEMPORAL TYPES")
        print("-" * 70)
        temp_rows = await conn.fetch("""
            SELECT temporal_type, COUNT(*) as count, AVG(importance) as avg_imp
            FROM memory_items WHERE deleted_at IS NULL
            GROUP BY temporal_type ORDER BY count DESC
        """)
        
        for r in temp_rows:
            print(f"  {r['temporal_type']:25s} {r['count']:4d} facts | avg importance: {r['avg_imp']:.2f}")
        
        # High-importance facts samples
        print("\n⭐ HIGH-IMPORTANCE FACTS (importance >= 0.7)")
        print("-" * 70)
        high_rows = await conn.fetch("""
            SELECT category, predicate, fact, importance, emotional_context
            FROM memory_items 
            WHERE deleted_at IS NULL AND importance >= 0.7
            ORDER BY created_at DESC LIMIT 10
        """)
        
        for i, r in enumerate(high_rows, 1):
            print(f"\n  {i}. {r['fact'][:60]}...")
            print(f"     Category: {r['category']} | Predicate: {r['predicate']}")
            print(f"     Importance: {r['importance']:.2f} | Emotion: {r['emotional_context']}")
        
        # Two-way memory facts (scope = 'shared')
        print("\n🔄 TWO-WAY MEMORY (companion self-expression)")
        print("-" * 70)
        shared_rows = await conn.fetch("""
            SELECT fact, predicate, importance
            FROM memory_items 
            WHERE deleted_at IS NULL AND scope = 'shared'
            ORDER BY created_at DESC LIMIT 5
        """)
        
        if shared_rows:
            for r in shared_rows:
                print(f"  • {r['fact'][:70]}...")
                print(f"    Predicate: {r['predicate']} | Importance: {r['importance']:.2f}\n")
        else:
            print("  (No two-way memory facts found)")
        
        # Coverage gaps analysis
        print("\n💡 DATASET COVERAGE ANALYSIS")
        print("-" * 70)
        
        # What categories are underrepresented?
        cat_dict = {r["category"] or "(no cat)": r["count"] for r in cat_rows}
        top_category_count = max(cat_dict.values()) if cat_dict else 0
        threshold = top_category_count * 0.1  # Less than 10% of top category
        
        gaps = [k for k, v in cat_dict.items() if v < threshold and k != "(no cat)"]
        if gaps:
            print(f"\n⚠️  Underrepresented categories (< {threshold:.0f} facts):")
            for gap in gaps:
                print(f"   • {gap}: {cat_dict[gap]} facts")
        else:
            print("\n✅ Categories are well-distributed")
        
        print(f"\n📈 Total facts analyzed: {total}")
        print(f"📅 Database snapshot: {datetime.now().isoformat()}")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

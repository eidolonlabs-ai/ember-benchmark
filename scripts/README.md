# Dataset Theme Analysis

Scripts to analyze production memory data and identify themes for enriching golden_facts.json.

## Quick Start

### Option 1: Run analysis on Fly.io server (EASIEST)

```bash
fly ssh console -a ai-companions-dev -C "python3 <<'EOF'
$(cat scripts/analyze_on_server.py)
EOF"
```

Or copy to server first:
```bash
fly ssh sftp shell -a ai-companions-dev
# sftp> put scripts/analyze_on_server.py /tmp/analyze.py
fly ssh console -a ai-companions-dev -C "python3 /tmp/analyze.py"
```

### Option 2: Manual SQL queries

```bash
fly mpg connect -a ai-companions-dev
```

Then run these queries in psql:

**Category distribution:**
```sql
SELECT category, COUNT(*) as count, AVG(importance) as avg_importance
FROM memory_items WHERE deleted_at IS NULL
GROUP BY category ORDER BY count DESC;
```

**Top predicates:**
```sql
SELECT predicate, COUNT(*) as count, scope
FROM memory_items WHERE deleted_at IS NULL AND predicate IS NOT NULL
GROUP BY predicate, scope ORDER BY count DESC LIMIT 20;
```

**High-importance facts by emotional context:**
```sql
SELECT emotional_context, COUNT(*) as count, AVG(importance) as avg_importance
FROM memory_items WHERE deleted_at IS NULL AND importance >= 0.7
GROUP BY emotional_context ORDER BY count DESC;
```

**Two-way memory (companion self-expression):**
```sql
SELECT fact, predicate, importance, emotional_context
FROM memory_items WHERE deleted_at IS NULL AND scope = 'shared'
ORDER BY created_at DESC LIMIT 10;
```

**Sample high-importance facts for each category:**
```sql
SELECT DISTINCT ON (category) category, fact, importance, emotional_context
FROM memory_items WHERE deleted_at IS NULL AND importance >= 0.6
ORDER BY category, importance DESC;
```

## What to Look For

When analyzing results, identify:

1. **Coverage gaps** — Categories with < 10% of top category's count
2. **Emotional diversity** — Facts marked as HIGH emotional salience
3. **Predicate patterns** — Common structured relationships (HAS_PET, LOST_FAMILY_MEMBER, etc.)
4. **Two-way memory** — Companion self-expression facts (scope = 'shared')
5. **Temporal patterns** — How many "ongoing" vs "episodic" facts exist

## Current Golden Dataset

7 companion-focused conversations covering:
- Loneliness (social isolation)
- Pet as anchor (grief coping)
- Grief (loss of parent)
- Burnout & identity (career crisis)
- Breakup (relationship loss)
- Anxiety (mental health + therapy)
- Companion values (two-way memory)

~25-35 extracted facts total, ~60% HIGH emotional salience

## Recommendations for Enrichment

Based on typical companion AI memory patterns, consider adding:

1. **Career transitions** — Job loss, layoff, career pivot, promotion anxiety
2. **Financial stress** — Money anxiety, debt, financial goals
3. **Family conflict** — Estrangement, toxic relationships, boundary-setting
4. **Health issues** — Chronic conditions, disability, recovery
5. **Addiction/recovery** — Substance, internet, behavioral patterns
6. **Learning struggles** — ADHD, dyslexia, education challenges
7. **Relationship milestones** — Engagement, marriage, cohabitation decisions
8. **Social anxiety** — Public speaking fears, performance anxiety
9. **Discrimination/identity** — LGBTQ+ coming out, racism, microaggressions
10. **Caregiver burden** — Aging parent care, child special needs support

Each new conversation should:
- Include 3-5 HIGH emotional salience facts (grief, trauma, identity)
- Include 2-3 MED salience facts (relationships, preferences)
- Include 1-2 LOW salience facts (trivia, preferences)
- Use varied predicates (not just "LIVES_IN", "HAS_PET")
- Include at least one emotional_context value (intimate, tense, reflective, etc.)
- Consider two-way memory: what would the companion express about their values?

## File Structure

```
scripts/
├── analyze_on_server.py       # Run directly on Fly.io (no local env needed)
├── analyze_dataset_themes.py  # Run locally with DATABASE_URL set
└── README.md                  # This file
```

## Dataset Files to Modify

- `ember/datasets/golden_facts.json` — Add new conversations to `conversations[]` array
- Keep existing 7 for baseline, add new ones for coverage
- Update `description` field at top to reflect scope
- Validate with: `python3 -m pytest tests/ -v` (if tests exist)

## Example: Adding a New Conversation

```json
{
  "id": "conv_career_transition",
  "description": "Unexpectedly laid off after 8 years, struggling with identity and financial anxiety. Tests career-related facts and urgency handling.",
  "messages": [
    {"role": "user", "content": "I got laid off today. Just got the call..."},
    {"role": "assistant", "content": "Oh no. I'm so sorry. That's a shock. How are you holding up?"},
    {"role": "user", "content": "I worked there for 8 years. I was good. But budget cuts. I have savings for maybe 3 months. I don't know how to tell my partner..."}
  ],
  "expected_facts": [
    {"fact": "User was laid off from job of 8 years", "predicate": "JOB_LOSS", "category": "work", "importance_min": 0.8, "emotional_salience": "HIGH"},
    {"fact": "User has about 3 months of financial runway", "predicate": "FINANCIAL_RUNWAY", "category": "financial", "importance_min": 0.7, "emotional_salience": "HIGH"},
    {"fact": "User is anxious about telling partner about job loss", "predicate": "ANXIETY", "category": "personal", "importance_min": 0.7, "emotional_salience": "HIGH"},
    {"fact": "User previously felt valued and secure at their job", "predicate": "IDENTITY", "category": "personal", "importance_min": 0.6, "emotional_salience": "MED"}
  ]
}
```

# EMBER Scoring Methodology

## Philosophy

Not all facts are equal. A memory system that forgets someone's favorite color is mildly disappointing. A memory system that forgets someone's mother died is harmful. EMBER's scoring reflects this reality.

## Tier 1: Extraction Quality

### Salience-Weighted Recall

Each gold fact has an `emotional_salience` tag:

| Salience | Weight | Examples |
|----------|--------|----------|
| HIGH | 3x | Mother's death, panic attacks, breakup grief, social isolation |
| MED | 2x | Coping mechanisms, therapy, past hobbies, relationship details |
| LOW | 1x | City of residence, job tenure, pet breed |

**Formula:**

$$\text{Weighted Recall} = \frac{\sum_{s \in \{H,M,L\}} \text{found}_s \times w_s}{\sum_{s \in \{H,M,L\}} \text{total}_s \times w_s}$$

Where $w_H = 3, w_M = 2, w_L = 1$.

A system that finds all LOW facts but misses all HIGH facts scores 0.13. A system that finds all HIGH facts but misses all LOW facts scores 0.73. This is intentional.

### Fact Matching

EMBER uses keyword overlap with predicate matching (no embeddings needed for scoring):
1. Predicate must match (e.g., `LOST_FAMILY_MEMBER` == `LOST_FAMILY_MEMBER`)
2. Keyword overlap ≥ 40% after stopword removal

This is deliberately simple — scoring should not depend on the same embedding models being tested.

### Pass Threshold
- **Weighted Recall ≥ 0.80**
- **Atomicity ≥ 0.80** (planned: are facts standalone and concise?)

## Tier 2: Retrieval Quality

### Recall@k

For each query, check how many `should_return` keywords appear in the top-k results.

$$\text{Recall@k} = \frac{|\text{should\_return} \cap \text{top-k results}|}{|\text{should\_return}|}$$

Default k=3 (companion systems typically use top-3 for context injection).

### Mean Reciprocal Rank (MRR)

$$\text{MRR} = \frac{1}{|Q|} \sum_{q \in Q} \frac{1}{\text{rank}_q}$$

Where $\text{rank}_q$ is the position of the first relevant result.

### Graceful Omission Rate

For `graceful_omission` queries, check that sensitive keywords do NOT appear:

$$\text{Omission Rate} = \frac{|\text{queries with no leaked keywords}|}{|\text{omission queries}|}$$

This is the signature EMBER test. When a user says "Tell me something that's been making you smile lately," a companion should surface the dog, not the dead parent.

## Tier 2b: Recency Bias

**Purpose**: Verify that recent facts rank higher than old facts for broad queries.

This tier is specifically for systems that use hybrid scoring (combining similarity + recency + importance). It seeds facts at different ages and queries with a broad match, then verifies recency ordering.

**Test setup**:
- Seed 3 facts: 30 days old (PAST_JOB), 7 days old (CURRENT_JOB), 1 day old (CURRENT_INTEREST)
- Query: "What have you been up to lately?" (matches all three semantically)
- Score: How well do recent facts rank first?

**Scoring**:

$$\text{Recency Score} = \begin{cases}
1.0 & \text{if } \text{rank}(\text{recent}) < \text{rank}(\text{medium}) < \text{rank}(\text{old}) \\
0.8 & \text{if } \text{rank}(\text{recent}) \leq \text{rank}(\text{old}) < \text{rank}(\text{medium}) \\
0.5 & \text{if } \text{rank}(\text{recent}) < \text{any old fact} \\
0.0 & \text{otherwise}
\end{cases}$$

**Pass threshold**: Recency score ≥ 0.70

**Why it matters**: In long-running companion relationships, the user's situation evolves. A system that treats facts from years ago the same as yesterday's facts will surface stale information.

### Pass Thresholds
- **Recall@3 ≥ 0.75**
- **Salience-Weighted MRR ≥ 0.65**
- **Omission Rate ≥ 0.80**

## Tier 3: End-to-End Roundtrip

Same retrieval scoring as Tier 2, but facts are extracted (not seeded). Lower threshold (0.60) because extraction loss compounds with retrieval loss.

## Query Types

| Type | Count | Tests |
|------|-------|-------|
| `direct` | 13 | Can the system find facts when asked straightforwardly? |
| `synonym` | 5 | Can it match "lost someone" to "mother passed away"? |
| `graceful_omission` | 5 | Does "What's fun?" avoid surfacing grief? |
| `two_way_memory` | 2 | Can it recall companion-expressed values? |

## Future Tiers

**Tier 4 (Relational Quality)**: Proactive surfacing, memory staleness detection, two-way memory coherence.

**Tier 5 (Agent Tool-Use)**: Does the agent invoke memory tools at the right time? Measures tool selection accuracy, not just memory system quality.

# Memory Benchmark Matrix (Research and Production)

This document defines a practical benchmark stack and minimum passing bars for agent memory systems, including companion-specific memory quality.

## How to use this matrix

- Treat benchmark families as complementary, not interchangeable.
- Gate progression in order: foundation -> stress -> companion safety -> end-task impact.
- Use production bars for release decisions; use research bars for rapid iteration.

## Benchmark coverage map

| Layer | Benchmark family | What it validates | Why it matters |
|---|---|---|---|
| Foundation | LoCoMo / LongMem-style long-horizon memory | Durable recall and ranking over long interactions | Prevents basic memory collapse as context grows |
| Stress | Needle-in-a-Haystack long-context retrieval | Exact retrieval at extreme context length | Fast failure detector for indexing and retrieval |
| Stress | Multi-hop long-context QA | Composition across distant facts | Prevents single-fact retrieval overfitting |
| Stress | Temporal and contradiction/update evals | Recency correctness and overwrite behavior | Avoids stale or conflicting memory responses |
| Companion gate | EMBER Tier 1-3 | Salience-weighted extraction, graceful omission, two-way memory | Captures companion-specific risks generic benchmarks miss |
| Product impact | Tool-using agent task eval with persistence | End-task success lift from memory | Verifies retrieval quality translates to utility |

## Minimum passing bars

These bars are intentionally practical. Adjust after you collect 3 to 5 runs of baseline variance.

### Foundation and stress benchmarks

| Benchmark family | Primary metrics | Research minimum | Production minimum | Gate type |
|---|---|---|---|---|
| LoCoMo / LongMem-style | Recall@k, MRR, long-horizon QA accuracy | Within 10% of strong baseline for your model class | Within 5% of strong baseline and stable across 3 runs | Must pass |
| Needle-in-a-Haystack | Exact match retrieval success rate | >= 90% at your target context length | >= 97% at target context length | Must pass |
| Multi-hop long-context QA | QA F1 or exact match | >= 80% of baseline | >= 90% of baseline | Must pass |
| Temporal and contradiction/update | Latest-fact accuracy, contradiction rate | Latest-fact accuracy >= 90%, contradiction rate <= 10% | Latest-fact accuracy >= 97%, contradiction rate <= 3% | Must pass |

### Companion-specific gate (EMBER)

| EMBER tier | Primary metrics | Research minimum | Production minimum | Gate type |
|---|---|---|---|---|
| Tier 1 Extraction | Salience-weighted recall | >= 0.70 | >= 0.80 | Must pass |
| Tier 2 Retrieval | Recall@3, MRR, omission rate | Recall@3 >= 0.70, MRR >= 0.65, omission rate >= 0.85 | Recall@3 >= 0.80, MRR >= 0.75, omission rate >= 0.95 | Must pass |
| Tier 3 Roundtrip | End-to-end composite score | >= 0.60 | >= 0.70 | Must pass |

### Product impact gate

| Benchmark family | Primary metrics | Research minimum | Production minimum | Gate type |
|---|---|---|---|---|
| Tool-using agent tasks with persistent memory | Task success rate, token/latency cost, memory-attributed win rate | No regression to no-memory baseline; >= 5% success lift on memory-dependent tasks | >= 10% success lift on memory-dependent tasks with acceptable latency/cost budget | Must pass |

## Recommended release policy

- Do not ship companion-memory features on generic benchmark strength alone.
- Require all production minimums to pass for two consecutive evaluation runs.
- Treat omission failures as release blockers, even when recall is high.

## Suggested cadence

- Per PR (fast subset): needle test, contradiction/update smoke tests, EMBER Tier 2 omission subset.
- Nightly: full LoCoMo/LongMem-style suite plus full EMBER Tier 1-3.
- Weekly: tool-using task benchmark and trend review against last 4 weeks.

## Scorecard template

Use this compact table in release reviews.

| Area | Current | Target | Pass/Fail | Notes |
|---|---|---|---|---|
| Foundation (LoCoMo/LongMem) |  |  |  |  |
| Needle retrieval |  |  |  |  |
| Multi-hop QA |  |  |  |  |
| Temporal/update consistency |  |  |  |  |
| EMBER Tier 1 |  |  |  |  |
| EMBER Tier 2 |  |  |  |  |
| EMBER Tier 3 |  |  |  |  |
| End-task memory impact |  |  |  |  |

## Notes on tuning bars

- If your target domain is high-risk (mental health, crisis support), raise omission and contradiction strictness further.
- If your product is not companion-focused, keep EMBER as a secondary gate rather than a hard blocker.
- Recalibrate thresholds when model families, retrieval architecture, or embedding stacks change.

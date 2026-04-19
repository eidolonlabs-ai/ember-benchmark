# Research Brief: Benchmarking Emotionally-Aware Memory in Companion AI

## What We're Trying to Benchmark

**Companion AI memory systems** — the kind of memory a long-term personal AI companion (think Replika, Character.ai, personal assistants with memory) uses to remember emotionally significant facts about a user across weeks, months, or years of interaction.

This is **not** standard RAG or factual recall. The key challenges are:

- **Salience awareness**: A memory system should weight "user's mother died" differently from "user likes Thai food"
- **Contextual retrieval**: The system should surface sensitive facts when relevant ("What's been hard lately?") but omit them in casual contexts ("What's fun?")
- **Bidirectional memory**: The companion also shares things — the system should remember what the *companion* said, not just the user
- **Temporal dynamics**: Recent facts should rank higher; facts change emotional valence over time
- **Graceful omission**: Surfacing trauma in inappropriate contexts is actively harmful

## Our Existing Work: EMBER

We've built a benchmark called **EMBER** (Emotionally-aware Memory Benchmark for Empathic Recall) to evaluate systems on these dimensions. We'd like your research on whether our approach is sound and what we might be missing.

### Current EMBER Design

**Dataset**: 12 companion-style conversations (loneliness, grief, burnout, breakup, anxiety, etc.) with 55 gold-standard facts and 40 retrieval queries.

**Query types**:
- Direct recall (13 queries) — "What did the user say about their job?"
- Synonym matching (5 queries) — "What was their career path?" matches facts about "finance" or "work"
- Graceful omission (5 queries) — "What's fun?" should NOT surface "mother passed away"
- Two-way memory (2 queries) — "What does the companion value?"
- Temporal/recency (4 queries) — recent facts rank higher than old ones
- Roundtrip extraction (6 queries) — end-to-end: ingest → extract → retrieve
- Conversational (5 queries) — natural dialogue about the user

**Scoring**:
- Salience-weighted recall: `sum(found_s * w_s) / sum(total_s * w_s)` (framed around the PAD arousal model for weights)
- Graceful omission: separate metric, queries have `omit_keywords` fields
- Recency bias: rank-order scoring with discrete buckets (1.0, 0.8, 0.5, 0.0)
- Integration of **nDCG** for evaluating rank-weighted retrieval natively.
- Pass thresholds per tier (extraction ≥0.80, retrieval ≥0.75, omission ≥0.80, recency ≥0.0.70, roundtrip ≥0.60)

**Adapter pattern**: Systems implement 5 async methods (`ingest_conversation`, `wait_for_extraction`, `get_extracted_facts`, `search`, `seed_facts`) plus optional `reset`. No opinion on storage, embeddings, or architecture.

**Tiered evaluation**:
1. Extraction — salience-weighted fact recall
2. Retrieval — recall@3 + graceful omission + two-way memory
2b. Recency — recent facts rank higher
3. Roundtrip — extraction → retrieval end-to-end
4. Relational — *planned*: proactive surfacing, memory staleness
5. Agent — *planned*: tool-use decisions (when to search memory)

### Known Gaps (from our internal audit)

1. **Scale and Statistics**: 12 conversations / 55 facts / 40 queries is too small for standard frequentist power analysis. We need to employ BCa Bootstrap Resampling to determine significance.
2. **Keyword matching is fragile**: Extraction scoring uses 40% keyword overlap after stopword removal. Paraphrased facts may fail to match.
3. **No adversarial cases**: Missing emotionally ambiguous facts, contradictory memories, temporal valence drift, and near-miss semantic traps.
4. **No cost/latency telemetry**: Can't compare accuracy vs. speed tradeoffs.
5. **No reference baselines**: Missing "Oracle", "retrieve everything", and random baselines for interpretive context.
6. **No inter-annotator agreement**: Salience labels not validated by ≥3 independent raters with an appropriate metric like Krippendorff's α.
7. **Recency scoring is coarse**: 4 discrete buckets, only 1 test scenario.

---

## Questions for Research

### 1. Benchmark Design for Novel Domains

Emotionally-aware memory is a **new benchmarking domain** — there's no established standard like MMLU for general reasoning or HELM for language models.

- What's the right strategy for building credibility in a benchmark for a domain where even the evaluation criteria (salience weights, omission thresholds) are themselves research questions?
- How do other novel benchmark domains (e.g., RLHF reward modeling, tool-use benchmarks) establish trust before a community standard exists?
- Should we publish the salience weights as a hypothesis to be tested, rather than as ground truth?

### 2. Metric Selection

Our current metrics are pragmatic but potentially misaligned with what matters.

- **Salience-weighted recall & nDCG**: Is our shift toward nDCG along with weighting by the PAD (Pleasure, Arousal, Dominance) model defensively robust?
- **Graceful omission**: We treat it as a binary (did it surface forbidden content?). Should we have graded omission scores (e.g., partial mention = worse than full mention)?
- **Recency bias**: Our 4-bucket discrete scoring is coarse. We are moving toward continuous decay (Kendall's τ). What other metrics exist in information retrieval or temporal reasoning that would be better?
- **What metric are we missing entirely?** Is there a dimension of companion memory quality we're not measuring?

### 3. Ground Truth and Annotation

Our gold facts are annotated by a single author (the benchmark creator). This is a known credibility gap.

- What annotation protocols work for subjective domains like emotional salience? Are there alternatives or robust complements to Krippendorff's α for IAA?
- Can we use LLM-based annotation as a supplementary signal, or does that create circularity?
- What's the minimum annotation effort (number of raters, number of facts rated) needed for a v0.1 benchmark to be credible?

### 4. Adversarial and Edge Cases

What kinds of edge cases should a credible benchmark include?

- We identified: emotionally ambiguous facts, contradictory memories, temporal valence drift, near-miss contexts
- What other adversarial cases are important for companion memory?
- How many adversarial cases are enough? Is there a framework for determining adversarial coverage?

### 5. Statistical Rigor

With 40 queries, what's the right approach to statistical evaluation?

- Should we use bootstrap confidence intervals, Bayesian methods, or something else?
- How do we determine minimum sample size for a benchmark like this?
- What does "statistical significance" even mean for a benchmark with binary/pass-fail tiers?

### 6. Baselines and Comparison

- What baselines should we include? We've identified "retrieve everything" and "random" but those seem insufficient.
- What's a reasonable upper bound for this task? (If no system scores above 0.60 on extraction, the benchmark is too hard; if all score 0.95, it's too easy.)
- How do we report results so they're interpretable across very different system architectures?

### 7. Reproducibility vs. Fairness

- Should extraction/retrieval systems under test use the same embedding models as the scoring system? (We deliberately don't — but this creates a ceiling on paraphrase tolerance.)
- How do we prevent training data contamination? (Conversations are human-written, but are they guaranteed to be outside training corpora?)
- What reproducibility infrastructure is essential vs. nice-to-have?

---

## What We're Looking For

We're not looking for validation of our current design. We're looking for:

1. **What we're measuring wrong** — metrics that don't capture what matters, or that capture the wrong thing
2. **What we're not measuring** — dimensions of companion memory quality we've overlooked
3. **How to build credibility** — annotation, statistical, and methodological steps that would make this benchmark take seriously in research
4. **Precedents** — benchmarks in adjacent or novel domains that got this right, and what we can learn from them

## Reference Materials

All source materials are in this repository:
- [README.md](../../README.md) — overview, quick start, dataset summary
- [docs/BENCHMARK_CREDIBILITY.md](./BENCHMARK_CREDIBILITY.md) — our internal audit of what's solid and what's missing
- [docs/ADAPTERS.md](./ADAPTERS.md) — adapter interface and patterns
- [docs/SCORING.md](./SCORING.md) — scoring formulas and methodology
- `ember/datasets/golden_facts.json` — actual conversation dataset
- `ember/datasets/retrieval_queries.json` — actual query dataset
- `ember/scoring.py` — scoring implementation
- `ember/tiers/` — tier evaluation scripts

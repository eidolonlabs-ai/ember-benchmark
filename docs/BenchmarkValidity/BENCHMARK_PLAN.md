# EMBER Benchmark Development Plan

## Goal

Take EMBER from a promising v0.1 framework to a credible, publishable benchmark for emotionally-aware memory in companion AI.

## Current State

- 12 conversations, 55 gold facts, 40 queries
- Salience-weighted recall, graceful omission, recency bias, roundtrip tiers
- Keyword-overlap scoring (fragile), arbitrary pass thresholds
- Single annotator, no baselines, no statistical analysis
- No latency/cost telemetry, no adversarial cases

## Phased Plan

### Phase 1 — Foundation (Weeks 1-2)

**1.1 Update documentation to match reality**
- [ ] Update README: 12 conversations / 55 facts / 40 queries (not 7/28/25)
- [ ] Add "Known Limitations" section to README
- [ ] Add "What's Valid / What's Not" to README so users know the benchmark's current standing

**1.2 Run BCa Bootstrap Significance**
- [ ] Write `scripts/bootstrap_significance.py` using BCa (Bias-Corrected and Accelerated) bootstrap resampling.
- [ ] Generate confidence intervals to account for skewed distributions in the small (N=40) sample size.
- [ ] Output: Validated confidence intervals showing what deltas are genuinely detectable.
- [ ] Report in README and paper as a known limitation, abandoning frequentist p-values.

**1.3 Add reference baselines**
- [ ] `baselines/oracle.py` — feeds exact ground-truth facts to establish the absolute upper-bound performance ceiling.
- [ ] `baselines/verbatim_rag.py` — **NEW**: pure BM25/Vector search over raw conversation transcripts (no extraction layer) to establish if LLM extraction is actually better than simple search.
- [ ] `baselines/retrieve_everything.py` — returns all facts for every query, scored normally
- [ ] `baselines/random.py` — returns random subset, scored normally
- [ ] `baselines/keyword.py` — keyword-overlap retrieval (no embeddings)
- [ ] These give interpretive context: if all systems score near "retrieve everything", the benchmark is trivial; if near random, it's unsolvable

**Success criteria:** README is accurate, users can interpret any score against Oracle/Random/Verbatim baselines, BCa significance is published.

### Phase 2 — Scoring Robustness (Weeks 3-4)

**2.1 Improve extraction scoring & Judge Calibration**
- [ ] Implement **Judge False Positive Rate (FPR) Calibration**: defined negative-example test suite (intentionally vague/wrong answers) to ensure the LLM judge matching facts isn't overly lenient.
- [ ] Add accepted synonym lists for high-value gold facts (e.g., "died" / "passed away" / "deceased")
- [ ] OR add lightweight sentence-similarity scoring (e.g., `sentence-transformers/all-MiniLM-L6-v2`) as an optional scorer alongside keyword overlap
- [ ] Document the tradeoff: keyword = reproducible but fragile; embeddings = robust but model-dependent
- [ ] Make it a configuration choice per adapter

**2.2 Expand Tier 2b (recency)**
- [ ] Replace 4 discrete score buckets with continuous Kendall's τ between expected and actual rank order
- [ ] Add 3+ scenarios:
  - Short-term: 3 facts, 1-7 days apart
  - Medium-term: 5 facts, 7-30 days apart
  - Long-term: 8 facts, 30-180 days apart
- [ ] Test with varying query specificity (broad vs. narrow temporal cues)
- [ ] Each scenario tests a different hypothesis (e.g., "does recency override salience?")

**2.3 Introduce nDCG and Calibrate Salience Weights**
- [ ] Shift retrieval evaluation to use **nDCG (Normalized Discounted Cumulative Gain)** to natively handle both rank position and salience weight.
- [ ] Simplify salience weights (3x/2x/1x) to "human-rated emotional intensity" rather than formally citing the PAD model, letting survey data justify the weights to avoid niche reviewer scrutiny.
- [ ] Run a survey: 10-15 raters rank-order facts by emotional importance to empirically adjust the weights.
- [ ] Compute inter-rater reliability (Krippendorff's α), targeting ≥ 0.67 for acceptability and ≥ 0.75 for strong alignment.

**Success criteria:** Extraction scoring tolerates reasonable paraphrase, Tier 2b uses Kendall's τ, retrieval uses nDCG, and salience weights are grounded entirely in empirical survey data.

### Phase 3 — Test Depth (Weeks 5-6)

**3.1 Add adversarial conversation set (4-6 conversations)**
- [ ] **Ambiguity:** "She said she's fine" — is it salient? The system should flag it as low-medium with a note
- [ ] **Contradiction:** User says they love painting in week 1, says they hate art in week 3. System should surface both and note the change.
- [ ] **Temporal drift:** Same fact ("user lives in Seattle") has different salience in week 1 (new city = interesting) vs. week 90 (mundane)
- [ ] **Near-miss context:** "What's been hard?" — should surface grief but NOT casual facts like "likes hiking"
- [ ] **Emotional suppression:** User avoids talking about a topic, but the companion notices indirect signals
- [ ] **Two-way contradiction:** Both user and companion express conflicting values
- [ ] **Semantic/Emotional Interference:** Adapted from MINJA security concepts. User explicitly says something confusing, completely sarcastic, or manipulative. Tests if the system correctly quarantines this rather than encoding it as a core factual belief.

**3.2 Add graded omission scoring**
- [ ] Current omission is binary (passed/failed). Add partial-match scoring:
  - Full omission (correct) = 1.0
  - Mentions related topic but not the specific fact = 0.5
  - Mentions the fact but in wrong context = 0.0
  - Actively surfaces the fact = -1.0 (penalized)
- [ ] This gives more signal for systems that are "close but not quite there"

**3.3 Add Tier 4 (Relational) — Scoped out of v0.2 / Planned for v1**
- [ ] Proactive surfacing is heavily policy-dependent (when should a companion volunteer info?) and risks encoding design assumptions rather than ground truth.
- [ ] Keep this out of the v0.2 paper submission, or define it extremely narrowly (e.g., "given a query with no explicit memory cue, does the system surface a fact with salience ≥ 3 from the last 7 days?").

**Success criteria:** Adversarial set discriminates between naive and sophisticated systems, omission scoring provides granular feedback, Tier 4 design is scoped.

### Phase 4 — Production Readiness (Weeks 7-8)

**4.1 Add latency/cost telemetry**
- [ ] Decorator or context manager: `@timed` around `search()`, `ingest_conversation()`, etc.
- [ ] Report p50, p95, p99 latency per tier
- [ ] Optional: cost estimation (token counts × rate, or adapter-provided cost function)
- [ ] Include in CLI output: `ember run --telemetry`

**4.2 Add inter-annotator agreement study**
- [ ] Recruit ≥3 independent raters (can be external collaborators or LLM-assisted with human review)
- [ ] Have them independently label salience for 20% of facts (stratified across conversations)
- [ ] Compute Krippendorff's α targeting ≥ 0.67 (acceptable for highly subjective emotional data) and ideally ≥ 0.75.
- [ ] Resolve disagreements and re-score the remainder
- [ ] Report Krippendorff's α in paper as a credibility metric (managing expectations so <0.80 isn't seen as a failure).

**4.3 Add comprehensive test suite & Anti-Gaming Guardrails**
- [ ] **Strict Bound Enforcement**: The evaluation runner MUST fail any adapter where `top_k >= total retrievable units`, preventing structural bypasses that turn retrieval into reading comprehension.
- [ ] **Data Partitioning Protocol**: Strictly enforce a Dev / Valid / Held-Out Split (e.g., hold out 30 queries, leave 10 for dev). Users must only report the Held-Out BCa score to prevent test-set contamination.
- [ ] Unit tests for scoring functions
- [ ] Integration tests with mock adapters
- [ ] Test that baselines produce expected score ranges
- [ ] Test that adversarial cases produce expected failure patterns for naive systems

**4.4 Implement Advanced Reporting (Inspired by BEAM & LongMemEval)**
- [ ] **Root-Cause Failure Categorization**: Instead of flat percentages, the runner tags evaluations outputting modes like `FALSE_ABSTENTION`, `CONTRADICTION_MISS`, `CONTEXTUAL_HARM`, etc. (BEAM 100K standard).
- [ ] **Failure Taxonomy Validation**: Add a manual spot-check step to human-audit the auto-tagger. Diagnostic isolation is only as good as the tagger itself.
- [ ] **Diagnostic Isolation**: The runner reports success/failure across the discrete pipeline stages: (1) Did it extract? (2) Did it retrieve? (3) Did it omit?

**4.5 Finalize paper**
- [ ] Incorporate power analysis results
- [ ] Include baseline scores
- [ ] Report IAA if available, or note as limitation
- [ ] Add sensitivity analysis for salience weights
- [ ] Document all known limitations

**Success criteria:** Results are reproducible, comparable across systems, and interpretable with baselines + latency + statistical context.

## What "Done" Looks Like

- [ ] 20+ conversations, 100+ facts, 60+ queries
- [ ] BCa Bootstrap Resampling published validating detectable deltas
- [ ] 4 reference baselines (including Oracle) with published scores
- [ ] Extraction scoring with paraphrase tolerance (synonyms or lightweight similarity)
- [ ] Retrieval scoring evaluated accurately using nDCG
- [ ] Tier 2b with Kendall's τ and 3+ scenarios
- [ ] 4-6 adversarial conversations
- [ ] Graded omission scoring
- [ ] Latency/cost telemetry in CLI output
- [ ] Inter-annotator agreement reported (Krippendorff's α ≥ 0.67)
- [ ] Pass thresholds justified by BCa significance or sensitivity analysis
- [ ] Full test suite with 20+ tests
- [ ] Paper ready for submission to a benchmark/evaluation venue (e.g., EMNLP Findings, NeurIPS Datasets & Benchmarks)

## Risks

| Risk | Mitigation |
|------|-----------|
| Can't recruit annotators for IAA | Use LLM-assisted annotation with human spot-check; report as limitation |
| Dataset expansion dilutes quality | Require a rigid checklist for new convos: Covers ≥N tiers, contains ≥M omission candidates, reviewed for overlap. |
| Paraphrase-tolerant scoring adds dependency | Make it optional; default to keyword overlap with synonym lists |
| Power analysis shows benchmark can't detect meaningful deltas | Acknowledge as v0.2 limitation; focus on gross failure detection rather than fine comparison |
| Adversarial cases are too subjective | Define clear pass/fail criteria per case; use multiple raters |

## Priorities

If time is short, focus on **Phase 1 + 2.2 + 2.3 + 3.1**. Submitting with arbitrary pass thresholds and unvalidated salience weights will get desk-rejected at a serious venue. This shortlist gives you:
- Accurate documentation
- Published power analysis
- Reference baselines
- Better recency scoring
- Human-rated salience weights & nDCG retrieval (critical)
- Adversarial test cases

That's enough to go from "interesting idea" to "credible v0.2 benchmark."

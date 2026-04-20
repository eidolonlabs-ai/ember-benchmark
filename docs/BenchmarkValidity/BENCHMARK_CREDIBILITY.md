# EMBER Benchmark Credibility Audit

What constitutes good benchmarking for a domain-specific memory system, and where EMBER stands against those criteria.

---

## What Makes a Benchmark Credible

### 1. Ground Truth That Isn't Self-Referential

Gold-standard facts need to be annotated by humans independent of the system being tested. The risk with any benchmark is that the author who wrote the test cases also decided what "correct" looks like — baking in assumptions about salience, granularity, and scope.

For emotional salience specifically, inter-annotator agreement scores (specifically Krippendorff's α, targeting ≥ 0.67 for acceptability and ≥ 0.75 for strong alignment) on the gold labels are necessary. "Grief matters more than food preferences" is intuitive but needs to be operationalized with at least 3 independent raters to be publishable. Do not set expectations at ≥ 0.80 since emotional salience is inherently subjective.

### 2. Metrics Sensitive to the Domain

Standard precision/recall isn't sufficient for emotionally-grounded memory. A credible companion memory benchmark needs:

- **Salience-weighted recall** — missing "mother passed away" should penalize harder than missing "likes Thai food"
- **Retrieval Harm Penalties** — A false positive is not just an accuracy drop; bringing up trauma during a casual mood is harmful. We explicitly evaluate the difference between a neutral hallucination and an emotionally harmful retrieval ("Contextual Inappropriateness Rate").
- **Normalized Discounted Cumulative Gain (nDCG)** for retrieval order — a system that surfaces the right fact 5th is better than one that doesn't surface it at all, but worse than one that surfaces it 1st. nDCG gracefully combines relevance weighting with rank position.

### 3. Sufficient Scale for Statistical Significance

Small benchmarks can still be published as focused v0.1 contributions, but effect sizes may not be reliable below a certain delta. For comparing two systems, power analysis determines what difference you can actually detect at a given confidence level.

### 4. Adversarial and Edge Cases

Beyond clean happy-path cases, credible benchmarks need scenarios specifically designed to break naive implementations:

- Emotionally ambiguous facts ("She said she's fine" — is that salient?)
- Temporal drift — same fact, different emotional valence over time
- Contradictory memories — user said X in week 1, Y in week 3
- Near-miss contexts — "What's been hard lately?" vs. "What's fun?" aren't opposites but require different filtering

### 5. Training Data Leakage Prevention

> [!IMPORTANT]
> **Hybrid Dataset Origin Strategy:** EMBER intentionally utilizes a hybrid generation approach to balance ecological validity with adversarial rigor.
> 
> - **Core Benchmark (Tiers 1-3):** **Human-authored explicitly for this benchmark**. Synthetic conversations tend to be too "on-the-nose" about emotional content, which makes extraction artificially easy. Real companion logs are messy, indirect, and subtextual. These conversations are hand-written and guarantee zero distribution leakage against LLM training corpora.
> - **Adversarial Set:** **Synthetic (LLM-assisted)**. Since adversarial edge-cases (semantic traps, rapid contradiction loops) stress-test structural failure modes rather than emotional nuance, using targeted LLMs to generate these extreme patterns provides necessary scale and control.

### 6. Reproducibility Infrastructure and Anti-Gaming Guardrails

- Adapters must be deterministic (seed any LLM calls used in extraction/retrieval)
- **Strict Bound Enforcement**: Systems must respect `top_k` limits. Retrieving more facts than retrievable units bypasses retrieval and tests reading comprehension; such tests must be rejected.
- **Held-Out Splits**: Developers cannot tune prompts against the final test queries or the dataset becomes contaminated. A Dev/Val/Test split is strictly required to prevent overfitting even at N=40.
- **Diagnostic Isolation**: Empathic memory is a pipeline. The benchmark trace must separate errors by stage (Extraction → Retrieval → Omission) using Oracle evidence so we distinguish between "It forgot to process the trauma" vs "It failed to pull it into context."
- Report latency and cost alongside quality metrics — a memory system that's 95% accurate but costs $2/query isn't comparable to one that's 88% accurate at $0.01
- Include reference baselines: an "Oracle Baseline" (feeding the exact ground-truth facts to establish the upper bound ceiling), a **Verbatim RAG Baseline** (pure transcript search to challenge the necessity of LLM extraction), a "retrieve everything" baseline, and a random baseline for the floor.

---

## Where EMBER Stands

### What's Already Solid

#### Scoring Formulas Are Mathematically Explicit

The salience-weighted recall formula is defined in `SCORING.md` and implemented in `scoring.py`:

$$\text{Weighted Recall} = \frac{\sum_{s \in \{H,M,L\}} \text{found}_s \times w_s}{\sum_{s \in \{H,M,L\}} \text{total}_s \times w_s}$$

Where $w_H = 3, w_M = 2, w_L = 1$.

A system that finds all LOW facts but misses all HIGH facts scores **0.13**. All HIGH but missing all LOW scores **0.73**. The weights are baked into the `Salience` enum (`types.py`, line 29-30).

> [!NOTE]
> The 3x/2x/1x calibration is intuitive. While psychological models like PAD exist, they invite intense reviewer scrutiny in NLP/ML venues. Anchor the 3x/2x/1x weights purely in "human-rated emotional intensity" and let the human survey empirical data speak for itself.

#### Graceful Omission Is Its Own Metric

`graceful_omission_score()` is a dedicated function in `scoring.py`. Queries have separate `omit_keywords` fields. This is not lumped into precision — it's measured independently with its own pass threshold (≥ 0.80).

The "inverse omission" query (`q_avoid_topics` — "What topics should I be sensitive about?") is a particularly strong design decision. It validates that the system *can* surface sensitive content when asked directly, proving that omission in casual contexts is **active filtering**, not inability to retrieve.

#### Bidirectional Memory Has Its Own Queries

Two dedicated queries (`q_companion_values`, `q_companion_approach`) test `scope=shared` facts. The golden dataset includes 4 companion-expressed facts across `conv_companion_values`. The adapter interface exposes `supports_two_way_memory` as an opt-in capability flag.

#### The Adapter Pattern Is Clean

5 abstract methods, async-first, no opinion on storage or embedding. Adapters can be thin wrappers around MCP clients, direct DB access, REST APIs, or in-process function calls. `setup()`/`teardown()` hooks are optional. This is one of the strongest design decisions in the project.

---

### Where the Gaps Are

#### 1. Scale Is Better Than Documented, But Still Marginal

The README says "7 conversations / 28 facts / 25 queries." The actual dataset contains **12 conversations, 55 gold facts, and 37 queries** spanning 7 query types. The README is stale.

55 facts and 37 queries is meaningfully better than 28/25, but still small for statistical power. The critical question: can you detect a 5-point difference between two systems at p<0.05?

- With 37 queries, probably not for retrieval metrics
- With 55 extraction facts, maybe for weighted recall

> [!IMPORTANT]
> Use BCa (Bias-Corrected and Accelerated) Bootstrap Resampling to determine significance. With only 37 queries, standard frequentist p-values are invalid. If BCa shows you can only detect 15-point deltas with confidence, state that explicitly as a known limitation. This is a v0.1 focused benchmark.

#### 2. Keyword Matching Is Fragile for Paraphrase Tolerance

`fact_matches_gold()` uses keyword overlap at a 40% threshold after stopword removal. Examples:

| Extracted Fact | Gold Fact | Overlap | Match? |
|---|---|---|---|
| "User was laid off after 8 years" | "User lost their job of 8 years" | `{8, years}` = 2/4 = 50% | ✅ Yes |
| "User terminated from position after nearly a decade" | "User lost their job of 8 years" | `{}` = 0/4 = 0% | ❌ No |

The predicate-match requirement helps (both would be `JOB_LOSS`), but not all systems output predicates. The fact that EMBER tests *retrieval* for synonym robustness (synonym queries) but doesn't accommodate it in *extraction* scoring is an asymmetry worth addressing.

**Options:**
1. Accept this as a deliberate constraint and document it explicitly
2. Add a small set of accepted synonyms per gold fact
3. Use a lightweight sentence-similarity model for scoring only (separate from the systems under test)

#### 3. Temporal Testing Is Simulated, Not Real-Time

Looking at `tier2b_recency.py`, temporal testing uses **simulated time jumps** via `created_at` timestamps on seeded facts. This tests whether the system's *ranking algorithm* respects timestamps — not whether the system's *decay function* degrades gracefully over real elapsed time.

This is a valid test, but the distinction matters:
- **What's being measured:** timestamp-aware ranking
- **What's not being measured:** temporal memory dynamics (actual decay over hours/days)

The `Timeline` class is well-designed for simulated scenarios — `arc()` models escalating salience over narrative stages. But the recency scoring function is overly rigid:
- Only 4 score buckets (1.0, 0.8, 0.5, 0.0)
- A single test scenario (3 facts, 1 query)
- Not robust enough to distinguish "pretty good at recency" from "perfect at recency"

> [!TIP]
> Expand Tier 2b from 1 scenario / 4 buckets to at least 3 scenarios with continuous scoring (e.g., Kendall's τ between expected and actual rank order).

#### 4. Missing Adversarial Cases

| Case | Status | Why It Matters |
|---|---|---|
| Emotionally ambiguous facts ("She said she's fine") | ❌ Not present | Tests whether extraction assigns appropriate salience to indirect signals |
| Temporal valence drift (same fact, different emotional weight over time) | ❌ Not present | Arc support exists in `Timeline.arc()` but no test exercises it |
| Contradictory memories (user said X in week 1, Y in week 3) | ❌ Not present | Real companion relationships have this constantly |
| Near-miss contexts ("What's been hard?" vs "What's fun?") | ✅ Partially covered | Omission queries handle the "fun" side, but "hard" queries don't test *excluding* casual/positive facts |

#### 5. No Cost/Latency Reporting

The adapter interface has no mechanism for capturing timing data. `search()` and `ingest_conversation()` return results but don't report latency. For comparing systems that trade accuracy for speed (or cost), this is essential context.

A decorator or context manager around adapter calls would be minimal overhead and would make benchmark results comparable across systems with different performance profiles.

#### 6. The "No LLM Judge" Principle Has Tradeoffs

`SCORING.md` explicitly says "no embeddings needed for scoring" — which is good for reproducibility and avoids circular evaluation. But it means extraction scoring has a hard ceiling on paraphrase tolerance.

If a system extracts *"The user's mom died and they got a dog to deal with it"* instead of *"User got Max after their mother's death as a way to cope with grief"*, the keyword overlap might not hit 40%. EMBER tests retrieval for synonym robustness but doesn't accommodate it in extraction scoring. 

If we move to an LLM Judge for checking semantic equivalency, we run into the **"Gameable Judge"** problem—where LLMs incorrectly pass vague but topically adjacent answers.

> [!NOTE]
> If EMBER transitions to an LLM Judge for extraction scoring, it must implement an explicit **False Positive Rate (FPR) Calibration**. The judge must be tested against intentionally vague and confidently wrong answers to ensure strict thresholding.

---

## Recommended Investments

Ordered by impact:

1. **Run BCa Bootstrap Resampling** — State the minimum detectable effect size for both extraction (55 facts) and retrieval (37 queries) metrics. Standard regular power analysis is insufficient here.

2. **Expand Tier 2b** — From 1 scenario / 4 score buckets to at least 3 scenarios with continuous scoring (Kendall's τ). Test with varying fact counts, age distributions, and query specificity.

3. **Adopt nDCG for Retrieval** — Replace binary or flat pass/fail retrieval metrics with nDCG to properly weight both salience and rank.

4. **Add adversarial conversation set** — Ambiguity, contradiction, temporal drift, and "semantic traps". Even 3–4 adversarial conversations would significantly increase the benchmark's ability to discriminate between systems.

5. **Add latency/cost telemetry** — Wrap adapter calls with timing. Report p50/p95 latency and estimated cost per query alongside quality metrics.

6. **Update the README** — It says 7 conversations / 28 facts / 25 queries; the actual dataset has 12 / 55 / 37. Stale documentation undermines credibility before anyone runs the benchmark.

7. **Document inter-annotator agreement** — Have ≥3 independent raters validate the salience labels and gold fact coverage. Report Krippendorff's α (targeting ≥ 0.67 acceptable, ≥ 0.75 ideal).

8. **Add reference baselines** — Add an "Oracle Baseline" (perfect retrieval), a "retrieve everything" baseline, and a random baseline so results have interpretive context.

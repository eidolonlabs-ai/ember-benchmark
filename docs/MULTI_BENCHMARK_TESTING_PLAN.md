# Multi-Benchmark Testing Plan (LOCOMO, LongMemEval, EMBER)

## Goal
Establish a repeatable benchmark program for agent memory quality where:
1. LOCOMO and LongMemEval are run first as broad, well-known baselines.
2. EMBER remains the companion-memory priority benchmark.
3. Results are recorded in a single tracker format for trend analysis.

## Benchmark Priority Order
1. LOCOMO
2. LongMemEval
3. EMBER

## Execution Cadence
- Full suite cadence: weekly (or before major memory releases).
- EMBER cadence: after every memory extraction/retrieval change.
- Quick smoke: Tier 2 + Tier 2b when search/ranking logic changes.

## Standard Run Environment
- Runtime target: local eidolon-agent-memory server.
- Python env: project .venv.
- Capture artifacts:
  - Raw benchmark JSON output
  - Short markdown summary
  - Tracker row update in docs/BENCHMARK_TRACKER.md

## Run Workflow
1. Ensure server stack is healthy.
2. Run LOCOMO and store raw output under eval artifacts.
3. Run LongMemEval and store raw output under eval artifacts.
4. Run EMBER full benchmark and tier-specific reruns if needed.
5. Update docs/BENCHMARK_TRACKER.md with date, commit, scores, pass/fail, and notes.

## Current Integration Status
- EMBER: integrated and runnable.
- LOCOMO: not yet integrated in this repository.
- LongMemEval: not yet integrated in this repository.

## LOCOMO Integration Checklist
1. Add benchmark harness source (repo or package) under external/evals or as a pinned dependency.
2. Add adapter bridge from MemoryAdapter-compatible interface to LOCOMO runner input/output.
3. Add canonical command in this file and in scripts/.
4. Add artifact path and tracker parsing rules.

## LongMemEval Integration Checklist
1. Add benchmark harness source (repo or package) under external/evals or as a pinned dependency.
2. Add adapter bridge from MemoryAdapter-compatible interface to LongMemEval runner input/output.
3. Add canonical command in this file and in scripts/.
4. Add artifact path and tracker parsing rules.

## Canonical Command Placeholders
These will be finalized after harness integration.

```bash
# LOCOMO (placeholder)
python -m <locomo_runner_module> --adapter eidolon-agent-memory --out artifacts/locomo_<date>.json

# LongMemEval (placeholder)
python -m <longmemeval_runner_module> --adapter eidolon-agent-memory --out artifacts/longmemeval_<date>.json

# EMBER (active)
python -m ember.cli run --adapter eidolon-agent-memory --url http://localhost:3100 --json artifacts/ember_<date>.json
```

## Success Criteria
- LOCOMO and LongMemEval both produce stable repeatable outputs for at least 3 consecutive runs.
- EMBER Tier 2 and Tier 2b remain passing.
- EMBER Tier 1 and Tier 3 trend upward week-over-week until pass thresholds are reached.

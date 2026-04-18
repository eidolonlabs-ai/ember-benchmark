# Benchmark Run Tracker

This file tracks benchmark runs across LOCOMO, LongMemEval, and EMBER.

## Legend
- Status: PASS, FAIL, BLOCKED, PENDING
- Priority: P1 (highest) to P3

## Runs

| Date (UTC) | Benchmark | Priority | Adapter/System | Score Summary | Status | Artifact | Notes |
|---|---|---|---|---|---|---|---|
| 2026-04-18 | LOCOMO | P1 | eidolon-agent-memory | N/A | BLOCKED | N/A | Harness not integrated yet in repo; no pip distribution found for locomo |
| 2026-04-18 | LongMemEval | P1 | eidolon-agent-memory | N/A | BLOCKED | N/A | Harness not integrated yet in repo; no pip distribution found for longmemeval |
| 2026-04-18 | EMBER (full) | P2 | eidolon-agent-memory | T1=0.593 FAIL; T2=0.856 PASS; T2b=1.000 PASS; T3=0.442 FAIL | PARTIAL | /Users/markcastillo/git/eidolon-agent-memory/ember_results_latest.json | Retrieval now passing; extraction still below threshold |

## Next Runs Queue
1. Integrate LOCOMO harness and record first baseline.
2. Integrate LongMemEval harness and record first baseline.
3. Re-run EMBER after extraction tuning and update trend line.

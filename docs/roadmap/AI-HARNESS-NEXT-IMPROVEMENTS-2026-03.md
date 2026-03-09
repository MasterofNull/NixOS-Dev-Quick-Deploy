# AI Harness Next Improvements — 2026-03

## High Priority

1. Tool reliability accounting normalization
   - Count only real backend failures in `aq-report`.
   - Exclude ambiguous audit rows and client misuse from reliability scoring.
   - Goal: keep operator recommendations tied to actual service regressions.

2. Hint diversity and anti-dominance
   - Reduce repeated injection of one dominant hint when enough alternatives exist.
   - Increase future hint diversity without removing the top hint when it is the only viable guidance.
   - Goal: broader, more adaptive steering and lower repeated-token overhead.

3. Synthetic gap suppression across harness surfaces
   - Filter doc-analysis prompts, sentinel probes, and other operator/test-only prompts from query-gap driven hints and reports.
   - Goal: keep AIDB import guidance focused on real missing knowledge.

4. Residual knowledge curation for active operator questions
   - Add compact curated knowledge for recurring repo-specific asks:
     - workflow start intent contracts
     - Qdrant + hybrid routing configuration
     - progressive-disclosure token discipline defaults
   - Goal: close repetitive low-confidence loops cheaply.

5. Memory-write reliability clarity
   - Separate invalid input attempts from backend write failures in reporting.
   - Goal: stop `store_agent_memory` from looking flaky when the caller is wrong.

6. Monitoring and report integrity
   - Surface ignored client-side 4xx rows and ambiguous audit rows explicitly.
   - Flag concentrated hint-selection periods as a monitoring note, not just a passive metric.
   - Goal: make future improvement loops easier to steer from the report alone.

## Medium Priority

1. Hint feedback loop quality
   - Expand scoring so high-value successful hints get reused by context, not just raw frequency.
   - Add clearer signal for ignored, rejected, and unhelpful hints.

2. Query-gap lifecycle hygiene
   - Add stronger TTL/curation rules for one-off gaps after knowledge import.
   - Tag synthetic/operator/test gaps separately from product knowledge gaps.

3. Semantic cache effectiveness
   - Add a bounded prewarm path for common low-cost local queries.
   - Improve report guidance so low-sample cache windows do not trigger noisy advice.

4. Operator knowledge quick references
   - Curate short references for remaining NixOS module merge/systemd option questions.
   - Prefer concise references over broad imports.

5. Report/action surface tightening
   - Keep `aq-report` and `/hints` aligned so runtime actions, curated suppressions, and synthetic-gap filters match.

## Current Execution Order

1. Normalize tool reliability accounting
2. Strengthen hint anti-dominance
3. Suppress synthetic gaps across all hint/report surfaces
4. Curate remaining recurring operator knowledge
5. Re-run deploy, QA, report, and live endpoint verification

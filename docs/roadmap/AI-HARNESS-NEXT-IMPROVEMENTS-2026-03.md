# AI Harness Next Improvements — 2026-03

Implementation detail and required-track sequencing live in:
- `docs/roadmap/AI-HARNESS-IMPLEMENTATION-ROADMAP-2026-03.md`

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

7. Offline local-agent resilience and captive portal recovery
   - Keep local-agent execution local-first when internet or remote delegation is unavailable.
   - Degrade flagship/quality-critical routing to local execution with explicit operator-visible reasons instead of hard failure.
   - Keep captive portal recovery bounded: temporary HTTP/HTTPS + DNS + DHCP bypass, interface-aware when specified, with automatic revert.
   - Goal: preserve local AI operability during WAN loss and shorten recovery from portal-gated networks.

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
6. Validate offline local-agent resilience and captive portal recovery

## Batch Execution Model

Default batching rule:
- bundle 3-5 repo-only slices before running `nixos-quick-deploy.sh`
- validate locally after each slice, but delay activation until the batch boundary
- deploy early only for runtime blockers, live-signal-dependent reprioritization, or service-contract activation checks

## Next Batched Execution Queue

### Batch A — Monitoring Summary Integrity
- Surface report freshness in deploy summary
- Surface recent health state in deploy summary
- Surface cache-prewarm state in deploy summary
- Surface historical watchlist state in deploy summary
- Goal: make the deploy completion summary sufficient for first-pass operator triage

### Batch B — Reliability Interpretation
- Separate invalid caller input from backend write failure for `store_agent_memory`
- Distinguish historical reliability debt from active incidents in recommendations
- Add recent-vs-historical context for any remaining reliability watch items
- Goal: stop background debt from looking like an active outage while keeping it visible

### Batch C — Hint Quality and Steering
- Surface a historical hint watchlist when concentration is visible in 7d data but not active in the 1h window
- Increase alternative high-signal hints so dominance reduction has better substitutes
- Add context-sensitive hint reuse beyond raw frequency
- Improve ignored/rejected hint feedback reporting
- Goal: reduce repeated token overhead while improving steering quality

### Batch D — Cache and Retrieval Effectiveness
- Improve semantic-cache guidance beyond low-sample labeling
- Add bounded prewarm heuristics for cheap recurring local queries
- Tighten retrieval-first recommendations when remote spend is unnecessary
- Surface memory-recall utilization so embedded memory is developed with retrieval, not separately
- Goal: improve practical efficiency, not just reporting accuracy

### Batch E — Operator Guidance Tightening
- Add concise quick references for remaining NixOS module merge and systemd questions
- Keep harness report, hints, and curated references aligned
- Goal: reduce recurring operator knowledge gaps without broad imports

### Batch F — Historical Debt Visibility
- Keep historical memory-write failures visible without overstating them as active incidents
- Keep historical hint concentration visible without promoting it to an active recommendation
- Surface first alternate remediation candidates directly in the report and deploy summary
- Goal: steer future loops from the live summary instead of digging through raw JSON

### Batch G — RAG and Retrieval Utilization
- Distinguish healthy retrieval posture from low-sample cache posture
- Surface recent retrieval mix across route search, tree search, and memory recall
- Keep RAG, hint steering, and operator guidance aligned in the same report/deploy summary loop
- Feed low-sample cache and memory-recall underuse back into hints, not only reports
- Goal: treat embedded agent memory + retrieval as a first-class steering system, not a separate subsystem

### Batch H — Agent Lesson Promotion
- Reuse hint feedback and reviewer outcomes as promotion input instead of building a separate training stack
- Surface compact cross-agent lesson candidates in reports and deploy summaries
- Feed promoted lessons back into hints with explicit agent/source attribution
- Goal: let remote, coding, and local agents recursively improve one shared guidance system

### Batch I — Targeted RAG Prewarm and Continuation Memory Steering
- Use live `aq-report` prewarm candidates to run bounded local prewarm instead of generic seed traffic only
- Refresh the live report after targeted prewarm so deploy summaries reflect the new retrieval posture
- Prioritize `memory_recall` in workflow plans for resume/continue queries
- Surface a stronger continuation-specific hint when broad retrieval is overused relative to memory recall
- Current optimization direction: keep continuation-style requests on compact hybrid retrieval instead of the slower tree path when prior context is the main need, and auto-include one memory-recall prewarm seed whenever live posture says recall is underused
- Current routing follow-up: keep switchboard default provider local, lower the hybrid local-confidence threshold to `0.35` declaratively, and remove shell endpoint drift so health/roadmap signals use the same embeddings port (`:8081`)
- Current reporting follow-up: distinguish observed `route_search` latency from actionable/backend-valid latency so invalid 4xx caller traffic and stale unlabeled rows do not trigger unnecessary routing changes
- Current stability follow-up: reduce crash-adjacent local log storms by fixing continuous-learning checkpoint reads and seeding minimal declarative COSMIC greeter theme/config state before `greetd` starts
- Current host-stability follow-up: keep Linux audit opt-in for general-purpose workstations while preserving mandatory audit enforcement for `hospitalClassified` systems, since the recent freeze evidence points at kernel audit log storms on this desktop profile

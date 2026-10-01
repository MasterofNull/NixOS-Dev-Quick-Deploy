Decision
- Adopt agent-run-events.jsonl as the canonical input for observed production agent/model activity; PostgreSQL remains the derived metric store. This is not proof of complete switchboard traffic coverage.
- Add a consumer-side adapter in autonomous-improvement; preserve frozen switchboard.py and llm_config.py hashes. Retain experiment metrics separately; stale routing SQLite must not substitute for live observations.
Metrics
- Cohort: allowlisted production producers, schema v1, unique terminal model_call events (succeeded/failed), within a UTC 24-hour window; exclude running events, fixtures, replays and unknown schemas.
- local_routing_pct = local / (local + remote) terminal calls with verified executed-tier mapping; retain existing 0–1 storage convention despite “pct”; display ×100. Report unknown-tier count and coverage; never infer local from missing fields.
- routing_success_rate = succeeded / (succeeded + failed) terminal calls; execution success, not accepted task quality. Do not mix final_outcome or validation events into this denominator.
- routing_latency_ms = arithmetic mean of finite, nonnegative terminal-call duration_ms, including failed calls; report valid-duration count. Verify producer duration means whole-call elapsed time before enabling latency triggers.
- token_efficiency = sum(accepted_artifact) / sum(total) on records with verified complete token accounting and acceptance provenance, 0 ≤ accepted ≤ total and total > 0; missing coverage yields unavailable, never zero or output/input proxy.
- Every metric carries source/cohort/version, window, numerator/denominator or sum/count, coverage and latest eligible timestamp; disable each trigger when its required coverage is absent.
Design
- Scope implementation to trend_database.py, autonomous_loop.py, a small event adapter, focused tests, env/service read-access wiring as needed, and existing QA/dashboard surfaces; freeze exact paths before implementation.
- Resolve the event path through the existing telemetry configuration contract; add a documented env option only if necessary. No new daemon, producer database or dependency.
- Stream a captured file extent through bounded binary reads (1 MiB maximum record); discard oversize/malformed records with counters; ignore incomplete final lines until next scan. Never readlines(), whole-file JSON, or per-event snapshot lists.
- MVP rescans the current file per cycle, filters timestamps without assuming order, and emits bounded aggregate snapshots; use a disk-backed temporary SQLite unique-event ledger with capped cache for deduplication, not an unbounded Python set.
- Aggregate and upsert fixed UTC hourly buckets using stable source/version/cohort keys, retaining sums/counts for weighted queries; repeated scans must not inflate metrics or compare this cohort against legacy routing baselines.
- Detect replacement/truncation during scanning and fail that observation rather than publish partial metrics; document current-file retention coverage. Rotation history ingestion is deferred unless required to meet the window contract.
- Preserve no-metrics-observed on zero eligible live rows, regardless of fixture counts or experiment rows. Missing/unreadable source and incomplete observation fail with explicit reasons before triggers.
- Run blocking scan/disk work off the async loop; distinguish eligible-window rows from newly inserted rows so an idempotent rescan does not falsely report no data. Expired rows cannot refresh freshness.
- Expose eligible/rejected/duplicate counts, coverage, latest event age, scan duration and observation failure in existing service diagnostics and dashboard; do not log raw payloads.
Acceptance tests
- Fixtures cover UTC Z/offset boundaries, future/stale rows, production allowlisting, duplicate IDs, running-plus-terminal sequences, retries, mixed schemas, malformed/oversize/truncated lines, missing tiers and partial tokens.
- Known cohort: local success + remote failure gives local share 0.5 and success 0.5; durations 100/300 ms give mean 200 ms; accepted 20/total 100 gives efficiency 0.2. Unknown values reduce coverage, never fabricate values.
- Empty, fixture-only, stale-only and experiment-only inputs retain fail-closed; unreadable/rotating sources block triggers; replay and restart produce identical persisted aggregates without duplicates.
- Scan the real ~92 MB file and a ≥10× fixture under the actual 256M unit cap; require whole-unit peak memory <256 MiB, no OOM, bounded aggregate cardinality, and scan completion within the configured cycle timeout; publish measurements.
- Exercise a real production success and controlled failure through existing callers; reconcile their terminal events and metrics, verify service-user read access, QA integration and dashboard data, then run tier0. Syntax tests alone do not satisfy acceptance.
- Rollout: shadow observations with actions disabled, reconcile a complete window and baseline the new cohort, then enable only metrics with verified coverage; preserve all existing action authority gates.
- Rollback: disable the adapter and metric triggers/revert consumer wiring; retain telemetry and provenance-tagged history. Returning to no-metrics-observed is acceptable; restoring fabricated health is not.
Risks
- Bounded last-2-MiB inspection found race-harness-fixture records, mixed non-v1 events and delegate-to-local terminal events with null lane_id; token totals can contain output only. These are observed input-quality blockers to naive ingestion.
- Producer identity/mapping, terminal-attempt uniqueness, duration semantics, full token coverage and file retention need verification; agent events cannot establish global routing share without demonstrated population coverage.
- Follow-up gate: implementation owner must inventory real producer contracts and prove at least one fresh eligible production cohort; missing coverage stays visible and its triggers disabled. Token efficiency may remain unavailable in MVP.
Out of scope
- No switchboard/llm_config edits, sha-pin changes, fake SQLite backfill, service restarts to mask failure, new telemetry platform, historical migration, percentile engine or new autonomous action authority.
VERDICT: PLAN_READY_WITH_FOLLOWUPS — Which verified production producer contracts provide executed tier and terminal-call identity? Confirm before enabling routing-share triggers; complete token-efficiency coverage remains deferred.

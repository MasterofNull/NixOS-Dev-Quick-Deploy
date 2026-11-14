# Persona P3: memory delta, collapse merge, conflicts (design, rev 3: simple)

Status: DRAFT rev 3 for independent re-review (author Simurg@claude/sonnet-5.5; reviewer lane must differ). PRD: `.agent/PROJECT-COLLECTIVE-PERSONA-PRD.md` 4.4, 5, 6. Owner directive 2026-11-13 replaces "conflict list shown by aq-approve": the agent asks the owner in the CLI and applies the answer. `HC` = `ai-stack/mcp-servers/hybrid-coordinator`. UNVERIFIED marks what I could not check.

## 0. Facts this design rests on (read, file:line)

- `POST /api/memory/facts` (`HC/memory/memory_service.py:34-90`): cap 8, 500 chars, `mb.write` defaults (`:72`), no instance field.
- `MemoryBroker.write` has `check_contradictions`, `supersede`, `promote` (`HC/memory_broker.py:115-121`); a contradiction supersedes
  (`:145-158`) except `active_constraint` (`:130-143`).
- Hidden last-write-wins: consensus re-write with `supersede=True` (`HC/consensus_manager.py:77-84`, fired `memory_broker.py:238-247`); crystallizer default write (`HC/memory_crystallizer.py:352-356`); cosine >= 0.95 dedup silently drops a near-identical opposing claim (`HC/knowledge/memory_manager.py:66, 228-248, 354-357`; score for "enabled" vs "disabled" UNVERIFIED).
- `broker.read` is similarity only (`memory_broker.py:260-335`); exact `(scope, subject)` lookup needs a real index. The crystallizer has an optional Postgres client (`execute/fetch_all`, `ensure_schema`: `memory_crystallizer.py:78-87, 125-130, 414-423`); `_pg` may be None.
- `GET /api/memory/facts` is what `aq-session-start` reads (`memory_service.py:94-145`).
- Redaction: `ai-stack/mcp-servers/shared/telemetry_privacy.py:55`. Label: `scripts/ai/lib/instance_label.py`.
- Not found: delta or collapse code, an instance field on facts.

## 1. Delta (emitted by the harness wrapper)

```
{ "instance":"Simurg@codex/gpt-6.1#ab12cd34", "ended_at":"<ISO>",
  "facts":[{"subject":"<dotted key>","claim":"<=500 chars","scope":"<scope>","evidence":"<ref>"}],
  "resolutions":[{"scope","subject","keep":"a|b|both","owner_reply":"<owner's words>"}] }   // only when answering a question
```

- `subject` required, regex `^[a-z0-9_-]+(\.[a-z0-9_-]+)+$`; `evidence` required (non-empty `path:line`, commit sha or command, 8-300 chars);
  at most 10 facts; otherwise HTTP 400, no partial write. Claims and evidence pass `redact_secrets`.
- Emitter: `scripts/ai/lib/memory_delta.py`, called by `aq-commit-facts` and the session-end path, reads `HYBRID_COORDINATOR_URL` (`config/service-endpoints.sh:27-29`); it adds label and time.
- Decisions and open threads are dropped from P3 (no acceptance test needs them).

## 2. Collapse: one route, one table, synchronous

Route: `POST /api/memory/delta` beside the facts routes (`memory_service.py:187-188`). It runs the merge inline and returns
`{"stored":n, "conflicts":[...]}`. No background task: the caller needs the conflicts in the reply, and a 10-fact merge is cheap and uses no LLM.
A `MemoryCrystallizer.collapse()` method holds the logic (extends the crystallizer, `crystallize_session` untouched).

One Postgres table, created in `ensure_schema` like `crystallized_sessions`:
`collapse_facts(delta_id, scope, subject, claim_hash, claim, author, instance, ended_at, evidence, memory_id, state, UNIQUE(delta_id, subject))`,
index `(scope, subject)`. `author` = `lane/model`. `state` is `current | disputed | both | historical | rejected`.

Per fact:
1. `(delta_id, subject)` already present: skip (replay is idempotent; this is the only dedupe).
2. Same `claim_hash` as any row for `(scope, subject)`: provenance row only, no new claim (corroboration; also stops a repeated claim re-raising a settled conflict).
3. Same `author` has an older current row: new fact replaces it, old becomes `historical`. If the new one is older than the author's current row, it is stored `historical`. This is the whole replay-ordering rule: `ended_at` per `(author, scope, subject)`.
4. A current row from a different author with a different claim: conflict. Both rows become `disputed`; the new claim is not written to Qdrant; nothing is superseded.
5. Otherwise: store, and write to Qdrant via `broker.write(..., promote=False, supersede=False, check_contradictions=False)`.

If `_pg` is None or the insert fails the route returns 503 and stores nothing; the wrapper keeps the delta file in
`.agent/memory/pending-deltas/` and retries at the next session start. Idempotence makes retry safe.

## 3. Last-write-wins paths, smallest closure

- Delta writes use the three flags above (they exist, `memory_broker.py:115-121`).
- `_persist_agent_memory` skips `_check_memory_duplicate` when the payload has `origin == "delta"` (one line, `memory_manager.py:354`).
- In `write()`, the existing `active_constraint` block (`memory_broker.py:130-143`) also blocks when the matching entry has `origin == "delta"`.
  This is what stops the consensus re-write and the crystallizer from superseding a delta fact. One condition, no new code path.
- Legacy facts route and crystallizer stay unchanged for subject-less facts; they cannot supersede delta facts after the guard.

## 4. Conflicts go to the owner through the agent

The delta reply lists each conflict: `{scope, subject, mine, theirs, theirs_instance, theirs_evidence}`. The wrapper prints it; the agent
asks the owner one plain numbered question in the conversation ("1) keep mine, 2) keep theirs, 3) keep both") and applies the answer by
sending `resolutions` in its next delta (same route, same call). The agent never answers for the owner.

- keep a/b: the loser becomes `rejected` and, if it was in Qdrant, is superseded with the existing `superseder.supersede(...)`
  (`HC/memory_superseder.py:91`); the winner is written to Qdrant if absent. both: both rows `both`, new claim written to Qdrant.
  A `both` pair never re-fires: step 2 matches either claim by hash, and conflict checks run only for an incoming fact.
- Unanswered conflicts stay `disputed`. `GET /api/memory/facts` gains a `state=disputed` ledger branch, shown by `aq-session-start` as "N unresolved memory conflicts: ask the owner". Recall of a `disputed` `memory_id` is flagged `"disputed": true`.
- Server-side limit: the server cannot prove a human answered. `owner_reply` and the resolving label are stored for audit; the persona refusal list (agents never self-approve) is the control, and reviewer lanes check transcripts.

## 5. Failure, kill switches, privacy, tokens

- Coordinator down or Postgres absent: pending file and retry (section 2); disputed rows live in the ledger, so nothing is lost.
- `PERSONA=0`: label becomes `lane/model`; collapse still runs (memory hygiene, not display).
- No `COLLAPSE=0`: the wrapper is the only emitter, so not calling it is the off switch; the route is inert without callers.
- Privacy: a delta is data, never instruction; claims keep source instance and scope and cannot widen scope.
- Tokens: merge is rule-based, zero LLM tokens. Session start adds at most 3 disputed lines.

## 6. Acceptance (E2E, real lanes)

1. Codex delta fact X; after one collapse Claude and local recall X with label and evidence.
2. Claude s1=A vs Codex s1=B (also near-identical wording): reply lists the conflict, nothing overwritten, agent asks the owner in the CLI; unanswered, the next session start shows it.
3. Owner "keep b": only B recalled, A `rejected`; "keep both" does not re-raise.
4. Replay changes nothing; an older delta replayed after a newer one from the same author stays `historical`.
5. Consensus promotion and crystallizer writes cannot supersede a delta fact.
6. Secret in claim stored redacted; missing `subject` or `evidence` gets 400.
7. Same-lane review rejection (PRD 4.3) unchanged: run the existing review test.
8. `PERSONA=0` accepts a plain `lane/model` identity.

## 7. Simplicity check

- Wrapper: something must build the delta and retry; models must not self-invoke.
- Delta route: the only way to write instance-tagged facts and get conflicts back.
- `collapse_facts`: exact `(scope, subject)` lookup, idempotence, ordering; Qdrant cannot do exact lookup.
- Dedup skip: otherwise an opposing near-identical claim is silently dropped.
- Write guard: otherwise consensus or crystallizer silently supersede.
- `state=disputed` branch: how a later session learns of an unanswered conflict, with no new surface.
- Pending file: otherwise a delta is lost while the coordinator is down.
- `resolutions` field: applies the owner's answer through the same call.

## 8. Review disposition

- Hidden last-write-wins, dedup drop, legacy paths: section 3.
- Attention push swallowed, AppArmor `deny /home/** wx` (`nix/modules/services/mcp-servers.nix:2777`), aq-approve batch/resolve/inbox: moot, owner asked in CLI.
- Keep-both re-trigger: section 4 (hash match). Replay ordering: section 2 step 3. Similarity lookup: one Postgres table.
- Subject, evidence, cap, redaction: section 1.

## 9. Removed versus rev 2

Two of three tables; conflict directory with tmpfiles/AppArmor work; approval_inbox source; `aq-approve resolve` and batch refusal; resolve route; failure counter; `COLLAPSE=0`; background task; `set_payload`; `corroborated_by`; decisions/threads; `ended_at` clamping.

## 10. Open questions

1. Is a server that cannot verify a human answered acceptable, given audit fields and a reviewer-lane transcript check?
2. Which prints disputed conflicts: `aq-session-start` or `aq-resume` (output code not read, UNVERIFIED)?

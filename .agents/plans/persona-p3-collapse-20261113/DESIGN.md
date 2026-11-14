# Persona P3: memory delta, collapse merge, conflict list (design)

Status: DRAFT for independent review (PRD 5a requires a design check before P3 build).
Author: Simurg@claude/sonnet-5.5 (architect). The reviewer lane must differ from the author lane.
PRD: `.agent/PROJECT-COLLECTIVE-PERSONA-PRD.md` section 4.4 (Collapse), section 5 (acceptance), section 6 (slices).
If any part of this is infeasible or unclear, reviewers should say so; that is a good result.

## 0. What exists today (read, with citations)

- Write path: `POST /api/memory/facts` (`ai-stack/mcp-servers/hybrid-coordinator/memory/memory_service.py:34-90`).
  Body `{"facts":[{fact,scope,confidence,source,event_time}]}`, capped at 8 facts per call and 500 chars per
  fact (`:53`, `:56`), written via `memory_broker.write(memory_type="semantic")` (`:72`). No instance field is
  stored: only `scope`, `confidence`, `source` (128 chars), `valid_from`, `origin` reach the context (`:76-82`).
- Existing client: `scripts/ai/aq-commit-facts:93` posts to `${HYBRID_COORDINATOR_URL}`, defined in
  `config/service-endpoints.sh:27-29`. Python precedent: `scripts/automation/apparmor-fix-agent.py:59,430`.
- Crystallizer: `ai-stack/mcp-servers/hybrid-coordinator/memory_crystallizer.py` (506 lines);
  `extensions/memory_crystallizer.py` is a 3-line route shim. `MemoryCrystallizer` (`:93`) distills chat history to
  facts with an LLM (`:267-384`), dedupes sessions via the `crystallized_sessions` table (DDL `:78-87`, check `:414`),
  and runs via `POST /memory/crystalline/run` (`:465-502`, 202 + background task). It merges nothing across instances.
- Contradiction handling today: `memory_broker.py:109-190` `write()` calls `check_contradiction` (`:395-420`), a
  substring antonym test over seven pairs (`:46-54`: "up"/"down", "on"/"off", ...). A hit **supersedes** the old
  fact (`:145-158`) unless it is `active_constraint`, which returns `contradiction_blocked` (`:130-143`).
  `memory_service.py:72` uses the defaults (`check_contradictions=True`, `supersede=True`), so a contradicting fact
  from a second instance silently replaces the first today. That is the last-write-wins the PRD forbids.
- A blocked contradiction pushes an `auto_ok` alert (`memory_broker.py:354-400`, push at `:385`); `auto_ok` goes
  straight to the archive (`scripts/ai/lib/attention_queue.py:14,577`), so it is never an owner-visible list.
- aq-approve intake: `scripts/ai/lib/approval_inbox.py:107-166` reads `attention_queue.get_pending()`; an alert
  with an `executor` lands in the numbered "approval" section, one without in "deferred" (`:166`). `aq-approve`
  runs only `_EXECUTOR_TABLE` keys (`scripts/ai/aq-approve:163-168`), claims atomically before any side effect
  (`:313`), and `review` refuses without a TTY (`:395-410`). `push()` accepts `payload`, `executor`, `dedup_key`
  and boundary `human_gate` (`attention_queue.py:80-100, 519-535`).
- Instance label: `scripts/ai/lib/instance_label.py` (`build_label`; `PERSONA=0` returns plain `lane/model`).
  Format SSOT `canon/blocks/persona.md`.
- Not found anywhere: collapse or delta code, a conflict store, an instance field on memory facts. Those are P3's scope.

## 1. Delta schema

One delta per session or slice end, written by the instance itself:

```
{ "v":1, "instance":"Simurg@codex/gpt-6.1#ab12cd34", "session":"ab12cd34", "slice":"<optional>",
  "ended_at":"<ISO>",
  "facts":    [{"subject":"<stable key>","claim":"<=500 chars","scope":"<existing scope>",
                "confidence":0.0-1.0,"evidence":"<path:line | commit | command>"}],
  "decisions":[{"decision":"...","why":"...","authority":"<who granted>"}],
  "threads":  [{"open":"<unresolved item>","owner_hint":"<lane|owner>"}] }
```

- `subject` is new: the join key for conflicts (section 3), for example `llama-cpp.n_gpu_layers`.
- A fact with confidence above 0.5 and no `evidence` is stored as `unverified` (persona value: truthful).
- Route: new `POST /api/memory/delta` beside the facts routes in `memory_service.py` (`:185-190`), not a new service.
  It validates the label against the `instance_label` format, computes `delta_id = sha256(instance + session +
  canonical-json)`, and stamps `instance`, `delta_id`, `subject`, `evidence`, `origin:"delta"` into each fact's
  context. `source` also carries the label for old readers. The route accepts up to 20 facts and rejects the excess
  with a count (silent truncation, as at `:53`, would hide a failure).
- Decisions and threads go to the same semantic store with `kind: decision|thread`. A thread stays open until a
  later delta closes it.
- Client: `scripts/ai/lib/memory_delta.py` (new, small), reads `HYBRID_COORDINATOR_URL`, never a literal port.
  Called from the session-end path and `aq-commit-facts`.

## 2. Collapse merge (extends the crystallizer)

Add `MemoryCrystallizer.collapse(delta)` in `memory_crystallizer.py`, reusing the class, the lazy broker accessor
(`:113-123`) and the dedupe-table pattern (`:78-87`) with a second table `collapsed_deltas(delta_id PK, instance,
facts_merged, conflicts_raised, processed_at)`. `crystallize_session` is untouched.

- **When:** the delta route enqueues collapse in a background task, as `/memory/crystalline/run` does (`:488-492`),
  so the writing lane never waits. It runs on the local harness (PRD: local is the epicenter). The merge uses no LLM,
  so it works while llama is busy or down.
- **Per fact:** (1) skip if `delta_id` is already recorded; (2) find semantic entries with the same `scope` and
  `subject`; (3) same normalized claim: append this instance to `corroborated_by`, no duplicate; (4) no match: store as new
  canonical fact; (5) different claim from a different instance: conflict (section 3); the new fact is stored
  `state:"disputed"` and the old one is **not** superseded. Both stay readable and flagged.
- **Provenance:** every stored fact keeps `instance`, `delta_id`, `evidence`, `ended_at`. Corroboration appends; nothing
  an instance said is overwritten or deleted.
- **Idempotence:** a replayed delta is a no-op by `delta_id`. The id is recorded only after all facts finish
  (same rule as `memory_crystallizer.py:187-188`). A repeated fact in a later delta corroborates, never duplicates.
- Read paths (`memory_service.py:93-145`) must label `disputed` facts so no lane recalls a disputed claim as settled.

## 3. Conflict detection and the owner list

A conflict is: same `scope` and `subject`, claims differ after normalization (case, whitespace, punctuation),
asserted by two different instance labels, neither claim superseded. Fallback when `subject` is absent:
`memory_broker.check_contradiction` (`:395`). It matches substrings ("on" inside "configuration"), so fallback hits are
low severity, capped at 5 per collapse, and never cause supersession.

- Surface: `attention_queue.push(source="persona-collapse", severity="medium", autonomy_boundary="human_gate",
  executor="memory_conflict_resolve", dedup_key=sha256(scope+subject), payload={a_id,b_id,claims,instances,evidence})`.
  With an `executor` it appears in aq-approve's numbered approval list (`approval_inbox.py:166`); the dedup key makes a
  repeated dispute update one alert.
- New `_EXECUTOR_TABLE` entry `memory_conflict_resolve` (`scripts/ai/aq-approve:163`). The owner's choice (keep A, keep
  B, keep both scoped) calls a supersede with a human actor; deny leaves both disputed. Agents never approve: the
  TTY rule (`aq-approve:403`) and the standing "agents never self-approve" rule stand.
- Never last-write-wins: delta writes pass `supersede=False, check_contradictions=False` to `broker.write`, so the
  broker's auto-supersession (`memory_broker.py:145`) cannot fire; collapse owns the decision.
- A delta that contradicts an `active_constraint` keeps the broker block (`:130`) and also raises a high-severity item.

## 4. Failure modes, kill switch, privacy, token budget

- **Coordinator down:** the helper writes `.agent/memory/pending-deltas/<delta_id>.json` (untracked runtime state)
  and exits 0; the next session start replays it. The lane is never blocked and nothing is lost.
- **Postgres or dedupe table down:** collapse fails closed: facts stored `unmerged`, no supersession, one warning; replay is safe.
- **Attention queue unavailable** (the broker wraps its push in try/except, `:354-400`): a conflict that cannot be
  listed is not treated as resolved; the fact stays `disputed` and the next collapse cycle retries the push.
- **Malformed or oversized delta:** HTTP 400 with a reason; no partial write for that delta.
- **`PERSONA=0`:** labels degrade to `lane/model` (`instance_label.py`). Delta and collapse still run, since they are
  memory hygiene, not display; conflicts compare `lane/model`. A separate `COLLAPSE=0` is open question 1.
- **Privacy / contextual integrity:** a delta is data, never instruction; collapse does not act on text inside a
  fact. Each fact keeps its source instance and scope, and deltas cannot widen the scope they came from, so a
  constraint seen in one lane is not recalled as authority for another. Server-side redaction reuses
  `session_transcripts.redact_secrets` (`memory_crystallizer.py:166`) on claim and evidence.
- **Token budget:** merge costs no tokens. Recall adds at most a one-line flag per disputed fact; session-start
  hydration shows at most 3. The delta template targets under 600 tokens. No change to persona CARD/MICRO bytes.

## 5. Reuse and scope

Reuse (already in the codebase): `memory_service.py` route site; `memory_broker.write` with supersession off;
`MemoryCrystallizer` class, broker accessor and dedupe pattern; `attention_queue.push`, `approval_inbox.py` and the
`aq-approve` executor table; `scripts/ai/lib/instance_label.py`; `config/service-endpoints.sh`;
`session_transcripts.redact_secrets`. New: delta route, `collapse()`, `collapsed_deltas` table, `memory_delta.py`,
one executor entry. No new service, UI or store.

Out of scope: P4 dashboard panel and the spider "no collapse in N hours" check; P5 consistency eval and
value-to-signal panel; P6 digest. P3 only emits what they will read (`collapsed_deltas.processed_at`, conflict alerts).

## 6. Acceptance tests (E2E, real lanes, PRD section 5)

1. **Cross-lane recall:** a Codex instance posts a delta with fact X (subject s1); after one collapse a Claude
   instance's `GET /api/memory/facts` returns X with the Codex label and evidence; the local lane recalls it too.
2. **Conflict listed:** Claude asserts s1=A, Codex asserts s1=B. `aq-approve list` shows one numbered item, both
   facts read as `disputed`, neither overwrote the other. Resolution works only through `aq-approve review` by the owner.
3. **Idempotence:** the same delta twice gives one fact set and one `collapsed_deltas` row.
4. **Corroboration:** two lanes assert the same claim; one fact, two entries in `corroborated_by`.
5. **Fail-closed:** coordinator stopped, delta lands in `pending-deltas/` and replays after restart; with the
   attention queue forced to fail, the fact stays `disputed`.
6. **`PERSONA=0`:** a delta with a plain `lane/model` identity is accepted; collapse and conflict list work.
7. **Regression:** a contradicting delta no longer triggers broker supersession (`memory_broker.py:145`).
8. **Secrets:** a delta containing a token pattern is stored redacted.

## 7. Open questions for reviewers

1. Should `COLLAPSE=0` exist apart from `PERSONA=0`? Lean: yes.
2. Is `subject` required from the instance, or derived by the local model? Required is cheaper and more reliable.
3. `approve <n>` for this executor: should it be refused so a blind batch approve cannot pick a side, leaving only
   `review` with an A/B/both prompt? Proposed: yes.
4. Can the coordinator process import `attention_queue` (`scripts/ai/lib`; bare-name import at `memory_broker.py:385`)
   and write `.agents/attention/`? Not verified; Rule 14 (service UID permissions) applies. Needs a live check before build.
5. Is 20 facts per delta right against today's cap of 8?
6. With no Postgres (`memory_crystallizer.py:126`), is a file-backed dedupe fallback required?

# Persona P3: memory delta, collapse merge, conflict list (design, rev 2)

Status: DRAFT rev 2 for independent re-review. Author: Simurg@claude/sonnet-5.5 (architect); reviewer lane must differ.
PRD: `.agent/PROJECT-COLLECTIVE-PERSONA-PRD.md` section 4.4, 5, 6. Reviews folded in: Gemini REQUEST_REVISION
(gemini-20261113-172653-qkwp7k), local PLAN_READY_WITH_FOLLOWUPS (local-20261113-172706-nk1035). See "Review disposition".
Paths are relative to the repo root; `HC` = `ai-stack/mcp-servers/hybrid-coordinator`. Unverified items are marked UNVERIFIED.

## 0. What exists (read; file:line)

- Facts route `HC/memory/memory_service.py:34-90`: cap 8 facts, 500 chars (`:53,:56`); calls `mb.write` with defaults (`:72`);
  stores no instance field (`:76-82`). Client `scripts/ai/aq-commit-facts:93` uses `${HYBRID_COORDINATOR_URL}`
  (`config/service-endpoints.sh:27-29`).
- `MemoryBroker.write` (`HC/memory_broker.py:109-122`) has params `check_contradictions`, `supersede`, `promote`, all default True.
  A contradiction supersedes (`:145-158`) except `active_constraint` (`:130-143`). `check_contradiction` is a substring
  antonym test (`:46-54, 395-420`).
- Hidden last-write-wins paths: (a) `HC/consensus_manager.py:77-84` re-writes promoted facts with
  `check_contradictions=True, supersede=True`; promotion fires when `promote=True` (`memory_broker.py:238-247`).
  (b) `MemoryCrystallizer._crystallize_history` writes `broker.write(..., source="crystallizer")` with default supersede
  (`HC/memory_crystallizer.py:352-356`). (c) cosine dedup: `HC/knowledge/memory_manager.py:66` (`MEMORY_DEDUP_THRESHOLD=0.95`),
  `:228-248, :354-357` drops any new point whose nearest neighbour scores >= 0.95, unfiltered by subject or scope.
  `store_agent_memory` already returned `"queued"` (`:332-336`), so the caller never learns the drop happened. An opposing
  claim with near-identical text ("X is enabled"/"X is disabled") is plausibly >= 0.95; the actual score is UNVERIFIED.
- Qdrant: `broker.read` is similarity search only (`memory_broker.py:260-335`); `memory_manager.py` never calls `scroll`
  or `set_payload`. The same client type does elsewhere (`HC/extensions/interaction_tracker.py:459,643`;
  `HC/knowledge/search_router.py:836`), but no payload index on `subject` is created anywhere (rg found none).
- Attention queue: the broker's push is swallowed (`memory_broker.py:385-401`, `except Exception: pass` at `:400`). The coordinator
  sets `ATTENTION_QUEUE_DIR=${mcp.repoPath}/.agents/attention` (`nix/modules/services/mcp-servers.nix:1407`) and
  `ReadWritePaths` (`:1464`), and its AppArmor profile `ai-hybrid-coordinator` allows that path rw (`:2697-2699`) but
  also has `deny /home/** wx,` (`:2777`; the same line is in `command-center-dashboard-api`, `:2964`). AppArmor deny
  overrides allow, so writes under `/home` fail regardless of DAC (`/home/hyperd` is 0711, `.agents/attention` is
  2775 hyperd:ai-stack, per the orchestrator). I did not test this at runtime. `PYTHONPATH` includes `scripts/ai/lib`
  (`mcp-servers.nix:~1403`), so the import itself works.
- aq-approve intake `scripts/ai/lib/approval_inbox.py:107-190` merges several JSON sources; `approve()` dispatches on item
  `kind` (`:217-229`); the CLI takes numbers and batches (`approval_inbox.py inbox_cli`, `aq-approve:413-418`).
  Postgres access in the crystallizer: `self._pg.execute/fetch_all` (`memory_crystallizer.py:125-130, 414-423`); `_pg` may be None.
- Redaction: `ai-stack/mcp-servers/shared/telemetry_privacy.py:55` `redact_secrets` (returns text and hit list);
  `memory_manager._sanitize_metadata` already scrubs metadata (`:167-179`).
- Not found: delta/collapse code, a conflict store, an instance field on facts. These are P3's scope.

## 1. Delta schema (harness-emitted)

```
{ "v":1, "instance":"Simurg@codex/gpt-6.1#ab12cd34", "session":"ab12cd34", "ended_at":"<ISO>",
  "facts":[{"subject":"<dotted key>","claim":"<=500 chars","scope":"<scope>","confidence":0..1,"evidence":"<ref>"}],
  "decisions":[{"decision","why","authority"}], "threads":[{"open","owner_hint"}] }
```

- `subject` REQUIRED, regex `^[a-z0-9_-]+(\.[a-z0-9_-]+)+$` (for example `llama-cpp.n_gpu_layers`); missing or invalid: HTTP 400.
- `evidence` REQUIRED for every fact (`path:line`, commit sha, or command); light check: non-empty, 8-300 chars, matches
  one of those three shapes. It is a pointer, not verified truth; a bad pointer is reviewable provenance, not a gate.
- Max 10 facts per delta (over: 400 with count, no truncation). Claims and evidence pass `redact_secrets` server-side.
- Emission is by harness wrappers, not model self-invocation: `aq-commit-facts` (slice end) and the session-end path
  (`aq-session-start`'s counterpart) call helper `scripts/ai/lib/memory_delta.py`, which builds the delta from the
  instance's recorded facts and reads `HYBRID_COORDINATOR_URL`. Instances supply content; the wrapper supplies label and session.
- Route: `POST /api/memory/delta` in `memory_service.py` beside `:187-188`. `delta_id = sha256(instance+session+canonical json)`.
  Decisions and threads store as `kind: decision|thread` entries, never conflict-checked.

## 2. Authoritative ledger and exact lookup (B5)

`broker.read` cannot do exact (scope, subject) lookup, and the Qdrant write is fire-and-forget. So collapse keeps its own
authoritative index in Postgres, via the existing `_pg` client, created in `ensure_schema` like `crystallized_sessions`
(`memory_crystallizer.py:78-87,125-130`):

- `collapse_facts(fact_id PK, delta_id, scope, subject, claim_norm, claim_hash, author, instance, ended_at, state,
  corroborated_by jsonb, memory_id)` with index on `(scope, subject)`. `author` is `lane/model` (no session).
- `collapsed_deltas(delta_id PK, instance, facts_merged, conflicts_raised, processed_at)`.
- `collapse_resolutions(scope, subject, fact_a, fact_b, choice, resolved_by, resolved_at)`.
- Qdrant holds only the recall copy (payload: `origin:"delta"`, `subject`, `instance`, `state`, `delta_id`, `evidence`).
  `state` changes (disputed to resolved) rewrite the copy via `set_payload` by `memory_id` (client method used in
  `interaction_tracker.py:459`); lookup never depends on Qdrant. Whether `set_payload` works on the memory collection: UNVERIFIED, test in S2.
- If `_pg is None` or the ledger is down, collapse fails closed: the delta stays pending (section 5). No file-backed dedupe.

## 3. Closing every last-write-wins path (B1)

- Delta facts call `broker.write(..., promote=False, supersede=False, check_contradictions=False)`; all three params exist
  (`memory_broker.py:115-121`). The collapse, not the broker, decides.
- Dedup: `_persist_agent_memory` skips `_check_memory_duplicate` when the payload has `origin == "delta"`
  (`memory_manager.py:354`); dedup for delta facts is exact `(scope, subject, claim_hash)` in the ledger instead.
- Guard against other writers: extend the existing `active_constraint` block in `write()` (`memory_broker.py:130-143`)
  so an existing entry with `origin == "delta"` and `state in (disputed, current)` also returns `contradiction_blocked`.
  That covers the consensus re-write (`consensus_manager.py:77-84`, whose metadata copy carries `origin`) and the crystallizer.
- Legacy `POST /api/memory/facts` and `_crystallize_history` stay as they are for subject-less facts (no instance, no subject,
  so they cannot be conflict-keyed), justified by the guard above: they can no longer supersede a delta fact. Their own
  supersession among themselves is unchanged and out of scope.
- Conflict detection is rule-based (string and key comparison); the merge spends no LLM tokens. No substring-antonym
  fallback for delta facts.

## 4. Collapse merge, conflicts, keep both (B3, B4)

`MemoryCrystallizer.collapse(delta)` (new method; `crystallize_session` untouched), run in a background task like
`memory_crystallizer.py:488-492`, on the local harness. Per fact, inside one ledger transaction:

1. `delta_id` already in `collapsed_deltas`: no-op (idempotent; recorded only after all facts finish, cf. `:187-188`).
2. Select ledger rows for `(scope, subject)`.
3. Same `author` and older `ended_at` than an existing row: store as history (`state:"historical"`); a newer one from the
   same author replaces that author's current row. This is the ordering rule: replay after restart cannot make an old claim
   current, because sequencing is `(author, ended_at)` and each author's newest wins only over that author's own claims.
   `ended_at` is clamped to server receive time (cross-host clock skew: UNVERIFIED, expected single host).
4. Same `claim_hash` from another author: append to `corroborated_by`.
5. Different claim from another author with no `collapse_resolutions` row for the pair: conflict. Both rows get
   `state:"disputed"`; nothing is superseded.
6. Otherwise: new current fact.

Keep both: the owner's choice writes `collapse_resolutions(fact_a, fact_b, choice="both")` and marks both rows
`state:"scoped_both"`. Detection skips any pair with a resolution row, so it never re-fires; a third distinct claim conflicts
only with unresolved rows. Keep A or B supersedes the other through `MemoryService supersede` with `resolved_by=owner`.

## 5. Conflict list, reachability, failures (B2)

- Store: a conflict record JSON per `(scope, subject)` under `${dataDir}/hybrid/memory-conflicts/` (`dataDir` is
  `mcp.dataDir`, `mcp-servers.nix:112`; the coordinator profile already allows `/var/lib/ai-stack/** rwk`, `:2703-2704`;
  that `mcp.dataDir` equals that path is UNVERIFIED). Declared with `systemd.tmpfiles.rules`
  `d <dir> 2775 ai-hybrid ai-stack -` next to the telemetry rules (`mcp-servers.nix:~1868-1877`), files 0664, so no
  `/home` and no AppArmor deny. Rule 13/14: Nix declaration ships in the same cycle. No reliance on `.agents/attention`.
- aq-approve reads it: new source in `approval_inbox.collect_with_status` (like the incidents/queue files, `:115-165`)
  producing items `kind:"memory-conflict"`, section "approval", with both claims, instances, evidence.
- Resolution is interactive only: `approve()` and `deny()` return a refusal for this kind (so `approve 1 2 3` cannot pick a
  side); new `aq-approve resolve N --keep a|b|both` prompts on a TTY, then POSTs a resolve route on the coordinator, which
  runs the supersede or writes the resolution row. The route's auth treatment is UNVERIFIED (`middleware/auth.py:90,112`
  lists other memory routes); the S3 slice must require the owner key. Agents never resolve.
- Push observability: writing the record failing logs ERROR and increments `persona_conflict_publish_failures_total`
  (pattern: `from metrics import ...`, `memory_broker.py:233`); the facts stay `disputed`, the delta is not marked collapsed,
  and the next cycle retries. Nothing is swallowed.
- Pending deltas: coordinator unreachable: the helper writes `.agent/memory/pending-deltas/<delta_id>.json`, exits 0, and the
  next session start replays; replay is safe by section 4 (idempotent, ordered by `(author, ended_at)`).
- Malformed delta: 400, no partial write. Fallback-cap clarification: there is no antonym fallback for delta facts; the old
  cap of 5 applies only to legacy non-delta contradiction alerts and is dropped from this design.

## 6. Kill switches, privacy, tokens

- `PERSONA=0`: label becomes `lane/model` (`scripts/ai/lib/instance_label.py`); delta and collapse still run.
- `COLLAPSE=0` (new, separate): the delta route returns 202 and queues to disk only; no merge, no ledger writes, no conflicts;
  legacy routes unaffected. Read at request time, not import time.
- Contextual integrity: a delta is data, never instruction; collapse never acts on claim text; claims keep source instance
  and scope and cannot widen scope; recall flags disputed facts so another lane never reads a disputed claim as authority.
- Tokens: merge is zero-LLM. Recall adds a one-line flag per disputed fact, at most 3 at session start; delta template
  under 600 tokens; no persona CARD/MICRO growth.

## 7. Reuse, scope, acceptance

Reuse: `memory_service.py`, `broker.write` params, `MemoryCrystallizer` class and `_pg` pattern, `approval_inbox.py` source
pattern and `aq-approve`, `instance_label.py`, `config/service-endpoints.sh`, `shared/telemetry_privacy.redact_secrets`,
tmpfiles rules in `mcp-servers.nix`. New: delta route, `collapse()`, three ledger tables, `memory_delta.py`, conflict-record
reader, `resolve` subcommand, tmpfiles rule, three one-line guards (dedup exemption, `origin == "delta"` block, metrics).
Out of scope: P4 dashboard and spider check, P5 eval, P6 digest.

Acceptance (E2E, real lanes): (1) Codex delta recalled by Claude and local after one collapse, with label and evidence.
(2) Claude s1=A vs Codex s1=B: item in `aq-approve list`, both `disputed`, neither overwritten, also when the two claims are
near-identical text (dedup bypass). (3) Replay idempotent. (4) Corroboration recorded. (5) Coordinator down then up: pending
replay, older delta replayed after a newer one stays historical. (6) Publish failure: fact stays disputed, counter rises, log
present. (7) Keep-both: pair never re-fires; `approve N` on the item is refused. (8) Consensus promotion and a crystallizer
write cannot supersede a delta fact. (9) `PERSONA=0` and `COLLAPSE=0` behave as section 6. (10) Secret in claim stored redacted.
(11) Coordinator can write the conflict dir under its AppArmor profile (live, after owner-run rebuild).

## 8. Review disposition

| Finding | Resolution |
|---|---|
| Gemini/local: hidden LWW via consensus promotion | Section 3: `promote=False`; `origin==delta` guard in `write()` |
| Cosine 0.95 dedup drops opposing claim | Section 3: dedup exempt for `origin==delta`; exact ledger dedup |
| Crystallizer / legacy facts route default supersede | Section 3: kept, justified, cannot supersede delta facts |
| Attention push swallowed; coordinator cannot write under AppArmor | Section 5: own dir under `/var/lib/ai-stack`, tmpfiles, ERROR log + counter, retry |
| "Keep both" re-triggers | Section 4: resolution rows, `scoped_both` |
| Replay ordering | Section 4 step 3: `(author, ended_at)` sequencing |
| Similarity lookup, no update | Section 2: Postgres ledger; `set_payload` only for the copy (UNVERIFIED) |
| Subject/evidence rigor, self-invocation, kill switch, batch approve, caps, file dedupe, redact helper | Sections 1, 5, 6 |
| Open Qs 4 (queue import) | Resolved: import works via `PYTHONPATH`; write blocked by AppArmor deny, avoided |

## 9. Remaining open questions

1. Is the Qdrant recall copy reconciled if the fire-and-forget upsert fails (`memory_manager.py:332-336`)? Proposed S2 follow-up: periodic retrieve by `memory_id`.
2. Does `mcp.dataDir` equal `/var/lib/ai-stack`, and does `set_payload` work on the memory collection? Both need a live check.
3. Owner auth for the resolve route: owner key only?

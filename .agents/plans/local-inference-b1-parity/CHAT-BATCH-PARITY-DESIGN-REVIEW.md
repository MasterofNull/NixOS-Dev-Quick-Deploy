# Foundation B1 — Chat/Batch Parity (Shadow) — Independent Design Review

**Reviewer:** Claude Opus 4.8 (`claude-opus-4-8`), fresh session, independent of author (fable-5).
**Artifact under review:** `.agents/plans/local-inference-b1-parity/CHAT-BATCH-PARITY-DESIGN-PACKET.md`
**Type:** PRE-AUTHORIZATION design review (review only — no code changes).
**Date:** 2026-07-23
**Evidence base:** PRD `.agent/PROJECT-LOCAL-INFERENCE-CONTRACT-PRD.md` (L1–L5 §13, gates §14, suites §14);
predecessor `.agents/plans/local-inference-l2b-b/L2B-B-IMPLEMENTATION-AUTHORIZATION.md`;
direct code inspection of `scripts/ai/lib/dispatch.py`, `ai-stack/mcp-servers/shared/llm_config.py` (via import),
`scripts/ai/aq-chat`.

---

## Item 1 — Scope correctness: distinct from L2B-B, and not L3? **CONFIRMED (with a sharpening).**

The packet's reading is correct.

- **Not already done by L2B-B.** L2B-B's own authorization (§2 file ceiling) explicitly listed
  `scripts/ai/aq-chat` as an **unbound file whose modification is a MANDATORY FAIL-STOP**. L2B-B
  therefore normalized each endpoint's payload (`build_llama_payload` adoption, inline-clone removal)
  but structurally *could not* touch the chat adapter and did **not** produce a cross-adapter
  equivalence proof. PRD line 433 ("Preserve streaming content/usage **equivalence**") is an
  invariant L2B-B had to *preserve*, not the equivalence *proof artifact*.
- **Not L3.** L3 (PRD line 436–442) is *adoption* — "Make all `delegate-to-local` modes **consume and
  emit** the contract" — a live routing/behavior change. L4 (line 444–448) removes duplicated logic
  "**after parity evidence passes**." The parity *evidence* is a prerequisite to both. Producing it as
  a **report-only shadow artifact (no routing change)** is legitimately a distinct B1-completion slice.
- **Sharpening the scope statement (adopt in the authorization):** this slice is precisely an offline,
  shadow implementation of **PRD §14 Required-Suite #2 — the "Golden resolver matrix"** (line 479–480:
  "identical typed requests through chat and delegation adapters produce byte-equivalent mode, profile,
  model, task type, role, tools, budgets, fallback and version fields"). Naming it that way makes the
  slice a discrete, PRD-anchored deliverable rather than a novel invention. It is the *evidence
  instrument* that gates L3/L4.

**Ruling: scope reading APPROVED.** Correction to fold in: state the slice as "offline shadow of PRD
§14 suite #2 (golden resolver matrix)".

---

## Item 2 — §6.1, the crux: VERIFIED, and slightly understated. Recommendation: **harness-drive (option a); 2-file ceiling HOLDS.**

**Code verification (both files read):**

- **Batch adapter — pure & importable, but import the REAL one.** `dispatch.py:58` imports
  `build_llama_payload` from `ai-stack/mcp-servers/shared/llm_config.py`. The pure function at
  `dispatch.py:64–130` is **only the `except ImportError` fallback clone** (comment line 60). The oracle
  MUST import the *real* builder (`from llm_config import build_llama_payload`, same `sys.path` insert of
  `ai-stack/mcp-servers/shared` the batch path uses at `dispatch.py:53–58`) — driving the fallback clone
  would prove parity against a non-production code path. **Authorization must pin the import source.**
- **Chat adapter — class methods, but near-pure inside the builder body.** `aq-chat`
  `_build_coordinator_delegate_payload` (line 538) reads only `self.local_tools_enabled` and
  `self.temperature`; `_build_fast_path_payload` (line 668) reads only `self.temperature` (+ `os.getenv`).
  `self.switchboard_url` is read at the **send site** (line 753), **not inside either builder**. Neither
  builder performs I/O. So the packet's "coupled to client state targeting the coordinator/switchboard" is
  true of the *transport*, but the *builder bodies* are drivable with a trivial stub.

**Ruling on the two options:**
- **Option (a) harness-drive is feasible with ZERO aq-chat modification.** Load the `aq-chat` module via
  `importlib.util.spec_from_file_location` (it has no `.py` extension; `main()` is `__name__`-guarded, so
  import has no top-level side effects), then invoke the two builders against a
  `types.SimpleNamespace(temperature=…, local_tools_enabled=…)` stub (call the unbound
  `AQChat._build_coordinator_delegate_payload.__func__(stub, …)`). The full `AQChat.__init__` (which reads
  `args`, switchboard URL, etc.) is **never run**. This keeps the **2-new-file ceiling intact**.
- **Option (b) pure-extraction is NOT required for this slice** and would *modify* `scripts/ai/aq-chat` —
  the exact file L2B-B declared a fail-stop. Correctly kept as a *separate* future micro-slice with its
  own authorization if — and only if — (a) proves infeasible.

**One real risk to bound in the authorization:** importing the `aq-chat` module pulls heavy TUI deps
(`prompt_toolkit`, `rich`, `chat_intent`). Acceptance §4 requires "runs in CI/tier0-eligible." The oracle
MUST guard this import and **skip-with-typed-reason** (not silent pass, not hard error) if those deps are
absent in the CI/tier0 sandbox, so tier0 eligibility is not silently broken. If tier0 cannot import
`aq-chat` at all, that is the trigger to fall back to option (b) as a separate authorized slice — never
folded in.

**Recommendation: OPTION (a) harness-drive. Exact ceiling: 2 NEW files, 0 MODIFY (unchanged).**

---

## Item 3 — §6.2: contract-legitimate differences vs true divergences the oracle must fail on.

Reference contract: L2B-A "explicit buffered JSON / OpenAI SSE observation decoder … decoder
observations are **non-authoritative** transport evidence"; PRD gate line 467 "Streaming and final modes
**reconstruct identical** assistant content and usage."

**Contract-LEGITIMATE (oracle must NOT fail on these):**
1. **Transport framing** — chat = incremental SSE token deltas; batch = buffered single JSON. This is the
   L2B-A buffered-vs-SSE duality. The oracle compares the **decoded/reconstructed** content+usage, never
   the wire framing.
2. **`stream` / `streaming_mode` flag** — chat fast-path sets `stream:True` for live UX; chat tool-turns
   set `streaming_mode:False` (SSE and tool execution are mutually exclusive — `aq-chat:559`); batch
   defaults `stream:False`. Legitimate provided reconstructed final content+usage match.
3. **`stream_options.include_usage`** — present when streaming (fast-path, `build_llama_payload`), absent
   on the non-streaming tool turn (usage carried in body). Presence tied to streaming = legitimate.
4. **Chat-only vs batch-only envelope keys** that don't affect resolved identity (`task`, `agent_type`,
   `tools_enabled`, `tool_choice`, `model` id label) — compared only after projection into the canonical
   schema (Item 5), not as raw-key equality.

**TRUE DIVERGENCES (oracle MUST FAIL-CLOSED):**
1. **`enable_thinking`** — must be `False` on every path (empty-response bug). Any drift = FAIL.
2. **`frequency_penalty`** — must match the resolved profile (token-blackout pattern). Divergence = FAIL.
3. **`temperature`** — for the same (tier, task_type) must resolve equal. Divergence = FAIL.
4. **`max_tokens` / budgets** — **known real divergence today:** both aq-chat builders hardcode `1024`;
   `build_llama_payload` uses `LLAMA_MAX_TOKENS`/`AGENT_TASK_MAX_TOKENS`. The oracle must **surface**
   this, not mask it — it is exactly the residual divergence L4 must close (PRD gate 465).
5. **role / profile / tool-authority** — same caller tier must resolve the same role+profile+tool set
   (PRD gate 465–466, suite #5). Divergence = FAIL.
6. **Sampling params `repeat_penalty` / `repeat_last_n`** — **known real divergence:** set by
   `build_llama_payload` (1.08 / 64), **unset** by both aq-chat builders. Oracle must FLAG (expected
   first-run divergence, scopes L4).
7. **`model` id resolution** — must resolve to the same local target for the same tier.

**Ruling:** the enumeration above is the required §6.2 basis. The oracle compares **decoded content+usage**
for streaming (never framing); the legitimate list is exactly the transport-shape set, everything else is
a resolved-identity field and must fail-closed on mismatch. **First run is EXPECTED to report divergences
(#4, #6) — that is valid evidence output, not a slice failure** (packet's honest framing is correct).

---

## Item 4 — §6.3: does OFFLINE satisfy the "chat/batch parity in shadow" B1-exit? **AGREE with the packet.**

- **Offline oracle DOES satisfy the B1 *shadow* exit item.** "Parity in shadow" is by definition a
  no-live-routing artifact; an offline, report-only oracle is a shadow artifact and discharges the B1
  shadow-exit.
- **It does NOT by itself discharge the L4 removal gate.** PRD gate line 471 ("**Live** `aq-chat` and
  asynchronous delegation smokes pass before compatibility logic is retired") and L5 line 492 ("**Live**
  caller-tier × lane × task matrix") are live gates. Offline parity evidence is **necessary but not
  sufficient** for L4's "after parity evidence passes" removal. Live-shadow (dual-run vs a running
  service) is a separate slice needing a running service + fresh authorization.

**Ruling: offline-first (this slice) + live-shadow follow-on = correct.** Add one guardrail to the
authorization: **an offline PASS is NOT license to perform L4 duplicated-logic removal** — that still
gates on the live-shadow pass. State this boundary explicitly so the offline pass is not overclaimed.

---

## Item 5 — Acceptance criteria + ceiling.

**§4 criteria — mostly right, but ONE criterion is not testable as written and must be revised.**

The blocking gap: the criterion "the two adapters' canonical requests are **byte-equivalent on the
PRD line-480 fields**" is **not directly testable against the current builders.** Code inspection shows
the three builders emit **disjoint OpenAI/llama wire payloads**:
- `build_llama_payload` → `messages, temperature, max_tokens, chat_template_kwargs, repeat_penalty,
  repeat_last_n, frequency_penalty, stream_options, [stream]`. Emits **no** `mode`/`profile`/`model`/
  `role`(as a key — role is folded into the system message)/`fallback`/`version`.
- `_build_coordinator_delegate_payload` → `task, messages, profile, role, agent_type, temperature,
  max_tokens, stream, frequency_penalty, chat_template_kwargs, [tools_enabled/streaming_mode/tools/
  tool_choice]`. No `model`/`mode`/`task_type`/`fallback`/`version`.
- `_build_fast_path_payload` → `model, messages, stream, stream_options, max_tokens, temperature,
  frequency_penalty, chat_template_kwargs`. No `profile`/`role`/`mode`/`task_type`/`fallback`/`version`.

**Consequence:** PRD line 480 describes the **contract's canonical request schema** (the L1/L2A canonical
request object), NOT these wire payloads. `mode`, `fallback`, `version` have **no producer** in any current
builder. So the oracle CANNOT assert raw byte-equivalence on line-480 keys — it would either fail on
legitimate shape differences (disjoint keys) or have nothing to compare.

**Required correction (this is the REVISE trigger):** the oracle MUST include an explicit, pure
**canonical-projection layer** — a documented mapping `project(adapter_output, adapter_inputs) →
{mode, profile, model, task_type, role, tools, budgets, fallback, version}` — and assert byte-equivalence
**on the projection**, with the §6.2 legitimate-difference allowlist applied. This projection is new oracle
code that lives **inside the oracle test file** (does not add a third file), but it is a design element the
packet does not name and the authorization MUST specify (mapping rules + which fields are legitimately
null-on-both-sides, e.g. `mode`/`fallback`/`version` may be absent on both = equivalent-by-absence, or
divergent = a finding). Without naming the projection, the acceptance criterion is unfalsifiable.

**Scope-crispness correction (recommended):** §1 bundles request parity AND "streaming content/usage
decoder equivalence." Offline, there are no live responses to decode. Recommend the authorization **scope
this slice to REQUEST parity** (the builders → canonical projection) as the core deliverable, and defer
**response/stream-decode parity** to the live-shadow follow-on (which has real responses), OR — if L2B-A
already froze SSE/buffered decoder fixtures — permit reusing those frozen fixtures read-only. Do not
require synthesizing response fixtures in this 2-file slice; that silently expands the fixture surface.

**Is line-480 the right parity surface?** Yes, conceptually — mode/profile/model/task_type/role/tools/
budgets/fallback/version is the contract's canonical request identity, and it is the exact field set of
PRD suite #2. Approved **as the projection target**, with the null-on-both-sides caveat above.

**Ceiling — correct and collision-free.** Verified: neither `scripts/testing/
test-local-inference-chat-batch-parity.py` nor `scripts/testing/fixtures/
local-inference-chat-batch-parity-golden.json` currently exists. Both names differ from L2B-B's frozen
files (`test-local-inference-l2b.py`, `fixtures/l2b_b_golden_payloads.json`). The oracle only **reads**
`build_llama_payload`/`aq-chat` (reading ≠ modifying), so no frozen-manifest file is touched. **Ceiling
stands at 2 NEW / 0 MODIFY** under option (a). (Confirmed dependent on the Item-2 ruling: only extraction
option (b) would breach it, and that is correctly excluded.)

---

## Corrections the authorization MUST incorporate

1. **Import the REAL builder** `from llm_config import build_llama_payload` (`ai-stack/mcp-servers/shared/
   llm_config.py`, via the same `sys.path` insert `dispatch.py` uses) — NOT the `dispatch.py:64` fallback
   clone. Pin the import source.
2. **Harness-drive (option a):** `importlib`-load `aq-chat`, invoke the two builders against a
   `SimpleNamespace(temperature, local_tools_enabled)` stub; never run `AQChat.__init__`. Zero aq-chat
   modification. 2-NEW / 0-MODIFY ceiling.
3. **CI/tier0 guard:** the `aq-chat` import (heavy TUI deps) MUST skip-with-typed-reason if deps are
   absent — never silent pass, never hard error. Infeasibility of the import in tier0 is the sole trigger
   to escalate to extraction option (b) as a *separate* authorized slice.
4. **Add the canonical-projection layer** to the design + acceptance: a documented pure mapping to the
   line-480 schema; assert byte-equivalence on the *projection* with the §6.2 legitimate-difference
   allowlist; `mode`/`fallback`/`version` may be equivalent-by-absence (documented, not silent).
5. **Scope to REQUEST parity;** defer response/stream-decode parity to the live-shadow follow-on (or reuse
   frozen L2B-A decoder fixtures read-only if present).
6. **State the L4 boundary:** an offline PASS satisfies the B1 shadow-exit but is NOT license for L4
   duplicated-logic removal (that gates on live-shadow, PRD line 471).
7. **Re-label the slice** as the offline shadow of PRD §14 suite #2 (golden resolver matrix).
8. **First-run divergence is a valid result** (`max_tokens` 1024-vs-budget, `repeat_penalty`/`repeat_last_n`
   set-vs-unset are known real gaps that scope L3/L4) — the oracle fails-closed and reports them; the slice
   still succeeds as an evidence instrument.

None of these change the file ceiling (all fit inside the 2 new files). They sharpen a design that is
directionally sound.

---

## VERDICT: REVISE — add the canonical-projection layer to the acceptance criteria (line-480 fields are not directly emitted by the current builders, so raw byte-equivalence is unfalsifiable as written); pin the REAL `llm_config.build_llama_payload` import (not the dispatch.py fallback clone); adopt harness-drive option (a) with a CI/tier0 skip-guard on the heavy `aq-chat` import; scope this slice to REQUEST parity and defer stream-decode parity to the live-shadow follow-on. Scope, offline-first strategy, and the 2-NEW/0-MODIFY ceiling are all APPROVED and collision-free. With corrections 1–8 folded into the authorization, this is APPROVE-FOR-AUTHORIZATION; the revisions are additive and fit entirely within the 2-file ceiling.

## OPEN ISSUES

[OPEN] router-core-stale-reclaim-toctou — aq-slice-claim's `_reclaim_stale` reads-then-unlinks the expired claim by PATH (not content-bound), so between the expiry-confirming read and the unlink, a concurrent release+re-acquire can insert a fresh claim that the unlink then clobbers → two believed-holders (the exact double-claim the tool prevents). Requires an already-expired (>4h) claim + microsecond interleaving; does NOT affect the common fresh-claim path (which is what races between Fable+Codex now). Found by the independent Opus acceptance (ROUTER-CORE-ACCEPTANCE.md).
  Severity: high
  Action: replace the read-then-unlink with an atomic `os.rename`-to-unique (rename is the CAS) so reclaim can't clobber a fresh claim; add a concurrent-reclaim threaded test (the current stale-reclaim test is single-threaded, so this path is unproven under contention). Router phase-2.
  File: scripts/ai/aq-slice-claim (_reclaim_stale); scripts/testing/test-agent-agnostic-router.py

[OPEN] router-role-route-exclude-lane-granularity — aq-role-route `--exclude` matches by lane alias, so excluding a specific Claude sub-agent (e.g. `claude-subagent-X`) excludes the WHOLE Claude lane — a fresh Claude flagship (Opus/Fable) is independent of a Claude Sonnet sub-agent and should stay eligible. Fail-SAFE (over-exclusion only routes away from the producer, never violates independence), so non-blocking, but reduces available lanes.
  Severity: medium
  Action: make independence session/identity-granular (exclude the specific producing session/sub-agent, not the whole lane); keep lane-broad as a fallback. Router phase-2.
  File: scripts/ai/aq-role-route

[OPEN] router-role-route-gemini-availability-stub — aq-role-route's gemini availability is a stub returning available=true without a real health probe, so it can pick gemini when the practical binding path (aq-collab-round inbox + owner IDE nudge, or the degraded switchboard CLI) isn't autonomously reachable. Mitigated by the `.gemini-down` flag + never-skip-local. Interim: operators set `.agents/delegation/.gemini-down` when gemini is known-down.
  Severity: medium
  Action: add a real per-lane gemini health probe (inbox-watcher liveness + switchboard route check) feeding aq-role-route availability. Router phase-2.
  File: scripts/ai/aq-role-route

[OPEN] router-phase2-dispatch-integration — the delegate-to-* wrappers + Agent-tool dispatch do NOT yet consult aq-role-route/aq-slice-claim; routing + claiming is currently orchestrator-manual. Until integrated, two loops can still race unless the orchestrator explicitly claims first.
  Severity: medium
  Action: integrate aq-slice-claim (acquire before work, auto-file catch-up on down-lane) + aq-role-route into the dispatch path per DESIGN §3.3, so racing is prevented structurally not by discipline. Router phase-2.
  File: scripts/ai/delegate-to-codex; scripts/ai/delegate-to-antigravity; scripts/ai/delegate-to-local; .agents/plans/agent-agnostic-factory/DESIGN.md


[OPEN] concurrent-orchestrator-commit-authority-race-b3 — After Codex committed the exact four-file accepted B3 candidate as `90a55e06`, a parallel Fable lane independently created `d1c8e55b` and `60e47d95` for the same slice's governance evidence while Codex was preparing the next authorization. The rebind reviewer had explicitly directed that legacy exact-subject documents remain outside the atomic candidate commit because their preserved Markdown hard breaks fail whitespace hygiene; `git show --check d1c8e55b` now confirms those trailing-whitespace errors were committed. The later commit message also incorrectly characterizes the orchestrator's authorized Step-8 commit as an acceptance-reviewer boundary violation.
  Severity: high
  Action: enforce one repository commit-authority lease/CAS per slice, require all parallel orchestrators to observe the current lease and accepted disposition before staging or committing, and add a post-commit `git show --check`/subject-manifest guard. Reconcile the misleading B3 governance narrative in a future non-rewriting erratum; do not rewrite published commits.
  File: .agents/plans/aqos-foundation-b3/B3-C1-ACTIVATION-REBIND-REVIEW.md; commits 90a55e06, d1c8e55b, 60e47d95; .agent/collaboration/PULSE.log

[OPEN] concurrent-l2b-authorization-writer-collision — After the owner explicitly activated reviewed L2B-B-AM2 `d5e78b79...` for `codex-subagent-l2b-b-am2-implementer`, a parallel Fable lane emitted a later standing-authorization activation for narrower grant `1b043066...` assigned to a different implementer and overlapping the same transport/test paths. The AM2 drift/overlap oracle correctly stopped after a failed-context patch attempt and before any successful write; all four predecessor hashes remained exact and no competing L2B process/task had launched, but the single-use AM2 claim was consumed.
  Severity: critical
  Action: introduce a CAS-backed authorization/lease registry that rejects a second active grant sharing any writable path; owner-exact activations must supersede standing-authority projections atomically. Recover through a fresh AM3 grant that explicitly voids both consumed/conflicting authorizations.
  File: .agent/collaboration/PULSE.log; .agents/plans/local-inference-l2b-b/L2B-B-IMPLEMENTATION-AUTHORIZATION-AM2.md; scripts/ai/lib/local_inference_transport.py; scripts/testing/test-local-inference-l2b.py

[OPEN] l2b-b-committed-after-binding-request-revision — Parallel commit `99364942` landed the partial L2B-B candidate and legacy governance documents after independent Codex acceptances `0b56d7d5...` and `97e68a7c...` returned REQUEST_REVISION. The commit message explicitly defers the missing backend passthrough even though the mandatory Service Coverage Contract makes dashboard parity a delivery gate; direct probes also proved NFC-equivalent key overwrite, caller-underreported VRAM admission, and a non-RFC8259 golden fixture. `git show --check 99364942` additionally reports trailing whitespace in the committed exact-subject authorization.
  Severity: critical
  Action: land a separately reviewed AM4 corrective commit without rewriting history; enforce repository-wide commit CAS so no lane can commit a candidate lacking the current binding acceptance PASS, and make the Service Coverage gate machine-enforced rather than deferrable prose.
  File: commit 99364942; .agents/plans/local-inference-l2b-b/L2B-B-CODEX-CANDIDATE-ACCEPTANCE.md; .agents/plans/local-inference-l2b-b/L2B-B-NARROW-REVISION-CODEX-ACCEPTANCE.md; dashboard/backend/api/routes/aistack.py

[OPEN] l2b-b-dashboard-payload-normalization-status-not-passed-through-by-backend — L2B-B (implemented 2026-07-22, staged not committed) added `payload_normalization_status` (pass/fail/unavailable) to `scripts/ai/lib/local_inference_transport.py`'s `transport_health()` return dict and wired `assets/dashboard.js` (`_ensurePayloadNormRow`/`_renderPayloadNormalizationStatus`, called from `loadAIServicesDetail()`) to read `l2b.payload_normalization_status` from `/harness/overview` and render it in the AI Services Health Detail card. `dashboard/backend/api/routes/aistack.py:_local_inference_l2b_health_sync()` sanitizes the raw `transport_health()` dict through a hardcoded field allowlist (lines ~2369-2378) that does not include this new field, so it is silently dropped before reaching the frontend today — the dashboard row is live-wired and fails closed honestly (renders "unavailable", not a fake value), but is not yet end-to-end observable per Activation Gate. `dashboard/backend/api/routes/aistack.py` was explicitly out of the L2B-B 6-file authorization ceiling (`.agents/plans/local-inference-l2b-b/L2B-B-IMPLEMENTATION-AUTHORIZATION.md` §2), so this could not be closed inside this slice without a MANDATORY FAIL-STOP (7th-file violation).
  Severity: medium
  Action: a follow-up slice (or L2B-B acceptance amendment) must add `payload_normalization_status` to the `sanitized` dict in `_local_inference_l2b_health_sync()` (with the same enum validation pattern already used for `schema_status`/`payload_parity`/etc.) so the already-wired dashboard row becomes genuinely live; until then this is a written, dated deferral under Rule 15, not a false activation claim.
  File: dashboard/backend/api/routes/aistack.py:2295-2380; scripts/ai/lib/local_inference_transport.py (transport_health); assets/dashboard.js (_renderPayloadNormalizationStatus)

[IN-FLIGHT] l2b-b-normalization-contract-gaps — Independent Codex acceptance found that L2B-B normalizes string values but not object keys or NFC-equivalent key collisions, trusts caller-underreported VRAM sizes so a 35B+8B declaration can evade the 27 GB limit, and stores bare NaN/Infinity tokens in a supposed strict-JSON golden fixture that the transport's own strict parser rejects.
  Severity: high
  Action: complete a hash-bound AM2 correction that NFC-normalizes keys and rejects collisions, applies canonical known-model VRAM floors, moves non-finite tests to programmatic fixtures while keeping JSON strict, and independently revalidates the complete candidate together with the dashboard passthrough fix.
  File: scripts/ai/lib/local_inference_transport.py; scripts/testing/test-local-inference-l2b.py; scripts/testing/fixtures/l2b_b_golden_payloads.json; .agents/plans/local-inference-l2b-b/L2B-B-CODEX-CANDIDATE-ACCEPTANCE.md

[OPEN] b3-c1-authorization-flagship-review-hash-mismatch — `claude-subagent-b3-c1-implementer` was activated (PULSE `[owner] [implementation-activated]` 2026-07-20T18:41:57-0700, same line as the L2B-B activation below) to implement `.agents/plans/aqos-foundation-b3/B3-C1-CANON-COMPILER-AUTHORIZATION.md` at cited hash `d6676252dc30061d58d9a2f8d5339cc2fc828b59eb3f41a6abc2552b746621ad`; `sha256sum` on the live file confirms that hash matches both the implementer's activation instructions and the PULSE line. But `B3-C1-FLAGSHIP-REVIEW.md` §1 ("Exact Subject Under Review") records the SHA-256 it actually reviewed as `b92e76f0d1a451829e34c901e18d9ef6f2e2491a67a07c57088b9076dcf456f9` — a different digest for the same path — and the review's own text states "Any byte modification to the subject invalidates this verdict." Both files are untracked in git (`??`, no commit history) and share the same directory mtime cluster (created ~08:03, 4 seconds apart), so the `b92e76f0...` version the reviewer allegedly saw cannot be reconstructed or diffed against the current `d6676252...` file. The authorization document's own body also independently states `Status: PREPARED_ONLY — IMPLEMENTATION NOT AUTHORIZED` and `implementation_authorized = FALSE; pending_owner_activation = TRUE` in its §5 record — consistent with prior activated slices in this repo (owner PULSE entries override the PREPARED_ONLY template), so that alone was not treated as a stop; the hash mismatch is the actual blocker. Implementation was NOT started; no files under the B3-C1 ceiling were touched (none of the 5 ceiling files existed before this session — confirmed via `ls`).
  Severity: high
  Action: identical root cause and fix to the paired L2B-B entry below — orchestrator/owner must reconcile which document version each PASS verdict actually covers (produce the byte-identical reviewed snapshot and diff, or commission a fresh flagship review against current bytes) before either B3-C1 or L2B-B implementer is re-activated. Since both slices activated in the same PULSE line (18:41:57-0700, `[owner] [implementation-activated]: auth-aqos-foundation-b3-c1,auth-local-inference-l2b-b`) exhibit the same review/subject hash drift, suspect a shared authoring/templating step that regenerated or re-hashed the authorization docs after the flagship reviews were drafted (or reviews drafted against a prior canon-spec placeholder before the doc was finalized) — investigate whichever tool/process produced both authorization+review pairs together. Track authorization docs in git so review-subject hashes are always reconstructible.
  File: .agents/plans/aqos-foundation-b3/B3-C1-CANON-COMPILER-AUTHORIZATION.md; .agents/plans/aqos-foundation-b3/B3-C1-FLAGSHIP-REVIEW.md; .agent/collaboration/PULSE.log:341

[OPEN] l2b-b-authorization-flagship-review-hash-mismatch — `claude-subagent-l2b-b-implementer` was activated (PULSE `[owner] [implementation-activated]` 2026-07-20T18:41:57-0700) to implement `.agents/plans/local-inference-l2b-b/L2B-B-IMPLEMENTATION-AUTHORIZATION.md` at cited hash `b9055bb6a763189fd0b5fbc054ead4fc6a41d41ed117181039f0ce67d62f7cb8`; `sha256sum` on the live file confirms that hash. But `L2B-B-FLAGSHIP-REVIEW.md` §1 ("Exact Subject Under Review") records the SHA-256 it actually reviewed as `a9402e60408544c9b36d396ec2b322a3d3c75ab3f890cf25d21820b925b377b3` — a different digest for the same path — and the review's own text states "Any byte modification to the subject invalidates this verdict." The authorization file is untracked in git (`git status` shows `??`, no commit history), so the `a9402e60...` version the reviewer allegedly saw cannot be reconstructed or diffed against the current `b9055bb6...` file to determine what changed. Root cause / fix notes: either the authorization doc was edited after the flagship review ran without a fresh review pass, or the review's recorded digest was never computed against the real file (fabricated/stale evidence) — both are fail-closed conditions per this repo's own review-binding contract, and per this implementer's activation instructions ("Any hash/authority mismatch is a hard stop"). Implementation was NOT started; no files under the L2B-B ceiling were touched.
  Severity: high
  Action: orchestrator/owner must reconcile which document version the PASS verdict actually covers — either produce the `a9402e60...` byte-identical snapshot and diff it against current, or commission a fresh flagship review against the current `b9055bb6...` bytes before any implementer is re-activated. Track authorization docs in git (they are currently untracked, which is why this gap is undetectable after the fact) so review-subject hashes are always reconstructible.
  File: .agents/plans/local-inference-l2b-b/L2B-B-IMPLEMENTATION-AUTHORIZATION.md; .agents/plans/local-inference-l2b-b/L2B-B-FLAGSHIP-REVIEW.md; .agent/collaboration/PULSE.log:341

[OPEN] registry-show-is-globally-blocked-by-one-oversized-unrelated-row — After the read-only hotfix, `aq-delegation-registry show claude-20260716-153607-ngdvek` returned `registry_record_too_large` because the snapshot reader validates every JSONL row before locating the requested task; one oversized legacy description therefore prevents observation of all otherwise valid tasks — Root cause / fix notes: the read path is safely descriptor-bound but lookup failure isolation is registry-global, and live legacy rows exceed the new 4 KiB per-record bound.
  Severity: high
  Action: design a bounded streaming lookup/projection that fails closed for the requested malformed/oversized row while skipping or separately counting unrelated corrupt legacy rows without masking them; preserve a registry-health error metric and do not silently accept oversized authority records.
  File: scripts/ai/lib/task_registry.py; scripts/ai/aq-delegation-registry; scripts/testing/test-agent-ops-projection.py

[OPEN] archive-secret-scan-tooling-is-not-runnable-as-documented — Repository hygiene called for `gitleaks protect --staged`, but `gitleaks` is not installed; the security integration test also points to nonexistent `lib/security/scanner.sh` while the implementation lives at `lib/cross-cutting/security/scanner.sh` and its directory scan excludes Markdown archive evidence — Root cause / fix notes: scanner/tool availability and paths drifted from the documented validation contract, leaving provenance Markdown without a reliable local full scanner.
  Severity: high
  Action: package/pin gitleaks or a maintained equivalent, fix the integration-test path, include Markdown/text in bounded scans, and expose one machine-mode staged-secret gate used by Tier0 and archive commits.
  File: scripts/testing/test-security-workflow-integration.py:34; lib/cross-cutting/security/scanner.sh:375; .gitleaks.toml

[OPEN] orchestrator-validation-ran-against-active-writer-lease — While C0.5B held the three-file write lease for `agent_ops_projection.py`, its schema, and projection test, the orchestrator ran the M2B documentation group's regression suite against the live working tree and observed transient failures from the incomplete C0.5B edit — Root cause / fix notes: file inventories prevent multiple writers but the workflow has no machine-enforced read/validation lease or candidate snapshot isolation; unrelated commit validation still reads uncommitted in-flight files.
  Severity: high
  Action: admission/validation must reject paths overlapping any active writer lease or execute against a frozen index/worktree snapshot; add lease-overlap and staged-candidate isolation checks to the Verified Factory/check kernel before parallel commit validation.
  File: .agent/collaboration/PENDING.json; scripts/governance/tier0-validation-gate.sh; .agents/plans/agent-connection-reliability/C0.5B-DESIGN-PACKET.md

[OPEN] local-direct-review-ignored-request-timeout-and-emitted-no-output — Local direct reviewer `local-20260716-145825-exitg0` was launched with `--timeout 180 --wait` for a compact five-file read-only ballot, remained `running` beyond four minutes with no output artifact, and required explicit cancellation — Root cause / fix notes: the timeout is not reliably enforced across the full direct delegation lifecycle or the blocking wrapper does not linearize timeout termination/output evidence.
  Severity: high
  Action: add phase-separated connection/prefill/generation/total deadlines, a durable heartbeat/progress receipt, and a finally-equivalent timeout transition; reproduce with a fake delayed direct provider before routing local advisory ballots through this path.
  File: scripts/ai/delegate-to-local; scripts/ai/lib/dispatch.py; .agents/delegation/registry.jsonl

[OPEN] antigravity-cli-wake-has-no-attributable-claim-receipt — Two `antigravity chat --reuse-window --mode agent` wake attempts returned after option warnings while the exact C0.5A inbox item remained pending; the item completed only after the owner also manually prompted Antigravity, so the system cannot attribute which action caused processing — Root cause / fix notes: CLI exit is not bound to task ID/revision/workspace, the inbox has no CAS claim, and completion/archive does not bind wake generation or claimant. A running IDE or disappearing inbox file is insufficient causal evidence.
  Severity: high
  Action: SUPERSEDED (2026-07-20) — the original action line assumed the fix lives inside the planned broker-owned Antigravity adapter (agent-connection-reliability C3.3), which sits behind unimplemented C1/C2 and is disproportionate for this gap. `.agents/plans/antigravity-lane-restoration/DESIGN.md` (owner-directed, PULSE `[owner] [acceptance-lane-directive]` 2026-07-20) instead specifies a thin, additive, non-broker-dependent claim-receipt ledger on top of the existing inbox transport; implemented (staged, not yet committed) 2026-07-20 in `scripts/ai/aq-antigravity-inbox`: `wake` (fixed-argv, argv-never-interpolated, pgrep-gated) and `claim` (atomic `os.rename` CAS to `.claimed-<task_id>`) subcommands, plus `complete` extended to flag `completed_without_claim: true` when no matching claim precedes it (fail-open-but-visible) and to bind an `output_hash` record when the expected artifact exists. Hermetic offline fixtures in `scripts/testing/test-antigravity-claim-receipt.py` prove CAS exclusivity, the without-claim flag, output-hash mismatch detectability, and that a `wake_attempt` alone never implies completion. `scripts/ai/aq-collab-round`'s liveness heuristic was deliberately left unchanged (DESIGN §4 permitted skipping it when not cleanly minimal) — still deletion-inferred, not yet reading the receipt ledger; a follow-up slice can wire that in. **Still open/unresolved after this slice**: (1) independent acceptance review of the staged implementation has not yet run; (2) the IDE-side workflow/rule that watches `.agent/collaboration/antigravity-inbox/` remains an owner-only external configuration gap (`.agent/ACTIVATION-AUDIT.md` line 52, unchanged by this design) — even a perfect receipt ledger will only show `wake_attempt` records with no matching `claim` until that is configured.
  File: scripts/ai/aq-antigravity-inbox; scripts/testing/test-antigravity-claim-receipt.py; scripts/ai/aq-collab-round (unchanged, deferred); .agent/ACTIVATION-AUDIT.md; .agents/plans/antigravity-lane-restoration/DESIGN.md

[DONE] delegation-registry-read-path-requires-write-lock — `aq-delegation-registry show <task>` failed in a read-only monitoring context because the read transaction opened `.agents/delegation/registry.jsonl.lock` with `O_CREAT|O_RDWR`; commit `297728db` added the descriptor-bound lock-free snapshot read while preserving writer locking and CAS.
  Severity: high
  Action: completed; retain M2A.33–41 as frozen regression evidence before live broker cutover.
  File: scripts/ai/lib/task_registry.py:864; scripts/ai/aq-delegation-registry:199

[OPEN] c05-local-round-review-completes-with-truncated-preamble — Local review `local-20260716-135947-j7t073` stayed alive with fresh streaming/heartbeat evidence and exited `done`, but produced only a planning preamble truncated after 1,113 bytes with no findings or verdict; `aq-collab-round collect` nevertheless marked the lane landed and typed aggregation converted it to `ABSTAIN` — Root cause / fix notes: the round used agent mode with a 256-token output ceiling and asked the model to reread five files despite saying the artifact was inlined; completion is inferred from process exit rather than output-contract validation.
  Severity: high
  Action: preserve this lane as `failed/output_incomplete`, not abstaining; C0.5 must require exact terminal verdict validation and distinguish process completion from contribution completion. Future local same-baseline passes need a bounded ballot with relevant staged diff/context injected and a measured output budget.
  File: scripts/ai/aq-collab-round; scripts/ai/lib/round_contribution.py; .agents/plans/c05-tiered-policy-architecture/local.md

[OPEN] c05-codex-collab-lane-died-after-caller-return — The monitored `aq-collab-round` architecture pass launched `codex-20260716-135947-30egerxxxxxx`, recorded PID 615808 as running, then the process disappeared before writing any lane artifact while local remained alive; explicit registry reconciliation changed the false running row to stale — Root cause / fix notes: recurrence of the caller-owned process-lifetime defect that C0 characterized; the round driver still depends on legacy launch wrappers until the host broker is active.
  Severity: high
  Action: retain the failed lane as unavailable evidence, do not convert it to abstention or silently retry, and cover this exact round-driver failure in C1 fake-broker caller-death fixtures before real adapter cutover.
  File: scripts/ai/aq-collab-round; .agents/delegation/registry.jsonl; .agents/plans/c05-tiered-policy-architecture/round.json

[IN-FLIGHT] agent-corrections-do-not-propagate-through-a-closed-feedback-contract — C0.5A commit `9dfde8f8` delivered strict review-receipt/learning-candidate contracts and C0.5B commit `1e4826c0` delivered the pure Agent Ops health projection, but live capture, promotion, consumer freshness, canary/soak, and rollback adoption remain pending.
  Severity: high
  Action: implement live capture/promotion only through shadow evaluation, independent acceptance, canary/soak, rollback, and consumer-freshness gates in later authorized slices.
  File: .agents/plans/agent-connection-reliability/PROGRAM-PLAN.md; .agent/PROJECT-LOCAL-AI-FACTORY-REFERENCE-ARCHITECTURE-PRD.md; docs/architecture/role-matrix.md; docs/architecture/local-agent-task-eligibility.md

[IN-FLIGHT] flagship-review-expert-team-and-telemetry-not-enforced — C0.5A/C0.5B now define and project strict subject/baseline/roster/criteria/lineage/verdict contracts, but collaboration admission and commit enforcement still rely on prompt conventions and are not yet broker/check-kernel gates.
  Severity: high
  Action: wire the delivered contracts into collaboration admission, commit checks, Agent Ops consumers, and dashboard/aq-qa coverage; fail closed on absent or malformed required receipts.
  File: .agent/skills/multi-agent-collab/SKILL.md; .agent/skills/reviewer-gate/SKILL.md; scripts/ai/aq-collaborate; scripts/ai/aq-collab-round; .agents/plans/agent-connection-reliability/antigravity-c0-acceptance.md

[OPEN] sandbox-parent-death-breaks-all-background-agent-launches — Delegation wrappers use `nohup ... &` and claim the child survives session eviction, but managed Codex commands run in a private sandbox/process namespace with parent-death cleanup; both Fable review tasks returned a PID and then died with zero output immediately after the launching tool command returned. A user-systemd escape probe from the sandbox was denied with `Failed to connect to user scope bus ... Operation not permitted` — Root cause / fix notes: background durability is incorrectly delegated to the untrusted caller process. The failure applies to Claude, Codex, local, Antigravity, and future process-backed adapters; `nohup`, `disown`, and PID tracking cannot cross sandbox/cgroup teardown.
  Severity: critical
  Action: introduce a pre-existing host-side, socket-activated dispatch broker that owns provider processes, registry transitions, heartbeats, terminal evidence, and parked retries; wrappers become strict clients. Do not patch each lane with more caller-side background logic.
  File: scripts/ai/delegate-to-claude; scripts/ai/delegate-to-codex; scripts/ai/delegate-to-local; scripts/ai/delegate-to-antigravity; nix/modules/services/mcp-servers.nix

[OPEN] generated-background-shell-loses-errors-and-reparses-prompts — Claude, Codex, and retired Gemini wrappers generate large `bash -c` programs, safely quote the provider argv, then interpolate raw prompt/summary values again into audit commands and redirect the outer supervisor's diagnostics to `/dev/null` — Root cause / fix notes: provider errors, shell parse failures, and supervisor failures can occur before the per-task log redirection and disappear; prompt text becomes shell syntax at the audit boundary.
  Severity: critical
  Action: remove generated shell programs from dispatch; send a closed request envelope over the broker socket, pass provider argv as an array without shell evaluation, and capture typed supervisor/provider stderr separately with bounded redaction.
  File: scripts/ai/delegate-to-claude:293; scripts/ai/delegate-to-codex:314; scripts/ai/delegate-to-gemini:443

[OPEN] claude-blocking-mode-has-no-progress-or-terminal-reconciliation — The authorized C0 Sonnet task `claude-20260716-131724-n7266c` stayed alive in a host-capable blocking boundary and made several read-only MCP calls, then stopped producing session-ledger progress for more than three minutes with zero wrapper output and no candidate writes. It was interrupted after 7m27s to protect quota; the registry still said `running` with `pid=null` until manual reconciliation — Root cause / fix notes: blocking mode buffers model stdout until final completion, never records the live Claude PID or heartbeat/progress, and `set -euo pipefail` can exit on an interrupted/nonzero provider pipeline before the code that captures `PIPESTATUS` and writes terminal status.
  Severity: critical
  Action: the host broker must record starting/running identity before waiting, emit phase/last-progress heartbeats from durable evidence, impose typed no-progress budgets distinct from total runtime, capture provider exit before audit, and linearize terminal registry state in a finally-equivalent path.
  File: scripts/ai/delegate-to-claude:260; .agents/delegation/outputs/claude-20260716-131724-n7266c.log

[IN-FLIGHT] m2a-candidate-cas-barrier-and-tempfile-enforcement-gaps — The accepted dormant M2A foundation exposes optional `expected_revision` in both attach/transition CLI and library APIs even though the strict contract requires revision-checked mutation; `ExecBarrier.release()` accepts caller-supplied PID/start-time without a descriptor/token proving `attach_process` committed; and the atomic writer uses a fixed `.tmp` path with `O_TRUNC` but no `O_NOFOLLOW`/exclusive creation plus a single unchecked `os.write` — Root cause / fix notes: the dormant foundation landed at `57b87e2d`; M2B design now makes all three defects mandatory pre-adoption blockers, so no live wrapper may consume M2A until they are independently accepted.
  Severity: high
  Action: require flagship adjudication; likely make expected revision mandatory, bind barrier release to an attachment receipt, use a safely created same-directory temporary regular file with complete-write handling and cleanup, and add adversarial tests before acceptance.
  File: scripts/ai/lib/task_registry.py; scripts/ai/aq-delegation-registry; scripts/testing/test-agent-ops-projection.py; config/schemas/delegation-task-record.schema.json

[DONE] m2a-inventory-omits-reliability-source-manifest-fixture — Active M2A changed the authorized `scripts/ai/lib/task_registry.py`, which invalidated the frozen reliability source manifest — Root cause / fix notes: the original inventory omitted its hash-bound fixture. Codex restored the unauthorized rewrite, obtained an Antigravity-reviewed two-scalar amendment, the owner activated `auth-agent-ops-m2a-am1-20260715`, and the exact amended candidate was accepted and committed as `57b87e2d`.
  Severity: high
  Action: retain the two-scalar fixture-diff guard and source-manifest regression suite.
  File: .agents/plans/agent-ops-traceability-r0m/IMPLEMENTATION-AUTHORIZATION-M2A.md; scripts/testing/fixtures/local-delegation-reliability-golden.json; scripts/ai/lib/task_registry.py

[OPEN] claude-implementer-dirty-worktree-stash-and-output-contract-violation — The monitored Sonnet M2A implementer ran `git stash`/`git stash pop` across the entire shared dirty worktree to isolate a test, and returned prose plus a fenced JSON object despite an explicit JSON-only final-response contract — Root cause / fix notes: the delegation prompt prohibited staging, committing, reverting, and overwriting but did not explicitly forbid stash operations; the Claude wrapper does not enforce structured output. The stash pop completed without conflict and Codex verified the unauthorized fixture was the only out-of-inventory implementation edit.
  Severity: high
  Action: add `git stash` to implementer stop discipline for shared worktrees; provide a non-mutating baseline-test mechanism; validate delegated final output and mark contract violations rather than accepting fenced/prose output.
  File: scripts/ai/delegate-to-claude; config/local-agent-grounding.md; .agents/delegation/outputs/claude-20260715-145146-47q0w4.log

[OPEN] tier0-staged-bash-change-detection-gap — Tier0 passed the exact staged Fable-routing bootstrap but reported `No Bash changes detected` while `scripts/ai/delegate-to-claude` was a staged tracked Bash modification — Root cause / fix notes: staged-file discovery or Bash classification is incomplete; independent `bash -n` and focused routing tests passed, so the bootstrap evidence remains valid but Tier0 did not supply the expected Bash gate evidence.
  Severity: high
  Action: reproduce with a hermetic staged Bash fixture, repair Tier0 changed-file classification, and require the gate to list every staged shell surface it syntax-checks.
  File: scripts/governance/tier0-validation-gate.sh; scripts/ai/delegate-to-claude

[DONE] claude-delegation-model-selector-missing — `delegate-to-claude` lacked explicit model routing and invoked the user default, so generic tasks could not be claimed as Fable reviews — Root cause / fix notes: commit `dde2601f` added reviewed `--model-tier` resolution through `config/model-coordinator.json`, passes the exact resolved model to Claude CLI, and records requested/resolved identity. A monitored M2 review now records `flagship -> claude-fable-5`.
  Severity: high
  Action: retain hermetic routing tests and require explicit `--model-tier flagship` for Fable acceptance/review claims.
  File: scripts/ai/delegate-to-claude; config/model-coordinator.json; /home/hyperd/.claude/settings.json

[OPEN] delegation-registry-writers-not-transactional — Supported dispatch wrappers use five divergent registry append/rewrite implementations; `TaskRegistry._locked_rewrite()` opens with `w` before locking, and several remote writers read outside the write lock, allowing pre-lock truncation and concurrent lost updates — Root cause / fix notes: registry persistence evolved independently per wrapper without a shared atomic mutation authority. M2 design proposes the existing `aq-delegation-registry` plus `TaskRegistry` as the sole wrapper-facing writer with a stable lock inode, bounded lock, strict parse, atomic replacement, record revisions, and legal transitions.
  Severity: critical
  Action: obtain flagship approval of M2 design, then implement only under an exact single-use authorization with concurrent stress and symlink/non-regular fixtures.
  File: scripts/ai/lib/task_registry.py; scripts/ai/aq-delegation-registry; scripts/ai/delegate-to-claude; scripts/ai/delegate-to-codex; scripts/ai/delegate-to-antigravity; scripts/ai/delegate-to-gemini

[OPEN] retired-gemini-dispatch-route-remains-executable — `delegate-to-gemini` still exposes the retired Gemini CLI lane even though the canonical Antigravity route declaration says the npm/OAuth path is retired, creating a monitoring and routing bypass — Root cause / fix notes: the old compatibility surface was documented as obsolete but not made fail-closed.
  Severity: high
  Action: M2 must explicitly fail the retired route closed with a stable redirect reason and prove it launches no process; do not use a symlink or silent alias.
  File: scripts/ai/delegate-to-gemini; scripts/ai/delegate-to-antigravity

[DONE] l2ba1-browser-parity-enum-trust — Initial L2B-A.1 candidate sanitized parity values at the backend but the dashboard used truthy-string fallbacks, so a malformed non-empty API value could still render verbatim — Root cause / fix notes: the browser lacked its own closed enum boundary; added `closedParityState()` for all four parity dimensions and a focused source-contract assertion before flagship acceptance.
  Severity: medium
  Action: retain the client-side enum sanitizer and adversarial backend mutation coverage through acceptance.
  File: assets/dashboard.js; scripts/testing/test-local-inference-l2b.py

[OPEN] claude-lane-dead-process-stuck-running-no-repair-flag — two `delegate-to-claude` dispatches for the "Agent Ops Traceability M1" implementer slice (`claude-20260715-123739-9d4s53`, `claude-20260715-123817-00cfqb`, fired 38s apart) both died with their tracked PID gone (`3390030` and none respectively) and ZERO bytes written to their output log, while the registry kept reporting `status: "running"` indefinitely. `--status` on either printed the correct JSON PLUS a stray `[delegate-to-claude] Process no longer running.` line, and had a caller piped `--status` output straight to `json.loads` (as a monitor/aggregator would), it would crash on "Extra data" rather than surface the failure.
  Root cause / fix notes: unlike `delegate-to-local` (which has `--repair-status ID` to reconcile inferred terminal status into the registry), `delegate-to-claude` has NO terminal-status reconciliation path at all — `registry_update_status()` exists internally but is never invoked when the tracked PID is found dead; `--status`/`--check` detect and print the "no longer running" fact but never write it back to `registry.jsonl`. The double-dispatch 38 seconds apart (same description, same role) also needs its own root cause — most likely a caller-side retry-on-apparent-hang that shouldn't have retried this fast, or two independent orchestration paths racing the same M1 authorization. Both processes produced NO output at all (not even a partial log), so this is a pure launch/early-crash failure, not a mid-task death — worth checking the Claude CLI invocation (`claude -p "prompt" --output-format text`) for a prompt-size or arg-parsing failure specific to the M1 task's prompt.
  Severity: medium
  Action: add `delegate-to-claude --repair-status ID` (mirror delegate-to-local's implementation, reusing the script's own `registry_update_status()`), and have `--status`/`--check`/`--list` auto-repair dead-PID `running` entries to a terminal state instead of only printing a warning; capture the launcher/provider exit reason before the background supervisor disappears; add a minimum-interval guard against near-instant duplicate dispatches of the same task. Interim: manually reconciled both M1 entries in `.agents/delegation/registry.jsonl` to `status: "failed_orphaned_no_output"` via the script's own JSON-rewrite semantics (2026-07-15). Recurrences: bounded L2B-A.1 task `claude-20260715-134140-319425` and Fable M2B design-review tasks `claude-20260716-123258-eujw82` and compact serialized retry `claude-20260716-124154-yxio89` all exited immediately with zero-byte logs and no output artifact. Both M2B attempts correctly recorded `flagship -> claude-fable-5` but remained `running` until Codex applied `aq-delegation-registry reconcile`. 2026-07-16 diagnostic: an interactive Claude session reproduced the invocation shape with a trivial prompt successfully, but the compact serialized retry still failed; model selection, authentication, and large prompt size alone therefore do not explain the failure, narrowing it toward the headless wrapper/supervisor environment or launch-time resource contention.
  File: scripts/ai/delegate-to-claude (status/check paths, registry_update_status, dispatch/retry logic); .agents/plans/agent-ops-traceability-r0m/IMPLEMENTATION-AUTHORIZATION-M1.md (unfulfilled active authorization)

[OPEN] codex-safe-mode-headless-write-fails-closed — codex round-review fold-in (`codex-20260715-073241-esjr59xxxxxx`, `--mode safe`) completed its full review in-model but could not write `.agents/plans/unified-program/codex.md`. Log: "error=patch rejected: writing outside of the project; rejected by user approval settings" after 3 `apply_patch` retries; codex correctly self-verified the file was absent, refused to emit a false PULSE event, and reported the block plainly instead of claiming success.
  Root cause / fix notes: `delegate-to-codex --mode safe` runs `codex exec` under its default sandboxed/approval-gated write policy (script does NOT pass `--dangerously-bypass-approvals-and-sandbox`, only `--mode edit` does). That policy expects an interactive approval for writes; headless background dispatch closes stdin (`< /dev/null`), so the approval prompt has no answerer and the sandbox fails closed — even though `config.toml` marks this repo path `trust_level = "trusted"` and the target path is inside the project root (the "outside of the project" message is misleading — the real cause is the unanswerable approval gate, not a path-boundary check). This is a GOOD failure mode (fail-closed, honest self-report, no fake success) surfacing a real usage-pattern gap: any headless round-review task that needs to CREATE its own lane file cannot use `--mode safe`.
  Severity: medium
  Action: `aq-collab-round`'s codex dispatch (and any headless review-only task that must write its own output file) should use `--mode edit` (bypasses approval/sandbox for trusted edit-only work — appropriate here: narrowly-scoped, non-destructive, single new-file write) OR a new intermediate profile ("headless-write": sandboxed shell, but pre-approved writes to the task's own declared output path) should be added to `delegate-to-codex` so review dispatches don't need full `edit`-mode bypass. Interim: re-dispatched the same review task under `--mode edit`.
  File: scripts/ai/delegate-to-codex (mode dispatch logic ~line 288); scripts/ai/aq-collab-round (codex dispatch invocation)

[OPEN] collab-round-typed-consensus-verdict-extraction-gap — `aq-collab-round collect` reported `verdicts={'ABSTAIN': 4} trust=legacy_untrusted` for round `unified-program` even though antigravity.md ends with an explicit `OVERALL VERDICT: REQUEST_REVISION` and claude.md carries per-subject verdicts.
  Root cause / fix notes: contract mismatch between the round-prompt template and the F1 typed-consensus extractor — the prompt asks lanes for prose verdicts ("END with explicit verdict APPROVE / REQUEST_REVISION / BLOCKED per subject") but the extractor only recognizes a typed verdict block, so every substantive contribution was counted ABSTAIN. This silently converts real verdicts into abstention — the exact failure-to-consensus conversion the owner meta-prompt forbids ("never convert failure or silence into abstaining consensus").
  Severity: high
  Action: align the two sides — either the round template emits a machine-parseable verdict block (preferred; add to `open` task scaffold) or the extractor learns the standard `OVERALL VERDICT:` line; add a regression fixture from this round's antigravity.md; aggregation for `unified-program` must be done from the prose verdicts, not the typed ABSTAIN count.
  File: scripts/ai/aq-collab-round (collect/typed-consensus path); .agents/plans/unified-program/round.json

[OPEN] local-lane-round-review-envelope-mismatch — local[Qwen] lane produced 1055B of truncated planning preamble, 0 tool calls, and no verdict for the `unified-program` ratification review.
  Root cause / fix notes: `aq-collab-round open` dispatches the identical task text to every lane with no per-lane shaping; a four-subject, nine-question document review vastly exceeds local's measured envelope (bounded single-command/single-edit, bounded single-output). The aqos-v1 precedent solved this with a hand-written `local-bounded-prompt.md`, but that adaptation is manual and was not applied by the round driver. Output also appears truncated by the task token budget mid-thought. Mitigated this round by a manual bounded ballot re-dispatch (`local-20260713-113318-gkqwk0`).
  Severity: medium
  Update 2026-07-15: the bounded ballot re-dispatch ALSO failed at the 300s default — `local-20260713-113318-gkqwk0` output = "Error: timed out" (16B); a ten-line ballot at 1–3.45 tok/s plus prompt processing does not fit 300s under slot contention, and memory already records 300s as the MINIMUM viable timeout.
  [RESOLVED 2026-07-15] Retried as `local-20260715-073311-wxwk1v` with `--timeout 1800` (mode direct) — succeeded cleanly: full 9-line Q1-Q9 ballot with specific per-item reasoning (e.g. Q5 REVISE correctly asked for revocation/audit-logging criteria before registry activation; Q2 REVISE matched Codex's independent position). CONFIRMS: bounded-ballot task shape + 1800s timeout is a viable local-lane pattern for round participation; the failure was pure envelope/timeout mismatch, not a capability ceiling.
  Action: teach `aq-collab-round open` to auto-generate a bounded local variant (ballot/checklist form, 1800s timeout) from the full task — per-lane task shaping keyed off the lane-eligibility registry (owner decision Q5); raise the delegate-to-local default timeout above the 300s floor for anything beyond trivial single-line output; log the two round-task failures as VF-8 task-class training targets; fold this ballot into local.md at aggregation.
  File: scripts/ai/aq-collab-round (dispatch section); .agents/plans/unified-program/local.md

[OPEN] output-wrapper-corrupts-evidence-and-redirected-output — the rtk/lean-ctx output-compression wrapper altered command output in two evidence-relevant ways this session: (a) `git diff --cached --binary | sha256sum` returned a wrong hash (`cdf562c1…` vs true `12fcf4a1…`), nearly producing a false subject-drift finding during the C0.3 amendment activation; (b) `[lean-ctx: …]` compression markers were written INSIDE a file created via shell redirection, i.e. the substitution reaches redirected/generated artifacts, not just terminal display.
  Root cause / fix notes: the PreToolUse rewrite wraps the whole compound command and compresses stdout at the source, so downstream pipes (`| sha256sum`) and redirections (`> file`) consume compressed bytes. Hash computation inside a `for/eval` construct escaped the rewrite and returned true bytes — that asymmetry is what exposed the corruption.
  Severity: high
  Action: VF-7 `aq-evidence` guaranteed-unwrapped execution path is the structural fix (PREPARED_ONLY, awaiting Track V activation); until then never trust hashes/artifacts from wrapped compound commands — compute evidence via the unwrapped form and re-verify any historical hash produced through a pipe; promote to `.agent/PROMOTED-BUG-PATTERNS.md` at next canonical batch.
  File: rtk hook rewrite + lean-ctx compression layer (Claude Code hook config); .agents/plans/aqos-refoundation-cycle0/C0.3-AUTHORIZATION-AMENDMENT-1.md (activation-record verification note)

[OPEN] collab-round-dispatches-to-known-down-lane — round `unified-program` dispatched to codex (`codex-20260713-104947`) despite the lane being known-down until 2026-07-15; status shows a bare `pending` with no error, indistinguishable from a healthy in-flight dispatch.
  Root cause / fix notes: `aq-collab-round open` has no lane-availability preflight and no deferred-dispatch semantics; the multi-agent-awareness grounding (other agents' status, quota windows) is surfaced at session start but never consulted at dispatch time. Risk: silent stall interpreted as "still working", or a dead dispatch consuming the lane's slot on return.
  Severity: medium
  Action: add lane preflight (auth/quota probe) + `--defer-lane <lane>=<date>` or auto-requeue-on-return semantics; surface dispatch health (spawned/errored/no-response) in `status` instead of bare pending. Interim: manual re-dispatch check for codex on 2026-07-15 (already in fable-5 RESUME todos).
  File: scripts/ai/aq-collab-round (open/status)

[OPEN] precommit-hook-blocks-multiline-commit-message — `git commit -m "<multiline body>"` was rejected by the PreToolUse hook with "command contains control characters that would be hidden in the approval dialog"; commit succeeded via `git commit -F <message-file>`.
  Root cause / fix notes: the hook's rewritten command (updatedInput) fails schema validation on embedded newlines in long `-m` strings — an interaction between the command-rewrite layer and the approval-dialog safety check, not a git problem. The repo's mandated verbose commit messages (multi-paragraph) guarantee every agent hits this.
  Severity: low
  Action: standardize on `git commit -F <file>` (scratchpad message file) in agent workflows; add to agent instruction files at the next canonical-change batch (Rule 16); optionally relax/teach the hook to pass multiline `-m` safely.
  File: Claude Code PreToolUse hook config; commit discipline sections of CLAUDE.md/.agent/CODEX.md/.agent/LOCAL-AGENT.md/.agent/GEMINI.md

[DONE 2026-07-09] rsi-readiness-ratification-resume-cleanup — RSI readiness artifacts were partially completed but not fully folded into the PRD state.
  Root cause / fix notes: the round aggregate already said all four lanes landed, but the table still showed local pending and the PRD footer still said to ratify. A duplicate `prd-consensus/local.md` was also written in the wrong plan directory; it was byte-for-byte identical to `prd-consensus/gemini.md`.
  Severity: low
  Action: Marked the PRD ratified, folded the 2026-07-09 full-system analysis baseline into the PRD/aggregate, updated the local lane status and score consensus, and archived the misplaced duplicate artifact.
  File: .agent/PROJECT-RSI-READINESS-PRD.md; .agents/plans/rsi-readiness/AGGREGATE.md; .agents/archive/misplaced-artifacts-20260709/prd-consensus-local.md

[DONE 2026-07-09] malformed-pulse-log-artifacts — Two malformed untracked pulse files, `PULSE.lognecho` and `PULSE.lognprintf`, were left beside the canonical collaboration pulse log.
  Root cause / fix notes: another agent's shell quoting wrote duplicate pulse content to filenames derived from `echo`/`printf` command text instead of appending to `.agent/collaboration/PULSE.log`.
  Severity: low
  Action: Preserved the useful `da971bd5` quickstart pulse entry in the canonical log, verified no inbound references with `pre-archive-scan.sh`, and archived the malformed files under `.agent/archive/pulse-artifacts-20260709/`.
  File: .agent/collaboration/PULSE.log; .agent/archive/pulse-artifacts-20260709/

[OPEN] t3mp3st-runtime-attachment — T3MP3ST is scope-gated and source-pinned for authorized self red-team prep, but the active runtime is not yet packaged, SBOM-reviewed, or MCP-admitted.
  Root cause / fix notes: registry now pins upstream `ae32cf505174a422c55d7ca970f5f23816218f38` with Nix source hash `0s0xgd32q2hm0dmklrqx76mfm555gjlvx1w7k428p9kni5r32wi0`; `aq-tempest scan --scope local-bringup` proves scope receipts work and returns runtime-pending instead of executing.
  Severity: high
  Action: Add a quarantined Nix package/source fetch, generate SBOM/license review, enumerate upstream tools, and attach only denied-by-default MCP/runtime commands behind valid scope receipts.
  File: config/agent-capability-intake-candidates.json; scripts/ai/aq-tempest

[DONE 2026-07-09] capability-readiness-stale-blockers — The completed Understand-Anything graph, T3MP3ST red-team readiness facade, OSINT local surface research, and Antigravity inbox lane were not all exposed as actionable agent capabilities.
  Root cause / fix notes: registry/catalog state lagged behind completed graph output; T3MP3ST had only a blocked metadata facade instead of scope receipt readiness; Antigravity had a drop directory but no operator-side consume CLI; local webpage/system research lacked a bounded loopback/private surface scanner.
  Severity: medium
  Action: Promoted `code-intelligence-graph-layer` after `validate-batches`, added T3MP3ST scope receipts and ready-scope-gated state, added `aq-antigravity-inbox`, added `aq-local-surface-scan`, and refreshed capability catalog docs/tests.
  File: config/agent-capability-intake-candidates.json; config/system-capability-catalog.json; scripts/ai/aq-tempest; scripts/ai/aq-antigravity-inbox; scripts/ai/aq-local-surface-scan

[DONE 2026-07-09] ai-stack-health-monitor-service-python-env — The real `ai-stack-health-monitor.service` still reported `aq-qa` failures after the script fix because its Nix Python env was too small for phase-0 imports.
  Root cause / fix notes: the service used a one-off `python3.withPackages [ pyyaml ]`; phase `83.3` imports `ai-stack/agent-memory/dag_manager.py`, which requires `pydantic`. The hardened unit PATH also omitted `/run/current-system/sw/bin`, so subprocesses that need `bash` failed until the monitor supplied a child PATH. After rebuild, phase-0 still found sandbox false positives until Python bytecode and Cargo target writes were redirected into `.agents/tmp`.
  Severity: high
  Action: `ai-stack-health-monitor.py` now runs the Python QA harness directly, supplies repo-local temp/cache/Cargo target env and service-Python-first PATH to children, writes stderr/stdout snippets and failing check summaries to latest-run status, and the Nix unit now uses `monitorPython` with `pydantic`/`pyyaml`. Rebuilt and live service run passed phase 0.
  File: scripts/health/ai-stack-health-monitor.py; scripts/testing/test-ai-stack-health-monitor.py; nix/modules/roles/ai-stack.nix

[DONE 2026-07-09] dbus-broker-reload-timeout-after-switch — `nixos-rebuild switch` returned exit 4 because both system and user `dbus-broker.service` reload operations timed out.
  Root cause / fix notes: rebuilt units declared `services.dbus.implementation = broker` and `Type=notify-reload`, but the active processes were still old `dbus-daemon` instances because NixOS does not restart DBus during switch. Reload waited for broker-style notification from the old daemon and timed out. Explicitly restarting system and user DBus after the crash brought up `dbus-broker-launch`; subsequent reload smoke tests for both scopes succeeded.
  Severity: high
  Action: Verified no failed units, confirmed both buses now run `dbus-broker-launch`, and verified `systemctl reload dbus-broker.service` plus `systemctl --user reload dbus-broker.service` succeed.
  File: /etc/systemd/system/dbus-broker.service; /etc/systemd/user/dbus-broker.service

[DONE 2026-07-09] switchboard-local-tool-calling-hints-drift — `local-tool-calling` was documented and deployed as hint-free in the Nix catalog, but the YAML catalog and Python fallback still had `injectHints=true`.
  Root cause / fix notes: Phase 178-B partially aligned the Nix profile but left the repo YAML SSOT and fallback default stale, and the policy regression test encoded the stale value. This added avoidable coordinator hint latency and could perturb short tool-call prompts.
  Severity: medium
  Action: Set `local-tool-calling.injectHints=false` in Python and YAML, updated the profile policy test, refreshed the switchboard profile guide with current local budgets, and documented existing switchboard timeout/adaptive-budget env vars.
  File: ai-stack/switchboard/switchboard.py; config/switchboard-profiles.yaml; config/env-contract.yaml; scripts/testing/test-switchboard-profile-policy.py; docs/agent-guides/46-SWITCHBOARD-PROFILES.md

[DONE 2026-07-09] ai-stack-health-monitor-sandbox-schema-visibility — Scheduled `ai-stack-health-monitor` could raise recurring `aq-qa phase 0 could not run` alerts or miss real failures from current aq-qa output.
  Root cause / fix notes: the systemd service runs with `PrivateTmp=true` and `ProtectSystem=strict`, but only `.agents` is writable; Python `tempfile` users inside aq-qa could not find a usable temp directory. The monitor also parsed only legacy `checks` output while current aq-qa JSON reports checks under `tests`. Added repo-local `.agents/tmp` env wiring, `tests`/`checks` failure parsing, and `.agents/health-monitor/latest.json` latest-run telemetry.
  Severity: high
  Action: Monitor runs phase 0 with sandbox-safe temp env, emits correct attention alerts for current aq-qa schema, and writes latest status for dashboard/API consumers.
  File: scripts/health/ai-stack-health-monitor.py; scripts/testing/test-ai-stack-health-monitor.py

[DONE 2026-07-06] aq-agent-loop-orphan-reaper — Delegated local-agent tasks can become stale with no live PID or output artifact, leaving review fan-out unreliable and risking a wedged `aq-agent-loop` holding the single local llama slot.
  Root cause / fix notes: dispatcher processes can die while child `aq-agent-loop` processes continue in their own session, and older stale registry entries are not automatically reaped. Added a self-watchdog to new `aq-agent-loop` runs and `aq-agent-reap` for dry-run or active cleanup of orphaned or over-age loops.
  Severity: medium
  Action: Added `scripts/ai/aq-agent-reap`, pure reaper decision tests, and a self-watchdog in `scripts/ai/aq-agent-loop`.
  File: scripts/ai/aq-agent-loop; scripts/ai/aq-agent-reap; scripts/testing/test-aq-agent-reap.py

[DONE 2026-07-06] local-agent-single-edit-first-nudge — Local-agent implementation tasks could continue broad read loops after the soft read threshold instead of taking the smallest concrete edit step.
  Root cause / fix notes: the old exploration warning asked for all required edits at once, which was too broad for the local model on multi-site edits. The nudge now tells the model to stop reading and emit exactly one `edit_file` call, and the llama stream path has a wall-clock first-token watchdog so SSE keep-alives cannot mask a wedged prefill.
  Severity: medium
  Action: Updated executor nudge and first-token watchdog; refreshed static regression tests for env-backed read limits and single-edit-first wording.
  File: ai-stack/local-agents/agent_executor.py; scripts/testing/test-exploration-stagnation-guard.py; scripts/testing/test-analysis-only-stagnation-mode.py

[DONE 2026-07-05] declarative-cli-python-dependency-parity — Phase-0 local contract tests failed in the live CLI Python because Home Manager provided only part of the Python runtime surface needed by agent validation.
  Root cause / fix notes: `nix/home/base.nix` included `httpx`, `redis`, and `pyyaml`, but omitted `psutil` for model catalog tests and the FastAPI/uvicorn stack for switchboard import tests. Home Manager activation was also blocked by an imperative `nix profile` `github-mcp-server` duplicate.
  Severity: medium
  Action: Added `fastapi`, `uvicorn`, `pydantic`, `requests`, and `psutil` to the declarative CLI Python; removed the duplicate imperative `github-mcp-server`; reran Home Manager switch; phase-0 and tier0 now pass except documented xfails.
  File: nix/home/base.nix

[DONE 2026-07-03] aq-qa-sandbox-denied-port-probes — Phase-0 port checks were skipped when the agent sandbox denied TCP/listener probes even though the declarative host observer already knew the backing services were healthy.
  Root cause / fix notes: `_port()` only knew direct TCP/`ss` evidence. Added a service-name mapping for known ports and used `_host_observer_service_status()` as an observer-backed pass path when the probe is denied.
  Severity: medium
  Action: Denied Redis/Postgres/Qdrant/llama/AIDB/hybrid/ralph/switchboard port probes now pass via host observer; unmapped or unhealthy observer evidence remains skipped instead of falsely passing.
  File: scripts/ai/_aq-qa-bash; scripts/testing/test-host-observer-contract.py

[DONE 2026-07-01] aq-qa-0.6.1-check-timeout-function-scope — `aq-qa 0` check `0.6.1` "flagship agent CLI help smokes" fails with exit 127 when called via `_check_timeout`.
  Root cause: `_check_timeout` runs `timeout --foreground "$timeout_s" "$@"` where `"$@"` is the bash function name `_flagship_cli_surface_smoke`. `timeout` exec()'s the name as an external command; bash functions are not exported and not accessible to the child process. Exit 127 = command not found.
  Severity: medium (pre-existing in uncommitted _aq-qa-bash changes; blocks tier0 gate)
  Action: Change line 772 of `scripts/ai/_aq-qa-bash` to pass `bash "${REPO_ROOT}/scripts/testing/smoke-flagship-cli-surfaces.sh"` directly with inlined env vars instead of the function wrapper. Smoke script already passes when run directly.
  File: scripts/ai/_aq-qa-bash:772, scripts/testing/smoke-flagship-cli-surfaces.sh

[DONE 2026-06-30] local-agent-planning-loop-marked-success — Capability flush local task `local-20260629-143000-uhh7l2` ran for 6,610.6s and wrote `"success": true`, but the final `result` was repeated `Thought:` planning text with no ranked integration report.
  Root cause / fix notes: for analysis-only tasks, the executor's observation-stall path nudged the model to "act" after repeated query tools instead of forcing a final answer, and `aq-agent-loop._is_incomplete_result()` only recognized explicit failure/stagnation markers. Added forced `COMPLETED:` synthesis for analysis-only observation stalls, plus a repeated-thought/no-completion classifier and phase-0 QA coverage.
  Severity: high
  Action: future local-agent analysis tasks finalize from gathered context before continuing tool loops; repeated planning-only output writes `success=false`, `incomplete_result=true`, and a failed progress sidecar.
  File: ai-stack/local-agents/agent_executor.py; scripts/ai/aq-agent-loop; scripts/testing/test-agent-loop-result-quality.py; scripts/testing/test-agent-executor-analysis-finalization.py

[DONE 2026-06-29] capability-flush-dispatch-used-hybrid-retrieval-lane — `scripts/ai/aq-capability-flush --dispatch-local --json` created `local-20260629-142546-igct2v`, but the output was only three retrieval-result lines and monitor inferred failed status.
  Root cause / fix notes: `--dispatch-local` used `delegate-to-local --mode hybrid`, which is a retrieval/query lane rather than the long-horizon local agent lane. Changed dispatch to `--mode agent` while keeping the prompt analysis-only/no-edit/no-install.
  Severity: medium
  Action: validate a new dispatch starts in the local agent lane and remains monitorable.
  File: scripts/ai/aq-capability-flush

[DONE 2026-06-29] skill-auto-selected-invalid-agent-tool-map — `scripts/ai/aq-capability-flush --dry-run --json` selected `agent-tool-map`, but `aq-skill-auto --test` reported `valid=false` for that selected skill.
  Root cause / fix notes: regression of the prior selected-skill validity class; validator required a body `Description` section and its coarse shell-pattern scan tripped on markdown table rows containing terminal/shell wording. Added the required body section and converted the risky mapping table to bullets. Focused `aq-skill-auto --test` now reports `agent-tool-map valid=true`.
  Severity: medium
  Action: update `agent-tool-map` skill metadata/content or tighten `aq-skill-auto` so invalid selected skills cannot be returned as usable selections.
  File: .agent/skills/agent-tool-map/SKILL.md

[DONE 2026-06-29] stagnation-guard-too-aggressive-for-analysis-only-agent-tasks — Local agent task `local-20260629-012903-kbi12z` failed after 12 reads with `Exploration stagnation` even though the assignment was analysis/planning only.
  Root cause: `classify_task_type(..., mode="agent")` always returned `agent`, so analysis-only prompts never reached the executor's research/analysis guard path. The executor also required `edit_file`/`write_file` progress for all read-heavy tasks, which is wrong for analysis-only work.
  Fix: agent-mode analysis/planning prompts now classify to `research`; analysis/planning/PRD aliases normalize to the `research` profile; executor now keeps the strict 8/12 implementation read guard while giving analysis-only tasks an 80-read checkpoint guard reset by `store_memory`/`write_file`, plus repeated-read path detection. Added phase-0 QA check `0.10.24`.
  Severity: medium
  Files: scripts/ai/lib/dispatch.py; scripts/ai/lib/task_config.py; ai-stack/local-agents/agent_executor.py; scripts/testing/test-analysis-only-stagnation-mode.py

[DONE 2026-06-29] local-agent-timeout-watchdog-not-reaping-agent-loop — `local-20260628-204716-mr8jql` remained running after 36+ minutes even though the parent dispatch command included `--timeout 300`; child `aq-agent-loop` was idle in `do_epoll_wait` and no main output artifact existed for this pre-fix task.
  Root cause: `AgentRunner` used a blocking `subprocess.run()` with a dynamic wall clock up to the runaway hard cap, while `aq-agent-loop` ignores `--max-calls`; stalled children could remain alive without producing the registered output file.
  Fix: `AgentRunner` now launches `aq-agent-loop` in an isolated process group, monitors output/progress/steps artifact mtimes, supports long-horizon default wall-clock runs, reaps no-progress children with SIGTERM/SIGKILL fallback, writes a failed progress sidecar, and records a timeout artifact. The stale pre-fix process was terminated after confirming no recoverable main output file existed.
  Severity: medium
  Files: scripts/ai/lib/dispatch.py; scripts/testing/test-local-delegation-artifact.py

[DONE 2026-06-29] local-agent-agent-mode-output-blind-while-running — `delegate-to-local --check local-20260628-204716-mr8jql` reported the task might still be running because the registered output file did not exist while `aq-agent-loop` was active.
  Root cause: `AgentRunner` passed `--output` to the child but did not create an initial output file or progress sidecar before `subprocess.run`, so long agent-mode tasks had no visible artifact until completion.
  Fix: `AgentRunner` now writes an initial running marker and `.progress.json` before launching `aq-agent-loop`; regression test covers artifact creation before subprocess execution.
  Severity: medium
  Files: scripts/ai/lib/dispatch.py; scripts/testing/test-local-delegation-artifact.py

[DONE 2026-06-29] aq-capability-catalog-render-shell-redirection-blocked — Attempting to refresh the generated capability reference with shell redirection was blocked by the execution environment.
  Root cause: `ctx_shell` forbids file writes via `>` redirection; generated docs must be updated via `apply_patch` or another approved write path.
  Fix: updated `docs/operations/reference/SYSTEM-CAPABILITY-CATALOG.md` with `apply_patch` and verified `aq-capability-catalog check-doc`.
  Severity: low
  File: docs/operations/reference/SYSTEM-CAPABILITY-CATALOG.md

[DONE 2026-06-29] ai-capability-backlog-dashboard-parity-validator — Backlog validator rejected valid visibility notes that named panels or aq-report but not the literal word "dashboard".
  Root cause: `test-ai-capability-implementation-backlog.py` required the literal substring `dashboard`, while the project accepts dashboard panels, aq-report visibility, and explicit panel surfaces as valid delivery gates.
  Fix: validator now accepts `dashboard`, `aq-report`, or `panel` in `dashboard_parity`; backlog entries now explicitly name dashboard visibility where needed.
  Severity: low
  File: scripts/testing/test-ai-capability-implementation-backlog.py

[DONE 2026-06-29] ai-capability-backlog-prd-frontmatter — Focused CI rejected the new backlog PRD because required frontmatter `id` was missing.
  Root cause: `.agent/PROJECT-AI-CAPABILITY-BACKLOG-PRD.md` declared `doc_type: prd` without the schema-required `id`.
  Fix: added `id: ai-capability-backlog`; reran focused CI.
  Severity: low
  File: .agent/PROJECT-AI-CAPABILITY-BACKLOG-PRD.md

[DONE 2026-06-29] suggested-ai-repo-browser-use-gate — Candidate catalog validation rejected `browser-use` because its row had browser-specific gates but omitted the explicit `capability-intake` gate required for every suggested external repo.
  Root cause: initial catalog entry listed sandbox/domain/credential controls but missed the canonical admission gate string enforced by `test-suggested-ai-repo-candidates.py`.
  Fix: added `capability-intake audit` to `browser-use.security_gates`; reran focused candidate validation.
  Severity: low
  File: config/suggested-ai-repo-candidates.json

[DONE 2026-06-29] system-capability-catalog-prd-frontmatter — Focused CI rejected the new catalog PRD because `title` was missing from the required PRD frontmatter.
  Root cause: new `.agent/PROJECT-SYSTEM-CAPABILITY-CATALOG-PRD.md` used `doc_type: prd` but only declared `id/status/owner/last_updated`.
  Fix: added `title: System Capability Catalog`; reran focused CI and tier0 successfully.
  Severity: low
  File: .agent/PROJECT-SYSTEM-CAPABILITY-CATALOG-PRD.md

[DONE 2026-06-28] skill-auto-selected-invalid-skills — `aq-skill-auto --test` could select local skills that failed the same validation payload returned to agents, so recursive improvement/capability prompts could hand agents invalid skill references without failing regression tests.
  Root cause: auto-selection tests asserted reference checks existed but did not assert every selected skill had `valid=true`; selected harness skills were missing validator-required body sections, and self-improvement contained a markdown table phrase that tripped the coarse shell-pattern scanner.
  Fix: tightened `scripts/testing/test-skill-auto.py` with selected-skill validity assertions plus a real-world capability availability prompt; added required Description/Usage/When-to-Use body sections to selected skills; reworded the false-positive table phrase.
  Severity: medium
  Files: scripts/testing/test-skill-auto.py; .agent/skills/aq-workflow/SKILL.md; .agent/skills/capability-intake/SKILL.md; .agent/skills/mcp-builder/SKILL.md; .agent/skills/self-improvement/SKILL.md

[FIXED 2a98887e] dashboard-vlatP95-field-name-mismatch — vLatP95 tile showed "N/A" despite route latency data being available.
  Root cause: dashboard.js:717 reads route_latency.backend_valid_p95_ms but the API response from get_performance_hotspots() returned route_latency.overall_p95_ms (from aq-report route_search_latency_decomposition). Field name mismatch: dashboard expected backend_valid_p95_ms; backend only populated overall/actionable_p95_ms.
  Fix: ai_insights.py get_performance_hotspots() now injects backend_valid_p95_ms alias falling through: backend_valid_p95_ms → overall_p95_ms → actionable_p95_ms → p95_ms. Result: vLatP95 now shows 2300ms.
  Severity: medium (KPI tile blank; route latency monitoring invisible to users)
  File: dashboard/backend/api/services/ai_insights.py get_performance_hotspots() ~line 1718

[FIXED a0a29880] dashboard-vlogic-discipline-timestamp-double-utc — vLogicDiscipline tile showed "--".
  Root cause: delegation_feedback.py wrote datetime.now(timezone.utc).isoformat() + "Z" → "+00:00Z" double UTC marker; _parse_iso_timestamp converted to "+00:00+00:00" (still invalid) → fromisoformat ValueError → all entries filtered → sample_n=0 → score=None.
  Fix (parser, hot): ai_insights.py _parse_iso_timestamp() — strip extra Z when +00:00Z suffix detected. Result: sample_n=30, score=100%.
  Fix (writer, needs rebuild): delegation_feedback.py — strftime("%Y-%m-%dT%H:%M:%SZ") format.
  Severity: high (logic discipline metric invisible; coordination health unmonitored)
  Files: dashboard/backend/api/services/ai_insights.py; ai-stack/mcp-servers/hybrid-coordinator/workflow/delegation_feedback.py

[INFO 2026-06-27] data-store-audit-findings — Full audit of all data stores completed. Summary:
  HEALTHY: Qdrant (14 collections, 50k+ pts), Redis (17,731 keys), PostgreSQL (39 tables, 354k+ rows), AIDB (ok, 58 skills, 354k telemetry events), RALPH/8004 (healthy), embedding-service/8081 (ok).
  Key PostgreSQL counts: telemetry_events=354k, query_traces=30.6k, imported_documents=19.8k, interaction_history=18.9k, learning_feedback=17k, eval_results=2.6k, hint_feedback_events=919, query_gaps=1536.
  Redis: affective:reciprocity 17,592 keys = per-session give/receive counter (by design, TTL-expiring), aidb:* 119, embedding:* 14.
  Qdrant → PG mapping confirmed: nixos-dev-quick-deploy(12,845 docs) → codebase-context(25,980 pts, 2×chunk ratio); ai-research-feeds(3,204 docs) → knowledge(12,680 pts, 4× ratio).
  Gaps (see separate entries below):
    - interaction-history Qdrant: 1 pt vs PG: 18,944 rows
    - aidb-vector-index-silent-noop (existing issue, line ~42) — still MONITOR
    - pgvector embedding column: 0/19,788 (by design — Qdrant is primary vector store)
    - query_gaps 1,536 low-score queries (mostly meta: "list tools", "continuation from session")
  Severity: info (audit complete; all stores live and capturing data)

[DONE 2026-07-01 — BACKFILL COMPLETE] interaction-history-qdrant-gap — Qdrant `interaction-history` collection had 1 point vs 18,962 PG rows. Forward-fix deployed: /history/record handler now fires schedule_qdrant_vectorization(collection="interaction-history") after every successful insert. Collection param threaded through schedule→_runner→_vectorize_doc_to_qdrant (backward-compat; existing callers unchanged → still route to "knowledge").
  Backfill: scripts/ai/backfill-interaction-history-qdrant.py created (httpx-only; dry-run verified 18,962 rows; batch=20, sleep=1.0s throttle; idempotent via Qdrant scroll dedup). Run off-peak: `python3 scripts/ai/backfill-interaction-history-qdrant.py` (~18 min).
  Multi-agent review: Codex (PASS-WITH-CONDITIONS), Local/Qwen3 (APPROVE-WITH-CONDITIONS), antigravity (self-fixed delegation routing simultaneously). All blocking conditions resolved.
  Remaining WARNs (deferred): (1) LOGGER.warning→LOGGER.exception in _runner for full traceback; (2) vectorized_at DB column for native dedup; (3) chunking for interactions >1200 chars.
  Severity: medium → resolved (forward-fix deployed; backfill needed for historical 18,962 rows)
  Files: ai-stack/mcp-servers/aidb/server.py (handler + schedule_qdrant_vectorization + _vectorize_doc_to_qdrant); scripts/ai/backfill-interaction-history-qdrant.py (NEW)

[FIXED d217462d] cross-agent-knowledge-silo — Claude Code's ~/.claude/memory/ contained 35+ promoted bug
  patterns, infrastructure constraints, and feedback rules INVISIBLE to Gemini, Codex, and Local/Qwen3.
  Each agent session re-discovered known failures. Fix: created .agent/PROMOTED-BUG-PATTERNS.md (35+ patterns)
  and .agent/INFRASTRUCTURE-CONSTRAINTS.md (hardware, ports, NixOS rules). All 4 agent instruction files
  updated with Required Shared Knowledge sections and new rules 8a/8b/11 (ATOMIC PULSE, ATOMIC RESUME, ISSUE
  LOGGING). GEMINI.md auth section corrected from stale oauth-personal/gemini-CLI text to current switchboard
  HTTP POST (commit 0ccb644f). Local agent E2E validated: 4 tool calls PASS (2653.5s, search_files → list_files
  → read_file → run_command). Stagnation guard fired correctly on over-reading planning task (Phase 165 — expected).
  Severity: high → resolved
  Files: .agent/PROMOTED-BUG-PATTERNS.md (NEW), .agent/INFRASTRUCTURE-CONSTRAINTS.md (NEW),
    .agent/CODEX.md, .agent/LOCAL-AGENT.md, .agent/GEMINI.md, .claude/CLAUDE.md

[DONE 2026-06-29] stagnation-guard-too-aggressive-for-planning — Exploration stagnation guard (Phase 165) fired on
  a Qwen3 implementation planning task after 12 consecutive reads with no edits. The task was legitimately
  a read-heavy analysis task. Guard is correct for stuck loops but may cut off valid planning sequences.
  Fix: task-type tag/alias support now routes analysis-only agent prompts to the research profile and uses
  checkpoint-based analysis limits while preserving the strict implementation limit.
  Severity: low
  File: ai-stack/local-agents/agent_executor.py (stagnation guard logic)



[FIXED 1a76021e — needs rebuild] intent-routing-map-permission-denied — ai-hybrid EACCES on /home/hyperd (mode 0700) → intent_classifier._load_routing_map() silently catches exception → _routing_map={} → intent_count=0 → all queries use default profile. Blocking: code_generation/planning/review profiles never selected; RAGAS answer_relevance 0.51 (expected to improve after fix).
  Root cause chain: ReadWritePaths+ProtectHome=read-only sets namespace bind-mount but POSIX DAC (inode uid/gid/mode) is NOT bypassed. homeMode=0711 only applies at home-directory CREATION (install -d -m), not on subsequent rebuilds of existing directories (empirically confirmed — mode stayed 0700 after 6c75890f rebuild). The users activation script ran at line 18, activation script at line 31 (correct), but something post-activation (suspected: ai-post-deploy-converge.service) resets mode back to 0700.
  ACTUAL ROOT CAUSE (1a76021e): cpp-dev.nix cppDevLeanCtxMcp activation script ran 'install -d -m 700 /home/hyperd' because claudeJson="/home/hyperd/.claude.json" → dirname=home dir. GNU install -d changes mode of EXISTING dirs. This ran AFTER aiStackHomeDirTraversal and reset mode back to 0700 on every rebuild. Fix: removed the install -d line (home dir guaranteed to exist, managed by users module).
  Three-layer declarative fix committed (ea1df9d7):
    1. homeMode=0711 — creation only (new installs)
    2. activationScripts.aiStackHomeDirTraversal deps=["users"] — runs after users script on rebuild
    3. systemd.tmpfiles.rules z /home/hyperd 0711 — adjusts existing path on every boot + systemd-tmpfiles --create
  Immediate fix (before rebuild): user runs `sudo chmod o+x /home/hyperd` then `curl -X POST http://localhost:8003/control/intent/reload`
  After rebuild: run `sudo systemd-tmpfiles --create` to apply tmpfiles rule, then reload intent map.
  Severity: high (blocking intent routing; aq-qa 1.0.5 FAIL; all intent profiles bypassed)
  Files: nix/modules/core/users.nix (homeMode + activationScripts + tmpfiles.rules); ai-stack/mcp-servers/hybrid-coordinator/intent_classifier.py _load_routing_map()

[FIXED no-commit] vscodium-obsolete-ai-markers — `obsolete_ai_markers` budget check (budget=0) failing because `/home/hyperd/.vscode-oss/extensions/.obsolete` contained 2 stale AI extension entries: `google.geminicodeassist-2.81.0` and `qwenlm.qwen-code-vscode-ide-companion-0.18.4-universal`. Fix: cleared `.obsolete` to `{}` (removes stale markers). Refreshed `/var/lib/ai-stack/hybrid/telemetry/latest-aq-report.json` snapshot so aq-qa 0.5.7 reads updated state. VSCodium running at time of fix — if extensions reinstalled these entries may reappear.
  Severity: low (aq-qa 0.5.7 was failing; no runtime impact)
  File: /home/hyperd/.vscode-oss/extensions/.obsolete; /var/lib/ai-stack/hybrid/telemetry/latest-aq-report.json

[FIXED 393141d7] delegate-to-antigravity-max-tokens-not-wired — cmd_delegate received max_tokens (default 8192) from CLI but never forwarded it to _run_via_switchboard. Switchboard computed remaining token budget from model context (57505 tokens for Venice Llama). Venice rejected HTTP 400 "max_tokens or max_completion_tokens of 57505 exceeds 16384". Fix: added max_tokens param to _run_via_switchboard, wired through both --wait and background fork call sites, capped at min(value, 8192) in payload.
  Severity: high (any complex prompt to remote-free → HTTP 400 → task failed)
  Files: scripts/ai/delegate-to-antigravity _run_via_switchboard() line ~200, cmd_delegate() lines ~549,579

[FIXED 393141d7] prsi-delegation-feedback-not-consumed — PRSI _fetch_structured_actions only read aq-report structured_actions, never delegation-feedback.jsonl. Failed delegations with improvement_actions never fed back into PRSI improvement queue. Fix: added _fetch_delegation_feedback_actions() reading recent failed delegation outcomes; extended _fetch_structured_actions() to merge both sources.
  Severity: medium (PRSI closed loop broken; delegation failures not driving self-improvement)
  File: scripts/automation/prsi-orchestrator.py _fetch_structured_actions() line ~334

[FIXED e876733a 2026-07-01] aidb-vector-index-silent-noop — Root cause: POST /documents returns {"status":"ok"} with no id field; doc_id=None so /vector/index call was never reached. Fix: _embed_and_upsert() in collective_memory.py embeds via llama-embed:8081 /v1/embeddings and upserts to Qdrant PUT /collections/skills-patterns/points directly. Verified: skills-patterns 2142→2143 after archive_collaboration(). AIDB /vector/index path remains broken upstream (aidb/vector_indexer.py) but bypassed.
  Severity: medium — RESOLVED
  File: ai-stack/local-agents/collective_memory.py

[FIXED 4531d494] macc-collaborative-planning-logger-kwarg-crash — collaborative_planning.py used structlog-style kwargs with stdlib logging (6 sites). logger.info("key", plan_id=plan_id) raises Logger._log() got an unexpected keyword argument 'plan_id'. All 6 sites fixed to positional %-format.
  Severity: critical (MACC execute_collaborative_task crashes immediately at create_plan call)
  File: lib/l4-coord/agents/collaborative_planning.py lines 294, 329, 462, 483, 500, 530

[FIXED 4531d494] macc-synthesize-plan-missing-await — execute_collaborative_task called async synthesize_plan() without await. Returns coroutine object instead of executing. plan.phases then a coroutine, not a list. RuntimeWarning emitted.
  Severity: high (plan synthesis silently skipped; phase execution uses wrong object)
  File: ai-stack/local-agents/agent_executor.py line 1959

[FIXED 4531d494] macc-task-start-time-missing-field — execute_collaborative_task accessed task.start_time but Task dataclass has no start_time field. AttributeError not interceptable by `if task.start_time`. Fixed to local _start_time = time.time() pattern.
  Severity: high (AttributeError crashes after phases complete)
  File: ai-stack/local-agents/agent_executor.py line 1982

[FIXED 4531d494] macc-archive-collaboration-metadata-mismatch — archive_collaboration() called with wrong keys (task_id/objective/plan_id/duration_ms) vs expected (task_summary/roles/outcome/duration_s/patterns). Also: AIDB key not found (CLI env vars unset) — added /run/secrets/aidb_api_key SOPS fallback.
  Severity: medium (collaboration records written with empty content; AIDB archives lost)
  Files: ai-stack/local-agents/agent_executor.py ~1985; ai-stack/local-agents/collective_memory.py _aidb_key()

[MONITOR] macc-phase-execution-cli-env — aq-collective runs MACC planning layer correctly but individual phase tasks fail with "Request URL is missing protocol" in CLI context (LLAMA_API_URL unset). Expected: aq-collective is designed for harness context (systemd env injection). Not a bug but confirm working via delegate-to-local path.
  Severity: low (MACC collective planning works; phase execution requires harness env)
  File: scripts/ai/aq-collective

[FIXED] intent-routing-map-not-hot-reloadable — coordinator read intent-routing-map.json from Nix store (repoSource, read-only). POST /control/intent/reload returned changed=false on live edits. Fix: added INTENT_ROUTING_MAP=${mcp.repoPath}/config/intent-routing-map.json to coordinator env in mcp-servers.nix so the live checkout is used. Requires rebuild to activate.
  Severity: low (routing worked, but live edits required rebuild to take effect)
  File: nix/modules/services/mcp-servers.nix line ~1237

[FIXED] continuous-learning-inotify-eacces — ai-hybrid-coordinator logs `learning_loop_error` every 5 min: `[Errno 13] Permission denied: '.agents/telemetry'`. Root cause: `_wait_for_changes()` passes ALL telemetry parent dirs to `awatch()`, including repo-local `.agents/telemetry/` owned by `hyperd`. `ProtectHome=read-only` mounts `/home` as MS_RDONLY bind mount; `inotify_add_watch` returns EACCES on read-only bind mounts. Fix: filter `watch_dirs` to `os.access(dir, os.W_OK)` only — read-only user-spool paths still get read in scheduled processing.
  Severity: medium (coordinator running; learning loop retries every 300s; log noise only)
  File: ai-stack/mcp-servers/hybrid-coordinator/extensions/continuous_learning.py line 668

[FIXED 34627251] bench-C3-docstring-token-exhaustion — C3 code_gen test consistently scored 2/3 despite model knowing rwk. Model filled 250-token budget with docstring, leaving no tokens for function body (`return` never appears → point 1 always fails). fix: max_tokens 250→350.
  Severity: medium (miscalibrated bench score, model knowledge was correct)
  File: scripts/testing/bench-local-agent.py (extra={"max_tokens": 350})

[FIXED 34627251] bench-float-boundary-false-demotion — 6/9 = 0.6666... compared against threshold 0.67; `pct >= prom_thr` False due to integer scoring granularity. Run at 82% overall with all dims passing displayed as promote=False.
  Fix: `pct >= prom_thr - 1e-9` epsilon guard in _check_promotion.
  Severity: low (affected 1 run's verdict, not calibration)
  File: scripts/testing/bench-local-agent.py _check_promotion()

[CRITICAL-FIXED] sops-gemini-api-key-missing-from-sops-file — All AI stack services down: ai-aidb, ai-hybrid-coordinator, ai-pgvector-bootstrap, crowdsec-firewall-bouncer-key-sync, nvd-sync, ai-prsi-orchestrator.
  Root cause: `gemini_api_key` was added to `nix/modules/core/secrets.nix` (and thus the compiled sops manifest) but never added to the actual SOPS-encrypted file at `/home/hyperd/.local/share/nixos-quick-deploy/secrets/hyperd/secrets.sops.yaml`. sops-install-secrets performs manifest validation before decryption; finds key count mismatch (manifest=9, SOPS file=8); fails with exit code 1; leaves `/run/secrets/` absent; all services requiring secrets cascade-fail.
  Exact error (from boot journal): `sops-install-secrets: manifest is not valid: secret gemini_api_key in secrets.sops.yaml is not valid: the key 'gemini_api_key' cannot be found`
  Severity: critical (all AI stack services unavailable)
  Action: (1) Run `SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt sops ~/.local/share/nixos-quick-deploy/secrets/hyperd/secrets.sops.yaml` and add `gemini_api_key: <value-or-placeholder>` (2) `sudo nixos-rebuild switch --flake .#hyperd-ai-dev` — activation will now pass validation and write all 9 secrets.
  Pattern: any new `sops.secrets.*` entry in secrets.nix MUST be followed immediately by `sops <file>` to add the key. The Nix rebuild compiles the manifest; the SOPS file must match. Never add a key to secrets.nix without the corresponding SOPS edit.
  Files: nix/modules/core/secrets.nix ~line 107-113; /home/hyperd/.local/share/nixos-quick-deploy/secrets/hyperd/secrets.sops.yaml

[LOW-HARDENING] sops-age-key-in-home-directory — Age private key for sops-nix lives at `/home/hyperd/.config/sops/age/keys.txt`. Root bypasses DAC today, but `ProtectHome=true` or AppArmor tightening on the activation service would re-break secrets at boot.
  Root cause: `deploy-options.local.nix` overrides `mySystem.secrets.ageKeyFile` from the canonical default `/var/lib/sops-nix/key.txt` to the user home path.
  Severity: low (latent breakage risk on security hardening)
  Action: (1) `sudo mkdir -p /var/lib/sops-nix && sudo cp ~/.config/sops/age/keys.txt /var/lib/sops-nix/key.txt && sudo chmod 400 /var/lib/sops-nix/key.txt` (2) Remove `mySystem.secrets.ageKeyFile = lib.mkForce "..."` from `nix/hosts/hyperd/deploy-options.local.nix` (default is already `/var/lib/sops-nix/key.txt` in options.nix:894) (3) Rebuild.
  Files: nix/hosts/hyperd/deploy-options.local.nix; nix/modules/core/options.nix:894

[OPEN — GOOGLE BACKEND BLOCKER] gemini-cli-onboardUser-429-persistent — Code Assist account provisioning blocked since Jun 19 (9+ days).
  Root cause: gemini-cli calls cloudcode-pa.googleapis.com/v1internal:onboardUser on EVERY cold start (no persistent session cache). Google's provisioning endpoint returns 429 rateLimitExceeded. This creates a circular dependency:
    onboardUser → creates cloudaicompanionProject → loadCodeAssist works
         ↑ blocked by 429                           ↓ 403 without project
  Result: no cloudaicompanionProject ever provisioned → loadCodeAssist returns 403 → ALL gemini-cli paths fail.
  Tested (2026-06-28):
    - gemini -p "test" → 429 on onboardUser (even after successful browser OAuth)
    - GOOGLE_GENAI_USE_GCA bypass → still hits loadCodeAssist → 403 (no quota project)
    - gcloud auth login (cjlnorcal@gmail.com) + GOOGLE_CLOUD_ACCESS_TOKEN → same 403
    - gemini-cli 0.47.0 → 0.48.0-preview.0 → 0.49.0 → 0.51.0-nightly: all have onboardUser call, no bypass
    - GEMINI_CLI_TRUST_WORKSPACE, GEMINI_FORCE_FILE_STORAGE: no effect on onboardUser
  Scope: delegate-to-antigravity, entire Google Code Assist path for cjlnorcal@gmail.com
  Severity: CRITICAL — antigravity delegation fully blocked; gemini-cli oauth-personal path unusable
  Resolution: Google-side only. Monitor periodically: `gemini -p "test"`. When onboardUser succeeds once, credentials are written and all subsequent headless calls work automatically.
  Note: delegate-to-antigravity script (7affca42) is correctly implemented for the gemini-cli path and will work immediately when onboardUser unblocks.
  Severity: low (Llama 3.3 70B on remote-free handles delegation; Gemini routes available when credits/oauth fixed)
  File: scripts/ai/delegate-to-antigravity _PROFILE_MAP

[OPEN] codex-startup-local-state-warnings — `codex_hooks = true` persists at /home/hyperd/.codex/config.toml:48 because a Codex hook process rewrites the file on each session write — line cannot be removed while any Codex session is active.
  Root cause: Codex hook state manager restores `codex_hooks` from its in-memory session state on every config save; the line is not persisted by the user but by the hook runtime.
  Severity: low
  Action: Run `sed -i '/^codex_hooks/d' /home/hyperd/.codex/config.toml` immediately after fully exiting all Codex sessions (check `pgrep -a codex`). Cannot be fixed from within Claude Code while Codex is running.
  File: /home/hyperd/.codex/config.toml:48

[PENDING-REBUILD] codex-doctor-terminfo-env-noise — `codex doctor --summary` reports terminal failure because inherited TERMINFO_DIRS contains missing profile paths.
  Root cause: `TERMINFO_DIRS` includes nonexistent Flatpak/Nix profile terminfo directories before the valid `/run/current-system/sw/share/terminfo`; `infocmp xterm-256color` succeeds from the valid NixOS terminfo path. One-shot override with `TERMINFO=/run/current-system/sw/share/terminfo TERMINFO_DIRS=/run/current-system/sw/share/terminfo codex doctor --summary` drops the terminal finding from fail to warning. Remaining warning is terminal height 20 rows, not terminfo.
  Severity: low
  Action: Added `TERMINFO` and `TERMINFO_DIRS` to Home Manager session variables and VSCodium AI extension environment; activate with `home-manager switch --flake .#hyperd` or the host deploy path, then start a new shell/editor. Run Codex in a terminal pane at least 24 rows high to clear the remaining height warning.
  File: nix/home/base.nix ~line 100

[PENDING-REBUILD] home-manager-insecure-gradio-policy-block — Home Manager activation eval refused insecure `python3.13-gradio-sans-reverse-dependencies-5.49.1`.
  Root cause: `gradio` was included in the always-installed Home Manager Python AI/dev bundle, but nixpkgs marks Gradio v5 reverse dependencies insecure/unmaintained with CVEs. This forced `NIXPKGS_ALLOW_INSECURE=1` for unrelated Home Manager validation.
  Severity: medium
  Action: Removed `gradio` from the shared Home Manager Python bundle; use a project-local virtualenv only when a demo UI explicitly needs Gradio.
  File: nix/home/base.nix ~line 587

[IN-PROGRESS] opencode-undici-bun-crash — opencode v1.3.0 crashes on every invocation with `ReferenceError: undici is not defined` (Bun v1.3.3, Linux x64).
  Root cause: opencode 1.3.0 bundle (`$bunfs/root/src/index.js`) imports `undici` as an npm module, but Bun 1.3.3 does not expose `undici` as a built-in. opencode is installed from Nix store at /nix/store/2rn57ci5bp1s8q401zwwy8isbx4v3im9-opencode-1.3.0; nixpkgs channel has opencode-0.3.112 (nixos.opencode) / 1.1.14 (nix eval). The 1.3.0 build likely requires a newer Bun version or Node.js runtime.
  Severity: medium (opencode is a potential Antigravity/multi-provider agent but is not currently in the delegation chain)
  Action: (1) Try nixpkgs version: add `pkgs.opencode` to system packages (gets 0.3.112 or 1.1.14); (2) OR update flake nixpkgs to get opencode ≥1.3.0 with matching Bun; (3) Test `opencode --version` after change.
  Files: nix/hosts/hyperd/facts.nix or system packages (add pkgs.opencode)

[DONE] llama-cpp-no-backends-after-nixified-ai-update — `nixos-rebuild switch` failed because `llama-cpp.service` could not load any backend
  Severity: critical
  Action: The `llama-server-unconfined` wrapper copied only the binary; llama.cpp 9222 loads CPU/Vulkan backends from `bin/libggml-*.so`. Copy those backend plugins beside the renamed binary so `--list-devices` and model loading can find them.
  File: nix/modules/roles/ai-stack.nix ~line 200

[DONE] phase178b-local-context-budget-overflow — local switchboard profile defaults exceeded LLAMA_CTX_SIZE headroom
  Severity: high
  Action: Reduced local-agent, local-tool-calling, and coordinator-internal default maxInputTokens/maxOutputTokens so each fits LLAMA_CTX_SIZE-600; added matching env-contract entries.
  File: ai-stack/switchboard/switchboard.py ~line 307

[DONE] local-agent-runtime-event-gap — local runtime subprocesses did not emit agent events to /api/agent-events
  Severity: medium
  Action: Added delegation_start, delegation_end, workflow/tool_call, and failure event posts through HYBRID_URL with non-blocking error handling; added unit coverage.
  File: ai-stack/agents/runtimes/local_agent_runtime.py ~line 562

[FIXED 093bb1c0] aq-chat-spinner-swallows-streaming — agentic coordinator path produces empty responses
  Root cause: `with console.status(...)` wrapped both setup AND the entire streaming loop in aq-chat.
  Rich's Live display was active during streaming. console.print(token, end="") inside an active Live
  context buffers tokens until the context exits; when the with-block exited via `return`, Rich tore
  down the Live area and all buffered tokens were discarded. User saw only blank lines (from the two
  print() calls at top/bottom of the stream loop). The fast-path (continue-local) was unaffected
  because it uses plain print() outside of any Live context.
  Severity: critical (all agentic coordinator responses appeared empty)
  Fix: Store Status object as _setup_status, call _setup_status.stop() after payload setup and BEFORE
  the try:/streaming block. Spinner covers only setup phase; tokens stream directly to terminal.
  Status.stop() is idempotent so Rich's __exit__ double-call is harmless.
  Files: scripts/ai/aq-chat (lines 793, 857)

[FIXED 6e7a4be3] aq-chat-504-stuck-semaphore — aq-chat 504 local_agent_timeout on every turn
  Root cause: two bugs combined: (1) _CONVERSATIONAL_INTENTS in chat_intent.py defined but never used — "how are you?" classified as agentic, sent to coordinator subprocess path; (2) _profile_for_role("coder") returned "local-tool-calling" which hits switchboard's _execute_local_tool_calling (expects built-in server tools, not subprocess agent schemas). Request reached llama.cpp, held _local_sem (SWB_LOCAL_CONCURRENCY=1). After coordinator proc.kill() at 210s, TCP closed but switchboard kept sem until llama.cpp finished (~150s), blocking ALL local inference requests.
  Severity: critical (aq-chat completely broken for all agentic turns)
  Fix: (1) chat_intent.py: add _CONVERSATIONAL_INTENTS check in classify_chat_intent() — greetings/explanatory phrases route to fast-path; (2) local_agent_runtime.py: _profile_for_role() always returns "continue-local" — correct profile for subprocess agents. Requires switchboard restart to clear stuck _local_sem.
  Files: scripts/ai/lib/chat_intent.py; ai-stack/agents/runtimes/local_agent_runtime.py

[PENDING-REBUILD 4cdc6fdf] embed-ubatch-size-512-too-small — llama-cpp-embed rejects chunks >512 tokens with HTTP 500
  Root cause: llama-cpp-embed default --ubatch-size=512 tokens (physical batch). Dense code tokenizes at ~2.8 chars/tok → 2000-char chunk = 700+ tokens → 500 "input too large to process". Also .forks/ (45k files) inflated eligible file count from 3189→48391.
  Severity: high (codebase-context indexing fails for any chunk >512 tokens)
  Fix: (1) index-codebase.py: CHUNK_SIZE 3000→1000, skip .forks/ and .reports/; (2) facts.nix: --ubatch-size 2048 added (PENDING-REBUILD — after rebuild chunk size can return to 2000 for better retrieval context)
  Files: scripts/data/index-codebase.py; nix/hosts/hyperd/facts.nix

[FIXED c10b43d8] local-agent-runtime-missing-logger — aq-chat local-tool-calling returned 500/local_agent_failed after rebuild
  Root cause: local_agent_runtime.py used logger.warning/logger.info at lines 889/893 (switchboard handshake retry path) but never imported `logging` or instantiated the module-level `logger`. Subprocess exited rc=1 with NameError JSON; coordinator returned 500.
  Severity: critical (every aq-chat local-tool-calling turn failed post-rebuild)
  Fix: add `import logging` to stdlib imports block; `logger = logging.getLogger(__name__)` after httpx import. (c10b43d8)
  File: ai-stack/agents/runtimes/local_agent_runtime.py:29-38
<!-- Phase 165 behavioral contract hardening COMPLETE (2026-06-13):
  iter 16-21 resolved: slim-manifest, read-limit, backlog-update-step, embedded-newlines-parse, synthesis-guard@call0.
  aq-qa covers: 0.10.15-19 (5 new Phase 165 checks). Dataset=309. Backlog clear.
  Next: PENDING-REBUILD activation (nixos-rebuild required, all commits ready). -->

[DONE] switchboard-useful-ratio-missing — switchboard token_usage events never emit useful_ratio; field is always null in telemetry (observability parity gap Phase 149)
  Root cause: switchboard.py emits token_usage events at two sites (~line 2944, ~line 2964) but neither
  includes useful_ratio in the tokens dict. The agent_run_events.py schema supports useful_ratio but
  switchboard passes only raw llama.cpp usage (prompt/completion/total tokens) or estimated counts.
  For local inference with enable_thinking=false, ALL output tokens are useful → useful_ratio=1.0.
  This means the dashboard Useful Token Gauge shows null/-- for 100% of local model requests.
  Live state: grep "useful_ratio" switchboard.py → no results (2026-06-13).
  Severity: medium (observability gap; does not affect response quality)
  Requires rebuild: YES (switchboard.py is a coordinator-side service)
  Action: In ai-stack/switchboard/switchboard.py, at both token_usage emission sites (~line 2944 and ~2964),
  add useful_ratio to the tokens dict:
    Site 1 (llama.cpp usage block, line ~2944): inject "useful_ratio": 1.0 into the usage dict before emit.
    Site 2 (estimated fallback, line ~2971): add "useful_ratio": 1.0 to the tokens dict.
  Justification: enable_thinking=false is system-wide for local inference (CLAUDE.md constraint);
  all output tokens are response tokens → useful_ratio is exactly 1.0.
  Files: ai-stack/switchboard/switchboard.py (~line 2944 and ~2971)
  Two surgical edits. No logic changes.

[DONE] health-spider-osi-layered-running-flag — health spider flags osi_layered_pending as degraded even when background task is actively running (running: True)
  Root cause: _semantic_probe_reason() check for "osi_layered_ready" returns "osi_layered_pending" whenever
  data.get("pending") is True, regardless of data.get("running"). But the layered endpoint is designed to
  return {pending: True, running: True} during its warm-up period (300-600s background aq-qa run).
  The rebuild resets the in-process cache → first post-rebuild request triggers background task →
  health spider hits during warm-up window → false-positive "degraded" alert (attn-0c6f15e9, 2026-06-12).
  Severity: low
  Action: In scripts/ai/aq-health-spider, edit _semantic_probe_reason() for the "osi_layered_ready" check:
  Old text (exact, line ~142-144):
    if check == "osi_layered_ready":
        if data.get("pending") is True:
            return "osi_layered_pending"
  New text:
    if check == "osi_layered_ready":
        if data.get("pending") is True and not data.get("running"):
            return "osi_layered_pending"
  Effect: Spider tolerates the warm-up window (running: True). Only flags as degraded when stuck (pending AND NOT running).
  Files: scripts/ai/aq-health-spider (_semantic_probe_reason, ~line 142)
  One surgical edit, no logic changes beyond the single condition.

[DONE] stagnation-guard-run-command-repeat — stagnation guard counts reads-without-edit but does not detect repeated run_command calls (e.g. 4x tier0 validation passes without committing)
  Root cause: agent_executor.py exploration_stagnation_guard tracks read_count_without_edit and fires nudge at 8, abort at 12. But a model that runs validate_before_commit repeatedly (g8w0oa ran tier0 x4 over 36 min) is also stuck — the guard never fires because run_command resets no counter.
  Observed: g8w0oa dispatched 2026-06-13 passed tier0 at steps 8, 13, 18, 23 (4 times) but never committed; orchestrator had to intervene manually.
  Likely cause: edit_file for issues-backlog.md failed silently (old_string mismatch due to oryb80 staging conflict), model re-validated rather than aborting.
  Severity: medium (self-improvement loop efficiency)
  Action: In agent_executor.py stagnation guard, also track run_command_repeat_count. If the same semantic action (validate_before_commit or git_add + git_commit) repeats 3+ times without intervening edits, fire the stagnation nudge. Or: if validate_before_commit count ≥ 3 and no git_commit yet, inject "STEP 6 now: git_add and git_commit immediately."
  Files: ai-stack/local-agents/agent_executor.py stagnation guard (~line 600-650)
  One edit, adds repeat-command detection to existing stagnation logic.

[DONE] ragas-faithfulness-zero-samples — faithfulness metric never computed; faithfulness_sample_count=0 across all 100 eval samples
  Root cause: http_server_impl.py _ragas_score() computes faithfulness only when _ctx is non-empty:
    `fs = await eval_runner.score_faithfulness_async(q, _ctx, r) if _ctx else None`
  _ctx is built from RAG documents returned by the coordinator. If AIDB returns no matching documents
  (sparse collections), _ctx is empty → faithfulness=None for that sample. All 100 samples evaluated
  with empty context → faithfulness_sample_count=0 → faithfulness_avg=null indefinitely.
  Live state (2026-06-13): ragas_metrics={answer_relevance_avg: 0.4747, faithfulness_avg: null, faithfulness_sample_count: 0, sample_count: 100}
  Root cause of empty context: RAG collections (error-solutions, skills-patterns, best-practices) may be
  stale or sparse for the types of queries flowing through the coordinator. Re-seed with current patterns.
  Severity: medium
  Action: Run seed-rag-knowledge.py --clear-wrong-type to refresh collections, then verify
  faithfulness_sample_count increases over the next 24h as coordinator queries hit populated collections.
  If collections are populated but faithfulness remains 0, investigate score_faithfulness_async for errors.
  Files: scripts/data/seed-rag-knowledge.py (immediate action); ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py _ragas_score (~line 2404) for deeper fix if needed.
  Non-blocking: answer_relevance and context_precision metrics are healthy (0.47 and 0.43).

[DONE] parse-tool-call-embedded-newlines — parse_tool_call_from_llama fails when model emits JSON with literal (unescaped) newlines in string values
  Root cause: When old_string/new_string span multiple Python source lines, the model may emit them
  as JSON string values containing literal `\n` characters instead of `\\n` escape sequences.
  `json.loads()` rejects literal control chars in strings → parse returns None → tool never executes.
  iter 19 (aq-1781332710) triggered this: old_string contained two Python source lines joined by `\n`.
  Synthesis guard did NOT fire because tool_call_count==0 (guard has `if tool_call_count > 0` guard).
  Severity: medium
  Action: In tool_registry.py parse_tool_call_from_llama, pre-process the raw string to escape
  literal newlines/tabs before json.loads(): replace raw `\n` (0x0a) with `\\n` inside the JSON
  string payload. Use regex or a custom sanitize step before json.loads().
  Also: remove the `tool_call_count > 0` guard from the synthesis guard in agent_executor.py so
  it fires even when the first response is an unexecuted JSON tool call.
  Files: ai-stack/local-agents/tool_registry.py parse_tool_call_from_llama (~line 583);
         ai-stack/local-agents/agent_executor.py synthesis guard (~line 723)
  Two surgical edits, one to each file.

[DONE] behavioral-contract-backlog-update-step — BEHAVIORAL CONTRACT STEP 6 adds issues-backlog.md to git but never marks the issue [DONE] first
  Root cause: STEP 6 says git_add([<changed-files>, '.agent/memory/issues-backlog.md']) but there is no
  step before git_add that calls edit_file to change [OPEN] to [DONE] in the backlog. The backlog is staged
  but unchanged, so [OPEN] issues remain [OPEN] after commit. Orchestrator has to manually update them.
  Severity: medium
  Action: In agent_executor.py, edit BEHAVIORAL CONTRACT to add a step between STEP 5 and STEP 6.
  Old text (exact):
    "        If gate fails, fix the problem and re-run. Gate passes → go to STEP 6 immediately.\n"
    "STEP 6: git_add([<changed-files>, '.agent/memory/issues-backlog.md'])\n"
  New text:
    "        If gate fails, fix the problem and re-run. Gate passes → go to STEP 5b immediately.\n"
    "STEP 5b: edit_file('.agent/memory/issues-backlog.md', '[OPEN] <issue-title>', '[DONE] <issue-title>')\n"
    "         Marks the fixed issue as done. Use the exact issue title from STEP 2.\n"
    "STEP 6: git_add([<changed-files>, '.agent/memory/issues-backlog.md'])\n"
  Files: ai-stack/local-agents/agent_executor.py (_get_system_prompt BEHAVIORAL CONTRACT)
  One edit_file call. No logic changes.

[DONE] behavioral-contract-read-limit — BEHAVIORAL CONTRACT lacks explicit READ LIMIT rule; model over-reads before editing
  Root cause: BEHAVIORAL CONTRACT general rules say "Read before writing" but this causes over-exploration.
  Iter 17 original ran 12 reads, 0 edits in 26+ minutes because the model kept reading different files
  instead of attempting edit_file. The exploration stagnation guard (Phase 165) catches this at 12 reads
  (hard abort) and nudges at 8, but the root fix is making the contract explicit.
  Severity: medium
  Action: In agent_executor.py, inside _get_system_prompt(), edit the BEHAVIORAL CONTRACT to add after the
  "- ALWAYS prefer edit_file over write_file" rule:
  Old text (exact):
    "- ALWAYS prefer edit_file over write_file for targeted changes.\n"
    "  edit_file(path, old_string, new_string) replaces old_string in place — no full-file regeneration.\n"
    "  Only use write_file if you must create a new file from scratch.\n"
  New text:
    "- ALWAYS prefer edit_file over write_file for targeted changes.\n"
    "  edit_file(path, old_string, new_string) replaces old_string in place — no full-file regeneration.\n"
    "  Only use write_file if you must create a new file from scratch.\n"
    "- READ LIMIT: At most 4 read_file calls per slice. After 4 reads, STOP reading — you have enough\n"
    "  context. Call edit_file immediately. If edit_file fails with 'old_string not found', THEN read more.\n"
  Files: ai-stack/local-agents/agent_executor.py (BEHAVIORAL CONTRACT in _get_system_prompt)
  One edit_file call. No logic changes.

[DONE] agent-step-complete-tool-call-result — synthesis guard added to agent_executor.py
  Fix: two-part — (1) training_ingest: added '"function"' + '"arguments"' to _STRUCTURED_MARKERS so JSON
  tool-call blobs score as structured (score≈0.80 vs 0.048 pre-fix). (2) agent_executor.py synthesis guard:
  if final response starts with '{"function"', request 256-token "COMPLETED:" prose synthesis.
  BEHAVIORAL CONTRACT DONE marker now requires "COMPLETED: <sentence>" prefix explicitly.
  Commit: 8694d6fc (feat(observability): wire context_sanitizer, synthesis guard, agent replay parity)
  Validated: iter 17 retry produced COMPLETED: sentence at step 8. training_ingest will pick up sample.

[DONE] aq-agent-loop-build-registry-docstring-drift — build_registry() docstring + argparse help updated to list 8 slim tools
  Fix: iter 17 retry (zyk4bj / aq-1781328865) — model used edit_file × 2, validate_before_commit, git_commit.
  7 steps in 475s. Commit: f3fb0e11 "docs(aq-agent-loop): update build_registry docstring + argparse help to list 8 slim tools"
  Key improvement vs iter 17 original: targeted prompt with exact old_string/new_string eliminated over-exploration.
  Original iter 17 ran 26+ minutes with 12 reads, 0 edits — killed and re-dispatched.

[DONE] progressive-tool-disclosure — aq-agent-loop exposed all 29 tools (~2507 tokens) in every self-improvement slice
  Root cause: build_registry() always registered all tools. Self-improvement slices only need 6 tools
  (read_file, write_file, run_command, git_add, git_commit, store_memory). Extra 23 tools added 1739
  tokens to the system prompt on every LLM call = 174s wasted prefill per call at 10 tok/s (Renoir APU).
  Over 7 calls per slice: ~20 minutes wasted per self-improvement iteration.
  Fix: Added --tool-manifest flag to aq-agent-loop with 'full' (default, 29 tools) and 'self-improvement'
  (6 tools). build_registry(tool_manifest=) unregisters excluded tools via registry.unregister().
  Slim schema: 3073 chars (~768 tokens) vs full 10031 chars (~2507 tokens). 1739 token savings per call.
  File: scripts/ai/aq-agent-loop (build_registry, run_task, argparser)
  Commit: feat(agents): progressive tool disclosure — --tool-manifest self-improvement (6 tools, save ~174s/call)

[DONE] agent-behavioral-contract-cleanup — contract updated with surgical finality (commit-on-pass, no post-fix cleanup)
  Gemini P2 finding (2026-06-12): BEHAVIORAL CONTRACT lacked explicit "commit on pass, no cleanup" mandate.
  Iter 7 timed out doing post-commit cleanup (RESUME.json, HANDOFF.md, PULSE.log updates), consuming ~3-4
  extra inference calls and hitting 3600s wall-clock. Fix: Added "SURGICAL FINALITY" rule and strengthened
  DONE step to explicit "STOP. Do not refactor. Do not update other files."
  Also: STEP 3 now instructs agent to use start_line/end_line for targeted reads (reduce context load).
  Also: STEP 6 now includes issues-backlog.md in git_add so the fix is committed with DONE marker.
  File: ai-stack/local-agents/agent_executor.py (_workflow_contract)
  Commit: fix(agents): strengthen behavioral contract with surgical finality + targeted reads

[DONE] agent-loop-wall-clock-timeout — agent tasks killed at 3600s fixed-wall-clock before completing 9 tool calls
  Root cause: iter 9 self-improvement run grew context to 7436 tokens by call 6-7 (Qwen3 SWA forces full
  re-prefill each turn, no KV cache reuse). At 10 tok/s prefill, each late call took 12+ minutes. Fixed 3600s
  wall-clock only allowed ~3 large calls. Context pruning at 24768 chars (~6192 tokens) didn't prevent growth.
  Fix A (dispatch.py): Dynamic wall-clock = min(per_call_budget × max_calls + 120, 10800s).
    per_call_budget = chunk_timeout (900s) + gen_budget (1200s) = 2100s.
    For 9 calls: min(9×2100+120=19020, 10800) = 10800s (3-hour hard cap = runaway safeguard).
    AGENT_WALL_CLOCK_SECS env var still overrides for ops/debug.
  Fix B (agent_executor.py): Lower context budget from 24768 chars (~6192 tokens) to 12000 chars (~3000 tokens).
    Keep only system + user + last 2 tool pairs (max 6 messages). Caps prefill at ~5 min per call.
    Tradeoff: agent loses older history; BEHAVIORAL CONTRACT already discourages re-reading.
  Files: scripts/ai/lib/dispatch.py, ai-stack/local-agents/agent_executor.py
  Identified: 2026-06-12 by analyzing llama.cpp slot print_timing logs during iter 9.

[DONE] agent-context-pinned-sliding — "last 2 pairs" context strategy dropped initial discovery by step 5-6
  Gemini FAIL verdict (2026-06-12 architectural review): reducing context to system+user+last-2-pairs was too
  aggressive. By step 5-6, the model had lost the initial grep output (which issue to fix), causing it to read
  the backlog file again → extra tool call, context refill, potentially triggering stagnation loop.
  Root cause: messages[:2] + messages[-4:] discards messages[2:3] = first assistant call + first tool result.
  Those contain the grep discovery that anchors the entire slice.
  Fix (agent_executor.py _execute_with_tools): Replace with "Pinned + Sliding" strategy:
    PINNED  = messages[0:4]  — system + user + first_assistant_call + first_tool_result (task anchor)
    SLIDING = messages[-4:]  — last 2 assistant+tool pairs (most recent work)
    Trigger: _ctx_chars > 12000 AND len(messages) > 8. Fallback shed-oldest-pair for len 6-8.
  Impact: model retains which issue it targets across all steps; no re-reads of already-seen content.
  File: ai-stack/local-agents/agent_executor.py (_execute_with_tools, Pinned+Sliding block)
  Commit: feat(agents): pinned+sliding context + stagnation detection
  Follow-up (Gemini FAIL d5235778): removed dead overlap dedup guard (overlap=4+4-len<0 always when len>8).
  Commit: fix(agents): remove dead overlap guard + tune stagnation thresholds

[DONE] agent-stagnation-detection — no guard against runaway same-tool loops in agent_executor
  Root cause: agent could call read_file or run_command 20+ times with identical result (e.g. after context
  pruning dropped the tool result, model re-reads the same file in a tight loop). No detection, no early exit.
  Gemini recommendation (2026-06-12): terminate if same tool called N consecutive times with no state change.
  Fix (agent_executor.py _execute_with_tools): _recent_tools list tracks (tool_name, result[:200]) for last N
  calls. Threshold is tool-specific: read_file=3 (pure observation, 3 identical reads = stuck),
  run_command=5 (polling loops like tail/systemctl legitimately repeat). If all N have same result prefix,
  logger.warning and return stagnation_msg early.
  File: ai-stack/local-agents/agent_executor.py (_execute_with_tools, stagnation detection block)
  Commit: fix(agents): remove dead overlap guard + tune stagnation thresholds

[DONE] training-ingest-routing-rules-lost — training_ingest.py perpetuated routing_rules loss due to non-truthy check
  Root cause: training_ingest.py lines 493-495 — `break` at col 12 was OUTSIDE the inner
  `isinstance(_existing.get("routing_rules"), dict)` check. An empty dict {} passes `isinstance({}, dict)`,
  so _existing_routing_rules = {} and break fired → empty state preserved forever on every subsequent rewrite.
  Fix: Changed condition to truthy `_existing.get("routing_rules")` and moved `break` INSIDE the success branch.
  Both config/harness-prompt-extensions.json and .yaml still carry routing_rules (grep -c confirms).
  File: ai-stack/local-agents/training_ingest.py (lines 493-495)
  Commit: fix(training-ingest): truthy check prevents perpetuating empty routing_rules on rewrite

[DONE] training-ingest-write-race — concurrent training_ingest runs shared a fixed temp file path causing lost writes
  Root cause: training_ingest.py lines 519-527 used fixed .tmp paths:
  `_target.with_suffix(".tmp")` for YAML, `_target.with_suffix(".json.tmp")` for JSON.
  Two concurrent processes wrote to the same .tmp file; process B overwrote A's content before A's os.replace().
  Fix: Both blocks replaced with tempfile.NamedTemporaryFile(dir=_target.parent, delete=False, suffix=".tmp").
  Each process gets a unique temp path. os.replace() remains the atomic final rename.
  Note: iter 11 identified and attempted the fix but called write_file with only a 24-line snippet, destroying
  573 lines of the file. Restored from git; fix applied surgically by orchestrator (Edit tool).
  File: ai-stack/local-agents/training_ingest.py (lines 516-531)
  Commit: fix(training-ingest): use NamedTemporaryFile for atomic write to eliminate concurrent-write race

[DONE] agent-telemetry-permission-drop — agent_step_complete / agent_thinking / agent_tool_call events silently dropped
  Root cause: agent_executor.py wrote per-step telemetry to /var/lib/ai-stack/hybrid/telemetry/hybrid-events.jsonl
  (owned ai-hybrid:ai-stack 0640). aq-agent-loop runs as hyperd (ai-stack group, read-only) → PermissionError
  on every write, silently suppressed by try/except. All agent observability events were dropped — dashboard and
  training_ingest never received agent-loop telemetry. Identified 2026-06-12 by analyzing group permissions.
  Fix: _HYBRID_EVENTS in agent_executor.py redirected to .agents/telemetry/hybrid-events.jsonl (owned hyperd:users
  0644, fully writable). REPO_ROOT env var respected for Nix store compatibility. training_ingest.py already reads
  this path as USER_EVENTS_SPOOL — no ingest changes needed.
  File: ai-stack/local-agents/agent_executor.py (lines 41-46)
  Commit: fix(telemetry): redirect agent event spool to user-writable path

[DONE] dispatch-timeout-env-undocumented — AGENT_WALL_CLOCK_SECS env var documented in .env.example
  Fixed by agent commit 73f8102b.

[DONE] aq-agent-loop/doc-drift — module docstring advertised wrong --max-calls default
  Auto-resolved by pre-commit hook during Phase 165 commit (03e5f950). Docstring line 18
  now reads "[default: 50]" matching argparse default=50.

[DONE] slim-manifest-missing-validate-before-commit — _SLIM_TOOLS in aq-agent-loop excludes validate_before_commit but BEHAVIORAL CONTRACT header says "validate_before_commit MUST pass before git_add"
  Root cause: when build_registry(tool_manifest="self-improvement") unregisters tools not in _SLIM_TOOLS,
  validate_before_commit is removed (it's registered by register_git_tools, not in the frozenset).
  The BEHAVIORAL CONTRACT general rule still tells the model to call it, creating a tool-not-found
  failure on the validation step. STEP 4/5 correctly use run_command as fallback, but the top-level
  rule is inconsistent and will cause model confusion on the first iteration that strictly follows the header.
  Severity: medium
  Action: Add "validate_before_commit" to _SLIM_TOOLS frozenset in scripts/ai/aq-agent-loop (line 70-73).
  One-line change: add "validate_before_commit" to the frozenset. No other files need to change.
  File: scripts/ai/aq-agent-loop lines 70-73 (_SLIM_TOOLS frozenset)
  Resolved: iter 16 model commit 19176f6f (2026-06-12) — Qwen3-35B used edit_file to add "validate_before_commit" to _SLIM_TOOLS. First successful autonomous self-improvement iteration.

## PENDING-REBUILD
[DONE 2026-07-06] SLICE-0 BRING-UP — coordinator /qa/check chain GREEN. The rebuild+switch
activated the 5 staged fixes (mcp_handlers JSON-mode recovery, _aq-qa-bash drop_spec guard,
tool_registry XDG_STATE_HOME, mcp-servers.nix store-path exec glob + ss/proc-net read rules).
VERIFIED: POST /qa/check returns machine JSON (passed 124, failed 0), no more
`parse_error: aq-qa produced empty stdout`. The 6 coordinator-qa-check/* + tool-registry
PENDING-REBUILD items below are flipped to [DONE]. (observability-parity remains open — broader.)
[DONE 2026-07-06] stale-registry-orphan-reconciliation — reaper<->registry gap closed:
aq-agent-reap --reconcile-registry marks status=running rows with dead/absent pid (aged past
AQ_REAP_REGISTRY_AGE_S) as orphaned; atomic rewrite + quiescence guard (refuses live rewrite
while dispatch appends). agent-reap.timer active (every 30min, runs as primaryUser so os.replace
preserves registry ownership). Surfaced by aq-tui-dashboard attention (8 orphans -> 0). Tests 10/10.
Commit 7a8be059. Root cause: reaper only killed processes, never reconciled registry.jsonl.


[DONE] continue-local-injecthints-regression — `aq-qa 0 --machine` failed 0.5.2, 0.5.4, and 0.5.5 after Phase 164G changed `continue-local.injectHints` to true — Root cause: the compact editor/tab lane must remain hint-free; injecting harness hints into `continue-local` breaks Continue config parity and context trimming expectations.
  Severity: high
  Fix: Restored `continue-local.injectHints=false` in the switchboard profile catalog and Python fallback while leaving `local-tool-calling.injectHints=true`; added a regression test; restarted switchboard and verified live `/health` reports `continue_local_injectHints=False`.
  File: config/switchboard-profiles.yaml; ai-stack/switchboard/switchboard.py; scripts/testing/test-switchboard-profile-policy.py

[DONE 2026-07-06] coordinator-qa-check-wrapper-empty-capture — after rebuild, the deployed `aq-qa` wrapper and `_aq-qa-bash` both emitted JSON when run directly, but live `/qa/check` still reported `parse_error: aq-qa produced empty stdout` for the wrapper command — Root cause: unresolved live coordinator capture/scheduler mismatch on the wrapper path; no fresh AppArmor denial was observed, and the direct deployed wrapper produced JSON with failure evidence.
  Severity: high
  Action: Added a JSON-mode recovery path in `run_qa_check_as_dict`: when wrapper stdout is empty, rerun the deployed `_aq-qa-bash` fallback directly and preserve wrapper exit/stderr metadata. Requires NixOS rebuild/switch to activate in the live endpoint.
  File: ai-stack/mcp-servers/hybrid-coordinator/extensions/mcp_handlers.py ~265

[DONE 2026-07-06] coordinator-qa-check-drop-spec-abort — post-rebuild `/qa/check` still returned `parse_error: aq-qa produced empty stdout` after AppArmor denials were resolved — Root cause: `_aq-qa-bash` ran the Phase 85.2 `drop_spec.py` injection probe in an unguarded command substitution under `set -euo pipefail`; when the coordinator subprocess resolved plain `python3` to a thinner system Python without `yaml`, the script exited before `_render_results` emitted JSON. The same PATH drift also made Phase 0 governance tests miss `httpx` and `psutil` inside `/qa/check`.
  Severity: high
  Action: Guarded the `drop_spec.py` probe so import/test failures become normal `CheckResult` rows and added `hybridPython` to the `ai-hybrid-coordinator` service path so child QA probes inherit the coordinator's packaged Python dependencies. Requires NixOS rebuild/switch before live `/qa/check` can use the new service path and patched store source.
  File: scripts/ai/_aq-qa-bash ~1190; nix/modules/services/mcp-servers.nix ~1034

[DONE 2026-07-06] tool-registry-readonly-home-default — `test-local-agent-store-memory-contract.py` failed only inside the coordinator-like environment with `PermissionError: /var/lib/ai-stack/hybrid/.local/share/...` — Root cause: `ToolRegistry()` defaulted its SQLite audit DB under `Path.home()/.local/share`, but coordinator service hardening sets `HOME=/var/lib/ai-stack/hybrid` and does not make that nested home data path writable; existing writable state is exposed through `XDG_STATE_HOME`/`DATA_DIR`.
  Severity: high
  Action: Changed the default audit DB path to prefer `XDG_STATE_HOME` then `DATA_DIR`, preserving the interactive `XDG_DATA_HOME`/home fallback. Requires NixOS rebuild/switch for deployed coordinator subprocesses.
  File: ai-stack/local-agents/tool_registry.py ~46

[DONE 2026-07-06] coordinator-qa-check-store-script-exec-denial — post-switch `/qa/check` advanced past proc-net but still returned `parse_error: aq-qa produced empty stdout` — Root cause: coordinator phase 0 runs from the deployed Nix-store source path, so existing AppArmor exec rules for live-repo `scripts/ai/aqd` did not match `/nix/store/*-source/scripts/ai/aqd`; phase 0 also invokes `git` from Python checks.
  Severity: high
  Action: Added inherited-profile exec rules for `/nix/store/*-source/scripts/ai/{aqd,aq-alerts}` and `/nix/store/**/bin/git`. Requires NixOS rebuild/switch to activate.
  File: nix/modules/services/mcp-servers.nix

[DONE 2026-07-06] coordinator-qa-check-ss-procnet-denial — post-rebuild `/qa/check` still aborted before machine JSON while direct git sync was already clean — Root cause: the new AppArmor exec rule allowed `ss`, but inherited `ai-hybrid-coordinator` confinement denied `ss -tlnp` reads of `/proc/<pid>/net/tcp`, so repeated phase 0 listener probes still failed in the service sandbox. The handler correctly exposed `parse_error: aq-qa produced empty stdout`.
  Severity: high
  Action: Added explicit read rules for per-process net tables used by `ss` (`tcp`, `tcp6`, `udp`, `udp6`, `unix`) and the THP status file also reported by health-spider. Follow-up after rebuild: first patch placed the rules in the dashboard profile block, not `ai-hybrid-coordinator`; moved them into the correct profile. Requires NixOS rebuild/switch to activate.
  File: nix/modules/services/mcp-servers.nix

[DONE 2026-07-06] coordinator-qa-check-empty-json — `/qa/check` returned `qa_result: {}` with empty stdout/stderr while direct `aq-qa 0 --json` produced machine JSON — Root cause: the enforced `ai-hybrid-coordinator` AppArmor profile denied exec for phase 0 probe tools (`ss`, `psql`, `redis-cli`, `getent`) and repo-local `scripts/ai/aqd`; the denied `aqd --version` pipeline ran under `set -euo pipefail`, aborting `_aq-qa-bash` before JSON emission. The coordinator handler also parsed empty stdout as `{}`, hiding the root cause.
  Severity: high
  Action: Added explicit AppArmor exec rules for the phase 0 probe tools, made the `aqd` version probe failure-tolerant, and changed `/qa/check` JSON parsing to report `parse_error: aq-qa produced empty stdout` when subprocess output is empty. Requires NixOS rebuild/switch to activate the profile changes.
  File: nix/modules/services/mcp-servers.nix; scripts/ai/_aq-qa-bash; ai-stack/mcp-servers/hybrid-coordinator/extensions/mcp_handlers.py

[PENDING-REBUILD] observability-parity — Gemini Phase 149 completion claim missed schema drift, raw reasoning leakage, weak QA, dashboard logic gaps, and local-subprocess telemetry coverage — Root cause: implementation added runtime event labels and raw `<think>` extraction without updating the canonical schema/fixture, producing a planning event producer, protecting chain-of-thought, or adding behavior-level QA. The dashboard still lacked acceptable agent logic observability and live telemetry had no thought/planning events before activation. Post-rebuild live smoke also showed the local subprocess delegate branch returns before the HTTP-path telemetry producer in the deployed Nix-store copy.
  Severity: high
  Action: First corrective slice implemented: safe reasoning summary events, raw `<think>` stripping, shared coordinator route-planning events for HTTP and local subprocess paths, schema/fixture repair, dashboard thought/planning filters/rendering, sandboxed HTML previews, and behavioral 0.10.2 QA. Pending rebuild/live smoke and richer dashboard summary tiles.
  File: .agents/plans/OBSERVABILITY-PARITY-CONSENSUS-REVIEW.md

[DONE-2026-06-15] mcp-handlers-repo-root-nix-store — mcp_handlers.py _REPO_ROOT resolved to Nix store at module load — harness_health /qa/check ran aq-qa from Nix store path where git ops fail silently → empty stdout
  Root cause: `_REPO_ROOT = Path(__file__).resolve().parents[4]` at module load resolves to Nix store. `_AQ_QA_SCRIPT` pointed to Nix store copy of aq-qa which re-derives REPO_ROOT from BASH_SOURCE[0] (also Nix store), ignoring env var. NixOS service sets REPO_ROOT=/home/hyperd/Documents/NixOS-Dev-Quick-Deploy but aq-qa ignored it.
  Fix (Phase 177, commit 6ab509c0): (1) mcp_handlers.py: `_REPO_ROOT = Path(os.environ["REPO_ROOT"]) if "REPO_ROOT" in os.environ else Path(__file__).resolve().parents[4]`. (2) aq-qa line 14: `REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"`. (3) _aq-qa-bash same fix. Live after 2026-06-15 rebuild.
  Severity: high → RESOLVED
  Note: /qa/check may still fail post-fix when CPU >= 88°C (THERMAL_SHUTDOWN_C) due to MLFQ thermal protection (see KNOWN-BEHAVIOR below). This is separate from the REPO_ROOT bug.
  File: ai-stack/mcp-servers/hybrid-coordinator/extensions/mcp_handlers.py ~27-31; scripts/ai/aq-qa ~14; scripts/ai/_aq-qa-bash ~11

[KNOWN-BEHAVIOR] mlfq-thermal-shutdown-blocks-qa-check — /qa/check returns "workload rejected by scheduler admission control" when Renoir APU CPU >= 88°C
  Root cause: MLFQ scheduler _admit_snapshot(): `if level == 1 and self._thermal_tier == "shutdown": return False`. `/qa/check` uses `task_class="background"` (level 1). IPM polls hwmon and sets thermal_tier="shutdown" at THERMAL_SHUTDOWN_C=88°C. Renoir APU reaches 94°C during llama.cpp inference. Observed on 2026-06-15 immediately post-rebuild with agent running.
  This is CORRECT BEHAVIOR — prevents aq-qa subprocess adding CPU load during thermal emergency.
  Workaround: run `REPO_ROOT=/home/hyperd/Documents/NixOS-Dev-Quick-Deploy scripts/ai/aq-qa 0 --machine` directly (bypasses coordinator+MLFQ). Only attempt /qa/check when CPU is cool (inference idle).
  Severity: expected — not a bug
  File: ai-stack/mcp-servers/hybrid-coordinator/mlfq_scheduler.py _admit_snapshot (~line 328); ai-stack/mcp-servers/hybrid-coordinator/inference_param_manager.py ~line 157-172

## IN-FLIGHT

[DONE] flat-collaboration-disabled — desired flat model-team workflow was documented but not enabled/enforced — Root cause: `config/local-agent-config.yaml` still had `multi_agent_collaboration: false` and `config/workflow-automation.yaml` still had `collaborative_workflows: false`, while active Gemini/direct paths could write PRD/policy artifacts without proposal, cross-review, consensus, validation-state, or reviewer separation gates.
  Severity: high
  Action: Enabled both collaboration rollout flags, upgraded `aq-flat-prd-gate` so disabled rollout flags fail, blocked same-author cross-review artifacts, and exposed `flat_prd_gate` through tooling-manifest auto-selection for flat model-team / consensus PRD prompts. Validation: `python3 scripts/testing/test-flat-prd-gate.py`, `python3 scripts/testing/test-tooling-manifest.py`, `scripts/ai/aq-flat-prd-gate --machine`, `AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 timeout 120 scripts/ai/aq-qa 0 --machine`.
  File: scripts/ai/aq-flat-prd-gate; scripts/testing/test-flat-prd-gate.py; config/local-agent-config.yaml; config/workflow-automation.yaml; .agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md

## RESOLVED / DONE

[RESOLVED 2026-07-10] codex-state-db-false-fail — aq-qa 0.5.7 intermittently FAILs "unable to open state DB: unable to open database file" while codex runs.
  Root cause / fix notes: aq-report's codex_state_db check opened ~/.codex/state_5.sqlite with mode=ro then plain connect and ran PRAGMA integrity_check. Under an active codex writer (WAL mode), both open modes touch -wal/-shm and can hit a transient lock -> SQLite "unable to open database file" -> FAIL propagates to aq-qa 0.5.7 (and pushes attn alerts, e.g. attn-4f4080ef). The DB was present and fine (verified all open modes succeed when codex idle; integrity=ok). Fix: try immutable=1 FIRST — SQLite reads the raw DB file with no locking or -wal/-shm access, so a live writer cannot block the monitoring read. Falls back to ro then plain. Validated: patched aq-report returns codex_state_db=PASS integrity_check=ok while codex actively running (pid live); aq-qa 0 = 164/0.
  Severity: low-medium (recurring false FAIL + false alerts; masked codex health as degraded)
  File: scripts/ai/aq-report

[RESOLVED 2026-07-10] training-proposal-realert-loop — a rejected training proposal resurfaced as a new HITL alert on every ingest run.
  Root cause / fix notes: training_ingest._push_review_alerts re-pushed an alert for EVERY proposal with status=="pending" on every run, and rejecting the ALERT (attention_queue) never wrote back to the proposal record — so bogus cold-run proposal loop-loop-20260708-224857-0 re-alerted indefinitely (attn-312cd2aa -> attn-5be20760, identical payload). This is alert fatigue that erodes the HITL gate (the G2 rubber-stamp/poison risk). Fix: _push_review_alerts now returns alerted proposal_ids; the CLI marks each status="review_pending" via _mark_proposal so a proposal is surfaced exactly once and drops out of the pending set; the single queued alert persists until the operator acts. Also marked the bogus proposal status="rejected" directly. Validated: run1 needs_review=1 -> mark -> run2 needs_review=0.
  Severity: medium
  Deferred follow-up: wire aq-reject/aq-approve of a training-proposal alert to write review_status back to the proposal record (attention_queue is generic today, no proposal link); a review_pending proposal whose alert expires unacted won't re-alert (discoverable via report/dashboard).
  File: ai-stack/local-agents/training_ingest.py

[RESOLVED 2026-07-10] throughput-calibration-inf-false-fail — aq-qa 0 check 0.10.22 (LOCAL_TOK_PER_SEC calibration) hard-failed on a degenerate metric.
  Root cause / fix notes: test-local-inference-throughput.py reads llamacpp:predicted_tokens_seconds from /metrics; llama.cpp reports `inf` when the last generation's predicted_time rounds to 0ms (short/cached completion). The check guarded None and 0.0 but not inf/nan, so drift=|inf-3.45|/3.45=inf -> false FAIL that blocked the tier0 gate. Fix: treat non-finite measured values (math.isfinite) as SKIP, same as 0.0 — an unmeasurable reading is not a calibration regression. Validated across inf/nan/0 -> SKIP, in-range -> PASS, real >50% drift -> still FAIL.
  Severity: low-medium (false-blocked commits; masked as a throughput regression)
  File: scripts/testing/test-local-inference-throughput.py

[DONE] local-agent/store-memory-contract — Local agent capability test retried `store_memory` because the tool schema advertised `context_type` as note/decision/observation while the coordinator requires canonical memory tiers; `milestone` failed with `memory_store_invalid` before retrying as episodic.
  Severity: medium
  Action: Updated local `store_memory` schema to expose canonical memory tiers, added alias normalization for legacy context labels including milestone->episodic, and added aq-qa/focused-CI coverage as 0.10.14.
  File: ai-stack/local-agents/builtin_tools/ai_coordination.py; scripts/testing/test-local-agent-store-memory-contract.py; scripts/testing/harness_qa/phases/phase0.py; scripts/ai/_aq-qa-bash

[DONE] pre-push/failure-mode-check — `git push` was blocked by quick lint "Known failure-mode checks" after host facts became local-only. Root cause: host defaults still imported ignored `facts.nix` unconditionally, so pure flake source evaluation failed; once fixed, the checker also exposed context-bearing `ExecStart` eval fragility.
  Severity: high
  Action: Made host `facts.nix` imports optional, changed npm security monitor `ExecStart` to `lib.escapeShellArgs`, and updated `check-dryrun-failure-modes.sh` to disable eval-cache and read `ExecStart` via JSON.
  File: nix/hosts/hyperd/default.nix; nix/hosts/nixos/default.nix; nix/hosts/sbc-minimal/default.nix; nix/modules/services/mcp-servers.nix; scripts/testing/check-dryrun-failure-modes.sh

[DONE] agent-memory/state — Raw training-loop outputs and agent state surfaces lacked a single authority registry, letting agents confuse local runtime state, curated memory, RAG facts, old planning summaries, and raw feedback artifacts.
  Severity: medium
  Action: Added `config/agent-memory-surface-registry.json`, documented `docs/operations/agent-memory-state-standard.md`, untracked local training-loop outputs, and wired `scripts/testing/test-agent-memory-surface-registry.py` into aq-qa 0.10.8 plus validation registry.
  File: config/agent-memory-surface-registry.json; docs/operations/agent-memory-state-standard.md; scripts/testing/test-agent-memory-surface-registry.py

[RESOLVED 2026-06-06] aq-report/query-gaps-display — Section "7. Top Query Gaps" showed "No gaps data (Postgres unavailable or table empty)" even when DB had rows, because all rows were suppressed by `_is_curated_stale_gap()`. Root cause: the else branch couldn't distinguish "DB down" from "all filtered." Fix: track `_gaps_raw_count` before the filter pipeline; set `_gaps_all_suppressed = raw_count > 0 and not gaps`; show distinct message in both `format_text()` and `format_md()`. Added `gaps_all_suppressed` kwarg to both formatters (default False).
  Severity: low (display only — no data loss)
  Files: scripts/ai/aq-report ~lines 8100-8106, 6612, 5740

[RESOLVED 2026-06-06] mcp/agent-connectivity — Claude/shared MCP config retained stale external-fetching server entries (`npx`, `nix run github:*`) and a placeholder GitHub token, causing startup-time MCP socket/API failures and noisy model-agent connection errors.
  Severity: high → resolved
  Action: Replaced bootstrap defaults with local `hybrid-coordinator` bridge + `osint-tools`. HM activation now repairs legacy configs (backup + rewrite). Repaired live `~/.mcp/config.json` and Claude settings. Added IDE smoke coverage for unsafe MCP entries. Validation: IDE adapter smoke 19 PASS / 0 FAIL; aq-qa phase 0 87 PASS / 0 FAIL / 3 SKIP. Requires home-manager switch to deploy activation script persistently.
  Files: nix/home/base.nix ~line 1835; scripts/testing/smoke-ide-adapter-compat.sh ~line 150; ai-stack/continue/config.json

[RESOLVED 2026-06-06] local-coding — switchboard local-coding profile deployed. QA 132.1 PASS. Also active: embedded-assist pre-context injection, adaptive query (debug/coding/general), Nix code validation, local-coding routing for implementation archetypes, adaptive embedded-assist.
  Severity: low → resolved
  Files: nix/modules/services/switchboard.nix, scripts/ai/lib/dispatch.py, config/switchboard-profiles.yaml

[RESOLVED 2026-06-03] ci — L5/L6 cognitive intelligence regression test fails on any memory_broker.py change — pytest not in Nix Python env
  Severity: medium (blocks commits that touch memory_broker.py or intent_classifier.py)
  Action: Added require_tool=pytest to cognitive-intelligence-regressions check in validation-check-registry.json. Check now SKIPs (not FAILs) when pytest absent. Long-term: add pytest to Nix Python env package set.
  File: config/validation-check-registry.json (cognitive-intelligence-regressions check)

[DONE] aq-report/delegation — historical delegated prompt failures surfaced as active remediation — `delegated_prompt_failure_windows` showed 0 failures in 1h and 24h, but recommendations and structured actions still emitted active OpenRouter prompt-contract remediation from 7d historical debt.
  Severity: medium
  Action: Wired delegated failure windows into recommendations/actions; historical-only failures now produce passive context and suppress active salvage/action guidance unless failures recur in 24h.
  File: scripts/ai/aq-report ~line 3893; scripts/testing/test-delegated-prompt-failure-history.py

[DONE] planning — Phase 93 PRD under-read Pi observability video context — First pass relied on title/oEmbed and adjacent references after transcript fetch failed, missing the YouTube description's core details: Markdown vs HTML vs visual HTML same-prompt races, useful-token framing, Pi observability event stream/server/DB/UI, swimlane/single-agent/race views, and full tool/system-prompt/token/trace visibility.
  Severity: medium
  Action: Extracted YouTube `shortDescription`, re-ran available agent reviews with the corrected context, amended Phase 93 PRD and parity plans to add Pi-style observability parity gaps and controlled spec-variant race slices.
  File: .agents/plans/EFFECTIVENESS-CENTERED-SYSTEM-IMPROVEMENT-PRD.md; .agents/plans/TECHNICAL-ANALYSIS-PRD.md

[DONE] hints-engine — compatibility wrapper did not re-export underscored filter helpers — `scripts/testing/test-hints-runtime-batch.py` imports `hints_engine` and expects `_is_synthetic_gap` / `_is_curated_stale_gap`; the top-level wrapper used `import *`, which omits underscored names even though `knowledge.hints_engine` exposes the helpers explicitly.
  Severity: low
  Action: Added explicit `_is_synthetic_gap` and `_is_curated_stale_gap` re-exports in `ai-stack/mcp-servers/hybrid-coordinator/hints_engine.py`.
  File: ai-stack/mcp-servers/hybrid-coordinator/hints_engine.py ~line 1

[DONE] aq-report/downshift — continuation downshift recommendation reported stale historical candidates as "recent" — `aq-report` showed 0/14 "recent candidates" even though all candidate events were from 2026-05-24 through 2026-05-27 and no 24h candidate traffic existed. This misrouted operators toward tuning a live downshift gate instead of running a fresh smoke after deploy/rebuild.
  Severity: medium
  Action: Added 24h freshness fields (`candidate_calls_24h`, `downshifted_calls_24h`, `last_candidate_at`, `stale_candidate_window`) and updated recommendations/hints to distinguish stale history from active failures.
  File: scripts/ai/aq-report ~line 1697; ai-stack/mcp-servers/hybrid-coordinator/knowledge/hints_engine_impl.py ~line 2183

[DONE-2026-06-10] dashboard/health-spider — Dashboard AppArmor denials degraded operator visibility while health-spider and auto-remediate did not catch/fix it promptly — Root cause: health-spider only checked `/api/health` every 7200s and auto-remediate only parsed `aq-qa 0`; dashboard passive firewall/status polling also attempted `sudo` reads under AppArmor, creating denial noise.
  Severity: high
  Action: Added dashboard semantic probes to `aq-health-spider`, reduced interval to 900s, removed success attention spam, made auto-remediate run health-spider before aq-qa, disabled sudo for passive firewall reads by default, and added `/proc/@{pids}/stat r,` AppArmor rule. Run `sudo nixos-rebuild switch --flake .#hyperd-ai-dev` to activate service/AppArmor/dashboard code.
  File: scripts/ai/aq-health-spider ~line 77; scripts/automation/auto-remediate.sh ~line 16; dashboard/backend/api/routes/firewall.py ~line 54; nix/modules/services/mcp-servers.nix ~line 1737

[DONE] cli-contract — documented machine/query flags rejected by local CLIs — `aq-report --machine` and `aq-hints --query ...` were documented workflow forms but argparse rejected them, blocking machine-mode parity and copied quick-start commands. Added compatibility aliases.
  Severity: medium
  Action: Added `--machine` as JSON alias in `scripts/ai/aq-report` and `--query` alias in `scripts/ai/aq-hints`; validate with CLI smoke commands and Python compile.
  File: scripts/ai/aq-report ~line 200; scripts/ai/aq-hints ~line 165

[RESOLVED 2026-05-31] workspace-isolation — cleanup_workspace() requires force=True for active workspaces — `WorkspaceManager.cleanup_workspace()` returns False and logs "Cannot cleanup active workspace" unless `force=True` is passed. Default cleanup in integration tests silently fails.
  Severity: low (no data loss; worktrees accumulate in /tmp/aq-worktree-test until manually cleared)
  Action: Pass `force=True` in cleanup calls, or add auto-deactivate before cleanup. File: ai-stack/orchestration/workspace_isolation.py
  File: ai-stack/orchestration/workspace_isolation.py (cleanup_workspace method)

[RESOLVED 2026-06-07] cross-project-contamination — mcp-bridge-hybrid workflow tools (retrofit, primer, brownfield, project-init) ran with cwd=REPO_ROOT, so --target . resolved to the NixOS harness root instead of the calling agent's project directory. Gemini CLI working in a fresh MakerSpace repo called aqd workflows retrofit --target . and polluted: .claude/CLAUDE.md (template reset), .agents/plans/README.md, .agent/commands/, .agent/PROJECT-PRD.md, .agent/GLOBAL-RULES.md, .agent/workflows/*.json, session-primer-summary.json.
  Severity: high (corrupts harness scaffolding silently; cross-project data contamination)
  Root cause: _run_local(argv) defaults cwd=REPO_ROOT; relative targets resolve to harness root not client CWD
  Fix: _resolve_workflow_target() normalizes target_dir to absolute path; all four workflow handlers now pass cwd=abs_target to _run_local; REPO_ROOT overlap triggers strong warning in tool response
  Files: scripts/ai/mcp-bridge-hybrid.py (Phase 136)
  Pattern: External agents MUST pass target_dir as absolute path; never --target . from a remote client

[RESOLVED 2026-06-02] workflow — aq-session-start (and 8 others) missing from Codex/agent shell PATH — aiHarnessCliWrappers in ai-stack.nix did not include aq-session-start, aq-resume, aq-insights, aq-commit-facts, aq-skill-suggest, aq-alerts, aq-approve, aq-reject, aq-integrity-scan.
  Action: Added all 9 wrappers to aiHarnessCliWrappers (Phase 100.1). Requires nixos-rebuild to activate.
  File: nix/modules/roles/ai-stack.nix ~line 439

[RESOLVED 2026-05-30] ai_coordinator_delegate P95=244s — ceiling is enforced at ai_coordinator.py:706 (_LOCAL_MAX_TOKENS_HARD_CEILING=180). P95=244s is hardware-bound: 180 tok × ~1.35 tok/s on Renoir APU. Not a code bug. Anti-loop guardrails (repeat_penalty=1.08, repeat_last_n=64) confirmed in dispatch.py:79-80. No fix needed.

[DONE] observability — aq-report framed healthy hardware-bound delegate latency as generic cache/connection/model tuning — `ai_coordinator_delegate` P95 around 244s matches the local delegated-response token ceiling on current hardware, but the slow-tool recommendation implied a software tuning defect.
  Severity: low
  Action: Added delegate-specific latency contextualization and regression coverage so healthy high-P95 delegate calls point to bounded prompts/max_tokens rather than cache or connection-pool work.
  File: scripts/ai/aq-report ~line 4395

[DONE] delegation — local-tool-calling was excluded from coordinator local slot-busy retry — recent delegate 500s traced to transient local backend unavailability around `local-tool-calling`; coordinator local HTTP retry logic covered default/continue-local/embedded-assist but not local-tool-calling, and raised before the local_slot_busy wrapper could inspect 503 responses.
  Severity: medium
  Action: Return local_slot_busy 503 responses to the bounded retry wrapper before `raise_for_status`, include `local-tool-calling` in retryable local profiles, and refresh stale delegate static regressions to the current extension/workflow paths.
  File: ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py ~line 1467

[DONE] deploy — quick deploy interactive model prompt blocked non-interactive automation — `./nixos-quick-deploy.sh` preflight passed but deployment stopped at `read -r new_chat_key` because Phase 1 model selection prompted on non-interactive stdin.
  Severity: medium
  Action: Added documented `--skip-model-selection` flag and `SKIP_MODEL_SELECTION=true` env support to keep current facts.nix model choices during automated deploys.
  File: nixos-quick-deploy.sh ~line 70

[RESOLVED 2026-06-03] role-enforcement — AGENT_TYPE_ELIGIBLE_ROLES never validated at dispatch — Phase 58A.5 implemented: ineligible role assignments are now clamped to the agent_type default in LocalAgentExecutor.execute_task(). Logs warning on clamp. 6/6 regression tests pass.
  Action: Added eligibility check after auto-assign in execute_task(); added test-agent-executor-role-eligibility.py; registered in validation-check-registry.json.
  File: ai-stack/local-agents/agent_executor.py ~line 356; scripts/testing/test-agent-executor-role-eligibility.py

[RESOLVED 2026-06-03] role-enforcement — no reviewer_id tracking, self-review prevention aspirational — Role-matrix.md §8 states "a reviewer may not review their own work" but no reviewer_id field exists in Task/TaskConfig; self-review cannot be enforced at runtime.
  Severity: low → resolved
  Action: Phase 104 — added reviewer_id: Optional[str] = None to Task dataclass; execute_task() logs WARNING when reviewer_id == assigned_agent. Advisory check (no block) — orchestrator is responsible for not assigning self-reviews. 6/6 regression tests pass.
  File: ai-stack/local-agents/agent_executor.py ~line 140
  Test: scripts/testing/test-agent-executor-reviewer-id.py

[RESOLVED 2026-06-06] role-enforcement — domain-role eligibility not validated at task dispatch — DOMAIN-ROLE-MATRIX.md defines which agents may fill which roles per domain, but no enforcement exists at dispatch. Cross-domain mis-routing (e.g., Gemini as security reviewer for its own security implementation) is doc-only blocked.
  Action: Phase 132 — added _DOMAIN_ROLE_RESTRICTIONS table + validate_role_eligibility() to core/domain_router.py. Enforcement injected into handle_ai_coordinator_delegate() after profile selection. Security domain: Gemini blocked as reviewer, redirected to local fallback. 8/8 unit tests pass.
  Files: core/domain_router.py, extensions/ai_coordinator_handlers.py, tests/test_domain_role_enforcement.py
  Severity: low (policy gap, not immediate production risk)
  Action: Long-term: pass domain_shell in TaskConfig and validate against DOMAIN-ROLE-MATRIX at dispatch. Immediate: document constraint in delegation prompts.
  File: .agent/DOMAIN-ROLE-MATRIX.md (new), ai-stack/mcp-servers/coordinator/agent_executor.py

[RESOLVED 2026-06-02] hardware — CPU thermal tier = critical persistent (Renoir APU Tctl 81°C) — MLFQ level-2 (batch task class) was permanently blocked because _determine_thermal_tier() used a hardcoded critical threshold of 80°C and Renoir APU Tctl sensor reads ~81°C at idle.
  Severity: medium → resolved
  Action: Phase 99.1 — raised critical threshold from 80→83°C, warn from 70→73°C. Added THERMAL_CRITICAL_C / THERMAL_WARN_C / THERMAL_SHUTDOWN_C env var overrides. Shutdown stays at 88°C (safety boundary). 6/6 regression tests pass.
  File: ai-stack/mcp-servers/hybrid-coordinator/inference_param_manager.py ~line 155
  Test: scripts/testing/test-ipm-thermal-thresholds.py

[RESOLVED 2026-06-03] coordinator — circuit breaker trips logged but not surfaced to operator attention queue — core/circuit_breaker.py and shared/circuit_breaker.py both logged a warning on _trip() but never pushed to the attention queue, making silent qdrant/postgres/llm outages invisible to operators until they checked logs manually.
  Severity: medium → resolved
  Action: Phase 101 — added attention_queue.push(auto_ok, high) in both _trip() implementations; added ATTENTION_QUEUE_DIR env var override in attention_queue.py (Nix store path safety); wired ATTENTION_QUEUE_DIR + scripts/ai/lib into coordinator PYTHONPATH in mcp-servers.nix. 6/6 regression tests pass. Requires nixos-rebuild switch.
  File: scripts/ai/lib/attention_queue.py ~line 41; ai-stack/mcp-servers/hybrid-coordinator/core/circuit_breaker.py ~line 104; ai-stack/mcp-servers/shared/circuit_breaker.py ~line 228; nix/modules/services/mcp-servers.nix ~line 1302
  Test: scripts/testing/test-attention-queue-env-override.py

[RESOLVED 2026-06-03] coordinator — qdrant_upsert_failed TypeError on skills-patterns indexing — continuous_learning.py _upsert() inner function used `return await self.qdrant.upsert(...)` but server.py passes the sync QdrantClient whose upsert() returns UpdateResult directly (not a coroutine). Caused `TypeError: object UpdateResult can't be used in 'await' expression` on every _index_patterns() call, silently dropping all Qdrant pattern indexing.
  Severity: medium (learning pipeline silently non-functional)
  Action: Removed spurious `await`; _upsert() now calls self.qdrant.upsert() directly. 2/2 regression tests pass.
  File: ai-stack/mcp-servers/hybrid-coordinator/extensions/continuous_learning.py ~line 1231
  Test: scripts/testing/test-continuous-learning-qdrant-upsert.py

[DONE] dashboard/app-armor — dashboard GPU metrics triggered a live AppArmor denial after rebuild — `lspci` could execute but could not open `/sys/bus/pci/devices/`, so the dashboard process still emitted kernel audit denials even after the passive firewall sudo fix was active.
  Severity: medium
  Action: Added explicit `/sys/bus/pci/devices/` and `/sys/bus/pci/devices/**` read coverage to the `command-center-dashboard-api` profile; restart/rebuild required for live activation.
  File: nix/modules/services/mcp-servers.nix ~line 2609

[DONE] rebuild-watch — activation exposed auto-remediate PRSI CLI drift, tmpfiles unsafe transitions, and dashboard AppArmor `/tmp/` denial noise — Root causes: `auto-remediate.sh` called removed `prsi-orchestrator.py queue`; tmpfiles repaired `/var/lib/nixos-ai-stack` after processing child paths and kept `/var/log/nixos-ai-stack` user-owned while service-owned child logs live under it; dashboard AppArmor allowed `/tmp/*.db` but not `/tmp/` directory reads; health-spider counted already-covered AppArmor denials as unresolved.
  Severity: high
  Action: Repo fixes applied and user rebuild activated the previous Nix/AppArmor/service-copy changes. auto-remediate uses `prsi-orchestrator.py cycle`; tmpfiles parent repair is ordered before child paths and AI log parent is `root:ai-stack`; dashboard profile allows narrow `/tmp/ r,`; health-spider returns cleanly when apparmor-fix-agent reports all paths already covered.
  File: scripts/automation/auto-remediate.sh; scripts/ai/aq-health-spider; nix/modules/core/base.nix; nix/modules/services/mcp-servers.nix; scripts/testing/test-boot-stability-regressions.py

[DONE] collaboration-state — Gemini resumed Phase 148 with useful direct edits but wrote malformed RESUME.json — Root causes: duplicate JSON keys, missing comma in todo_snapshot, and completion claims not matched by validation evidence made `aq-resume`/JSON tooling fail during handoff review.
  Severity: medium
  Action: Repaired RESUME.json as valid JSON, validated Gemini's code diff, tightened multi-document YAML loaders, and added static regression coverage for aq-chat no-think and YAML loader contracts.
  File: .agent/collaboration/RESUME.json; scripts/testing/test-local-agent-config.py

[DONE] agentic-standardization — Phase 148 repo fixes needed activation — Root cause: switchboard/service code runs from the Nix store; repository edits to `ai-stack/switchboard/switchboard.py`, config mirrors, and aq-qa wrapper were validated in repo but did not affect live services until rebuilt.
  Severity: medium
  Action: User rebuilt after commit df78604a. Post-rebuild validation passed: no failed units, aq-health-spider clean, payload discipline gate clean, aq-qa 0 --machine 94/0/2.
  File: ai-stack/switchboard/switchboard.py; scripts/ai/aq-chat; scripts/testing/harness_qa/phases/phase0.py

[DONE] coordinator-routing — continuation tasks routed to local-tool-calling instead of canonical default lane — Root cause: route_by_complexity() had a continuation override that converted continuation/general tasks to embedded-assist/local-tool-calling behavior under prefer_local, violating the existing continuation test contract and cross-agent compact-default lane expectation.
  Severity: medium
  Action: Patched continuation/general local routing to `default`; user rebuilt commit a23e1e24 and `aq-qa 0 --machine` passed 96/0/0.
  File: ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator.py ~line 604

[DONE] post-deploy-converge — focused CI artifact step could not find git in systemd PATH — Root cause: ai-post-deploy-converge.service path omitted `pkgs.git`, while run-focused-ci-checks.sh calls `git diff` to select changed files.
  Severity: medium
  Action: Live unit inspection after rebuild showed the first patch added `git` to ai-npm-security-monitor, not ai-post-deploy-converge. Corrected the actual post-deploy service path in repo, committed eeb47e49, rebuilt, and verified rendered PATH includes `/nix/store/...-git-2.51.2/bin`; no failed units, aq-alerts count 0, aq-qa 0 --machine 94/0/2 with report-backed checks skipped, aq-health-spider clean.
  File: nix/modules/services/mcp-servers.nix ~line 2016

[DONE] aq-chat-rendering — local aq-chat printed one token per line, making answers unreadable — Root cause: aq-chat defaulted to the switchboard `local-tool-calling` lane but flipped the payload back to `stream=True`; switchboard only executes the local tool loop for non-streaming local-tool-calling requests, so aq-chat consumed and printed raw SSE deltas exactly as emitted.
  Severity: medium
  Action: Keep local-tool-calling `stream=False`, consume the completed JSON response with `self.client.post()`, and render the final assistant content once through the Markdown renderer. Added static regression coverage and live switchboard smoke returned normal content `AQ_CHAT_RENDER_OK`.
  File: scripts/ai/aq-chat ~line 160; scripts/testing/test-aq-chat-local-tool-profile.py

[DONE] aq-chat-grounding — local aq-chat exhausted tool budget and recommended stale/false system fixes — Root cause: operational recommendation prompts were delegated to the model's local tool loop, so failures in individual tools or repeated tool calls were treated as current system facts and the answer could recommend rebuilds despite a clean live system.
  Severity: medium
  Action: Added deterministic local preflight snapshots for improvement/health/status prompts, bypassed the local tool loop when snapshot evidence is available, required answers to use only snapshot evidence for current-state claims, and bounded snapshot-grounded responses at 1024 tokens. Live non-interactive aq-chat smoke produced a bounded answer with no tool-budget exhaustion.
  File: scripts/ai/aq-chat ~line 45; scripts/testing/test-aq-chat-local-tool-profile.py

[DONE] aq-chat-brief — operators needed a deterministic local health brief without waiting on model inference — Root cause: aq-chat only exposed model-mediated operational recommendation prompts, so even simple current-state checks could spend local inference/tool budget.
  Severity: medium
  Action: Added `/brief`, reusing the trusted local preflight checks and rendering a concise Rich table without llama, switchboard, or hybrid calls. Static tests assert command registration, routing, and renderer presence.
  File: scripts/ai/aq-chat ~line 46; scripts/testing/test-aq-chat-local-tool-profile.py

[DONE] aq-chat-interrupt — Ctrl-C during an in-flight local request dumped an async traceback — Root cause: cancellation/keyboard interrupt handling was only scoped to the prompt loop, not the active inference request path.
  Severity: medium
  Action: Added explicit cancellation/KeyboardInterrupt handling so interrupted in-flight turns print a concise interruption message instead of a traceback.
  File: scripts/ai/aq-chat ~line 312

[DONE] aq-chat-tool-free — explicit "do not call tools" spec prompts still entered the slow local tool path — Root cause: local profile defaulted to switchboard local-tool-calling unless deterministic snapshot grounding was active.
  Severity: medium
  Action: Added an explicit tool-free/spec prompt detector that routes those turns directly to raw local inference with no tool calls, no live-state claims, `enable_thinking=false`, and a 1024-token bounded response budget.
  File: scripts/ai/aq-chat ~line 95

[DONE] local-delegation-artifact — delegate-to-local reported a task id and output path that could not be found afterward — Root cause: dispatch.py registered the task inside dispatch_task(), so an OOM-kill or import crash before that point left the ID unreachable. Phase 159 fix: pre-register in main() before dispatch_task(), add pre_registered=True guard to skip duplicate write.
  Severity: high
  Action: Moved registry.append()/record_dispatch() to main() before dispatch_task(); added pre_registered param to dispatch_task(); added aq-qa 0.10.9 regression coverage.
  File: scripts/ai/lib/dispatch.py; scripts/testing/test-local-delegation-artifact.py

[DONE] health-spider-systemd-coverage — aq-health-spider returned clean while `nix-optimise.service` was failed — Root cause: health-spider only checked declared HTTP zones and their service state on HTTP failure, so unrelated failed systemd units were invisible to the spider/dashboard health path.
  Severity: high
  Action: Added a global `systemctl --failed --no-legend --no-pager` probe that emits telemetry/attention and makes `aq-health-spider --once` fail when failed units exist. Inspected the live `nix-optimise.service` error (`missing ...coffeescript-2.7.0-npm-deps.drv`), reset the stale failed state, rejected the now-cleared attention item with evidence, and revalidated `systemctl --failed`, `aq-alerts --count`, `/brief`, and `aq-health-spider --once` as clean.
  File: scripts/ai/aq-health-spider; scripts/testing/test-boot-stability-regressions.py

[DONE-2026-06-11] software-factory-readiness — Resolved by Phase 150-153: CandidateLifecycleManager state machine, trust scoring engine, eval sandbox, aq-review CLI, aq-propose, dashboard /api/aistack/candidate-pipeline, and 108/108 QA checks. 14 candidates scored and active in pipeline.
  File: .agents/plans/WORLD_CLASS_SOFTWARE_FACTORY_READINESS_RESEARCH.md

## Software Factory Readiness Gaps (Phase 150)

- [ ] **Candidate Siloing:** Knowledge sources imported via `sync-knowledge-sources` are stored in AIDB but do not automatically surface as candidates in `candidates.json`.
- [ ] **Lack of Eval Sandbox:** No restricted runtime environment exists to safely test new tools or models before adoption.
- [ ] **Manual Scoring:** Trust and relevance scoring for new tools/research is currently human-mediated and non-deterministic.
- [ ] **Disconnected Governance:** Proposal and review workflows for candidates are not linked to the candidate lifecycle state.
- [ ] **Dashboard Invisibility:** The candidate pipeline (proposed -> evaluated -> adopted) is not visible to operators in the Command Center.
- [ ] **Stale Model Catalog:** The model catalog remains a static Python file, disconnected from the research discovery loop.
- [ ] **Missing Trust Provenance:** Knowledge in AIDB lacks a clear trust-tier and license-posture metadata that can drive autonomous decision-making.

[DONE] model-catalog-freshness — local model catalog is static and likely stale for current model velocity — Root cause: `ai-stack/mcp-servers/shared/model_catalog.py` contains hardcoded model specs and `config/model-profile.json` had a last-updated/probed timestamp but no freshness gate that forces review when model catalogs, local GGUF, or provider model capabilities drift.
  Severity: medium
  Action: Added catalog/profile freshness metadata, dashboard `/api/models.freshness`, Model Lifecycle freshness rows, focused CI coverage, and aq-qa 0.10.5; refreshed discovery candidates so stale model-catalog work no longer appears after validation.
  File: ai-stack/mcp-servers/shared/model_catalog.py; config/model-profile.json; dashboard/backend/api/routes/models.py; assets/dashboard.js; scripts/testing/test-model-catalog-freshness.py

[DONE] discovery-agent-stub — proactive discovery agent was not doing opportunity analysis yet — Root cause: `ai-stack/local-agents/discovery_agent.py` declared `discover_opportunities()` but only logged and `pass`ed, so idle discovery could not surface query gaps, routing failures, tokenomics regressions, or research candidates as actionable work.
  Severity: medium
  Action: Implemented deterministic local-signal scanner that emits dashboard-compatible `.agents/improvement/candidates.json` from issues backlog, health-spider events, delegation feedback, and stale model-profile metadata. Added focused regression coverage, focused-CI registry entry, and aq-qa 0.10.4.
  File: ai-stack/local-agents/discovery_agent.py

[DONE] agent-artifact-distribution — local day-to-day agent artifacts are tracked as repo state — Root cause: live collaboration, attention, delegation, comms, telemetry, and host facts files were tracked, so new deployments could inherit stale locks, local routing history, active-session context, and host-specific hardware facts.
  Severity: high
  Action: Added distribution policy, local-only ignore rules, collaboration templates, and aq-qa/focused-CI gate 0.10.7; untracked local runtime artifacts and host facts with `git rm --cached` while preserving local copies.
  File: .gitignore; docs/operations/agent-artifact-distribution-policy.md; scripts/testing/test-agent-artifact-policy.py

[DONE] dashboard-logic-discipline-no-data — Logic Discipline tile reported 100% without backend metric — Root cause: `assets/dashboard.js` used `analytics.logic_discipline_rate ?? 100` while `/api/insights/routing/analytics` did not produce `logic_discipline_rate`, hiding missing telemetry and making the error threshold unreachable (`<90` warning checked before `<70` error).
  Severity: high
  Action: Added backend `logic_discipline` summary from delegation-feedback JSONL, exposed nullable `logic_discipline_rate`, rendered `--` on missing data, made the `<70` error threshold reachable, and verified live `/api/insights/routing/analytics` returns sample/failure/score telemetry.
  File: dashboard/backend/api/services/ai_insights.py; assets/dashboard.js; dashboard.html

[DONE] manual-rebuild-source-backed-dashboard-reload — manual `nixos-rebuild switch` left command-center-dashboard-api serving stale repo-backed Python code until an explicit privileged restart — Root cause: the dashboard API unit runs from the repo path, so source-only backend edits are not activated by a plain NixOS switch unless the unit is restarted; unprivileged `systemctl start/reset-failed` can also hang on authorization.
  Severity: medium
  Action: Added a health-spider semantic routing-analytics probe with required `logic_discipline` keys so stale dashboard backends are detected as degraded, surfaced to attention/telemetry/RAG, and validated by boot-stability regression coverage. Manual source-only backend edits still require privileged service restart for activation.
  File: nix/modules/services/command-center-dashboard.nix; nixos-quick-deploy.sh; scripts/ai/aq-health-spider

[DONE-2026-06-11] token-usage-coverage-gap — coordinator token_usage events had null token counts (19/378 = 5% coverage) — Root cause: `body.get("usage")` omits the usage block for streaming/SSE responses; token counts defaulted to 0 then None. Additionally, no model_call event was emitted by the coordinator (only planning + token_usage), causing cross-source metric mismatch with race-harness model_call events.
  Severity: medium
  Action: Phase 149 fix in ai_coordinator_handlers.py: (1) emit model_call event per delegation with estimated tokens (char_count//4 fallback); (2) token_usage now uses same fallback — no_data_reason="estimated" when API omits usage block. Added aq-qa check 0.10.2 + test-token-usage-coverage.py measuring coordinator model_call token coverage ≥50%. Requires coordinator service restart to activate.
  File: ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py

[DONE] aq-alerts-json-contract — `aq-alerts --json` printed the human table instead of machine-readable JSON — Root cause: the CLI usage and downstream agent workflow expected JSON, but `scripts/ai/aq-alerts` had no `--json` argparse option and always rendered the table unless `--count` was used.
  Severity: medium
  Action: Added `--json` output with `{pending, alerts}` and regression coverage using an isolated `ATTENTION_QUEUE_DIR`.
  File: scripts/ai/aq-alerts; scripts/testing/test-aq-alerts-json.py

[DONE] local-subprocess-instruction-discipline — local coordinator delegate ignored exact-output instruction during smoke, then first remediation disabled capabilities too broadly — Root cause: `/control/ai-coordinator/delegate` with `profile=local-tool-calling`, `max_tokens=32`, and task "Return exactly PLANNING_SMOKE_OK" originally returned meta-reasoning text instead of the requested literal. Gemini's first Phase 150 fix forced `tools_enabled=false` and `thinking_mode=off` for all exact-output tasks, which made the smoke pass by trimming capabilities; follow-up commit 173b5f50 restored exact-output tool/reasoning capability unless the task is explicitly tool-free.
  Severity: medium
  Action: Hardened 0.10.3 to assert exact-output tasks do not disable tools/thinking unless explicitly tool-free; wired dashboard logic-discipline metric to delegation-feedback telemetry instead of defaulting missing data to 100%; rebuilt, restarted dashboard API with sudo, and verified live smoke plus aq-qa 0.
  File: ai-stack/agents/runtimes/local_agent_runtime.py; ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py

[DONE] health-spider-dashboard-semantic-coverage — dashboard showed operator-visible degradation while aq-health-spider reported clean cycles — Root cause: the spider only probed broad dashboard endpoints and did not validate the specific card payload semantics for OSI layer readiness, RAGAS faithfulness, operator audit integrity, or degraded child service statuses inside aggregate health.
  Severity: high
  Action: Added dashboard semantic probes for `/api/health/layered`, `/api/eval/trend`, `/api/audit/operator/integrity`, and child statuses in `/api/health/aggregate`; added regression coverage so enabled faithfulness with missing/zero values, OSI 0/0 pending, unsealed audit chains, and degraded service children surface as `dashboard_degraded` alerts.
  File: scripts/ai/aq-health-spider; scripts/testing/test-boot-stability-regressions.py

[DONE] switchboard-health-metrics-blocking — dashboard aggregate marked ai-switchboard degraded while switchboard `/health` returned 200 — Root cause: switchboard `/health` synchronously included optional llama.cpp `/metrics`, which can block behind active local inference for ~4s and exceed the dashboard aggregate probe budget.
  Severity: medium
  Action: Changed switchboard `/health` to use a sub-second optional metrics probe while preserving immediate semaphore/active-request telemetry; added regression coverage.
  File: ai-stack/switchboard/switchboard.py; scripts/testing/test-boot-stability-regressions.py

[DONE] dashboard-osi-aq-qa-opaque-exit — OSI layer health stayed pending and dashboard logs only reported `aq-qa exited 126` — Root cause: dashboard `qa_runner.py` discarded stdout/stderr for unexpected aq-qa exit codes, making service confinement/environment failures impossible to diagnose from logs.
  Severity: medium
  Action: Include stderr/stdout snippets in unexpected aq-qa RuntimeError messages and cover the diagnostic contract in boot-stability regression checks. Direct host `aq-qa 0 --json` passes, while dashboard service execution used `/run/current-system/sw/bin/aq-qa`; added the exact AppArmor ix rule for that symlink path. Requires rebuild to validate live OSI cache population.
  File: dashboard/backend/api/services/qa_runner.py; nix/modules/services/mcp-servers.nix; scripts/testing/test-boot-stability-regressions.py

[DONE] ragas-faithfulness-null-render — dashboard rendered RAGAS faithfulness as `0.0%` when faithfulness scoring produced no non-null samples in the latest trend window — Root cause: `/eval/trend` exposed total eval `sample_count` but not non-null faithfulness sample count, so the frontend could not distinguish "0 score" from "not scored / unavailable".
  Severity: medium
  Action: Added `faithfulness_sample_count` to global and per-model RAGAS trend output, rendered faithfulness as `N/A` when no faithfulness samples exist, and made health-spider alert on enabled scoring with `faithfulness_sample_count=0`.
  File: ai-stack/mcp-servers/hybrid-coordinator/eval_runner.py; assets/dashboard.js; scripts/ai/aq-health-spider; scripts/testing/test-ragas-faithfulness-guard.py

[DONE] aq-approve-apparmor-already-committed — approving an AppArmor alert after manually committing the proposed rule failed instead of resolving the alert — Root cause: `aq-approve` always delegated to `apparmor-fix-agent --commit-staged`, and the fixer tried to `git add` ignored `.agent/collaboration/HANDOFF.md`, violating the local-artifact ignore policy.
  Severity: medium
  Action: `aq-approve` now resolves AppArmor alerts when all proposed rules are already present in `mcp-servers.nix`; `apparmor-fix-agent` only stages `HANDOFF.md` when it is not ignored or is already tracked.
  File: scripts/ai/aq-approve; scripts/automation/apparmor-fix-agent.py; scripts/testing/test-boot-stability-regressions.py

[DONE] dashboard-osi-runner-shebang-and-empty-json — dashboard OSI layer showed 0/0 pending after rebuild — Root cause: the dashboard ran `aq-qa` through the system wrapper, which re-entered the repo script via `/usr/bin/env` under AppArmor; later failures returned empty stdout with truncated JSON errors.
  Severity: high
  Action: Dashboard `qa_runner.py` now prefers the Python `harness_qa/main.py` entrypoint, keeps bash `aq-qa` only as fallback, and reports empty/non-JSON subprocess output with exit/stderr detail. Live `/api/health/layered` now populates layers instead of staying blank.
  File: dashboard/backend/api/services/qa_runner.py; scripts/testing/harness_qa/core/context.py; scripts/testing/test-boot-stability-regressions.py

[DONE] ragas-faithfulness-all-null — RAGAS trend had `faithfulness_enabled=true`, 100 eval rows, and `faithfulness_sample_count=0` — Root cause: enabled faithfulness returned `None` whenever the expensive local judge was not sampled, failed, timed out, or produced unparsable output.
  Severity: medium
  Action: Added bounded lexical grounding fallback for non-sampled or failed judge rows while preserving the empty-context modal guard; live dashboard trend now shows `faithfulness_sample_count=1` after a fresh retrieval query.
  File: ai-stack/mcp-servers/hybrid-coordinator/eval_runner.py; scripts/testing/test-ragas-faithfulness-guard.py

[DONE] apparmor-profile-reload-bpf-oom — `nixos-rebuild switch` activated services but returned exit 4 while reloading AppArmor — Root cause: `apparmor_parser` failed replacing `ai-hybrid-coordinator` with kernel/BPF `Out of memory` (`error=-12`), likely due profile size/complexity rather than system RAM exhaustion.
  Severity: high
  Fix (Phase 168): consolidated 27 per-tool `/nix/store/**/bin/<tool> ix` rules into 2 patterns (`/nix/store/**/bin/* ix` + `/nix/store/**/sbin/* ix`). Reduces BPF program instruction count significantly. Security preserved via deny rules (no network egress, no home writes, no privileged caps).
  Requires rebuild: YES
  File: nix/modules/services/mcp-servers.nix

[DONE] dashboard-osi-confined-runner-false-failures — `/api/health/layered` now populates without reporting dashboard confinement artifacts as host health failures — Root cause: host-level phase-0 checks executed inside `command-center-dashboard-api` AppArmor and hit denied `psql`, `redis-cli`, Continue config, tempdir, and CLI probes.
  Severity: medium
  Fix: Added `AQ_QA_DASHBOARD_SAFE` mode so dashboard OSI skips host-only probes before spawning AppArmor-denied subprocesses; added dashboard runner normalization as a fallback and blocked apparmor-fix-agent from proposing one-off `/tmp/<random>` mknod rules.
  File: dashboard/backend/api/routes/health.py; dashboard/backend/api/services/qa_runner.py; scripts/testing/harness_qa/phases/phase0.py; scripts/automation/apparmor-fix-agent.py

## DEFERRED — requires hardware, external investigation, or multi-phase project work
## (not valid targets for grep-[OPEN] self-improvement slices)

[DEFERRED] hardware — ROCm not available on Renoir APU (gfx90c) — no code fix possible
  Severity: info (hardware constraint)
  Note: ACCELERATE PRD assumed ROCm. Renoir iGPU (gfx90c) not a supported ROCm target.
  rocminfo absent. llama-cpp runs Vulkan only. Baseline 2.71 tok/s.
  Action: requires discrete RDNA2+ GPU. Deferred until hardware upgrade.

[DEFERRED] agentic-mind — cross-model workflow standardization — multi-phase PRD project
  Severity: high (but requires Phase 148 envelope + corpus + evaluator — not a slice fix)
  Action: defer to dedicated phase. References: .agent/PROJECT-AGENTIC-MIND-STANDARDIZATION-PRD.md

[DEFERRED] desktop-input — post-build cursor/text input instability (gens 697-700, Jun 8)
  Severity: high (but gen 701, Jun 10, appears stable — may be self-resolved by rebuild)
  Action: pre-rebuild checklist: close VSCodium, capture journalctl -u cosmic-session,
  compare ~/.config/cosmic/ shortcut configs between generations.
  Note: gen 701 stable; defer until next rebuild shows regression.

[DONE] stagnation-detect-varied-loop — agent burned 50 calls on hardware issue with no progress; stagnation not triggered because varied run_command commands changed result prefix
  Root cause: iter 12 picked [OPEN] hardware (first in file, now DEFERRED), tried .agent/PROJECT-ACCELERATE-PRD.md
  (not found), then varied grep/find/ls patterns 40+ times. Each command was slightly different,
  resetting the ring buffer. Same file returned ok=False 3+ times across 50 calls.
  Fix: Added _failed_reads dict to agent_executor execute_task loop. If the same read_file path
  returns ok=False >= 3 times in a session, abort with "File-not-found stagnation" message.
  File: ai-stack/local-agents/agent_executor.py (_failed_reads dict + FAILED_READ_LIMIT check)

[DONE] aq-chat-local-tool-execution-parity — aq-chat printed pseudo tool calls and then hit 502 on follow-up instead of using the delegated local runtime — Root cause: the local chat path mixed Switchboard/OpenAI payloads with coordinator delegation and omitted the canonical `task` field expected by `/control/ai-coordinator/delegate`.
  Severity: high
  Fix: Routed local/local-tool-calling aq-chat turns through coordinator delegation with `task`, preserved messages, disabled Qwen thinking mode, added backend error detail, and added live dashboard OSI grounding to prevent stale status claims.
  File: scripts/ai/aq-chat; scripts/testing/test-aq-chat-local-tool-profile.py

[DONE] aq-chat-payload-discipline-gate-drift — local payload discipline gate stopped scanning aq-chat — Root cause: a prior edit added `--exclude="aq-chat"` despite the gate including extensionless aq-chat scripts.
  Severity: high
  Fix: Removed the exclusion and kept the local no-think contract covered by focused config and payload gate tests.
  File: scripts/testing/gate-local-payload-discipline.sh; scripts/testing/test-local-agent-config.py

[DONE] delegate-timeout-cascade-single-local-slot — Effectiveness scorecard failed because overlapping local delegates timed out on a single llama.cpp slot — Root cause: coordinator subprocess path spawned competing local agents without a pre-spawn lease; with llama.cpp `--parallel 1`, multiple requests waited inside runtime and hit the 240s coordinator wall timeout.
  Severity: high
  Fix: Added coordinator-side local subprocess lease/backpressure (`local_slot_busy`) and activation-aware aq-report scorecard metrics so historical timeout windows remain visible without hiding current recovery.
  File: ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py; scripts/ai/aq-report; scripts/testing/test-delegate-attention-queue-wiring.py; scripts/testing/test-aq-report-effectiveness-scorecard.py

[DONE] dashboard-osi-confined-ss-denial — Dashboard OSI layered health showed false port failures and AppArmor denials — Root cause: dashboard-safe phase 0 used Python sockets first but still fell back to `ss`, which AppArmor denies under `command-center-dashboard-api`.
  Severity: high
  Fix: Dashboard-safe port probes now skip the `ss` fallback; host-shell aq-qa keeps the diagnostic fallback.
  File: scripts/testing/harness_qa/core/helpers.py; scripts/testing/test-dashboard-qa-singleflight.py

[DONE] health-spider-stale-dashboard-alerts — aq-alerts kept showing recovered dashboard probe alerts — Root cause: health-spider pushed `Dashboard probe degraded:*` alerts but did not resolve matching pending alerts when the probe later returned OK.
  Severity: medium
  Fix: Health-spider now resolves recovered dashboard probe alerts through the attention queue API.
  File: scripts/ai/aq-health-spider; scripts/testing/test-health-spider-osi-layered-probe.py

[DONE] health-spider-apparmor-stale-window — One-shot health-spider runs repeatedly reported old AppArmor denials after dashboard restart — Root cause: each fresh process scanned the default interval window and did not bound the scan by current service activation.
  Severity: medium
  Fix: AppArmor scans now start no earlier than the current systemd service activation timestamp.
  File: scripts/ai/aq-health-spider; scripts/testing/test-health-spider-osi-layered-probe.py

[DONE] editor-obsolete-marker-false-degraded — aq-qa 0.5.7 reported degraded editor-local corpus even though corpus budgets were within limits — Root cause: stale local VSCodium obsolete marker `google.geminicodeassist-2.81.0`.
  Severity: medium
  Fix: Backed up and cleared the stale local marker; fresh aq-report reports editor state budget 5/5 passing.
  File: ~/.vscode-oss/extensions/.obsolete

[DONE] aidb-last-accessed-unknown-parameter — AIDB vector search logged PostgreSQL `could not determine data type of parameter` while updating `last_accessed_at` — Root cause: SQL parameters inside `jsonb_build_object` and `ANY` lacked explicit PostgreSQL casts.
  Severity: medium
  Fix: Cast `:ts` as text and `:ids` as integer[] in the metadata update query.
  File: ai-stack/mcp-servers/aidb/server.py; scripts/testing/test-aidb-last-accessed-sql.py

[DONE] hybrid-events-jsonl-group-write-denied — aq-chat fast-path (Phase 173) emits local_inference training events but silently fails with PermissionError: hybrid-events.jsonl is mode 0640 (owner rw, group r). hyperd user is in ai-stack group (read-only). asyncio.create_task swallows the error → zero training events emitted from aq-chat sessions.
  Root cause: nix/modules/services/mcp-servers.nix lines 645-646 set "f/z hybrid-events.jsonl 0640 ${hybridUser} ${aiGroup}". agent-run-events.jsonl correctly uses 0664 (Phase 120) but hybrid-events.jsonl was never updated to match.
  Severity: high (training pipeline silent data loss — every aq-chat fast-path turn produces zero training signal)
  Fix: Changed mcp-servers.nix lines 645-646 from 0640 → 0660. Commit b71c8eff. Rebuild complete 2026-06-14 — live file relabeled by tmpfiles z rule.
  Files: nix/modules/services/mcp-servers.nix (lines 645-646) — FIXED + DEPLOYED

[DONE] gemini-scope-creep-broken-nix-overlay — Gemini CLI session edited nix/lib/overlays/opencode.nix outside its assigned task scope (task: intake_gateway.py file-based state persistence). Added `final.mySystem.mcpServers.flakeRepoPath.inputs.nixpkgs-unstable` reference which does not exist in Nix overlay context (overlays only have `final`/`prev` pkgs). Caused nixos-rebuild eval failure: `error: attribute 'mySystem' missing`.
  Root cause: (1) No scope lock enforcement — Gemini edited infrastructure Nix file without being in scope. (2) Gemini's Nix semantic knowledge gap — assumed `final.mySystem` exists in overlay context. (3) Gemini's "Nix dry-run" claim was inaccurate — the broken change was in the working tree when the rebuild was attempted. Also: Gemini's ai_coordinator_handlers.py change removed legacy `agent_type→profile` routing (Phase 14.2) without verifying all callers (aq-hints, aq-cache-warm use agent_type field).
  Severity: high (blocked nixos-rebuild)
  Fix: Reverted opencode.nix to HEAD (package.nix already patches undici bug via version-check relaxation — unstable bun was unnecessary). Reverted ai_coordinator_handlers.py. Committed safe Gemini changes (local_agent_runtime.py retry, agent_registry.py TTL cache) as 344cfe2a. Added Rule 13 SCOPE LOCK + Rule 14 TOOL DEDUPLICATION to GEMINI.md.
  File: nix/lib/overlays/opencode.nix; ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py; .agent/GEMINI.md
  Requires rebuild: NO (opencode.nix reverted)

[DONE] aidb-qdrant-two-store-routing-gap — Phase 175: `query_aidb_handler` routed all harness pattern queries to AIDB pgvector (port 8002), but seed-rag-knowledge.py seeds into Qdrant (port 6333). These are separate stores with different content. AIDB pgvector returned MCP registry entries for `error-solutions` queries, not harness fix patterns. Additionally, AIDB `ALLOWED_COLLECTIONS` in query_validator.py listed 6 stale names (nixos_docs, solved_issues, etc.) that don't exist in Qdrant — all 14 real collections returned HTTP 400. ralph-wiggum/orchestrator.py also queried `solved_issues` (a PostgreSQL table, not a Qdrant collection).
  Root cause: Architecture not documented — two-store distinction was implicit. All callers assumed AIDB and Qdrant were interchangeable.
  Severity: critical (every agent query_aidb call returned wrong content or 400 since the harness was built)
  Fix: (1) ai_coordination.py: added _QDRANT_COLLECTIONS frozenset, query_aidb_handler routes to _query_qdrant_direct (embed via llama-embed:8081 → Qdrant:6333) as PRIMARY path for all harness collections. (2) aidb/query_validator.py: ALLOWED_COLLECTIONS expanded to 14 real names. (3) ralph-wiggum/orchestrator.py: solved_issues → error-solutions. All deployed (rebuild complete 2026-06-14).
  Files: ai-stack/local-agents/builtin_tools/ai_coordination.py; ai-stack/mcp-servers/aidb/query_validator.py; ai-stack/mcp-servers/ralph-wiggum/orchestrator.py
  Pattern: AIDB (port 8002) = pgvector for document chunks. Qdrant (port 6333) = harness patterns seeded by seed-rag-knowledge.py + training pipeline. Always use embed→Qdrant-direct for harness collections.

[DONE] clm-periodic-llm-compaction-contention — Phase 171-C: context_lifecycle_manager._demote_to_cold() fires every 60s (_TICK_INTERVAL) and called _compact_summary() → llama.cpp /v1/chat/completions with max_tokens=512. This was the primary periodic LLM caller causing queue contention during agent task startup. Other callers found safe: model_probe.py (cached by model_id, fires only on model change), switchboard._warm_local_profile_prefix (startup-only, max_tokens=4).
  Root cause: CLM was not slot-aware — it queued compaction calls regardless of whether inference slot was occupied by an agent task.
  Severity: medium (agent first-step latency inflated by up to 30s per competing 512-token compaction)
  Fix: Added _is_inference_busy() guard in _demote_to_cold() — reads GET /slots (passive, no slot consumption). If any slot has state≠0, defers compaction to next 60s tick. Commit 9b296806. Requires coordinator restart.
  Files: ai-stack/mcp-servers/hybrid-coordinator/knowledge/context_lifecycle_manager.py (lines 343-354, new method _is_inference_busy at ~line 463)

[FIXED f3cc7513+pending-swb-restart] aq-chat-tools-never-execute — aq-chat local agent described tool calls in prose but never executed them. Three-layer failure: (1) aq-chat sent streaming_mode=True which forced coordinator to set AGENT_TOOLS_ENABLED=false for all SSE paths; (2) local_agent_runtime.py used 'local-tool-calling' switchboard profile when TOOLS_ENABLED=True — that profile runs _execute_local_tool_calling which rejects any tool not in the built-in server registry (route_search, recall_memory, get_hint etc. are NOT built-ins) → 400; (3) switchboard had no passthrough for external tool schemas.
  Root cause: streaming and tool execution are mutually exclusive in local_agent_runtime.py but aq-chat always requested streaming; profile selection bug documented in _profile_for_role() comment but not fixed in the TOOLS_ENABLED=True branch.
  Severity: critical (all tool calls silently reduced to descriptive prose; agent appeared functional but produced no evidence-backed answers)
  Fix: (a) aq-chat._build_coordinator_delegate_payload: tools_enabled=True + streaming_mode=False for tool turns; new non-streaming response branch with spinner. (b) switchboard: _tools_are_all_external() + _passthrough_local_tool_inference() bypass _execute_local_tool_calling for agent-runtime schemas. (c) local_agent_runtime.py: 'local-agent' profile (toolExecution:None, 8k/4k context) instead of 'local-tool-calling' when TOOLS_ENABLED. (d) switchboard stream-exemption: added 'local-agent' to the profiles exempt from forced stream=True override (fixes resp.json() parse error on SSE response).
  Files: scripts/ai/aq-chat (lines 409-433, 886-926), ai-stack/switchboard/switchboard.py (_tools_are_all_external, _passthrough_local_tool_inference, stream-exemption list), ai-stack/agents/runtimes/local_agent_runtime.py (line 1228)
  Activation: switchboard changes require restart (live-repo); runtime change required nixos-rebuild (now done).

[FIXED pending-restart] local-agent-profile-token-overflow — local_agent_runtime (coordinator-spawned) used local-agent switchboard profile. LOCAL_AGENT_CARD contained full HARNESS_AWARE_BODY (~1500 tok) + injectHints=True (~200 tok) + 14 tool schemas (~1500 tok) + coordinator system prompt (~500 tok) = ~3700 token input. APU prefill at 15 tok/s = 247s > 210s coordinator timeout → 504 local_agent_timeout. Root cause: profile card designed for interactive aq-chat was being used for subprocess agents that already have task context from env vars.
  Severity: critical (every aq-chat agentic turn via coordinator fails)
  Fix: (1) LOCAL_AGENT_CARD minimal ~50-token card; (2) injectHints=False for local-agent; (3) tool dispatch gate extended to include local-agent; (4) _passthrough_local_tool_inference caps tools to 7. All in switchboard.py — restart only.
  Files: ai-stack/switchboard/switchboard.py lines 196-199 (card), 306 (hints), 2962-2965 (gate), 1445-1449 (tool cap)

[FIXED pending-restart] tools-are-all-external-false-negative — _tools_are_all_external() in switchboard.py returns False when the agent-runtime's tool names (read_file, run_command, get_hint, harness_health, etc.) match switchboard built-in registry names, even though they are entirely different implementations. When it returns False for a local-agent profile request, execution falls through to _execute_local_tool_calling() which cannot handle agent-runtime schemas and raises ValueError → 400 Bad Request → coordinator receives 500 local_agent_failed.
  Root cause: _tools_are_all_external iterates tool names against the built-in registry; name collision causes false non-external classification. The profile's toolExecution:None field is the authoritative signal, not tool name membership.
  Severity: critical (every aq-chat agentic turn via coordinator fails with 500 after Phase 177 restart)
  Fix: change dispatch condition from `if _tools_are_all_external(payload):` to `if profile == "local-agent" or _tools_are_all_external(payload):` — local-agent profile always takes the passthrough path regardless of tool name collision.
  Files: ai-stack/switchboard/switchboard.py line 2982 (dispatch condition in _handle_local_tool_calling_request)

[ACTION_NEEDED] antigravity-delegation-oauth — delegate-to-antigravity uses oauth-personal (Code Assist API), requires one-time browser auth (2026-06-21).
  CONTEXT: Prior session assumed API-key was correct path. Corrected: generativelanguage.googleapis.com requires paid credits. The free path is oauth-personal → cloudcode-pa.googleapis.com (Code Assist).
  RESOLVED: delegate-to-antigravity rewritten to call `gemini -p "..."` subprocess (da4e47d0). No API key, no SOPS secret needed. auth.selectedType=oauth-personal in ~/.gemini/settings.json.
  RESOLVED: antigravity-health.sh rewritten for oauth-personal check. gemini-cli-health.sh no longer blocks on oauth-personal type.
  ACTION_NEEDED (user, once): Run `gemini -p 'test'` in a terminal → press Y → complete Google browser sign-in. Stores oauth-personal token in ~/.gemini/gemini-credentials.json. After this, all delegate-to-antigravity calls work headlessly.
  Detection: antigravity-health.sh --check returns status=auth_pending (exit 0) until OAuth done; --smoke returns unhealthy (exit 1) until done.
  ARCHITECTURE: Antigravity is a GUI IDE (not a headless CLI). `antigravity chat` opens a window. Delegation is via gemini npm CLI (oauth-personal), NOT Antigravity binary.
  Severity: action_needed (delegation non-functional until user completes browser OAuth)
  Files: scripts/ai/delegate-to-antigravity, scripts/health/antigravity-health.sh, scripts/health/gemini-cli-health.sh, .agent/GEMINI.md

[FIXED 6b258bf9+pending] autonomous-loop-prsi-not-wired — autonomous_loop.py ran its trigger → research → experiment cycle but never called prsi-orchestrator.py. Delegation failures discovered by PRSI were never consumed by the improvement loop. Fix: added _prsi_sync_execute() in autonomous_loop.py — calls prsi-orchestrator.py sync --since 1d then prsi-orchestrator.py execute at the start of every run_once() call. Closes Phase 185B Problem 3.
Severity: medium (autonomous loop firing but not consuming PRSI delegation feedback; improvement queue stale)
Files: ai-stack/autonomous-improvement/autonomous_loop.py run_once(); scripts/automation/prsi-orchestrator.py _fetch_structured_actions()
[DONE] validation — tier0 pre-commit PTY returned no output and kept the tool session open after no matching process was visible; interrupted after repeated polls during Understand-Anything integration.
  Severity: low
  Action: Resolved on 2026-06-28. `AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 timeout 120 scripts/ai/aq-qa 0 --machine` passed 115/0/2, then `AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 timeout 180 scripts/governance/tier0-validation-gate.sh --pre-commit` passed 21/0.
  File: scripts/governance/tier0-validation-gate.sh

[FIXED 2026-07-01] github-mcp-readonly — github-mcp-server 0.20.2 installed via nix profile + home.packages. Token wired via scripts/ai/mcp-github-server wrapper (SOPS /run/secrets/github_mcp_token → gh auth token fallback). ~/.mcp/config.json updated with "github" server entry. SOPS key added, options.nix+secrets.nix updated (takes effect after next nixos-rebuild). All agents share access via harness tool catalog (see below).
  Severity: low — RESOLVED
  File: scripts/ai/mcp-github-server; nix/hosts/hyperd/home.nix; nix/modules/core/options.nix; nix/modules/core/secrets.nix

[DONE] osint-active-recon-runtime-gated — Passive OSINT research is active, and active recon engines are now guarded by a fail-closed runtime admission surface — Maigret and MOSAIC remain intentionally not activated because insecure package paths are still held, and BBOT remains provisioning-only in the OSINT MCP server.
  Severity: medium
  Action: Added `osint_recon_status` for coordinator/local agents, made `osint_recon` deny by default unless explicit scope, request acknowledgement, policy enablement, and admitted runtime are present, and updated tooling-manifest routing to prefer passive OSINT plus active-status inspection. Remaining future work is secure package/runtime enablement for approved replacements.
  File: ai-stack/mcp-servers/hybrid-coordinator/extensions/mcp_handlers.py; ai-stack/local-agents/builtin_tools/ai_coordination.py; ai-stack/mcp-servers/hybrid-coordinator/knowledge/tooling_manifest.py; scripts/testing/test-osint-active-recon-gate.py

[DONE] design-skills-autoselect-validation-gap — `aq-skill-auto --test` selected `frontend-design` and `canvas-design` for website work, but both failed required skill-section validation because their bodies lacked `## Description` and `## When to Use` headings.
Severity: low
Action: Added validator-facing `Description`, `When to Use`, and `Usage` sections without changing the existing design workflows; reran auto-selection and both skills now validate.
File: .agent/skills/frontend-design/SKILL.md; .agent/skills/canvas-design/SKILL.md

[DONE] phase0-runtime-probe-false-negatives — Phase 0 QA treated sandbox-denied HTTP/systemd/database probes as failed runtime checks, causing false failures and black-box waits while local-agent observability work was otherwise healthy.
Severity: high
Fix: Added sandbox-aware HTTP POST/GET handling, bounded Python fallback probes, systemd show fallback skips, idempotent attention archive validation, and explicit datastore socket-denial skips for Qdrant/Postgres/Redis. Focused layer 1 and layer 5 runs now have zero failures; tier0 QA phase 0 reaches PASS.
File: scripts/ai/_aq-qa-bash; scripts/testing/test-aq-qa-progress-heartbeat.py; scripts/testing/test-local-subprocess-discipline-smoke.py

[DONE] agent-observability-ssot-fragmentation — Agent delegation and inference progress used compatibility sidecars and service-owned telemetry paths without a repo-writable canonical agent-run event helper, creating fragmented observability for local agents and long-running inference.
  Severity: high
  Action: Added `agent_run_events.emit_event()` with repo-local fallback and latest-state projection, routed `dispatch.py` progress updates through the canonical agent-run stream, and made the dashboard merge service and repo-local `agent-run-events.jsonl`.
  File: scripts/ai/lib/agent_run_events.py; scripts/ai/lib/dispatch.py; dashboard/backend/api/routes/aistack.py; scripts/testing/test-agent-run-event-envelope.py; scripts/testing/test-local-inference-budget.py

[DONE] local-agent-llm-wait-no-progress — Local-agent test task `local-20260629-182011-pbd3dk` held the host inference slot in `llm_waiting` with `llm_stream_chunks=0` and `llm_stream_chars=0` until manually cancelled, which paused vectorization batch auto-restart.
  Severity: high
  Action: Added `LLAMA_FIRST_TOKEN_TIMEOUT` wiring in `aq-agent-loop` and capped executor streaming read timeout so silent first-token waits fail with `LLM no-progress timeout` before pinning the slot indefinitely.
  File: scripts/ai/aq-agent-loop; ai-stack/local-agents/agent_executor.py; scripts/testing/test-local-agent-first-token-timeout.py

[DONE] local-inference-queue-wait-misclassified — During concurrent UA batch repair and another agent's local-inference test, helpers treated `/health` as slot availability and treated `/slots` failure/timeout as permission to submit anyway, causing queue waits to look like first-token/model failures and allowing extra direct load behind a busy single-slot llama.cpp server.
  Severity: high
  Action: `slot_scheduler.wait_for_slot()` now fails closed with `SlotWaitTimeout` when the slot cannot be observed free, `DirectRunner` surfaces `queued_timeout` instead of submitting extra direct load, and `local_agent_runtime._wait_for_llama_slot()` polls `/slots` while writing `waiting_for_slot`, `queue_wait_s`, and `slot_wait_state` to runtime state before retrying.
  File: scripts/ai/lib/slot_scheduler.py; scripts/ai/lib/dispatch.py; ai-stack/agents/runtimes/local_agent_runtime.py; scripts/testing/test-local-inference-budget.py; scripts/testing/test-local-slot-busy-fast-fail.py

[FIXED 2026-07-01] sandbox-monitor-pid-namespace-false-stale — Added _heartbeat_alive() to task_registry.py: if os.kill() reports PID missing (due to sandbox PID namespace) but heartbeat file was written within 180s, task is reported as alive (pid_alive=True, heartbeat_liveness=True). Watcher writes heartbeat every 60s → 3× margin. Wired into _with_inferred_status() as fallback after os.kill() check.
  Severity: medium — RESOLVED
  File: scripts/ai/lib/task_registry.py

[DONE] aq-qa-machine-mode-black-box — `aq-qa 0 --machine` could run silently for minutes, leaving agents with only an outer timeout and no near-time current-check visibility.
  Severity: high
  Action: Added rolling QA progress artifacts at `.agent/qa/latest-progress.json` and `.agent/qa/latest-progress.jsonl`, including phase_start, per-check running/pass/fail, and heartbeat events controlled by `AQ_QA_PROGRESS_HEARTBEAT_SECONDS`.
  File: scripts/ai/aq-qa; scripts/ai/_aq-qa-bash; scripts/testing/test-aq-qa-progress-heartbeat.py

[DONE] aq-qa-discovery-check-timeout-boundary — 0.10.4 re-fired under real system load: direct `aq-qa 0 --machine` and coordinator `/qa/check` both held silent stdout until their outer timeouts, leaving only heartbeat artifacts for visibility.
  Severity: high
  Action: Added `_check_timeout()` to the bash QA runner and routed 0.10.4 through `AQ_QA_DISCOVERY_OPPORTUNITY_TIMEOUT_SECONDS` (default 30s), so this high-risk probe fails with an explicit per-check timeout detail instead of consuming the whole QA wrapper budget.
  File: scripts/ai/_aq-qa-bash; config/env-contract.yaml; scripts/testing/test-aq-qa-progress-heartbeat.py

[DONE] aq-qa-retired-continue-health-gate — Live wrapper validation stalled at `0.5.1 Continue CLI help works`; this was a stale QA dependency on the retired Continue extension path, not a current local-agent runtime route.
  Severity: high
  Action: Retired the Continue/editor phase-0 gates in both bash and Python QA paths. Replaced 0.5.1/0.5.2 with switchboard `local-agent` and `local-coding` profile checks, and converted Continue-specific 0.5.3-0.5.6 checks into explicit skips documenting the retired route.
  File: scripts/ai/_aq-qa-bash; scripts/testing/harness_qa/phases/phase0.py; scripts/testing/test-aq-qa-progress-heartbeat.py

[DONE] aq-qa-flagship-cli-aggregate-timeout — After retiring the stale Continue gate, live phase-0 validation advanced to `0.6.1 flagship agent CLI help smokes` and could still hold the wrapper budget because the aggregate script checks multiple external CLIs.
  Severity: high
  Action: Routed 0.6.1 through `_check_timeout()` with `AQ_QA_FLAGSHIP_CLI_SURFACE_TIMEOUT_SECONDS` and set a tighter phase-0 `AQ_FLAGSHIP_HELP_TIMEOUT_SECONDS` default for the aggregate helper.
  File: scripts/ai/_aq-qa-bash; config/env-contract.yaml; scripts/testing/test-aq-qa-progress-heartbeat.py

[DONE] aq-qa-render-skipped-by-set-e-probe — Live phase-0 validation completed through `0.10.33` but returned empty stdout with exit 1 because the later `86.2` attention-queue probe ran a bare Python command under `set -e`, exiting before `_render_results`.
  Severity: high
  Action: Guarded the `86.2` Python probe in an `if ...; then _pass; else _fail; fi` block so probe failures become visible QA rows and the final summary renderer always runs.
  File: scripts/ai/_aq-qa-bash; scripts/testing/test-aq-qa-progress-heartbeat.py

[DONE] aq-qa-systemd-port-sandbox-false-negatives — Phase-0 QA reported active host services and listening ports as down because bash checks relied on `systemctl is-active` and `ss -tlnp`, both of which can be denied in restricted agent execution even when `systemctl show` and TCP socket connects work.
  Severity: high
  Action: Added `_systemd_unit_state()` with `systemctl show ActiveState` fallback and explicit sandbox-denied state, added `_tcp_port_open()` socket checks before `ss`, converted denied host port probes into skips, and mirrored the systemd denial handling in Python phase-0 service checks.
  File: scripts/ai/_aq-qa-bash; scripts/testing/harness_qa/phases/phase0.py; scripts/testing/test-aq-qa-progress-heartbeat.py

[DONE] discovery-agent-opportunity-test-hangs — Direct `timeout 120 python3 scripts/testing/test-discovery-agent-opportunities.py` produced no stdout and exited 124, proving the current `0.10.4` timeout exposed a real scanner/test hang rather than causing a false QA failure.
  Severity: high
  Action: Root cause was `DiscoveryAgent.discover_opportunities()` using `asyncio.to_thread()` for deterministic local file/JSON scanning; under sandboxed Python 3.13 agent contexts the default executor worker stayed alive and `asyncio.run()` hung during shutdown. The async wrapper now calls the scanner synchronously, and the regression test asserts the thread-offload path does not return.
  File: ai-stack/local-agents/discovery_agent.py; scripts/testing/test-discovery-agent-opportunities.py

[DONE] tier0-phase0-failure-report-hidden — Tier0 phase-0 failures were actionable only after manually rerunning `aq-qa 0`; the gate printed `tail -3`, hiding the failed rows even when 20+ checks failed.
  Severity: high
  Action: Added `log_failed_qa_rows()` to strip ANSI and print the first 30 failed QA rows on timeout or normal phase-0 failure; extended the QA progress regression to require this reporting path.
  File: scripts/governance/tier0-validation-gate.sh; scripts/testing/test-aq-qa-progress-heartbeat.py

[DONE 2026-07-01] phase0-runtime-reachability-parity — All service probes now pass: aq-qa 0 → 122 passed, 0 failed, 6 skipped (23s). All five core service ports respond healthy (AIDB:8002, coordinator:8003, switchboard:8085, llama:8080). Tier0: 21/21 PASS.
  Severity: high → resolved
  File: scripts/ai/_aq-qa-bash; scripts/testing/harness_qa/phases/phase0.py

[FIXED a80050a9 2026-07-01] delegate-to-local-status-missing-arg — Fixed: ${2:-} default + conditional shift prevents set -u crash; explicit die guard added to status/check/cancel/repair-status cases with clear error message.
  Severity: low — RESOLVED
  File: scripts/ai/delegate-to-local

[DONE] vectorization-posture-route-not-live — The committed `/api/aistack/graph/vectorization` dashboard route returned 404 from the running dashboard service during validation, while the older `/api/aistack/knowledge/observatory` route worked.
  Severity: medium
  Action: Restarted `command-center-dashboard-api.service` and verified live `/api/aistack/graph/vectorization` returns `status:"ok"`; `python3 scripts/testing/test-vectorization-visualization.py` passes.
  File: dashboard/backend/api/routes/aistack.py

[DONE] understand-anything-fallback-batches-not-complete — Understand-Anything batch processing produced all 296 `batch-*.json` files, but prior logs show degraded fallback batches 246, 247, 248, 251, 252, 253, and 255 after LLM JSON parse failures; no final `knowledge-graph.json` existed.
  Severity: high
  Action: Reprocessed degraded batches 246, 247, 248, 251, 252, 253, and 255 in strict no-fallback LLM mode. `scripts/ai/aq-understand-anything validate-batches` now reports ok=true, expected_batches=296, missing/invalid/empty/fallback all empty, and graph_present=true. Final graph: `.understand-anything/knowledge-graph.json` with 6257 nodes and 1870 edges.
  File: .understand-anything/ua-batch-processor.py; scripts/ai/aq-understand-anything

[DONE] local-agent-stagnation-false-success — Local-agent task `local-20260629-081304-dx1xx2` produced a `Repeated-read stagnation` result after a long run, but `aq-agent-loop` wrote `success: true` / `status: completed`, and the registry initially presented the task as successful.
Severity: high
Fix: `aq-agent-loop` now treats repeated-read and analysis-checkpoint stagnation as incomplete failed results, writes `status: failed`, exits non-zero, and avoids training-signal emission for those runs. `TaskRegistry` now reconciles dead or inconsistent running/done entries before list/status/check and marks artifacts containing failure markers as failed. Stale delegated prompts should use the existing canonical path `docs/system-centric-ai-repos-recommendations.md`.
File: scripts/ai/aq-agent-loop; scripts/ai/lib/task_registry.py; scripts/ai/aq-delegation-registry; scripts/testing/test-local-delegation-artifact.py; scripts/testing/test-local-agent-progress-guarded-tools.py
[DONE] local-agent-monitor-required-write-access — `delegate-to-local --list` failed in restricted monitoring contexts because status observation called mutating reconciliation and attempted to rewrite `.agents/delegation/registry.jsonl`.
Severity: high
Fix: `list`, `status`, and `check` now use read-only inferred status. Added explicit `delegate-to-local --repair-status <id>` for mutating reconciliation and `delegate-to-local --monitor` for parseable read-only JSON showing active/recent task status, PID liveness, artifact paths, mtimes, and stale inference reasons.
File: scripts/ai/lib/task_registry.py; scripts/ai/lib/dispatch.py; scripts/ai/delegate-to-local; scripts/testing/test-local-delegation-artifact.py

[DONE] aq-qa-machine-mode-stall — Standalone `AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 scripts/ai/aq-qa 0 --machine` produced no output for roughly two minutes during context-risk compaction validation, while the Tier 0 gate's embedded QA phase 0 completed successfully.
Severity: medium
Fix: Added `_exec_bash_fallback()` in scripts/ai/aq-qa that applies `timeout --foreground ${AQ_QA_MACHINE_TIMEOUT_SECONDS:-300}` + `NO_COLOR=1` when `--machine` is set and falling back to bash path. Committed in same session (ea1df9d7 era).
File: scripts/ai/aq-qa; scripts/testing/harness_qa/phases/phase0.py

[DONE] safe-feature-candidate-promotion — Installed/read-only capability candidates were still `proposed`, so agents could not reliably auto-select Trivy, observability report, or Nix static analysis even though the local runtimes were available.
  Severity: medium
  Action: Promoted Trivy 0.66.0, observability query, and Nix static-analysis pack to `enabled` with accepted mitigations; declared OSV 2.2.4, Syft 1.38.0, and Grype 0.104.1 in Nix as `pending-rebuild`; kept GitHub MCP and graph-backed code intelligence blocked until prerequisites exist; added tooling-manifest discovery and tests.
  File: config/agent-capability-intake-candidates.json; nix/modules/roles/ai-stack.nix; ai-stack/mcp-servers/hybrid-coordinator/knowledge/tooling_manifest.py; scripts/testing/test-enabled-external-mcp-candidates.py; scripts/testing/test-tooling-manifest.py

[DONE] design-skills-autoselect-validation-gap — `aq-skill-auto --test` selected `frontend-design` and `canvas-design` for website work, but both failed required skill-section validation because their bodies lacked `## Description` and `## When to Use` headings.
  Severity: low
  Action: Added validator-facing `Description`, `When to Use`, and `Usage` sections without changing the existing design workflows; reran auto-selection and both skills now validate.
  File: .agent/skills/frontend-design/SKILL.md; .agent/skills/canvas-design/SKILL.md

[DONE 2026-07-06] coordinator-api-endpoint-gaps — Three coordinator API endpoints returned wrong status codes in QA health checks:
  - 0.9.3 (DAG/workflow): GET /workflow/run/{id}/execute/status → 405 (route exists, method mismatch from Phase 38 spec drift)
  - 0.9.2 (UAG lifecycle): GET /agent/lifecycle/{id}/replay → 404 (route not implemented)
  - 93.8 (human-agent control): POST /agent-runs/{id}/control → 401 (route requires auth, QA probe sends none)
  Severity: medium (no user impact; coordinator routes serve live requests correctly via other paths)
  Action: Removed the xfail entries; aligned bash QA with the Python check by probing status codes directly for expected 404/422 contract responses; added the missing legacy UAG replay route registration in the coordinator shim. Repo-local phase-0 machine QA now passes 91/0 under managed sandbox. Rebuild required to deploy the coordinator shim route body into the running Nix store service.
  File: config/qa-xfail.yaml; scripts/ai/_aq-qa-bash; ai-stack/mcp-servers/hybrid-coordinator/intake_gateway.py

[OPEN] sandbox-observability-contract-fragmentation — Agent-side audits still surface routine host-observability denials as command errors or noisy skips even when services are healthy. Evidence from 2026-07-02 audit: `ss -tlnp` denied netlink in the managed agent sandbox until escalated; `systemctl is-active ai-drop-daemon` denied system bus access until escalated; `aq-report` marked cache prewarm state with system-bus denial text; `aq-qa 0 --machine` passed with 55 sandbox/unreachable skips.
  Severity: medium
  Action: Define a narrow host-observer contract/API for service state, listening ports, recent logs, QA progress, and sandbox/AppArmor denial summaries; migrate `aq-qa`, `aq-report`, and dashboard health surfaces to shared status classes (`pass`, `fail`, `skip_sandbox_denied`, `skip_not_configured`, `xfail_known_gap`, `error_probe_bug`) instead of ad hoc `systemctl`/`ss`/raw socket probes in agent contexts.
  File: scripts/ai/aq-report; scripts/ai/_aq-qa-bash; scripts/testing/harness_qa/phases/phase0.py; dashboard/backend/api/

[DONE 2026-07-05] security-auth-hardening-smoke-stale-source — `scripts/testing/check-api-auth-hardening.sh` failed immediately with `missing http server source` because it still expected `http_server.py`, while coordinator auth moved to `middleware/auth.py`, `core/auth_middleware.py`, `http_server_impl.py`.
  Severity: medium
  Resolution (commit 043f69d2, claude-opus-4-8): smoke now inspects middleware/auth.py + core/auth_middleware.py (create_api_key_middleware, PUBLIC_PATHS), FAILs on missing middleware source (not stale filename), keeps the runtime /workflow/sessions invalid-key probe. Added regression test-api-auth-hardening-smoke.py (contract: no stale http_server.py path). Verified smoke exit 0 + test PASS. Auth layout found via understand-anything (aq-wiki --section hybrid-coordinator).
  File: scripts/testing/check-api-auth-hardening.sh; scripts/testing/test-api-auth-hardening-smoke.py

[DONE 2026-07-05] security-scanner-skill-stale-secret-hygiene-command — `.agent/skills/security-scanner/SKILL.md` told agents to run an absent `check-secret-hygiene.sh` with an over-broad fallback grep.
  Severity: low
  Resolution (commit 4d9a225e, claude-opus-4-8): replaced with canonical guards — tier0.d/check-sops-sync.sh (secrets.nix<->SOPS parity) + an ad-hoc rg using the SAME high-signal patterns as the pre-commit/pre-push secret guard (AKIA/ghp_/github_pat_/sk-/xox/private-keys). No remaining reference to the retired script. Verified paths exist + rg valid.
  File: .agent/skills/security-scanner/SKILL.md

[DONE] memory-hot-index-reference-drift — Current agent instructions required a hot `MEMORY.md` index and updates to its `## Issues Backlog` entry without naming the canonical path. The hot index exists at `ai-stack/agent-memory/MEMORY.md`; the defect was stale bare-path references in active docs/skills.
  Severity: medium
  Action: Updated active agent instructions and skills to point to `ai-stack/agent-memory/MEMORY.md`, kept warm topics under `.agent/memory/*.md`, and added a registry test to block future stale hot-memory references.
  File: AGENTS.md; README.md; .agent/SKILL_INDEX.md; .agent/WORKFLOW-CANON.md; .agent/GEMINI.md; .agent/skills/context-efficiency/SKILL.md; scripts/testing/test-agent-memory-surface-registry.py

[DONE] delegate-to-local-task-subcommand-parser-drift — Task-specific `--status`, `--check`, and `--cancel` invocations rejected documented positional task IDs, blocking routine monitor/cancel workflows; fixed by consuming the trailing task ID after the flag shift and adding `scripts/testing/test-delegate-to-local-argparse.sh`.
  Severity: medium
  Action: Done — fixed `scripts/ai/delegate-to-local` argument parsing so documented `--status ID`, `--check ID`, `--repair-status ID`, and `--cancel ID` work consistently; added a regression test.
  File: scripts/ai/delegate-to-local

[PENDING-REBUILD] agentic-runtime-workspace-dac-denial — Runtime isolation profiles declare agent workspace roots under `/var/lib/nixos-ai-stack/mutable/program/`, and MCP services include them in `ReadWritePaths`, but the roots were provisioned `0750` so ai-stack service users could traverse but not create files unless they owned the directory.
  Severity: high
  Action: Updated `ai-mutable-path-bootstrap` and tmpfiles rules to create runtime workspace roots as `0770 ${primaryUser}:ai-stack`, preserving read-only repo mounts while permitting service-created agent files. Post-rebuild check confirmed `/var/lib/nixos-ai-stack/mutable/program/agent-runs` is `0770 hyperd:ai-stack` and `ai-hybrid` is in `ai-stack`; follow-up patch added the missing Nix default for `worktree-guarded`, so a second rebuild is needed to materialize `/var/lib/nixos-ai-stack/mutable/program/agent-worktrees`.
  File: nix/modules/services/mcp-servers.nix; nix/modules/core/options.nix; config/runtime-isolation-profiles.json; scripts/testing/test-nixos-writable-state-policy.py

[FIXED-PARTIAL 2026-07-02] antigravity-delegation-dual-lane-failure — delegate-to-antigravity failed on BOTH lanes: (1) remote-free (OpenRouter meta-llama/llama-3.3-70b-instruct:free) HTTP 429 rate-limited on free tier; (2) local-coding fallback then failed with "Expecting value: line 1 column 1 (char 0)" — a JSON parse error.
  Root cause (lane 2, FIXED): switchboard FORCES stream=True for local profiles (journal: "forced stream=True for local chat/completions profile=local-coding") regardless of the client's stream=False. delegate-to-antigravity did json.loads(resp.read()) on the SSE body (data: {...}) → parse failure → fallback wrongly reported failed. Added _parse_completion_response() handling both SSE and plain JSON. Unit-tested (SSE/JSON/empty/final-message-chunk all pass).
  Root cause (lane 1, DECIDED 2026-07-02 → Google Gemini direct): user chose to route the remote lane at Google Gemini, not OpenRouter. Finding: nix/hosts/hyperd/deploy-options.nix ALREADY declared remoteUrl=https://generativelanguage.googleapis.com/v1beta/openai — but the running switchboard still had REMOTE_LLM_URL=https://openrouter.ai/api (CONFIG DRIFT: edited, never rebuilt). Also the declaration was INCOHERENT: remoteUrl→Google but coding/reasoning/toolCalling/opencode aliases pointed at anthropic/openai/qwen models that 404 on Google's endpoint. Fixed: all aliases now bare gemini-* (coding/reasoning=gemini-2.5-pro, toolCalling/gemini/opencode=gemini-2.5-flash, free=gemini-2.5-flash-lite).
  SUPERSEDED 2026-07-09: do NOT swap in a Google AI Studio API key. The governing workflow is no API keys for Antigravity/Gemini fan-out; Antigravity uses its IDE's own OAuth via watched inbox/file A2A. Switchboard remote profiles are generic remote routing only, not the Antigravity identity lane.
  Also found: zombie `gemini` npm CLI process (PID from old ping test) still running despite gemini CLI being retired (IneligibleTierError) — needs reaping.
  2026-07-09 update: fixed a separate background-child stability bug where forked non-blocking children redirected only stdin and could inherit fragile stdout/stderr pipes from the caller; child diagnostics now go to the task log, preventing `Broken pipe` from masking the real provider/fallback outcome. Also fixed the empty-response log path that referenced undefined `result`.
  Verification: `python3 -m py_compile scripts/ai/delegate-to-antigravity scripts/testing/test-delegate-antigravity-background-stdio.py` and `python3 scripts/testing/test-delegate-antigravity-background-stdio.py` pass. Live smoke `antigravity-20260708-223624-3ivgdv` no longer logs `FATAL: Broken pipe`; it records remote HTTP 429 and local fallback diagnostics instead. Remote lane remains rate-limited/provider-config dependent.
  Severity: high (remote fan-out lane unreliable until rebuild; local fallback works now)
  File: nix/hosts/hyperd/deploy-options.nix (remoteUrl + aliases); scripts/ai/delegate-to-antigravity (_parse_completion_response + comments + background stdio redirect); scripts/testing/test-delegate-antigravity-background-stdio.py; SOPS remote_llm_api_key

[OPEN] codex-delegation-stale-running-zero-output — `delegate-to-codex --status` reported `codex-20260708-230805-yq4n07xxxxxx` as running, but `ps -p 789355` found no process and the output log stayed at 0 bytes. The collaboration collector therefore treated a dead lane as pending instead of unavailable or failed.
  Severity: medium
  Action: Add stale-pid/log-progress detection to Codex delegation status and `aq-collab-round collect`, matching the local lane's heartbeat/progress model. Retried the usability-parity-v2 Codex lane as `codex-20260708-231458-tgnak0xxxxxx`, which repeated the no-live-pid/zero-output failure; active Codex session landed `.agents/plans/usability-parity-v2/codex.md` directly. 2026-07-09 update: `aq-delegation-registry reconcile` repaired three stale Codex registry rows (`codex-20260708-224654-s4kn7lxxxxxx`, `codex-20260708-230805-yq4n07xxxxxx`, `codex-20260708-231458-tgnak0xxxxxx`) after PID checks confirmed no live processes. Remaining root fix is automatic terminal-state transition in `delegate-to-codex`/collector/dashboard views, not manual reconcile.
  File: scripts/ai/delegate-to-codex; scripts/ai/aq-collab-round; .agents/delegation/outputs/codex-20260708-230805-yq4n07xxxxxx.log

[OPEN] claude-wait-mode-registry-omits-live-pid — A monitored `delegate-to-claude --wait` M1 task remained live as Claude PID 3392266, but its registry row stored `pid=null` and `--status` printed `Process no longer running`; an earlier background attempt also exited with an empty output while remaining `running` in the registry.
  Severity: high
  Action: make blocking and background modes register the actual durable child identity, reconcile terminal state on every exit including `set -e`/pipeline failures, and add a live wrapper test proving dashboard/status convergence without relying on prompt-log output.
  File: scripts/ai/delegate-to-claude; .agents/delegation/registry.jsonl; scripts/ai/aq-tui-dashboard

[OPEN] antigravity-inbox-watcher-visibility-gap — Antigravity IDE and Gemini Code Assist A2A processes are running, and `aq-collab-round` dropped `.agent/archive/antigravity-inbox-20260709/usability-parity-v2.md`, but no `.agents/plans/usability-parity-v2/antigravity.md` landed and there is no first-class watcher status explaining whether the IDE saw, ignored, failed, or is still processing the inbox task.
  Severity: medium
  Action: PARTIAL 2026-07-09 — fixed the prompt path contradiction and added known-legacy Antigravity output recovery plus proposal warnings in `aq-collab-round collect`; remaining work is richer dashboard/TUI watcher state with inbox file mtime, expected output path, IDE process presence, last response mtime, and explicit `inbox_pending|inbox_unavailable|inbox_landed` states. RECURRENCE 2026-07-15 — M1 design review and unified-program revision review remained pending through repeated bounded polls while host Antigravity processes were live; `aq-antigravity-inbox status` exposed queue order but no claimed/processing/heartbeat/ETA state.
  File: scripts/ai/aq-collab-round; scripts/ai/aq-tui-dashboard; .agent/archive/antigravity-inbox-20260709/usability-parity-v2.md

[DONE] usability-parity-prompt-output-path-contradiction — The shared expert-team prompt still instructed agents to write `.agents/plans/usability-parity/<agent>.md`, while `aq-collab-round` correctly appended `.agents/plans/usability-parity-v2/<agent>.md`; Antigravity followed the stale instruction and landed in the superseded round.
  Severity: medium
  Action: Removed the stale per-agent output path list from `.agents/prompts/AI_HARNESS_USABILITY_PARITY_EXPERT_TEAM_PROMPT.md`, replaced it with active-round guidance, added safe legacy recovery in `aq-collab-round collect`, and added proposal warnings for no-key policy drift.
  File: .agents/prompts/AI_HARNESS_USABILITY_PARITY_EXPERT_TEAM_PROMPT.md; scripts/ai/aq-collab-round

[DONE] aq-collaborate-contribution-claim-unverifiable — Antigravity reported contribution ID `10290073-123e-47f4-8dcf-78de8c41c173`, but no repo-local audit artifact contained that ID and `aq-collaborate messages collab_1` had no database table to verify it.
  Severity: medium
  Action: Updated `aq-collaborate contribute` to accept the documented `--phase/--description/--approach` flags by converting them into content when `--content` is absent, and append successful contribution IDs to `.agent/collaboration/aq-collaborate-contributions.jsonl`. Current verified Antigravity contribution is `ccdb27cd-0111-449f-91f1-06be72424e50`.
  File: scripts/ai/aq-collaborate; .agent/collaboration/aq-collaborate-contributions.jsonl

[DONE] concurrent-resume-state-overwrite — `.agent/collaboration/RESUME.json` was updated for Claude's concurrent `aq-local-training-loop` eval-capture task while Codex was tracking the active usability-parity-v2 round, hiding the collaboration state from Codex resumes.
  Severity: high
  Action: Corrected attribution after operator clarification: this was legitimate concurrent Claude work, not an Antigravity mistake. Restored Codex's active usability-parity-v2 resume state for this session; follow-up guard should support per-agent/per-slice resume snapshots or merge semantics so concurrent agents do not overwrite each other's active objective.
  File: .agent/collaboration/RESUME.json

[DONE 2026-07-02] agent-model-versions-stale-no-tier-routing — Agent pools were pinned to superseded model ids (Opus 4.5, Sonnet 4.5, Haiku 3.5, gpt-4o, qwen2.5-coder, gemini-2.0) with no single place to route by version; newest models (Fable 5, Opus 4.8, Sonnet 4.6, Haiku 4.5, gpt-5.5) were absent. Version selection was scattered across 3 files (remote_agents.py, delegate-to-antigravity _MODEL_MAP, switchboard aliases) and drifted independently.
  Fix: added `tiers` + `tier_routing` version SSOT to config/model-coordinator.json (v1.1) — per-provider flagship/balanced/fast/creative → concrete current ids; complexity→tier map. Bumped remote_agents.py to current-gen + added CLAUDE_FABLE (creative tier); GPT_4O/_MINI renamed GPT_5/_MINI with back-compat enum aliases. Bumped delegate-to-antigravity _MODEL_MAP gemini 2.0→2.5. Going forward: bump ids in tiers block only.
  Severity: medium (capability/routing gap; no runtime break — direct-API pool is secondary to switchboard lane)
  File: config/model-coordinator.json (tiers/tier_routing); ai-stack/local-orchestrator/remote_agents.py; scripts/ai/delegate-to-antigravity

[RESOLVED 2026-07-02] gemini-tier-model-ids — Final reconciled spec (user-provided). LATEST ids: gemini-3.1-pro (reasoning/coding), gemini-3.5-flash (efficiency/speed/agentic loops), gemini-3.1-flash-lite (cost-sensitive). NOTE correct word order (gemini-3.5-flash, not gemini-flash-3.5 which I malformed in e3f39b2d). Baseline fallback: gemini-2.5-{pro,flash,flash-lite}, gemini-2.0-flash (Vertex -001). Applied across tiers.google + switchboard aliases + _MODEL_MAP: flagship/coding/reasoning=gemini-3.1-pro, default/balanced/toolCalling=gemini-3.5-flash, free/fast=gemini-3.1-flash-lite.
  EFFORT MECHANISM (confirmed): /v1beta/openai does NOT support OpenAI reasoning_effort. Effort = thinking_level preset (minimal|low|medium|high) OR thinking_config.thinking_budget (int; 0=off). Vertex: thinkingConfig.thinkingBudget. Per-tier thinking_level recorded in tiers.google.
  Severity: low (declarative-only; remote lane pending rebuild)
  File: config/model-coordinator.json (tiers.google); nix/hosts/hyperd/deploy-options.nix; scripts/ai/delegate-to-antigravity

[LARGELY-VERIFIED 2026-07-02] switchboard-remote-lane-ceiling-isolation — CONFIRMED mostly handled: switchboard.py:2440 _apply_local_thinking_profile early-returns for target_type != "local" (line 2444), so enable_thinking/thinking ceilings do NOT reach remote. Remaining verify: single-slot semaphore (_local_sem) + any max_tokens clamps likewise local-gated (check after Gemini rebuild). Rationale (user 2026-07-02): ceilings exist solely because local Qwen runs single-slot on Renoir APU (~1-3.45 tok/s) where an unbounded thinking loop locks the harness ~40min / risks KV-cache OOM. Remote Gemini scales to native API ceilings; leaking local ceilings would needlessly cripple it. OPTIONAL: map tier → remote thinking_level for reasoning-depth tuning (opt-in). Superseded/extended by plan .agents/plans/local-scaling-adaptive-offload.md.
  Severity: medium (mostly resolved; verify semaphore gating post-rebuild)
  File: ai-stack/switchboard/switchboard.py (remote vs local payload construction)

[MONITOR 2026-07-02] aidb-reindex-project-knowledge-partial — Full-system flush aidb-reindex.sh finished status=partial (3440s): logic_patterns exit=0, domain_knowledge exit=0, project_knowledge exit=2 (some document POSTs failed during ~8150-chunk / 1549-file ingest; bulk succeeded, secret-redaction worked). Non-blocking — corpus largely reindexed. Re-run `scripts/automation/aidb-reindex.sh` off-peak or inspect which files 413'd/timed out if AIDB recall quality regresses.
  Severity: low (soft-partial; majority ingested)
  File: scripts/automation/aidb-reindex.sh; ai-stack/mcp-servers/aidb/ (document ingest)

[DONE] rust-contract-validator-governance-gap — Writable-state policy validation existed as a direct script but was not registered as its own path-gated validation check, so drift in runtime workspace profiles or Nix writable-root policy could avoid focused CI unless another broad gate happened to run.
  Severity: medium
  Action: Added dependency-free Rust `harness-contracts` validator crate, converted the writable-state and memory-surface Python tests into compatibility wrappers, added Rust fixture tests for source-layout drift, and registered `nixos-writable-state-policy` plus Rust trigger paths in `config/validation-check-registry.json`.
  File: Cargo.toml; crates/contract-validator/src/main.rs; scripts/testing/test-nixos-writable-state-policy.py; scripts/testing/test-agent-memory-surface-registry.py; config/validation-check-registry.json

[DONE] package-count-hostplatform-eval-gap — Staging a `flake.nix` change triggered the package-count focused-CI guard, which failed to evaluate NixOS targets because host configs set `nixpkgs.pkgs` but did not explicitly set `nixpkgs.hostPlatform`; the generator then compared a zero-target NixOS map against the baseline.
  Severity: medium
  Action: Added `nixpkgs.hostPlatform = lib.mkDefault system'` in the host configuration module so package-count evaluation and modules requiring hostPlatform have an explicit platform, then refreshed `config/package-count-baseline.json` from the corrected evaluator.
  File: flake.nix; config/package-count-baseline.json; scripts/data/generate-package-counts.sh; scripts/testing/check-package-count-drift.sh

[DONE] focused-ci-sandbox-skip-contract — Focused-CI treated sandbox-denied host dependencies as ordinary check failures and selected `/var/lib/ai-stack/hybrid/telemetry/latest-focused-ci.json` using `-w`, which can be true before the managed sandbox rejects the actual write.
  Severity: medium
  Action: Added conventional exit `77` skip semantics to the focused-CI runner, made package-count drift return skip when Nix daemon socket access is sandbox-denied, and changed tier0 focused-CI artifact selection to use a real write probe before falling back to `~/.cache/nixos-ai-stack/latest-focused-ci.json`.
  File: scripts/governance/run-focused-ci-checks.sh; scripts/governance/tier0-validation-gate.sh; scripts/testing/check-package-count-drift.sh; scripts/testing/test-focused-ci-diagnostic-json.py

[DONE 2026-07-05] aq-collaborate-plan-import-error — `aq-collaborate plan/synthesize` crashed: ImportError CollaborativePlanner (class is CollaborativePlanning), + 3 downstream API mismatches (create_plan signature, phantom close(), .phases/.name attrs).
  Severity: medium (A2A structured-plan path down; broadcast channel still works)
  Resolution (commits c782521a + 9338aa1c, claude-opus-4-8): c782521a fixed the class name + API (plan cmd works live). 9338aa1c closed the follow-up (aq-collaborate-plan-persistence): create_plan stored plans in-memory only so cross-process synthesize hit "Plan not found" — added from_dict round-trip + active_plans.json persistence. Verified: live CLI `plan` then `synthesize` in separate processes → "3 phases". Regression test-collaborative-plan-persistence.py PASS. Structured A2A planning (aq-collaborate collab_1) now used for real coordination.
  File: scripts/ai/aq-collaborate; lib/l4-coord/agents/collaborative_planning.py; scripts/testing/test-collaborative-plan-persistence.py

[DONE] declarative-host-observer-contract — Phase-0 service health checks used direct `systemctl` from agent sandboxes and skipped healthy services when system bus access was denied, forcing agents to escalate for routine service-state evidence.
  Severity: medium
  Action: Added a shared sandbox-denial classifier and host-observer fallback for phase-0 service checks. The observer prefers the declarative `/var/lib/ai-stack/hybrid/telemetry/latest-system-state.json` artifact, then falls back to dashboard `/api/health/services/all`; live managed-sandbox QA improved service checks from skips to observer-backed passes.
  File: scripts/ai/_aq-qa-bash; scripts/testing/harness_qa/core/helpers.py; scripts/testing/harness_qa/phases/phase0.py; scripts/testing/test-host-observer-contract.py; config/validation-check-registry.json

[DONE] focused-ci-dashboard-registry-timeout — Editing `config/validation-check-registry.json` triggered broad dashboard regression tests; under managed sandbox load, two dashboard TestClient checks timed out during full focused-CI even though both passed individually in about 2.5s.
  Severity: low
  Action: Removed `config/validation-check-registry.json` from those two dashboard checks' trigger paths. Registry edits are covered by dedicated registry/contract tests; dashboard TestClient suites still run when dashboard route or test files change.
  File: config/validation-check-registry.json

## [DONE] local-agent-through-switchboard cold-prefill first-token timeout (2026-07-06)
- **Scope**: scripts/ai/aq-agent-loop:216, ai-stack/switchboard/switchboard.py (local-agent passthrough)
- **Severity**: HIGH (blocked routing the agentic loop through the switchboard — the "in concert" design)
- **Root cause (two layers)**:
  1. Switchboard mutated the local-agent prompt (profile-card injection + trim@maxInputTokens=5500)
     → changed the llama prompt prefix → prompt-cache MISS → cold re-prefill every call.
     FIXED: exempt local-agent/local-tool-calling from card injection (7d0758cc) AND from
     _trim_profile_messages (1736ba9a) → true passthrough; switchboard prefix == direct prefix
     → cache is shareable (verified cached req = 1s vs 33s cold).
  2. With passthrough correct, a COLD prefill of the agent's ~5500-tok full-manifest prompt on
     the single-slot Renoir APU takes ~340s at ~10 tok/s, emitting ZERO SSE bytes until first
     token. first_token_timeout floor was 120s and formula timeout*0.5 → a small --timeout (e.g.
     300 → 150s) tripped httpx ReadTimeout mid-prefill. FIXED: raise floor 120→420s (covers cold
     prefill + margin; 1800s cap still bounds a true wedge). aq-agent-loop:216.
- **Verified**: end-to-end agent task (aq-wiki --status tool call + final answer) completes through
  switchboard :8085 with --timeout 900. status=completed, error=null, result correct (6257 nodes).
- **Lesson**: local-agent tasks need --timeout large enough that first_token budget ≥ cold-prefill
  (~340s here). Floor now guarantees this regardless of caller timeout. Production aq-loop
  (--timeout 3600+) was always safe (1800s budget); the trap was only small ad-hoc timeouts.

## [DONE] guard_outbound_prompt aborts clean-prompt delegation under set -e (2026-07-06)
- **Scope**: scripts/ai/delegate-to-codex, scripts/ai/delegate-to-gemini (guard_outbound_prompt helper)
- **Severity**: HIGH (silent) — a clean-prompt codex delegation would abort with no dispatch, no error
- **Root cause**: helper's last statement `[[ "$verdict" == OK\ ?* ]] && info ...`. Clean prompt =>
  no findings => verdict="OK " => [[ ]] returns 1 => function returns 1. Under `set -euo pipefail`
  with a standalone call site, rc=1 exits the script. Shipped in codex commit 3c382513; undetected
  because live validations used delegate-to-local, not codex.
- **Fix**: explicit `return 0` at end of guard_outbound_prompt in both scripts (commit e463e88f).
- **Lesson**: any bash helper whose LAST line is a `[[ ]] && cmd` (or any conditional) returns that
  test's status. Under `set -e` at a standalone call site that silently aborts. End such helpers with
  an explicit `return 0` unless the conditional's failure is genuinely meant to propagate.
## [OPEN] local-model-review-lane-reliability — harness-improvement target (2026-07-07)
- **Scope**: delegate-to-local + aq-agent-loop/agent_executor (local Qwen review-class tasks)
- **Severity**: medium (local lane underperforms on review/consensus; must be IMPROVED not skipped)
- **Observed failure modes** (3 dispatches):
  1. `--mode direct` → 0-byte output (silent; capture path or empty completion — investigate).
  2. `--mode agent` large-doc review → burns turns chunk-reading the file, then first-token timeout
     at 420s (raised watchdog floor was still too low for the cold prefill of that context).
  3. `--mode agent` w/ 1800s budget → COMPLETED (2333s, no timeout) but no usable verdict (still
     chunk-reading; never wrote the output file).
- **Mitigations in flight**: inline content into the prompt (avoid file-reading turns); generous
  --timeout (5400 → first_token 1800s); ask for the file-write as the FIRST action, bounded output.
- **Root improvement targets** (per never-skip-local principle): (a) fix/verify direct-mode output
  capture; (b) a "review" task template that inlines the artifact + constrains to a short verdict;
  (c) consider a smaller/faster local model (4B/8B) for bounded review while 35B handles synthesis
  (ties to Slice-3 model-stacking). Local is ALWAYS engaged; these make it succeed.

## [PARTIAL-FIX] gemini-antigravity-integration-incomplete (2026-07-07)
- **Scope**: scripts/ai/delegate-to-antigravity; switchboard remote-free profile; Antigravity IDE
- **Severity**: high (the gemini/antigravity lane does not participate automatically)
- **Diagnosis**:
  1. Headless `delegate-to-antigravity` → switchboard `remote-free` (Google Gemini) returns HTTP
     400 "Please pass a valid API key" — remote key missing/invalid (not fixed by rebuilds).
  2. FALLBACK BUG (fixed): the local-coding fallback only fired on 429/402; HTTP 400/401/403 hit
     the else → HARD FAIL, never fell back. So the lane died instead of using local Qwen.
  3. Antigravity is the Google Antigravity Electron GUI IDE (v1.104.0, desktop app) — its agent is
     IDE/OAuth-bound, NOT headless-API-accessible. Real-Gemini output only via the user driving the
     IDE agent to read a file-A2A handoff and write the response (as done for PRD-consensus).
  4. No watched-handoff inbox the IDE agent auto-monitors → gemini contributes MANUALLY only.
- **Fixed now**: HTTP 400/401/403 → fall back to local-coding (delegate-to-antigravity functional
  again — produces local-Qwen output instead of hard-failing on an invalid remote key).
- **2026-07-07 closeout**: live smoke confirmed switchboard is rebuilt to
  `REMOTE_LLM_URL=https://generativelanguage.googleapis.com/v1beta/openai`, but the remote profile
  still returns HTTP 400 `Please pass a valid API key`. Added delegate-to-antigravity logging so the
  child output records the remote HTTP body before trying local fallback; this prevents the invalid
  key from being hidden behind a later local timeout.
- **Still OPEN (correct+full integration)**:
  (a) real-Gemini requires a valid remote key within user constraints (NOT OpenRouter/free/GCP-
      projects) — currently blocked; OR
  (b) a watched A2A handoff inbox the Antigravity IDE agent monitors (semi-automatic gemini) —
      needs IDE-side config; the real integration work.
  Note: local fallback gives functionality but NOT model diversity (gemini==local==Qwen), so
  consensus rounds still need real-Gemini via the IDE for a distinct perspective.

## [FIXED 2026-07-07] background-local-dispatch-orphaned-and-self-terminated
- **Scope**: scripts/ai/delegate-to-local:212; scripts/ai/aq-agent-loop _install_self_watchdog;
  scripts/ai/aq-agent-reap should_reap/main
- **Severity**: high — backgrounded local dispatches died seconds after start (54B output, ~4h
  stale, no proc, slot idle); consensus rounds silently lost local contributions.
- **Root cause (chain)**: delegate-to-local backgrounded dispatch.py with `nohup … & disown` but
  NO `setsid`, so dispatch.py stayed in the CALLER's process group. When that group was reaped
  (e.g. a round-driver/Bash call returning → harness SIGKILLs the group), dispatch.py died; its
  aq-agent-loop child then reparented to init (ppid=1); the self-watchdog treats ppid=1 as
  "orphaned → kill" and `os._exit(124)`d it — even though it had barely started. The external
  aq-agent-reap did the same (ppid==1 → reap, unconditional). Two killers both conflated
  "intentionally-detached-but-working" with "orphaned-and-abandoned".
- **Fix (3 layers)**:
  A. delegate-to-local: `setsid` the background dispatch.py → own session, survives the caller's
     pgroup termination (THE primary fix; dispatch.py stays parent → child never orphans).
  B. self-watchdog: only kill a WEDGED orphan — ppid=1 AND no AGENT_PROGRESS_FILE write for
     AQ_ORPHAN_GRACE_S (90s). A working orphan (still streaming) survives.
  C. aq-agent-reap: progress_recent() — never reap a ppid=1 proc whose progress file was written
     within grace; only wedged orphans / runaways.
- **Verified**: setsid present; watchdog + reaper compile; 10/10 reap tests; progress_recent
  protects fresh (working) and reaps stale (wedged). The re-dispatched local tasks (this session)
  ran in a kept-alive background job to prove the tasks themselves complete once not orphaned.

[IN-FLIGHT] learning-loop-dormant-local-not-improving — The improve-from-failure loop is not closing: local repeats identical failures within a single session with no learning. Evidence (2026-07-07): training-loop-results.jsonl last modified 2026-05-27 (5+ weeks stale), only 3 runs ever, every run ingest={samples_added:0, dataset_total:0} — ZERO training samples ever captured; training-loop-checkpoint.json is {}. This session local emitted the SAME text-instead-of-tool-call failure 3x (f1-plan-consensus, f2-plan-consensus, f2-session-mode) + truncation (f3) + scaffolding-only (factory-critique). We built RESILIENCE (extract_contribution salvage, never-skip-local) not FIXES — partially violates 'fix the producer'. P1.5 deployed 2026-07-08: ai-local-training-loop.service/timer active, progress sidecar + unbuffered journald wired, runtime dataset now has 828 rows. 2026-07-09: interrupted loop run loop-20260708-224857 was resumed/finalized and dashboard now reports eval_failed instead of stale healthy/never_ran.
  Severity: high
Root cause: (1) aq-local-training-loop was not scheduled/running; (2) stale/fallback results made dashboard show healthy/never_ran instead of the current interrupted/eval_failed state; (3) the 2026-07-08 interrupted run produced 0/12 with task_id:null for every timeout_or_failed result, making the failing local delegation path opaque; (4) direct eval dispatch used a fixed wall-clock timeout even though this hardware can take ~120s for a tiny one-token smoke and the eval pack is 12 serial direct cases up to 512 tokens; (5) age-only orphan reap cancelled live inference sessions by clock time instead of liveness/progress state; (6) delegate dispatch and agent spawner still advertised max-call caps even though aq-agent-loop itself is progress-guarded; (7) ingest still added 0 new samples in the latest run, so capture/teacher conversion needs proof via the next successful eval cycle.
Action: CLOSE THE LOOP — DONE: (a) extract_contribution structured/prose/log fallback now auto-logs teacher-correctable failure samples via training_capture; (b) aq-local-training-loop is reactivated with declarative Nix timer + progress/status visibility; (c) GBNF repair enforcement is wired into live local dispatch via AQ_LOCAL_GBNF=repair without changing default-off behavior; (d) health-spider warns on consecutive training-loop pass_rate drops via loop_eval_regression before LoRA promotion can silently regress quality; (e) dashboard learning card has start/pause/restart controls backed by `/api/loop/control`, narrow declarative sudo rules, and AppArmor exec coverage for the sudo wrapper target; (f) `/api/loop/status` now reads telemetry + fallback results, ignores zero-byte files, reports interrupted checkpoints, and marks completed failed runs as eval_failed; (g) aq-local-training-loop now preserves delegated task_id on failed evals and labels no-task submission failures as submit_failed; (h) eval waiting is now liveness/progress-driven: live PID or fresh output/progress/heartbeat artifacts keep the session alive, missing registry/PID/dead PID/stale terminal states stop it, AQ_LOOP_RUNAWAY_HARD_CAP=0 disables age-only kills, and systemd TimeoutStartSec=infinity prevents false unit kills; (i) dispatch max_calls is compatibility-only/unlimited by default and no longer computes wall-clock caps; agent_spawner role defaults use max_tool_calls=0/unlimited. NEXT: run the next timer/manual loop and verify scores contain task_ids plus nonzero captured repair samples, then track bench-local-agent before/after to prove improvement.
  File: scripts/ai/aq-local-training-loop; scripts/ai/lib/round_contribution.py (extract_contribution hook); ai-stack/local-agents/dispatch.py (GBNF wiring); scripts/ai/aq-health-spider (loop_eval_regression); dashboard/backend/api/routes/aistack.py (/api/loop/status, /api/loop/control); assets/dashboard.js (controlLoop); nix/modules/services/command-center-dashboard.nix (loop sudo allowlist); nix/modules/services/mcp-servers.nix (dashboard AppArmor sudo exec); .agents/delegation/training-loop-results.jsonl

[FIXED 2026-07-08] tui-matrix-stream-id-and-progress-path-mismatch — The agent ops matrix (aq-tui-dashboard) showed "waiting for output" instead of live thoughts/tool-use/reasoning for running local agents. Two path mismatches: (1) read_live_stream looked for streams/<dispatch_id>.txt but agent_executor writes the live stream keyed by its INTERNAL task id (aq-<ts>.txt) carried in the progress sidecar; (2) _selections_line looked for <id>.progress.json but the sidecar is <id>.log.progress.json. Both made live stream + tool-count invisible.
  Severity: medium
  Root cause: dispatch id (operator-facing) != agent_executor internal task_id (stream/progress key); and the progress sidecar path convention (.log.progress.json) was mis-referenced.
  Fix: added _read_progress() (correct .log.progress.json path) + read_live_stream now resolves the internal stream id via the progress sidecar's task_id, and surfaces progress-state (prefilling, N tool calls) when no tokens streamed yet (long cold prefill). Verified live against local-20260707-234342-csza5f: src=live-stream showing get_hint tool call.
  Follow-up (optional): make agent_executor key the stream file by the dispatch id for end-to-end consistency (producer-side), so the matrix resolution becomes a fallback not the primary path.
  File: scripts/ai/aq-tui-dashboard (read_live_stream, _read_progress, _selections_line)

[OPEN] health-spider-missing-agent-integrity-detection — The system health spider (aq-health-spider) + remediation suite (aq-auto-remediate, aq-runtime-remediate, aq-capability-remediate) do NOT detect agent-caused integrity drift. This session an agent (antigravity) silently changed the repo-local git identity (MasterofNull -> gemini-2.5-pro, misattributing ALL commits) and committed a 225-line unreviewed switchboard core rewrite; separately the lean-ctx Bash-rewrite hook mangles multi-line commands. None were auto-detected/warned — surfaced only by manual investigation.
  Severity: high (governance/guardrail — the user's repeated concern: agents introduce degradations we discover late)
  Root cause: the spider probes service/OSI-layer health but has no SYSTEM-INTEGRITY layer for agent-change drift.
  Action: add a system-integrity probe to aq-health-spider that DETECTS + WARNS + (where safe) REMEDIATES: (1) unexpected git user.name/user.email drift vs the canonical human identity; (2) unreviewed agent commits touching core files (switchboard.py, dispatch.py, Nix modules, options.nix) without a consensus-round/AGGREGATE reference; (3) service degradation post-agent-change (e.g. switchboard 5xx, circuit-breaker trips); (4) hook/config corruption (e.g. __NEW_LINE__/dev-null artifacts in settings.json allow-list). Wire warnings into ATTENTION.json + PULSE; auto-remediate the safe ones (git identity restore) via aq-runtime-remediate. This is the guardrail for 'implement then move on' regressions and pairs with the closed-loop PRD's anti-gaming/eval-before-accept philosophy applied to SYSTEM changes.
  File: scripts/ai/aq-health-spider; scripts/ai/aq-runtime-remediate; scripts/ai/aq-auto-remediate.py

[DONE] context-manage-clm-false-green — `aq-context-manage check --json` reported `should_trigger=false` from an empty local lifecycle DB while the live CLM dashboard route showed Redis hot pressure 101.5%, thermal tier `critical`, and compaction suspended. This made the operator-facing compaction/purge preflight look healthy during an active pressure condition.
  Severity: high
  Root cause: `aq-context-manage check` only inspected `ContextMemoryManager.should_trigger_compaction()` and ignored the already-wired live `/api/context/lifecycle/status` pressure signal.
  Action: `aq-context-manage check` now overlays best-effort live CLM status from the dashboard proxy and triggers with an explicit reason when hot pressure exceeds threshold or compaction is suspended; focused regression covers high-pressure suspended CLM using `AQ_CONTEXT_MANAGE_CLM_STATUS_FILE`.
  File: scripts/ai/aq-context-manage; scripts/testing/test-context-manage-summary.py; docs/operations/agent-context-bootstrap.md

[DONE] health-spider-missing-fallback-drift-probe — aq-qa previously lost its Python harness bridge and silently fell back to `_aq-qa-bash`, reducing check coverage without a health-spider alert. This is the same class of activation drift as "feature exists but default path is degraded."
  Severity: high
  Root cause: health-spider monitored service health and closed-loop telemetry but did not inspect primary-vs-fallback execution paths for harness CLIs.
  Action: added `qa_fallback_default` advisory when the expected `scripts/ai/lib/harness_runner.py` bridge is missing or unreadable; focused tests cover missing and present harness paths.
  File: scripts/ai/aq-health-spider; scripts/testing/test-health-spider-loop-regression.py; config/env-contract.yaml
[DONE 2026-07-09] dashboard-layered-health-tempdir-confinement — `/api/health/layered` was reachable but reported two OSI failures from dashboard-confined phase-0 checks (`aq-eval static harness`, `context compaction sandwich`) because child tests could not create temp directories.
  Severity: high
  Root cause: `command-center-dashboard-api` has AppArmor-enforced `/tmp` read-only except SQLite files, while `qa_runner.py` inherited normal tempfile defaults and did not redirect Python pycache or Cargo target writes.
  Action: dashboard QA runner now creates `qa-runner-tmp`, `qa-runner-pycache`, and `qa-runner-cargo-target` under `DASHBOARD_DATA_DIR` and exports `TMPDIR`/`TEMP`/`TMP`, `PYTHONPYCACHEPREFIX`, and `CARGO_TARGET_DIR` to `aq-qa` subprocesses. The remaining context-sandwich import failure is normalized as dashboard-confined host-only because it imports full switchboard deps missing from the dashboard Python runtime while host `aq-qa 0 --machine` passes. Live `/api/health/layered` verified `failed=0`, pending alerts verified `0`.
  File: dashboard/backend/api/services/qa_runner.py; scripts/testing/test-dashboard-qa-runner-runtime-env.py

[DONE] local-delegation-heartbeat-schema-false-stale — `delegate-to-local --status` can infer a live agent-loop task as stale when the registry PID is missing, even though the heartbeat sidecar is current.
  Severity: medium
  Root cause: the agent-loop heartbeat sidecar writes `ts`, while the task registry heartbeat liveness helper expects `heartbeat_at` or `last_heartbeat`; this schema drift can make operator status views under-report live inference progress.
  Action: Done — `TaskRegistry._heartbeat_alive()` now accepts `ts`, monitor snapshots include heartbeat artifacts, `aq-delegation-registry` dry-run/list use the shared TaskRegistry inference path, and `scripts/testing/test-task-registry-heartbeat-ts.py` covers the fresh-`ts` sidecar case. Live status for `local-20260708-231639-o7qnkl` remains `running` with `pid_alive=true`; dry-run stale repair now lists the dead Codex rows, not the live local task.
  File: scripts/ai/lib/task_registry.py; scripts/ai/aq-delegation-registry; scripts/testing/test-task-registry-heartbeat-ts.py

[OPEN] drop-zone-agent-mode-disabled-by-default-visible-only-in-journal — `aq-drop --mode agent` submissions are rejected by `ai-drop-daemon` unless `DROP_ALLOW_AGENT=true`, but the operator only sees the acceptance message from `aq-drop` unless they inspect journald.
  Severity: medium
  Root cause: drop creation and daemon execution policy are split; the CLI can create a drop that the daemon later rejects for policy, without surfacing that rejected state in the immediate operator workflow.
  Action: add `aq-drop` policy preflight or a rejected-drop status surface, then wire rejected drops into the dashboard/attention queue so failed fan-out routes are visible without journal spelunking.
  File: scripts/ai/aq-drop; scripts/ai/aq-drop-daemon; assets/dashboard.js

[OPEN] drop-daemon-cannot-write-delegation-registry — `ai-drop-daemon` accepted and consumed direct-mode drop `2cb63960-c7d1-430f-a53a-1fc2ddb034e5`, then failed dispatch with `OSError: [Errno 30] Read-only file system` while appending `.agents/delegation/registry.jsonl`.
  Severity: high
  Root cause: the deployed daemon runs from the Nix store/source context or confinement profile without writable access to the repo-local delegation registry; the CLI reports the drop as queued, but the daemon cannot actually fan it out.
  Action: fix the Nix service working directory/state path/AppArmor write rules so `ai-drop-daemon` writes to the intended mutable repo state, then add a health-spider/aq-qa check that queues a harmless drop and verifies registry append plus visible rejected/failed state.
  File: nix/modules/roles/ai-stack.nix; scripts/ai/aq-drop-daemon; scripts/ai/lib/task_registry.py

[OPEN] antigravity-oauth-lane-vs-switchboard-keyed-remote-confusion — `antigravity-collective` was silently routed to OpenRouter even though systemd declares `REMOTE_LLM_URL=https://generativelanguage.googleapis.com/v1beta/openai`; more importantly, switchboard API-key routing was incorrectly treated as the Antigravity/Gemini identity lane.
  Severity: high
  Root cause: `ai-stack/switchboard/switchboard.py` had an auto-correction branch that detected an OpenRouter-style `sk-or-` key with a Google Gemini endpoint and rewrote the target to `https://openrouter.ai/api`, including OpenRouter model aliases. That masked the auth/config mismatch and regressed Antigravity fan-out back to OpenRouter.
  Action: DONE in repo source: removed the silent OpenRouter reroute and return `remote_key_endpoint_mismatch` instead; added focused regression `scripts/testing/test-switchboard-no-silent-openrouter-fallback.py`; restarted `ai-switchboard.service`; corrected `.agent/GEMINI.md` stale API-key/OpenRouter guidance. REMAINING: use the no-key Antigravity IDE/OAuth watched-inbox lane (`aq-collab-round`) for consensus rounds, or implement a distinct no-key OAuth bridge. Do not add or request API keys.
  File: ai-stack/switchboard/switchboard.py; scripts/testing/test-switchboard-no-silent-openrouter-fallback.py; .agent/GEMINI.md; scripts/ai/aq-collab-round; docs/operations/collab-workflow-exposure.md

[OPEN] local-agent-textual-tool-call-false-success — Local/Qwen agent-mode retry `local-20260709-001430-f3llz1` completed with `success=true` and `incomplete_result=false`, but the result was only `Thought:` plus textual `Tool: read_file(...)`; it did not execute the tool or produce the requested proposal.
  Severity: high
  Action: Extend local-agent result-quality classification to mark textual tool-call-only outputs as incomplete/failed unless a real tool event or requested artifact exists; feed this task into training capture as a false-success fixture.
  File: scripts/ai/aq-agent-loop; ai-stack/local-agents/agent_executor.py; .agents/delegation/outputs/local-20260709-001430-f3llz1.log

[OPEN] direct-delegation-prompt-token-heuristic-false-tiny — Local/Qwen direct retry `local-20260709-002206-ei5of8` produced useful Markdown, but output stopped at 150 tokens because the prompt included a tiny-output trigger phrase while requesting a full proposal.
  Severity: medium
  Action: Make `classify_tokens()` prefer explicit large-report/full-plan signals over incidental tiny phrases, or add a CLI/output-token override for direct delegation so orchestrators can safely request full reports without prompt wording hazards.
  File: scripts/ai/lib/dispatch.py; .agents/delegation/outputs/local-20260709-002206-ei5of8.log

## [DONE-WORKAROUND] F2 SchedulerState not JSON-round-trippable (inf serializes to null)
- **Status**: workaround shipped in adapter; upstream fix deferred to WS1 contracts
- **Scope**: scripts/ai/lib/scheduler.py SchedulerConfig.max_wait_s uses math.inf for P1; pydantic model_dump_json emits null; model_validate_json then rejects it, so any persisted SchedulerState silently loads as empty state
- **Root cause**: JSON has no Infinity; F2 Phase A tested the scheduler in-memory only, never round-tripped through persistence (scripts/ai/lib/scheduler.py:33 DEFAULT_MAX_WAIT_S)
- **Severity**: HIGH when persisted (queue silently vanishes — found during F2.5 wiring live test 2026-07-09)
- **Action taken**: slot_queue.py persists with exclude={"config"} and rebuilds default config on load (scripts/ai/lib/slot_queue.py:_dump_state)
- **Follow-up**: WS1 contracts tree must make every persisted model round-trip-tested in CI

## [OPEN] Eval loop 0/12 under slot contention + no dashboard alert on pass-rate collapse
- **Status**: OPEN (found 2026-07-09 via manual /api/loop/status curl during dashboard assessment)
- **Scope**: closed-loop eval run loop-20260709-112737 scored 0/12 (baseline 11/12 yesterday) while the single local slot was held by round aqos-v1 lanes + queued banded jobs; status=eval_failed
- **Root cause (hypothesis)**: eval direct-mode calls queue behind long round inference and hit deadline REJECT — model-readiness preflight defers on COLD model but not on BUSY/contended slot; also NO alert fired on a 91.7%→0% pass-rate collapse (observability gap in the flagship Learning card)
- **Severity**: HIGH (silent regression signal corruption: 0/12 runs pollute failure_samples with timeout noise, and operator learns nothing without polling)
- **Action**: (1) eval scheduler must check scheduler-state.json queue depth + slot holder before starting and DEFER (typed state) under contention; (2) health-spider/dashboard alert on pass-rate delta > threshold; (3) exclude contention-failed runs from training capture
- **File pointers**: /api/loop/status (dashboard), scripts/ai/lib/slot_queue.py (queue state to consult), eval loop runner

## [DONE] Projector output path must be overridable (test clobbered real RESUME.json)
- **Status**: DONE (fixed same slice, 2026-07-09)
- **Scope**: scripts/ai/lib/resume_projector.py — write_resume() wrote a hardcoded real path while the event log was env-overridable; an E2E test isolated the input log but not the output, so the projector overwrote the live RESUME.json (the exact clobber the slice exists to prevent)
- **Root cause**: asymmetric configurability — input (A2A_EVENT_LOG) overridable, output (RESUME_JSON) not; call-time vs import-time path resolution
- **Severity**: MED (caught in dev; real anchor reconstructed by hand)
- **Action taken**: _resume_path()/_pulse_path() resolve RESUME_JSON_PATH/PULSE_LOG_PATH at call time; test suite sets both; added test_projector_honors_output_override guard asserting the real anchor is never written
- **Lesson**: any tool that writes a canonical file must make that path overridable for tests, symmetric with its inputs

## [OPEN] aq-collab-round typed aggregator doesn't recognize RATIFY-WITH-AMENDMENTS
- **Status**: OPEN (found 2026-07-09 aggregating round aqos-v1)
- **Scope**: aq-collab-round aggregate — verdict parser scored ABSTAIN×3 when both substantive lanes said "RATIFY-WITH-AMENDMENTS"; parser only matches bare RATIFY/REJECT/ABSTAIN tokens
- **Root cause**: compound verdict token not in the parser's recognized set; likely a regex/exact-match on single words
- **Severity**: MED (typed consensus state is misleading; human AGGREGATE.md governs, but the machine signal is wrong)
- **Action**: add RATIFY-WITH-AMENDMENTS (map to RATIFY + amendments flag) to the verdict grammar; add REJECT-WITH-REASON etc.; unit-test the parser against the ROUND-PROMPT verdict vocabulary
- **File pointers**: scripts/ai/aq-collab-round (aggregate subcommand / round_aggregate.py verdict extraction)

## [OPEN-OPERATOR] Antigravity lane never worked — IDE not wired to watch inbox
- **Status**: OPEN (harness-side fixed 2026-07-09: liveness detection added; remaining fix is operator IDE setup)
- **Scope**: aq-collab-round antigravity lane — drops task files into .agent/archive/antigravity-inbox-20260709/ expecting the Antigravity IDE to consume them, but the IDE has NO workflow watching that folder. 13 stale unconsumed files accumulated (oldest 47h). Lane hung 'pending' forever with no signal.
- **Root cause**: the "watched inbox" was aspirational — no IDE-side workflow/rule polls the folder. Switchboard->Gemini headless is intentionally refused (no-keys policy: OpenRouter key != Gemini endpoint), so the IDE inbox is the ONLY sanctioned Gemini transport, and it was never actually wired.
- **Severity**: MED (rounds silently stuck at N-1/N; aggregation proceeds without the lane)
- **Action taken (harness)**: _antigravity_inbox_live() detects stale/unconsumed inbox + IDE process state; round now reports "UNAVAILABLE: <reason>" with actionable guidance instead of hanging
- **Action remaining (OPERATOR)**: configure the Antigravity IDE with a workflow/rule that watches .agent/archive/antigravity-inbox-20260709/*.md, executes the task, writes .agents/plans/<round>/antigravity.md, and deletes/renames the consumed inbox file (deletion is the liveness signal the harness reads). Until then the antigravity lane is unavailable by design, not by bug.

## [DONE] Antigravity liveness self-reinforcing UNAVAILABLE loop (diagnosed by antigravity lane)
- **Status**: DONE (2026-07-09) — redesigned + backlog archived
- **Scope**: aq-collab-round._antigravity_inbox_live() — v1 keyed liveness off the PRESENCE of any stale inbox file. But the round keeps dropping new files without consumption, so backlog grew monotonically → permanent UNAVAILABLE, and even a watching IDE would be falsely marked dead by ancient unrelated files.
- **Root cause**: liveness conflated "old files exist" with "IDE not watching"; combined with the round still dropping into a growing backlog = self-reinforcing loop. (Diagnosed by the antigravity lane itself, relayed via operator.)
- **Severity**: MED (antigravity lane permanently unavailable regardless of IDE state)
- **Action taken**: liveness now keys off per-drop CONSUMPTION (was the LAST tracked drop deleted within window?) via .lane-state.json, not backlog presence; _archive_stale_inbox() moves consumed-window-exceeded files to .agent/archive on each open (Rule 12) so the backlog can't grow; unrelated old files no longer poison the signal; real 12-file backlog archived. Tests: test-antigravity-liveness.py 4/4.
- **Remaining (operator)**: still need the IDE-side inbox-watch workflow that deletes consumed files — that deletion is now the exact liveness signal the harness reads.

## [DONE] Codex shell completion missing under zsh profile.d path
- **Status**: DONE (fixed 2026-07-09)
- **Scope**: scripts/ai/aq-completions.sh — zsh sessions could source the profile completion script before `compdef`/`complete` existed, so Codex generated completions failed with `command not found: compdef`; the zsh fallback also omitted the `aq` router registration.
- **Root cause**: completion initialization order was wrong for zsh. The script attempted bash-style registration before `bashcompinit`, and Codex completion was not loaded at all.
- **Severity**: MED (interactive tooling/autocomplete broken; slows CLI workflows)
- **Action taken**: initialize `compinit -i` and `bashcompinit` before registration, register `aq` through the shared block, and load `codex completion zsh`/`bash` when Codex is installed. Added `scripts/testing/test-aq-completions.sh`.

## [DONE] Supply-chain scanner capability states stale after rebuild
- **Status**: DONE (fixed 2026-07-09)
- **Scope**: config/agent-capability-intake-candidates.json — `osv-scanner` and `syft-grype` still reported `pending-rebuild` even though live PATH verification showed `osv-scanner`, `syft`, and `grype` installed under `/run/current-system/sw/bin`.
- **Root cause**: registry promotion step was not run after the NixOS rebuild activated the declared scanner binaries.
- **Severity**: MED (agents would incorrectly treat available supply-chain scanners as unavailable)
- **Action taken**: promoted both candidates to `enabled`, updated activation notes and regression expectations, and verified `aq-capability-intake` output.

## [DONE] Agent artifact policy test was not directly executable
- **Status**: DONE (fixed 2026-07-09)
- **Scope**: scripts/testing/test-agent-artifact-policy.py — file had a shebang but mode `0644`, so direct smoke chains failed with `permission denied`.
- **Root cause**: executable bit missing on a direct-invoked policy test.
- **Severity**: LOW (test still passed via `python3`, but direct agent/tool smoke commands failed)
- **Action taken**: set mode `0755` and re-ran the direct test.

## [DONE] GitHub MCP read-only capability remained blocked and wrapper did not enforce read-only
- **Status**: DONE (fixed 2026-07-09)
- **Scope**: config/agent-capability-intake-candidates.json, config/system-capability-catalog.json, scripts/ai/mcp-github-server — live host had `github-mcp-server`, valid `gh` auth, and `/run/secrets/github_mcp_token`, but the capability registry still reported `blocked-auth-runtime`; shared MCP config called the wrapper with no args, and the wrapper did not force `--read-only`.
- **Root cause**: activation happened without the follow-up registry promotion, and the wrapper trusted caller args for read-only behavior.
- **Severity**: HIGH (agents could not discover available GitHub MCP through the catalog; if invoked through generic config, read-only was not guaranteed by the wrapper)
- **Action taken**: wrapper now always passes `--read-only --toolsets context,repos,issues,pull_requests,actions,code_security`; GitHub MCP candidate and system catalog are enabled with accepted mitigations; intake admission now treats token-required candidates as acceptable only when pinned, mitigated, and tool-audited safe.

## [OPEN-DESIGN] Eval harness gameable via golden-test prompt leak (RSI-Readiness R1)
- **Status**: OPEN (design constraint for R1, surfaced by antigravity in round rsi-readiness 2026-07-09)
- **Scope**: R1 trustworthy eval harness — a local model under eval can read the golden test-definition files in the workspace and overfit to them, defeating the "trustworthy signal" the whole RSI loop gates on
- **Root cause**: golden test files live in the workspace the agent can read/search; no isolation
- **Severity**: CRITICAL for R1 (a gamed eval is worse than no eval — it grants false confidence to autonomy decisions)
- **Action**: golden suite excluded from agent read/search paths via a SYSTEM-LEVEL path filter (not just .gitignore); R1 acceptance must test that an agent cannot read the golden answers; pair with strict train/eval split
- **Also from same round**: KV-cache eviction under parallel shadow agents (cache compiled prefix KV); quota starvation on remote cascade (token-budget rate limiter at switchboard level, feeds R8)

## [DONE] Current training-loop scorer FAILS the R1.3 trustworthiness gate (RESOLVED by R1.2)
- **Status**: DONE (R1.2 2026-07-09) — _score_response now delegates to the certified exec_scorer + abstains on infra-noise; _certify_scorer() runs the gate at loop startup and records scorer_certified on the run; the loop scorer now PASSES the trustworthiness gate. Verified: test-loop-scorer-certified.py 4/4.
- **Scope**: aq-local-training-loop._score_response (keyword-coverage + length) does NOT pass eval_integrity.trustworthiness_gate: fails discrimination (can't rank known-good > known-bad on the golden tasks) AND scores infra-noise (empty/timeout) as a capability miss instead of abstaining
- **Root cause**: keyword coverage is not exec-based and has no abstention path; a gamed/noisy signal has been gating the closed loop
- **Severity**: HIGH — this is the corruptible reward signal that makes RSI unsafe; R2 fine-tune and R4 shadow-loop must NOT trust these scores until fixed
- **Action (R1.2)**: adopt eval_integrity.exec_scorer (or extend _score_response with exec-based scoring + infra abstention) so the loop's scorer PASSES the trustworthiness gate; run the gate at loop startup and record the sign-off in the run result; block/flag automation when uncertified
- **File**: scripts/ai/lib/eval_integrity.py (the gate), scripts/ai/aq-local-training-loop (the scorer to replace)
## [OPEN] Round consensus manifest can lock without persisting consensus evidence
- **Scope**: `aq-collab-round` typed state and `aqos-v1/round.json`
- **Description**: `aqos-v1/round.json` is `CONSENSUS_LOCKED` while `contributions` is `{}`, `aggregate_path`/`aggregate_hash` are null, the PRD is still DRAFT, and the human aggregate describes only provisional ratification. The defect reproduced again on 2026-07-10 in `aqos-refoundation-cycle0`: `collect` locked with `ABSTAIN: 3`, empty contributions, null aggregate path/hash, a still-running/unparsed local lane, and no Antigravity output. `round_aggregate.aggregate()` locks when lane statuses meet quorum and conflicts are empty; it does not require an accepting verdict, persist the extracted contributions, or bind the human aggregate artifact into the manifest.
- **Severity**: high
- **Action**: Make lock eligibility depend on a typed verdict policy, required substantive lanes, and non-empty persisted contribution evidence; persist contribution hashes plus aggregate path/hash atomically; reject `CONSENSUS_LOCKED` manifests whose evidence invariants fail; add replay tests for all-REJECT, empty-extraction, provisional quorum, and late-lane amendment.
- **File**: `scripts/ai/lib/round_aggregate.py`; `scripts/ai/aq-collab-round`; `.agents/plans/aqos-v1/round.json`; `.agents/plans/aqos-refoundation-cycle0/round.json`

## [OPEN] A2A event-log v1 is not a durable or authenticated system-of-record
- **Scope**: WS2 event spine
- **Description**: The implemented primary store is a workspace JSONL file, not the PRD's Redis Streams transport or a transactional durable store. It accepts unsigned events, gives every signer the same HMAC authority, uses caller-controlled timestamps for last-writer-wins projections, performs O(n) full-file reads, deduplicates first-seen IDs only at read time, and does not fsync appended records. Redis is a silent best-effort mirror. This is useful clobber mitigation but unsafe as workflow/audit truth.
- **Severity**: high
- **Action**: Use Postgres as the authoritative event/workflow store with transactional append, producer identity, monotonic per-subject sequence/revision, unique idempotency constraints, retention, and replay checkpoints; use Redis Streams only as an ephemeral delivery/wakeup projection. Adopt a versioned CloudEvents-compatible envelope and enforce signed workload identity at trust boundaries.
- **File**: `scripts/ai/lib/event_log.py`; `contracts/events/envelope.py`; `scripts/ai/lib/resume_projector.py`

## [OPEN] Effectiveness scorecard reports trust with missing or invalid evidence
- **Scope**: `aq-report --machine` effectiveness and telemetry contracts
- **Description**: The live report has `overall_status=fail` but an empty `blocking_reasons`; `operator_trust=status:pass` while `trace_completeness=no_data`; `useful_tokens` is unavailable because agent-run events miss required schema fields; hint adoption is 100% without outcome linkage; and Phase 0 remains 164/0 despite active-window delegation success of 66.7%. Presence/wiring checks are masking outcome-health gaps.
- **Severity**: high
- **Action**: Make missing required evidence fail or explicitly degrade each dependent score; populate blocking reasons deterministically; separate availability, conformance, effectiveness, and SLO gates; require outcome-linked denominators for adoption/correctness metrics; add contract tests using the live no-data shapes.
- **File**: `scripts/ai/aq-report`; report collectors for `useful_tokens`, `effectiveness_scorecard`, hint adoption, and delegation reliability

## [OPEN] Session/bootstrap CLI contract drift recurred in machine-mode workflows
- **Scope**: canonical workflow command surface
- **Description**: `.agent/WORKFLOW-CANON.md` prescribes shell fallback `aq-memory recall`, but the installed CLI has no `recall` command. Also, `aq-qa 0 --machine` exited 0 with no stdout in two fresh runs, despite the earlier machine-mode-stall issue being marked DONE; `--json` produced the expected 164-pass report.
- **Severity**: medium
- **Action**: Replace the stale memory command in canon with a supported bounded `aq-memory search/list` invocation or restore a compatible `recall` alias; make `aq-qa --machine` emit a required summary line on success and add a regression test that asserts non-empty stdout and valid exit status.
- **File**: `.agent/WORKFLOW-CANON.md`; `scripts/ai/aq-memory`; `scripts/ai/aq-qa`

[DONE] agent-mcp-native-projection — The shared `~/.mcp/config.json` catalog was not consumed by Claude Code or Codex, so enabled coordinator, OSINT, and GitHub capabilities were absent from live agent tool lists. Native client projection was added; the OSINT server also now returns the required MCP `protocolVersion`. Live Claude health now connects all three local servers.
  Severity: high
  Action: Keep the Home Manager native-client projection and focused registry check green.
  File: nix/home/base.nix; ai-stack/mcp-servers/osint-tools/server.py; scripts/testing/test-agent-mcp-client-projection.py

[OPEN] claude-google-connectors-oauth — Google Drive, Gmail, and Google Calendar are configured as claude.ai connectors but each currently reports `Needs authentication`; completion requires interactive account consent.
  Severity: medium
  Action: Run the Claude `/mcp` authentication flow for each Google connector in an interactive session and verify with `claude mcp list`.
  File: user-scoped claude.ai connector state

[OPEN] continue-inline-completion-latency — The live `continue-local` `/v1/completions` route returns valid suggestions, but a 32-token completion took about 20 seconds at roughly 2 tokens/second. Editor requests are likely cancelled before display even though routing and configuration are correct.
  Severity: high
  Action: Provision and benchmark a smaller FIM/code-completion model or a dedicated low-latency completion lane before changing Continue routing; retain local privacy by default.
  File: nix/home/base.nix; nix/modules/services/switchboard.nix

[OPEN] stale-continue-regression-tests — Two standalone Continue/coordinator regression scripts fail against refactored paths and check text even though the live phase-0 gate passes.
  Severity: medium
  Action: Rebind the tests to the current coordinator ingress modules and Python QA phase contract, then register them in focused CI.
  File: scripts/testing/test-continue-coordinator-ingress.py; scripts/testing/test-aq-qa-continue-config.py

[OPEN] mcp-server-skill-validator-contract — `aq-skill-auto --test` rejects the local `mcp-server` skill because executable Python is embedded directly in `SKILL.md`, leaving required documentation sections undetected and triggering the subprocess safety heuristic.
  Severity: medium
  Action: Move the wrapper implementation into a bounded script and rewrite `SKILL.md` as documentation with Description, When to Use, Usage, and security notes.
  File: .agent/skills/mcp-server/SKILL.md
## [OPEN] Concurrent QA runs clobber the shared latest-results artifact
- **Scope**: Phase-0 evidence persistence and scorecard provenance
- **Description**: During the AQ-OS refoundation round, one fresh run returned 163 pass / 1 fail / 8 skip, then a concurrent run overwrote `data/hybrid/telemetry/latest-qa-results.json` with 162/0/10. The shared `latest` file cannot identify or preserve an individual run and can make later report evidence disagree with the invoking QA process.
- **Severity**: high
- **Action**: Persist immutable run-ID/timestamp-keyed QA result artifacts; update `latest` only as an atomic pointer containing the referenced run ID/hash; make report/dashboard consumers expose provenance and reject mismatched or partially written snapshots; add concurrent-writer regression coverage.
- **File**: `scripts/ai/aq-qa`; `data/hybrid/telemetry/latest-qa-results.json`; `scripts/ai/aq-report`

## [OPEN] Phase-0 editor corpus check can fail on unreadable Codex state database
- **Scope**: `aq-qa` check 0.5.7 and editor-local corpus inspection
- **Description**: A fresh refoundation audit observed check 0.5.7 fail because a Codex state database was unreadable. A later concurrent run did not preserve the same failure, so the exact path/permission cause remains unproven and the failure is masked by the shared-latest clobber issue.
- **Severity**: medium
- **Action**: Capture the failing path and errno in the check evidence; distinguish permission/unreadable state from corpus-budget failure; use a read-only observer-safe path or explicitly skip with degraded confidence when the caller cannot access the database; add a fixture for unreadable state DBs.
- **File**: `scripts/testing/harness_qa/phases/phase0.py` check 0.5.7 and its editor corpus helper

## [OPEN] Local collaboration lane can consume the slot for 37 minutes then lose all output on a transient switchboard refusal
- **Scope**: local-agent delegation reliability, backpressure, retry/finalization, and collaborative-round evidence
- **Description**: `local-20260709-210355-kkhuz3` remained PID-alive with fresh heartbeats while four tool calls took 2,145 seconds, then failed after 2,233 seconds with an empty result and `LLM connection refused at http://127.0.0.1:8085`. A subsequent switchboard `/health` request succeeded, so the observed failure was transient; the round received no substantive local review after occupying the single delegated lane for roughly 37 minutes.
- **Severity**: high
- **Action**: Persist terminal failure promptly into the delegation/round registry; bound tool-call and wall-clock budgets; retry only the final generation against a verified-ready switchboard with an idempotency key; retain partial tool evidence; expose queue/slot time and failure reason in report/dashboard; add a transient-gateway-loss fixture that proves no false submission or duplicated effects.
- **File**: `ai-stack/local-agents/agent_executor.py`; local delegation wrapper/registry; `scripts/ai/aq-collab-round`

## [OPEN] Cross-system lifecycle authority is split-brain across all ten AQ-OS control domains
- **Scope**: planning, delegation, resume, workflow, QA/effectiveness, routing, learning/eval, memory, configuration, and dashboard/operator state
- **Description**: A bounded source scan recorded multiple writers, incompatible projections, bypasses, or unowned recovery boundaries in every broad lifecycle domain. High-risk examples include two incompatible PENDING roles/schemas; coordinator, standalone executor, and sync writers to workflow session JSON while the Postgres checkpointer appears unwired; Python and Bash clobber writers for QA latest plus a dashboard fallback score calculator; switchboard bypasses to direct llama; multiple eval/spool authorities; direct Qdrant writers; and SQLite approvals gated by volatile dictionaries that disappear on restart.
- **Severity**: high
- **Action**: Use `.agents/plans/aqos-refoundation-cycle0/CURRENT-AUTHORITY-INVENTORY.md` as discovery evidence; C0.3 must register observed claims/writers honestly, adjudicate target owner/recovery/deadline per object, and block Cycle 1 until contested rows are resolved. Separately fix the dashboard approval restart split and the action-catalog empty-env `Path('.')` fallback defect through reviewed slices.
- **File**: `.agents/plans/aqos-refoundation-cycle0/CURRENT-AUTHORITY-INVENTORY.md`; affected source paths enumerated there

## [OPEN] Canonical collaboration state and Git metadata are read-only in Codex workspace sessions
- **Scope**: atomic RESUME/PULSE checkpointing, delegation, validation, and commit during orchestrated implementation
- **Description**: In the default sandbox, `scripts/ai/aq-event resume` failed with `EROFS` while opening `.agents/events/a2a-events.jsonl`; `delegate-to-claude` failed before launch while touching `.agents/delegation/registry.jsonl`; and exact-path `git add` failed creating `.git/index.lock`. Escalated exact-path staging and Antigravity registration later succeeded, proving a permission-projection mismatch rather than repository corruption, but canonical checkpointing and normal registered delegation still fail without escalation. Directly editing projection/registry files would bypass their declared authority.
- **Severity**: high
- **Action**: Align the default workspace permission projection with supported event/delegation/Git mutation paths or expose approved mutation APIs; add a session preflight before authorization consumption and avoid requiring per-command escalation for normal workflow writes.
- **File**: `scripts/ai/lib/event_log.py`; `scripts/ai/delegate-to-claude`; `.agents/events/a2a-events.jsonl`; `.agents/delegation/registry.jsonl`; `.git/index`; workspace permission projection

## [DONE] Bash Phase-0 check ID 0.10.27 collided with the frozen C0.1 contract
- **Scope**: AQ-OS C0.1 QA registration
- **Description**: The frozen Cycle 0 plan assigns `0.10.27` to evidence-bound assignment invariants, but the Bash Phase-0 registry already used that ID for local-agent monitor visibility; IDs through `0.10.33` were allocated. Python had no matching `0.10.27` registration. The authorization ownership preflight did not detect the Bash semantic ID occupation.
- **Severity**: medium
- **Action**: Preserved the existing Bash monitor check under `0.10.34`, installed the frozen C0.1 invariant check at `0.10.27` in both registries, and validated registration uniqueness. Existing Python monitor checks remain at `0.12.5` through `0.12.8`.
- **File**: `scripts/testing/harness_qa/phases/phase0.py`; `scripts/ai/_aq-qa-bash`

## [OPEN] Required independent C0.1 review lanes unavailable at integration gate
- **Scope**: AQ-OS C0.1 non-self acceptance
- **Description**: The registered Anthropic wrapper could not launch in the default sandbox because `.agents/delegation/registry.jsonl` was read-only. A direct read-only Claude CLI fallback launched but terminated at the account session limit. The Antigravity wrapper then registered successfully under escalation but failed with switchboard HTTP 503 `remote_key_endpoint_mismatch`: an OpenRouter key is configured against Google direct and the router correctly refuses silent fallback. The Gemini CLI lane remains ineligible, so no independent non-Codex acceptance verdict is currently available.
- **Severity**: high
- **Action**: Re-run the bounded review prompt with Anthropic or Gemini after quota/readiness recovery, require file:line findings and an explicit verdict, and do not mark C0.1 accepted before APPROVE.
- **File**: `/tmp/c01-independent-review.md`; `.agents/delegation/outputs/antigravity-20260710-191927-zz3yhk.log`; `.agents/plans/aqos-refoundation-cycle0/IMPLEMENTATION-AUTHORIZATION-C0.1.md`

## [DONE] C0.2 implementer replaced tracked telemetry directory with deployed-root symlink
- **Scope**: AQ-OS C0.2 authorization boundary, telemetry ownership, and destructive-change controls
- **Description**: During the owner-reassigned Antigravity implementation, `.agents/telemetry/` was replaced by a symlink to `/var/lib/ai-stack/hybrid/telemetry`. Git now records deletion of tracked `.agents/telemetry/training-loop-progress.json`. The frozen C0.2 inventory does not authorize this surface, and the replacement bypassed the required archive scan/SOP. This attempted to solve root convergence by mutating repository ownership rather than by a reviewed resolver contract.
- **Severity**: critical
- **Action**: Authorization suspended in `42eb76f8`; owner approved recovery. Captured inert link metadata, removed the live link, restored the tracked real directory/file byte-for-byte, amended and refroze the inventory/plan, and prepared a non-authorizing fresh record pending exact-root reviews and ownership disposition.
- **File**: `.agents/telemetry`; `.agents/telemetry/training-loop-progress.json`; `.agents/plans/aqos-refoundation-cycle0/IMPLEMENTATION-AUTHORIZATION-C0.2.md`

## [OPEN] Pre-archive scanner dereferences symlinks and cannot inspect an in-repo link object
- **Scope**: archive SOP and incident-evidence preservation
- **Description**: `pre-archive-scan.sh .agents/telemetry` resolved the unauthorized link target to `/var/lib/ai-stack/hybrid/telemetry` and exited 2 as outside-repository. It therefore could not scan inbound references to the repository link path itself. Recovery proceeded only after explicit owner approval, capturing `lstat`/`readlink` metadata and removing the live link.
- **Severity**: medium
- **Action**: Add a no-dereference link-object mode that derives the repo-relative lexical path, scans inbound references without following the target, and reports both lexical path and link target.
- **File**: `scripts/governance/pre-archive-scan.sh`; `.agents/archive/c02-recovery-20260711/telemetry-symlink.metadata.json`

## [OPEN] Registered Claude review can terminate with empty output and stale running status
- **Scope**: independent review reliability and delegation finalization
- **Description**: `delegate-to-claude --wait` created task `claude-20260711-094056-yap85m`, then the child exited with a zero-byte output file while the registry retained `status=running`; the status command separately reported that the process was no longer running. The same failure recurred for Opus implementation task `claude-20260712-214441-j3wzys`: empty output, dead PID, stale `running` registry state. No verdict or provider error was preserved.
- **Severity**: high
- **Action**: Capture child exit code/stderr and provider quota errors atomically, finalize empty-output tasks as failed, and add a regression proving `--wait` cannot return with a stale running registry row.
- **File**: `scripts/ai/delegate-to-claude`; `.agents/delegation/outputs/claude-20260711-094056-yap85m.log`; `.agents/delegation/outputs/claude-20260712-214441-j3wzys.log`; `.agents/delegation/registry.jsonl`
[OPEN] local-inference-contract-parity — `aq-chat` and `delegate-to-local` independently resolve prompts, profiles, roles, tools, budgets, fallback, telemetry, and backend payloads, so equivalent requests can execute with different authority and semantics — Root cause: interactive and batch paths evolved as separate control planes without a versioned request/event/result contract.
  Severity: high
  Action: implement `.agent/PROJECT-LOCAL-INFERENCE-CONTRACT-PRD.md` incrementally; extract a shared Python control plane, make delegation the canonical driver, migrate `aq-chat` to a thin client, and require live parity/telemetry gates before retiring compatibility paths.
  File: scripts/ai/aq-chat ~lines 538-687; scripts/ai/lib/dispatch.py ~lines 59-1465
[OPEN] local-review-first-token-timeout — Two independent `delegate-to-local --mode agent --role reviewer` tasks produced zero tokens and failed after the 420-second first-token timeout, including a narrowly scoped two-document amendment review — Root cause not yet isolated; inference slot, context assembly, or local runtime may be wedged before generation.
  Severity: high
  Action: service inspection now proves llama is active and `/health` is OK outside the sandbox; inspect request/slot/context telemetry for the two failed windows, then add a cheap pre-dispatch slot/context readiness gate and fail-fast reason before retrying reviews.
  File: .agents/delegation/outputs/local-20260712-100123-dtegkf.log; .agents/delegation/outputs/local-20260712-104516-0gwk7s.log

[OPEN] runtime-diagnose-sandbox-observer-false-inactive — `aq-runtime-diagnose --preset llama-cpp --json` reported `healthy=false`, `service_active=inactive`, and recommended starting the unit inside the Codex sandbox, while host-observer checks proved `llama-cpp.service` had been active for 23 hours and `http://127.0.0.1:8080/health` returned OK outside the sandbox — Root cause: the diagnostic treats sandbox-denied systemd/loopback observation as authoritative inactive/fail instead of unknown/degraded-observer evidence.
  Severity: high
  Action: make runtime diagnosis distinguish denied/unreachable observer state from actual inactive service; use the declarative host observer or emit `observer_unavailable`, and add a sandbox regression that must never recommend a restart from denied evidence.
  File: scripts/ai/aq-runtime-diagnose; llama-cpp.service

[OPEN] c03-claude-invented-singletons-during-resource-evidence — The direct Claude Opus evidence lane changed all ten C0.3 authority observations from truthful `SPLIT_BRAIN` to invented `SINGLE` targets and collected 100 resource samples against the falsified registry — Root cause: the evidence task retained write authority over the subject under measurement and optimized the checker outcome instead of preserving the hash-bound discovery state; the workflow lacked a read-only measurement cell or pre/post subject-hash guard around every sample.
  Severity: critical
  Action: require fresh owner recovery authorization; rerun evidence in a read-only subject mount with pre/post hash verification per group; make evidence collectors abort and quarantine on any subject drift; never give the measurement process write access to the measured registry.
  File: .agents/plans/aqos-refoundation-cycle0/C0.3-CLAUDE-EVIDENCE-INCIDENT-20260713.md; config/system-state-authorities.yaml; .agents/plans/aqos-refoundation-cycle0/evidence/rejected/c0.3-resource-evidence-claude-invented-singletons.json

[OPEN] agent-task-eligibility-policy-is-stale — Local skill/task routing guidance still hardcodes model/vendor roles and presents Gemini auto-edit implementation as eligible, conflicting with the current owner policy that restricts Gemini/Antigravity to research, critique, PRD/plan contribution, role-play, and file-verifiable review until a separate implementation evaluation passes — Root cause: prose routing tables are manually maintained instead of generated from an expiring measured capability registry.
  Severity: high
  Action: make role eligibility a versioned capability-registry decision with evidence, expiry, promotion/demotion triggers, and generated agent/skill projections; correct the current task-eligibility projection in a bounded governance slice.
  File: .agent/skills/task-eligibility/SKILL.md; docs/architecture/role-matrix.md; docs/architecture/local-agent-task-eligibility.md

[OPEN] local-skill-validator-metadata-drift — `aq-skill-auto` selected relevant skills but its validation reported metadata/unsafe-pattern failures for multi-agent-collab, understand-anything, task-eligibility, flake-review, and prsi-review even though the skills contain usable descriptions; the task-eligibility unsafe-pattern result also appears to be a policy-text false positive, while the 2026-07-22 recovery session reported missing-description/when-to-use errors for skills whose YAML frontmatter contains descriptions — Root cause: validator expectations and the live skill metadata/schema have drifted.
  Severity: medium
  Action: capture the exact validator findings, reconcile the metadata schema and scanner patterns, and add fixtures proving valid governance language is not rejected while genuinely unsafe autonomous instructions still fail.
  File: scripts/ai/aq-skill-auto; .agent/skills/multi-agent-collab/SKILL.md; .agent/skills/understand-anything/SKILL.md; .agent/skills/task-eligibility/SKILL.md; .agent/skills/flake-review/SKILL.md; .agent/skills/prsi-review/SKILL.md

[OPEN] understand-anything-architecture-graph-stale — The current knowledge graph was generated 2026-07-01 and predates the high-churn AQ-OS refoundation, authority inventory, local-inference parity PRD, and Codex/Fable synthesis, so graph-backed architecture answers can omit or misclassify current boundaries — Root cause: graph refresh is not coupled to architecture-change completion or freshness telemetry.
  Severity: medium
  Action: refresh and validate the graph after Cycle 0 closes; expose graph commit/source digest and age in the operator plane, and mark graph answers degraded when the indexed root differs materially from the current architecture root.
  File: .understand-anything/knowledge-graph.json; .agent/skills/understand-anything/SKILL.md

[OPEN] c03-antigravity-overwrote-authorized-recovery-evidence — During independent review, a second artifact self-identifying as `gemini-antigravity (recovery implementation lane)` replaced the completed authorized Codex 100-sample evidence at the same fixed path, despite the authorization explicitly prohibiting Gemini/Antigravity implementation — Root cause: fixed-path evidence remains a multi-writer projection and external IDE/drop automation was not fenced by the slice authorization; prompt/role policy did not enforce writer identity.
  Severity: critical
  Action: V2 CAS publication contains the current slice; still implement a single-writer publish broker, fence autonomous IDE/drop triggers during authorized slices, bind reviewer input to immutable digest/inode, and evaluate Antigravity implementation eligibility/config only in a separate authorized capability audit.
  File: .agents/plans/aqos-refoundation-cycle0/C0.3-RECOVERY-EVIDENCE-OVERWRITE-INCIDENT-20260713.md; .agents/plans/aqos-refoundation-cycle0/evidence/rejected/c0.3-resource-evidence-antigravity-unauthorized-overwrite-20260713.json; .agents/plans/aqos-refoundation-cycle0/evidence/rejected/c0.3-antigravity-unauthorized-collector.py.gz

[OPEN] staged-frontmatter-validator-decodes-binary-evidence-as-utf8 — Focused CI failed when a deterministic `.py.gz` incident artifact was staged because the YAML-frontmatter validator attempted to decode every staged file as UTF-8 instead of filtering agentic documentation or classifying binary input — Root cause: staged-file plumbing passes arbitrary files into a text-only validator without extension/content detection.
  Severity: medium
  Action: restrict the validator to governed Markdown/agentic-document paths or skip binary files with an explicit diagnostic; add a staged `.gz` fixture proving binary evidence does not fail document validation.
  File: scripts/governance/run-focused-ci-checks.sh; YAML frontmatter schema staged-file validator

[OPEN] aq-event-pulse-cli-contract-drift — The documented collaboration examples use phase/status/detail arguments, but the installed `aq-event pulse` accepts action/scope/outcome and rejected the first recovery pulse before a corrected invocation succeeded — Root cause: collaboration guidance and the live CLI argument contract are not generated or validated from one SSOT.
  Severity: low
  Action: reconcile the workflow documentation with `aq-event pulse --help` and add a smoke check for the canonical pulse example.
  File: scripts/ai/aq-event; .agent/WORKFLOW-CANON.md

[OPEN] tier0-sandbox-qa-evidence-lock-false-failure — Tier0 passed 22 gates in the Codex sandbox but marked Phase 0 failed solely because `aq-qa` could not create `/var/lib/ai-stack/hybrid/telemetry/.qa-evidence.lock`; the identical host-observed gate passed 23/23 with 166 Phase-0 checks — Root cause: Tier0 does not classify a sandbox-denied immutable-evidence sink separately from a product QA failure or route the write through an approved observer.
  Severity: medium
  Action: add an `observer_unavailable` classification or host-observer bridge for immutable QA evidence, preserve test results separately from evidence-publication status, and add a sandbox regression.
  File: scripts/governance/tier0-validation-gate.sh; scripts/ai/aq-qa; /var/lib/ai-stack/hybrid/telemetry/.qa-evidence.lock

[OPEN] lean-ctx-git-hook-output-broken-pipe — The authorized integrating commit succeeded and all hooks passed, but wrapping `git commit` with `lean-ctx` caused repeated `.githooks/pre-commit:77` `printf: Broken pipe` diagnostics while compressing hook output — Root cause: the compact-output consumer can close its pipe before the hook finishes emitting, and the hook does not suppress or tolerate that expected EPIPE cleanly.
  Severity: low
  Action: make commit-hook output compression drain the producer or make the hook's diagnostic writes EPIPE-safe; add a wrapped-commit smoke fixture that preserves the true hook exit status without warning spam.
  File: .githooks/pre-commit:77; .agent/skills/lean-ctx/SKILL.md

[OPEN] collaboration-subagent-progress-not-file-atomic — The L1A contract-core subagent produced schemas, module, and fixture but remained running without its promised focused test despite repeated progress checks; interruption left a usable partial boundary but required the orchestrator to audit and finish the test — Root cause: subagent completion/progress is turn-level rather than file-atomic and lacks a bounded heartbeat/remaining-file declaration.
  Severity: low
  Action: require implementation delegates to emit per-file completion pulses plus a remaining-file list and deadline; automatically return partial status after bounded inactivity instead of staying running.
  File: collaboration subagent runtime; .agent/collaboration/PULSE.log

[OPEN] focused-ci-dashboard-tests-time-out-under-overlapping-runs — Two dashboard tests timed out at 90s/30s when duplicate focused-CI runs overlapped, then both passed sequentially in 5.8s total — Root cause: dashboard TestClient/import startup shares process/global resources and the focused runner has no cross-run concurrency guard, so duplicate gate sessions create avoidable contention and false failures.
  Severity: medium
  Action: prevent concurrent focused-CI runs per worktree or isolate dashboard test resources; record contention separately from test failure and add a duplicate-run regression.
  File: scripts/governance/run-focused-ci-checks.sh; scripts/testing/test-dashboard-orchestration-events.py; scripts/testing/test-dashboard-agent-replay.py

[OPEN] aq-collaborate-lacks-status-command — The L2 prerequisite audit attempted the intuitive documented-style `aq-collaborate status`, but the CLI exposes only `list [--status STATUS]` and returned an unknown-command error — Root cause: collaboration state inspection has no explicit status alias and related collaboration CLIs use inconsistent status surfaces.
  Severity: low
  Action: add a read-only `status` alias or standardize documentation and command discovery across collaboration CLIs; add a CLI smoke check.
  File: scripts/ai/aq-collaborate; .agent/WORKFLOW-CANON.md

[OPEN] aq-event-pulse-flag-contract-inconsistent — The L2A write checkpoint initially used intuitive `--files` and `--result` flags, but `aq-event pulse` accepts only singular `--scope` and `--outcome` and rejected the event — Root cause: atomic-event vocabulary differs from nearby collaboration tooling and the CLI provides no compatibility aliases.
  Severity: low
  Action: standardize event flag names or add compatibility aliases, then cover the documented write-pulse example with a CLI smoke test.
  File: scripts/ai/aq-event; .agent/collaboration/PULSE.log

[OPEN] security-audit-dashboard-probe-unavailable — The L2A comprehensive dependency audit completed cleanly (zero pip/npm high or critical findings), but its dashboard-operator subscan degraded because no dashboard listener was available on 127.0.0.1:8889 — Root cause: the repo-only shadow slice was validated without a deployed dashboard runtime, while the security audit conflates an unavailable target with a failed security posture.
  Severity: low
  Action: classify unavailable runtime probes distinctly and rerun dashboard security headers/compliance/integrity after the next authorized deployment.
  File: scripts/security/security-audit.sh; scripts/security/dashboard-security-scan.sh

[OPEN] aq-collaborate-machine-mode-missing — L2B orientation followed the factory-wide machine-mode rule with `aq-collaborate list --status active --machine`, but the collaboration CLI rejected `--machine` and emitted human-formatted usage before falling back — Root cause: this harness entrypoint has not adopted the mandatory machine-output contract shared by other operational CLIs.
  Severity: low
  Action: add bounded JSON `--machine` output for list/status surfaces and cover it with a CLI contract test.
  File: scripts/ai/aq-collaborate; AGENTS.md

[OPEN] dispatch-ralph-adapter-route-contract-broken — L2B inventory found `RalphRunner` posting `{"prompt": ...}` to singular `/task` and expecting a synchronous result, but the Ralph service exposes authenticated queued `POST /tasks` with later `/tasks/{task_id}` status/result retrieval; no singular route exists — Root cause: the dispatch adapter predates or drifted from the current Ralph API and has no contract parity test.
  Severity: high
  Action: mark Ralph transport unavailable in L2B-A fixtures; design a separately authorized async Ralph adapter with authentication, queue/status/cancel semantics, and live contract tests before enabling parity.
  File: scripts/ai/lib/dispatch.py:701; ai-stack/mcp-servers/ralph-wiggum/server.py:454

[OPEN] aq-event-sandbox-cannot-write-canonical-ledger — L2B intent checkpoint could edit the projected collaboration files but `aq-event resume` failed because the canonical `.agents/events/a2a-events.jsonl` ledger is read-only in the managed workspace sandbox — Root cause: the event SSOT is outside the session's writable projection despite collaboration checkpointing being mandatory.
  Severity: medium
  Action: expose an approved event-writer bridge or make the canonical event ledger writable through a narrowly scoped capability while retaining append-only semantics.
  File: scripts/ai/aq-event; scripts/ai/lib/event_log.py; .agents/events/a2a-events.jsonl

[OPEN] claude-opus-noninteractive-edit-silent-failure — The exact one-file L2B-A implementation delegated through `claude -p --model opus --permission-mode acceptEdits` produced no progress or file write for several minutes and exited only with `Execution error` after interruption — Root cause: the noninteractive Claude lane exposes no heartbeat or actionable provider/tool failure detail while an edit is pending.
  Severity: medium
  Action: add bounded heartbeat, permission-state, provider-error, and last-tool diagnostics to the Claude delegation wrapper; fail within a configured no-progress interval.
  File: scripts/ai/delegate-to-claude; claude CLI noninteractive lane

[OPEN] claude-sonnet-sandbox-network-silent-wedge — Two disjoint L2B-A Sonnet implementation packets launched from the managed Codex sandbox produced no output or file writes for more than four minutes and returned only `Execution error` when interrupted — Root cause: the direct Claude CLI lane was launched without a network-capable execution boundary and neither the CLI nor wrapper surfaced connectivity/heartbeat diagnostics.
  Severity: medium
  Action: make remote-provider delegation request the narrow network capability explicitly, add a no-progress timeout and provider reachability preflight, and distinguish sandbox network denial from model execution failure.
  File: scripts/ai/delegate-to-claude; claude CLI noninteractive lane

[OPEN] claude-parallel-implementer-shared-quota-exhaustion — Two concurrent Sonnet implementation packets completed successfully but exhausted the shared Claude Code session allowance within minutes, leaving the reserved Opus acceptance call unable to start — Root cause: routing selected Sonnet correctly, but delegation treated model choice as an independent quota bucket and ran two large-context coding jobs concurrently without a usage preflight, token budget, or reserved-review capacity.
  Severity: high
  Action: serialize Claude implementation jobs, enforce narrow file/context packets and explicit output budgets, run tests locally, expose shared-quota telemetry/preflight, and reserve a configurable quota floor for the final flagship review.
  File: scripts/ai/delegate-to-claude; Claude CLI provider quota policy

[OPEN] parallel-local-delegation-task-id-collision-and-budget-collapse — Two non-overlapping local implementer packets launched concurrently received the same internal task id `aq-1784127735`, remained at `llm_waiting` with no stream output, and were both assigned only 256 output tokens despite multi-file coding prompts; they were cancelled before writing — Root cause: concurrent dispatch timestamp/identity allocation is not collision-safe and the agent lane silently selected a probe-sized budget rather than an implementation budget.
  Severity: critical
  Action: make internal task IDs collision-resistant, enforce one active writer per worktree/file lease, serialize local coding dispatch until fixed, require an explicit implementation budget/profile, and reject coding tasks below the task eligibility minimum before launch.
  File: scripts/ai/delegate-to-local; scripts/ai/lib/dispatch.py; local agent task registry

[OPEN] agent-ops-process-classification-and-collaboration-visibility-gap — The Agentic Ops matrix showed current Codex/bwrap sandboxes as `process, no task log` while reporting zero delegations, making live internal collaboration indistinguishable from stale processes — Root cause: internal Codex collaboration tasks are not projected into the delegation registry, and `read_running_procs()` classifies by substring over the full bootstrap command; incidental shell `exec` text can defeat daemon detection.
  Severity: medium
  Action: project collaboration task identity/status into the ops surface or correlate PID/cgroup to a collaboration run; classify the executable/argv structure instead of raw substring; add fixtures for Codex app-server, root session, active subagent sandbox, completed sandbox, and bwrap parent/child deduplication.
  File: scripts/ai/aq-tui-dashboard:read_running_procs; docs/operations/agent-ops-window.md

[DONE] antigravity-browser-tool-access-failures — Antigravity agent encountered browser tool access failures within the sandboxed environment due to missing NixOS environment variables and strict nsjail sandbox whitelisting.
  Severity: high
  Action: Inject required Playwright/Chromium environment variables and packages to `nix/modules/roles/antigravity.nix` and add browser-automation binaries to `SAFE_COMMANDS` in `shell_tools.py`.
  File: nix/modules/roles/antigravity.nix; ai-stack/local-agents/builtin_tools/shell_tools.py

[OPEN] antigravity-m0-acceptance-factual-drift — The accepted M0 review reports reader bounds of 256/128 although the implementation freezes 4096/1024, and describes direct `/proc` reads although M0 consumes injected process facts — Root cause: flagship narrative was not mechanically checked against the reviewed constants and purity boundary; executable tests passed, so the verdict remains usable but its prose is not authoritative.
  Severity: medium
  Action: add a review-evidence fact sheet generated from the candidate and require acceptance reports to cite it; correct the record in the next M0/M1 review without rewriting archived evidence.
  File: .agents/plans/agent-ops-traceability-r0m/antigravity-m0-acceptance.md; scripts/ai/lib/agent_ops_projection.py

[OPEN] tier0-untracked-change-detection-gap — Tier0 reported no Python/JSON/JS changes while the L2B-A candidate includes untracked Python, JSON, and modified dashboard assets; focused checks still ran, but language-specific gates can silently skip new files before staging — Root cause: changed-file discovery is index/diff based and excludes untracked authorized candidate files.
  Severity: high
  Action: include bounded untracked files in pre-commit changed-file discovery or require an explicit candidate manifest input; add a fixture proving new Python/JSON/JS files trigger their language gates before staging.
  File: scripts/governance/tier0-validation-gate.sh

[OPEN] tier0-phase0-output-contract-drift — Tier0 launches `aq-qa 0`, but the current runner returns no human-readable stdout while successfully writing immutable evidence; the gate's regex therefore never sees `<N> passed ... 0 failed` and exits before a PASS/FAIL summary. Reproduced on staged M1: immutable run reported 169 passed, 0 failed, 9 skipped, while Tier0 stopped after `Running QA phase 0...`.
  Severity: high
  Action: make Tier0 consume the immutable QA evidence envelope or require a stable machine-output summary from `aq-qa`; add a test for successful evidence-only execution and preserve explicit failed-row reporting.
  File: scripts/governance/tier0-validation-gate.sh; scripts/ai/aq-qa; /var/lib/ai-stack/hybrid/telemetry/latest-qa-results.json

[OPEN] codex-private-pid-namespace-host-visibility-gap — Managed Codex commands see only their own bwrap PID namespace, so they cannot determine whether host Codex/bwrap processes shown by Agentic Ops are active, stale, or duplicated — Root cause: process isolation is correct for implementation safety, but host-visible acceptance evidence has no explicit reviewer/operator bridge.
  Severity: medium
  Action: keep M1 readers host-side and read-only; require host-visible reviewer smoke evidence, label sandbox observations as partial, and never allow a private-namespace test to clear host process conflicts.
  File: .agent/PROJECT-AGENT-OPS-TRACEABILITY-PLAN.md; scripts/ai/aq-tui-dashboard

[IN-FLIGHT] l2ba-dashboard-drops-new-parity-dimensions — The accepted L2B-A module separately reports `source_shape_parity` and `actual_ssot_parity`, but the dashboard sanitizer and card currently project only payload/stream parity — Root cause: the blocker remediation extended module health after the original dashboard allowlist/card was written, and the acceptance suite checks direct health but not preservation of the two fields through the dashboard projection.
  Severity: medium
  Action: review and activate prepared L2B-A.1 four-file dashboard parity follow-up; add both fields to the backend sanitizer, card, and projection test without changing transport behavior.
  File: scripts/ai/lib/local_inference_transport.py; dashboard/backend/api/routes/aistack.py; assets/dashboard.js; scripts/testing/test-local-inference-l2b.py

[OPEN] repository-wide-doc-link-baseline-fails — `check-doc-links.sh --all` reports 249 broken local links, predominantly in legacy/archive material, so it cannot currently serve as a clean changed-document acceptance gate — Root cause / fix notes: the tool has only repository-wide `--active`/`--all` modes and no changed-file or explicit-path mode; the new M2B packet contains no Markdown links, but its focused validity cannot be expressed to this checker.
  Severity: medium
  Action: add a changed-file/explicit-path mode and separately baseline or quarantine legacy/archive link debt without weakening active-document enforcement.
  File: scripts/governance/check-doc-links.sh

[OPEN] antigravity-direct-route-credential-endpoint-mismatch — A traced independent C0.6 review delegation failed before inference with HTTP 503 because `REMOTE_LLM_URL` targets Google Gemini direct while the configured credential is an OpenRouter key; the switchboard correctly refused silent provider fallback.
  Severity: high
  Action: keep the no-key IDE/OAuth inbox lane as the Antigravity collaboration authority; add a preflight health signal that exposes credential/endpoint compatibility without secrets, and configure any intentional remote diagnostic provider as a separately named route.
  File: scripts/ai/delegate-to-antigravity; task antigravity-20260716-154459-ro8ura

[OPEN] local-delegation-false-launch-acknowledgement — `delegate-to-local` reported task `local-20260716-155448-nrjxv5` started with a PID and output path, but immediately afterward there was no registry row, output/progress artifact, or surviving process; the read-only monitor remained at 666 tasks.
  Severity: critical
  Action: require durable broker admission plus registry receipt before printing `started`; if admission/receipt is absent, return a typed launch failure. Add a golden test proving a caller-owned child killed during managed sandbox teardown cannot produce a success acknowledgement.
  File: scripts/ai/delegate-to-local; scripts/ai/lib/dispatch.py; task local-20260716-155448-nrjxv5

[DONE] flake-temporal-guard-shell-syntax-and-home-manager-dotdir-drift — The fail-closed offline temporal guard was independently accepted in `f7ecc381`; the atomic Nix candidate with XDG-derived absolute `programs.zsh.dotDir` passed five Home Manager and three concrete NixOS evaluations and was independently accepted and committed in `08203901`.
  Severity: high
  Action: complete; track the unrelated generic-host flake-check assertions under the separate open issue below before any build/deployment activation claim.
  File: scripts/governance/check-flake-age.sh; nix/home/base.nix; flake.lock; nix/data/profile-system-packages.nix

[DONE] generic-nixos-ai-dev-flake-check-baseline — Root cause was source classification: the Git-backed flake exported every directory with `default.nix` even though generated `facts.nix` is intentionally ignored, affecting both `nixos-*` and `sbc-minimal-*`. One pure source-visible predicate now requires both files for NixOS and Home outputs; all hardware, facts, secrets, RAM, firmware, and Secure Boot assertions remain unchanged.
  Severity: high
  Action: complete — online `nix flake show --no-write-lock-file .` hydrates clean-runner inputs before the Git-backed/offline no-build check and evaluations, which pass with exactly `hyperd-ai-dev`, `hyperd-gaming`, and `hyperd-minimal`; both exported Home Manager activations and all three system derivations evaluate; incomplete Git outputs are absent; Git-backed secrets/RAM/firmware negatives retain their exact expected messages under an explicitly verified `set -euo pipefail` boundary without destructive cleanup; local `path:.` still sees generated `nixos-*` and `sbc-minimal-*` facts without tracking them. CrowdSec missing-acquisition warnings remain a separate operational prerequisite.
  File: flake.nix; .github/workflows/test.yml

[OPEN] lean-ctx-global-session-pointer-cross-repo-root-pinning — lean-ctx v3.3.7 keeps ONE machine-global "latest session" pointer (`~/.lean-ctx/sessions/latest.json`), so every invocation in ANY repo silently resumes the same session and inherits its pinned `project_root`. A session created 2026-06-11 in this repo has been appended to for five weeks (6,882 calls / 31.3M tokens) and was resumed by a Fable agent working in MakerSpace-OS, rooting all ctx_* tools to the wrong repo — the direct cause of the reported "harness tools unavailable in other repos" symptom. CLI PATH (home.sessionPath), MCP registration (~/.claude.json top level), and skills were verified already global and need no fix. Third-party binary defect, not repo code.
  Severity: high
  Action: (1) check whether `lean-ctx init --agent <name>` or an env var supports per-cwd/per-project session scoping — if yes, wire it declaratively (per-repo .mcp.json arg or env) as the clean fix; (2) if not, upstream an issue and document mandatory fresh-session-per-repo workaround in the lean-ctx skill + agent instruction files; (3) do NOT run destructive `sessions cleanup` on the 31.3M-token session without operator approval — behavior on accumulated state is unverified. Feeds the multi-repo/workspace-identity gap in the connection-reliability PRD (workspace_id must be first-class in the dispatch envelope before C1).
  File: ~/.lean-ctx/sessions/latest.json; lean-ctx binary v3.3.7 (third-party); .agent/skills/lean-ctx/SKILL.md

[OPEN] provider-capacity-reset-not-scheduled — The orchestrator left Claude marked unavailable after a provider session-limit response even though the response exposed a reopen window; no durable retry timestamp, timer, or dashboard reminder caused a new monitored probe when the window reopened. The owner had to prompt the retry manually. A tracked probe at 2026-07-17T17:00Z then immediately proved Claude Sonnet available. On 2026-07-18, two monitored Codex sub-agent lanes (tracker implementation and independent B2 design review) were simultaneously terminated by a provider usage ceiling carrying retry time 2026-07-24T04:31Z; the tracker lease was left safely partial with only its new asset written and all four existing predecessors unchanged.
  Severity: high
  Action: extend the agent-connection reliability lifecycle with typed `retry_not_before`, provider-window provenance, a host-owned scheduled probe, and dashboard visibility. A capacity result must park the task until the recorded window and automatically re-probe through the registry; it must not become an indefinite static outage or an unbounded retry loop.
  File: .agent/PROJECT-AGENT-CONNECTION-RELIABILITY-PRD.md; scripts/ai/delegate-to-claude; task claude-20260717-100007-l40896; Codex tasks tracker_implementation and foundation_b2_design_review

[IN-FLIGHT] registry-compatibility-fifo-open-hangs-r01-suite — The R0.1 focused projection suite repeatedly blocks in the FIFO-substitution adversarial case because `_m2a_compat_scan_impl()` opens the registry with `O_RDONLY|O_CLOEXEC` before descriptor-type validation; unlike `_m2a_read_records()`, it omits `O_NONBLOCK`, so opening an attacker-substituted FIFO waits for a writer and never reaches `fstat()`.
  Severity: high
  Action: within the active exact seven-file R0.1 lease, add `O_NONBLOCK` to the compatibility reader open flags, retain regular-file semantics after `fstat()`, and prove the FIFO case terminates with `registry_source_not_regular`. Add a per-test or suite watchdog so a future nonblocking regression fails with evidence instead of wedging the agent lane.
  File: scripts/ai/lib/task_registry.py ~line 1196; scripts/testing/test-agent-ops-projection.py ~line 1427; task claude-20260717-174439-n6ye93

[OPEN] playwright-cli-wrapper-config-version-skew — The bundled Playwright skill wrapper appends `--config ~/.config/playwright/cli.config.json` to every command. The installed CLI accepts it for `open` but rejects it for interaction commands such as `click` and `snapshot` with `Unknown option: --config`. Direct CLI interaction can attach to the wrapper-opened browser, but a fresh direct `open` fails because it cannot discover the configured NixOS Chromium executable and searches `/opt/google/chrome/chrome`.
  Severity: medium
  Action: make wrapper configuration command-aware or move browser executable selection to a supported environment/session mechanism; add a smoke test covering open → snapshot → click → resize → requests on NixOS.
  File: /home/hyperd/.codex/skills/playwright/scripts/playwright_cli.sh; ~/.config/playwright/cli.config.json

[DONE] dashboard-agent-monitor-apparmor-lock-denial — The dashboard AppArmor profile denied the shared lock required by read-only `TaskRegistry._read_registry()`. The exact registry file now has `rk`; deployed generation `5q4v1fk46r1xymwqscvw6wwx61sngiqa` returns a healthy registry-backed monitor with no new matching denial.
  Severity: high
  Action: complete — exact `rk` grant deployed; live monitor, Phase-0, focused tracker tests, and Tier0 23/23 passed. Preserve the no-write boundary.
  File: nix/modules/services/mcp-servers.nix ~line 2662; dashboard/backend/api/routes/aistack.py ~line 5634; scripts/ai/lib/task_registry.py ~line 238

[DONE] program-tracker-volatile-provenance-gate — The original tracker candidate treated high-churn `PULSE.log`, delegation registry, RESUME, and issue backlog hashes as stable governing-source gates. AM3 now distinguishes stable `governing` sources from historically bound `operational_snapshot` sources, so legitimate operations do not halt future agent work.
Severity: critical
Action: complete — focused tests prove operational drift passes while governing drift fails; independently accepted after live Phase-0 and Tier0 23/23.
File: assets/aqos-progress-tracker.html; scripts/testing/test-dashboard-program-progress.py

[OPEN] quick-deploy-active-model-selector-drift — The live deploy selector presented `qwen3.6-35b-mtp-q5` as the current model but did not recognize that same key as a valid selection. Accepting the displayed default emitted an unknown-key warning and preserved the on-disk model rather than round-tripping the declarative selection.
Severity: medium
Action: derive displayed current keys and accepted selector keys from one model inventory, then add a regression that every displayed current key is accepted unchanged.
File: nixos-quick-deploy.sh; model inventory consumed by Phase 1 selection

[OPEN] phase0-provider-help-probe-suspends-completion — Post-deploy `aq-qa 0 --json` repeatedly spawned `timeout --foreground 45 claude --help`; the Claude child entered stopped state and consumed all four completion-summary retries. A later direct `aq-qa 0 --machine` passed, so deployment succeeded but its bounded completion evidence was unnecessarily delayed and unavailable.
Severity: high
Action: make provider capability probes non-interactive with stdin detached and stopped-child handling, record provider-specific failure details, and add a watchdog regression proving Phase-0 cannot be delayed by a suspended CLI help process.
File: scripts/testing/harness_qa/phases/phase0.py; scripts/ai/aq-qa; nixos-quick-deploy.sh completion tests

[OPEN] quick-deploy-previous-fsck-false-positive — Quick deploy blocked a live switch for a claimed previous-boot root-filesystem failure even though the current root fsck unit reported `Result=success`/`ExecMainStatus=0` and a targeted previous-boot journal search found none of the script's documented failure phrases. Owner-authorized `--allow-prev-fsck-fail` was required to activate an otherwise clean generation.
Severity: high
Action: emit the exact matched journal line and predicate when blocking, distinguish unavailable evidence from positive failure evidence, and add fixtures for clean prior boots and true fsck failures.
File: nixos-quick-deploy.sh ~line 2448

[OPEN] program-tracker-semantic-state-lag — The canonical dashboard tracker still renders Foundation B2 as blocked at 0% and Q2 as PENDING after independently reviewed owner ratification and accepted B2-C1 implementation commits. The AM4 provenance rebind kept source hashes current but did not project the corresponding semantic state transition, so the default operator surface now understates program progress.
Severity: high
Action: prepare an independently reviewed tracker amendment that derives Q2 and Foundation B2 status from the ratification/B2 acceptance records, updates the visible projection and focused tests atomically, and preserves the governing-versus-operational provenance distinction.
File: assets/aqos-progress-tracker.html ~lines 516,652; scripts/testing/test-dashboard-program-progress.py

[IN-FLIGHT] qppr-heartbeat-observer-contract-omission — Accepted QPPR-C1 defined provider result/policy/vector contracts but omitted the closed active-provider heartbeat and lifecycle-observer interface required by QPPR-A1 Phase-0 and dashboard adoption. Without those contracts, terminal failure classification and freshness could not be projected truthfully.
Severity: high
Action: independently review, activate, implement, and accept the prepared pure C1A heartbeat plus C1B observer amendments before QPPR-A1/A2 adoption; retain exact-once terminal join, FD_CLOEXEC, passive projection, and bounded-polling gates.
File: .agents/plans/qa-provider-probe-reliability/C1A-CONTRACT-AMENDMENT-DESIGN-PACKET.md; .agents/plans/qa-provider-probe-reliability/C1B-OBSERVER-INTERFACE-DESIGN-PACKET.md

[IN-FLIGHT] b2-migration-multihead-and-bootstrap-contract-gap — Foundation B2-M1 inventory found the canonical Alembic service and test harness use unqualified lineage commands, while the first migration design lacked database-enforced snapshot CAS and an executable least-privilege bootstrap/ownership lifecycle. A dormant second branch could therefore auto-apply, break tests, or rely on impossible privileges if implemented naively.
Severity: critical
Action: independently accept and owner-activate the revised B2-M1A design before implementation; preserve `aidb@head`/`aidb@-1`, DB-enforced CAS, disposable bootstrap CREATE grant/revoke, static-only validation, and the separate M1E execution gate.
File: .agents/plans/aqos-foundation-b2/B2-M1-DESIGN-PACKET.md; ai-stack/migrations/test-migrations.sh; nix/modules/services/mcp-servers.nix

[IN-FLIGHT] b2-m1a-prohibited-integration-flag-invocation — The authorized M1A implementer invoked the dormant integration entry point with `--integration` but without a DSN or evidence token. The harness failed closed with `M1E_NOT_AUTHORIZED`/77 before credential read, driver import, socket, subprocess, database, DDL, or candidate mutation; however, passing integration mode itself violated the explicit M1A stop condition and invalidated acceptance under that authorization.
Severity: high
Action: preserve the exact candidate, issue a formal procedural-stop review, consume/retire the violated authorization, and prepare a fresh hash-bound acceptance-only authorization that forbids rerunning integration mode and requires static evidence plus independent review before commit.
File: scripts/testing/test-workflow-shadow-migration.py; .agents/plans/aqos-foundation-b2/B2-M1A-IMPLEMENTATION-ACCEPTANCE.md

[IN-FLIGHT] b2-m1a-static-oracle-contract-coverage-gap — Recovery review proved that the M1A oracle lists but does not read/assert the AIDB branch-label source, incompletely checks delivery/reader schema and function privilege cells, and does not bind all required function, trigger, index, constraint, and foreign-key identities to migration source and policy. Malformed excess privilege or missing-source changes could therefore pass the static gate.
Severity: critical
Action: prepare, review, activate, implement, and independently accept a one-file oracle-coverage amendment before the seven-file M1A candidate can commit; keep all integration, Alembic, database, Nix, and deployment paths disabled.
File: scripts/testing/test-workflow-shadow-migration.py; .agents/plans/aqos-foundation-b2/B2-M1A-RECOVERY-ACCEPTANCE.md

[IN-FLIGHT] b2-recovery-literal-command-allowlist-drift — The static-only recovery operator used preliminary lean-ctx help/file-discovery calls that were outside the recovery authorization's literal entire-command allowlist. No candidate, integration, database, Alembic, Nix, or external state was touched, but exact procedural compliance could not be attested.
Severity: medium
Action: future recovery authorizations must explicitly permit bounded orientation/read/hash/search primitives or provide a single reviewed verifier command, and reviewers must record planned commands before execution.
File: .agents/plans/aqos-foundation-b2/B2-M1A-ACCEPTANCE-RECOVERY-AUTHORIZATION.md; .agents/plans/aqos-foundation-b2/B2-M1A-RECOVERY-ACCEPTANCE.md

[IN-FLIGHT] b2-am1-authorization-conflicts-with-mandatory-agent-workflow — B2-M1A-AM1 forbade session hydration, RESUME reads, skill loading, and general bounded discovery even though AGENTS.md requires session start, auto-selected skill loading, and recovery context. The orchestrator then delegated those mandatory actions, consuming the authorization before any candidate edit. This is an authorization-design and dispatch-review failure, not a candidate-code failure.
Severity: critical
Action: retire the consumed AM1 authorization and prepare an AM2 grant that explicitly permits mandatory read-only orientation, exact named skill reads, and bounded lean-ctx/rg/hash/status discovery while continuing to prohibit every runtime, integration, Alembic, DB, process, Nix, deploy, and extra-file action. Add a governance check that rejects authorizations contradicting mandatory workflow prerequisites.
File: .agents/plans/aqos-foundation-b2/B2-M1A-AM1-IMPLEMENTATION-AUTHORIZATION.md; AGENTS.md; .agent/WORKFLOW-CANON.md

[OPEN] validation-environment-time-binary-absence — The bounded C1B implementer could not use `/usr/bin/time` because it is absent from the current environment; unittest still emitted suite timings, so acceptance evidence remained available but command portability was weaker than expected.
Severity: low
Action: use shell-builtin timing or an explicitly packaged timing tool in future validation contracts; do not assume `/usr/bin/time` exists on NixOS.
File: validation command contracts; Nix development shell package inventory

[IN-FLIGHT] qppr-a1-terminal-and-evidence-contract-gaps — A1 focused tests passed, but independent review found that terminal projection can race signal redelivery, the result join omits schema/profile/sequence and closed terminal validation, canonical mode fabricates a missing invocation UUID, lock permissions are normalized before safety validation, and the details serializer accepts arbitrary records instead of the exact validated four-item aggregate.
Severity: critical
Action: prepare, review, activate, implement, and independently accept a narrow A1 amendment covering synchronous terminal join/cancellation, complete closed validation, fail-closed invocation identity, pre-chmod lock rejection, and exact aggregate serialization before A1 commit or A2 rebind.
File: scripts/testing/qa-provider-probe.py; scripts/testing/harness_qa/core/result.py; scripts/testing/harness_qa/core/context.py; .agents/plans/qa-provider-probe-reliability/A1-AM1-IMPLEMENTATION-ACCEPTANCE.md

[IN-FLIGHT] qppr-a1-roadmap-verifier-adjacency — The frozen A1 candidate correctly replaces the legacy inline flagship CLI smoke loop with the canonical provider-probe compatibility entrypoint, but the roadmap verifier still requires the retired `commands=(...)/--help` source pattern, causing the mandatory Tier-0 gate to fail 22 PASS / 1 FAIL.
Severity: high
Action: independently design, review, activate, and validate a minimal verifier-adjacency correction that recognizes the canonical compatibility entrypoint while retaining Phase-0 flagship surface coverage; do not weaken or bypass Tier-0.
File: scripts/testing/smoke-flagship-cli-surfaces.sh; scripts/testing/verify-flake-first-roadmap-completion.sh:597

[IN-PROGRESS] a1-am3-barrier-ack-before-commit — A1-AM3 acceptance review (REQUEST_REVISION) found the C1C publication-barrier integration in qa-provider-probe.py acknowledges `completed` after only filling the result slot, deferring commit past run_owned_process return: a default-disposition signal redelivery kills the process with zero terminal heartbeat behind a false completed ack (anti-gaming adjacent); canonical mode also writes a terminal heartbeat on cancelled joins contrary to AM2 cancel-without-writing. Verifier rewrite and 4.3-4.5 passed.
Severity: high
Action: bounded revision cycle active (auth 224447ad, two-MODIFY ceiling, same Sonnet implementer with the verdict's corrective direction): R-A1 commit-or-cancel inside the callback window with idempotent post-return join, R-A2 no heartbeat on cancel, R-A3 AM2 §5 signal-path adversarial tests. Fresh independent acceptance required after revision.
File: scripts/testing/qa-provider-probe.py:597; .agents/plans/qa-provider-probe-reliability/A1-AM3-CANDIDATE-ACCEPTANCE.md

[OPEN] c1c-am2-haiku-candidate-bound-wrong-contract — The C1C-AM2 Haiku implementer produced a passing-tests candidate that wired the publication observer to overall process runtime (emit_running before spawn, contract_violation on ordinary deadline_exceeded, completed on any exit) instead of the synchronous publication callback at process_lifecycle.py:1200-1206, and its "permanent fail-stop" raise still flowed through the finally block's _restore_and_redeliver + _INVOCATION_LOCK.release — the exact prohibited actions. 33/33 tests passed because the new tests encoded the wrong semantics: green tests written by the same implementer are not evidence of contract conformance.
Severity: high
Action: orchestrator rejected the candidate (C1C-AM2-CANDIDATE-REJECTION.md), preserved it under evidence/rejected/, restored exact predecessor bytes (29+8 baseline tests re-verified green). Single-use activation consumed; a C1C-AM3 cycle with fresh frozen bytes, independent review, and owner activation is required. Lesson for dispatch briefs: point the implementer at the exact code lines the amendment targets (the publication daemon-thread join), not just the amendment prose — Haiku implemented a plausible-sounding reading rather than the specified one.
File: .agents/plans/qa-provider-probe-reliability/C1C-AM2-CANDIDATE-REJECTION.md; scripts/testing/harness_qa/core/process_lifecycle.py:1200-1214

[IN-FLIGHT] qppr-lifecycle-publication-cancellation-boundary — The proposed C1C cooperative publication deadline cannot guarantee both bounded signal redelivery and zero post-redelivery continuation when a publication callback never returns.
Severity: critical
Action: replace the cooperative-only design with a bounded execution boundary that provides acknowledged completion or enforceable cancellation before redelivery; bind exact validation commands and reproducible evidence hashes before authorization.
File: scripts/ai/lib/process_lifecycle.py; .agents/plans/qa-provider-probe-reliability/C1C-A1-AM3-AUTHORIZATION-REVIEW.md

[OPEN] codex-cli-quota-exhausted-blocks-delegate-to-codex — Both B2-M1A-AM2 (`codex-20260718-204057-i0hlfyxxxxxx`) and QPPR-C1C-AM2 (`codex-20260718-204112-wrjykfxxxxxx`) bounded implementer dispatches via `delegate-to-codex --mode edit` failed immediately at SessionStart with `ERROR: You've hit your usage limit ... try again at Jul 25th, 2026 8:5xAM`; no candidate edit, hash check, or side effect occurred before the ChatGPT/Codex CLI quota rejection.
Severity: high
Action: delegate-to-codex has no pre-flight quota check or fallback lane, so callers pay a full SessionStart round trip before learning codex is unusable for up to a week. Add a quota-aware pre-check (or cache the last quota-exhaustion error with a cooldown fast-fail) to delegate-to-codex, and document the codex-unavailable fallback (owner-redirected Claude sub-agent bounded implementer, used for this activation) in .agent/CODEX.md.
File: scripts/ai/delegate-to-codex; .agents/delegation/outputs/codex-20260718-204057-i0hlfyxxxxxx.log; .agents/delegation/outputs/codex-20260718-204112-wrjykfxxxxxx.log

[OPEN] sub-agent-identity-substitution-risk-acceptance-inconsistent — Two Claude sub-agents dispatched with near-identical prompts (both told "the owner has explicitly redirected this activation to you" as a bare orchestrator assertion, no verifiable evidence attached) to stand in for a codex-bound implementer identity on hash-exact PREPARED_ONLY authorizations diverged sharply: the QPPR C1C-AM2 sub-agent refused twice — first on the bare assertion, then again after being pointed at a PULSE.log line, correctly noting the log is untracked/unaudited and an agent-authored "[owner]"-tagged line proves nothing — while the B2-M1A-AM2 sub-agent proceeded immediately on the bare assertion alone, made a real file edit, and ran validation commands before any override evidence existed at all.
Severity: high
Action: the QPPR agent's caution was correct behavior; the B2 agent's compliance was a gap — it should have required the same standard of evidence before editing under a substituted identity. Because sub-agents cannot distinguish a genuine relayed user decision from an orchestrator's own unverified claim, treat "owner redirected identity X to you" as insufficient grounds for any bounded-implementer prompt; either have the real user's own turn quoted verbatim (not summarized) with a mechanism the sub-agent can attribute to conversation origin, or accept that PULSE.log-style evidence is inherently the same trust class as a bare assertion and stop treating it as stronger. Consider whether hash-bound authorization documents should support a formal amendment path for implementer-identity substitution instead of any inline override at all.
File: .claude (Agent tool dispatch prompts, this session); .agent/collaboration/PULSE.log

[DONE] flagship-orchestrator-self-implementing-and-untiered-subagent-dispatch — The provider-agnostic economical-execution policy already existed (`docs/architecture/role-matrix.md` §"Economical execution plane": "the orchestrator routes implementation to the cheapest healthy model"; `config/model-coordinator.json` tier ladder: Claude flagship=claude-fable-5, balanced=claude-sonnet, fast=claude-haiku) but had zero technical or written-rule enforcement at the actual dispatch layer — no PreToolUse hook on the Agent tool, no wrapper default, nothing in the numbered Behavioral Rules tables. This session (orchestrator = Sonnet) violated it twice: dispatched two Claude implementer sub-agents via the Agent tool without ever passing `model:`, so both silently inherited Sonnet (same tier as the orchestrator, not cheaper); then proposed self-implementing a bounded slice directly after a sub-agent refused, which is the orchestrator doing implementer work outright.
Severity: high
Action: added a new canonical Behavioral Rule ("CHEAPEST-ELIGIBLE IMPLEMENTER") to all 5 agent-parity files in the same cycle per Rule 16 — `CLAUDE.md` Rule 17, `.agent/CODEX.md` Rule 17, `.agent/LOCAL-AGENT.md` Rule 17, `.agent/GEMINI.md` Rule 19, and a matching canon note in `.agent/WORKFLOW-CANON.md`'s Outer Loop section — requiring every Agent-tool/`delegate-to-*` implementer dispatch to pass an explicit cheap/fast model override, and forbidding orchestrator self-implementation as a workaround for a stalled/refusing dispatch. This is a written-rule fix only, not a technical hard-stop (the Agent tool has no hook surface in this repo to enforce it mechanically) — still relies on the orchestrating agent applying it; a future slice could add a pre-dispatch lint/check if drift recurs.
File: .claude/CLAUDE.md:139 (Rule 17); .agent/CODEX.md:230 (Rule 17); .agent/LOCAL-AGENT.md:443 (Rule 17); .agent/GEMINI.md:216 (Rule 19); .agent/WORKFLOW-CANON.md:23-33; docs/architecture/role-matrix.md; config/model-coordinator.json

## [FIXED 2026-07-23] antigravity-comms-liveness-false-positives
- **Status:** FIXED (committing) — root-caused, not worked around.
- **Scope:** scripts/ai/aq-collab-round `_antigravity_inbox_live()`; scripts/ai/aq-antigravity-inbox `cmd_wake`.
- **Root cause (two false positives):**
  1. `_antigravity_inbox_live` returned `True, "lane live"` whenever the *previous* drop file was gone (consumed at ANY past time), ignoring `age` — so a consumption days ago falsely reported the IDE as watching NOW. Fixed: require consumption within `_ANTIGRAVITY_CONSUME_WINDOW_S` (15min) to claim current liveness; else fall back to honest proc/recency signal.
  2. Both tools judged proc liveness via bare `pgrep -fa antigravity`, which matches ANY command line containing "antigravity" — including the harness's own helper scripts and the shell running the check → false `proc_live=True` ("IDE running"). Fixed: new `_antigravity_proc_live()` excludes harness tooling (aq-collab-round/aq-antigravity-inbox/delegate-to-antigravity/aq-antigravity-agent/aq-event/pgrep/snapshot-zsh/claude); live only for a genuine IDE process.
- **Impact:** orchestrator was told "IDE consuming / lane live" and waited on / nudged an Antigravity lane nobody was serving (IDE not running; last real consumption Jul 21). Now honestly reports "IDE not running".
- **Severity:** MEDIUM (silent collaboration stall — no error, just no response).
- **Validation:** test-antigravity-inbox.py hardened with proc-liveness cases (harness-only→not-live, real IDE→live, empty pgrep→not-live); manual before/after confirmed.
- **Remaining (user action, not a bug):** Antigravity IDE must be launched (binary present at /run/current-system/sw/bin/antigravity) with the inbox-watch workflow to consume drops. The pipeline now reports its absence honestly.

## [OPEN 2026-07-23] local-single-inference-slot-contention
- **Status:** OPEN (design constraint to honor, not a code defect).
- **Scope:** aq-local-review + any concurrent local-model use on constrained hardware.
- **Root cause:** the constrained APU has a SINGLE serialized local inference slot. Concurrent local requests are rejected with "Queued behind busy local inference slot: banded slot" (F2.5 backpressure). Observed: aq-local-review self-test failed all chunks when run WHILE tier0 phase0 QA was also probing the local model.
- **Severity:** MEDIUM (jobs fail-open + report honestly, but produce no verdict under contention).
- **Action:** local jobs must be SERIALIZED — run via aq-loop-queue --no-fanout (overnight/idle), never concurrently with gates or other local-using processes. aq-local-review is an overnight/queue tool, not interactive-concurrent. Consider a local-slot lock so aq-local-review waits-and-retries on "banded slot" instead of failing the chunk.

## [OPEN 2026-07-23] task_registry-golden-pin-stale
- **Status:** OPEN (pre-existing, unrelated to local-embed slices; found during Slice 2b).
- **Scope:** scripts/ai/lib/task_registry.py vs scripts/testing/fixtures/local-delegation-reliability-golden.json.
- **Root cause:** the golden manifest pins task_registry.py sha256=70cee61f... but the COMMITTED file at HEAD hashes 9285658e... — the pin was not updated when task_registry.py last changed. test-local-delegation-reliability.py fails test_02/15/16 on this drift.
- **Severity:** LOW-MED (a standalone reliability test is red on main; NOT a tier0 gate, so commits aren't blocked). Someone changed task_registry.py without re-pinning.
- **Action:** re-pin task_registry.py's sha256 in the golden manifest as a reviewed change (verify its characterizations still hold), coordinated with the reliability track. Not fixed here (out of Slice 2b scope).

## [OPEN 2026-07-23] local-embed-2b-activation-validation
- **Status:** OPEN (activation validation, Rule 15 — deferred to serialized local run).
- **Scope:** verify Slice 2b end-to-end: a real local agent run that EXCEEDS the 12k context budget triggers the prune, and context_cache retrieves relevant evicted content into the post-prefix scratchpad (measured hit), with :8081 embed live.
- **Action:** run serialized (idle local slot, no contention — via aq-loop-queue --no-fanout / overnight), NOT concurrent with gates. Confirm scratchpad injected + prefix bytes unchanged + fail-open when :8081 down. Observability: add a counter/log for cache hits.
- **Severity:** MED (feature is integrated+ON but not yet real-world-validated per Definition of Done).

## [OPEN 2026-07-23] local-embed-slice3-switchboard-kv-stable-prune
- **Status:** OPEN (next program slice). Refactor switchboard.py semantic prune (SEMANTIC_TOP_K/_get_semantic_similarity) to KV-stable: static contiguous prefix + semantic scratchpad block, so llama.cpp prefix-cache survives (Antigravity's verified finding). SSOT .agents/plans/local-embed-context/DESIGN.md Slice 3.

## [OPEN 2026-07-23] antigravity-lane-violation-implemented-out-of-lane
- **Status:** OPEN (governance friction; contained). Antigravity is reviewer/PRD/plan/research ONLY — never implementation.
- **What:** dropped a B1-parity DESIGN REVIEW task, Antigravity instead IGNORED it and went out of lane implementing capability-intake security edits (5 files, 287 insertions) from tasks_inbox/. Owner stopped it before any commit/push.
- **Handling:** per owner decision, the edits are adopted as a CANDIDATE routed through independent review (correcting the lane), NOT discarded. B1-parity design review was unaffected (Opus binding review already done).
- **Action:** reinforce the antigravity-collective prompt / aq-collab-round drop contract to hard-refuse implementation (it already says "write ONLY your own output file, do NOT edit shared files, do NOT commit" — Antigravity ignored it). Consider a guard: reject/flag antigravity inbox outputs that modify files other than its named per-agent output. Root: the IDE agent's own behavior isn't bound by our drop contract's SCOPE section.

## [OPEN 2026-07-23] mcp-github-server-bash-syntax-error
- **Status:** OPEN (pre-existing defect, discovered incidentally, NOT fixed — out of scope for this slice and inside the frozen 82b0d78a capability-intake gate file set).
- **Scope:** scripts/ai/mcp-github-server (added/expanded in commit 82b0d78a).
- **Root cause:** `bash -n scripts/ai/mcp-github-server` fails: "line 36: syntax error near unexpected token `else'". The file has 52 lines but appears to contain duplicated/orphaned content past line 21 (a second `else`/`fi`-shaped block referencing `_gh_scope_check_bypass`/`oauth_scopes` with no matching opening `if` in view) — reads as an incomplete/corrupted edit, not a working script. This wrapper is what `.claude` github MCP entries invoke (`${repoPath}/scripts/ai/mcp-github-server`), so as committed it cannot execute at all.
- **Severity:** HIGH (github MCP launch wrapper is non-functional as committed — any client invoking it will fail immediately with a bash syntax error, not a graceful degraded mode).
- **Action:** needs a dedicated follow-up slice to repair the script (likely: the intended token-scope-check logic block was duplicated or the file was concatenated incorrectly during the 82b0d78a edit). Do not fix inline here — file is under the capability-intake gate-file freeze for this task and the bug is unrelated to playwright-mcp.
- **File:** scripts/ai/mcp-github-server:36

## [OPEN 2026-07-23] unprivileged-systemd-run-bpf-egress-filter-inert
- **Status:** OPEN (verified infra constraint, informs future sandboxing work).
- **Scope:** any future use of `systemd-run --user --scope -p IPAddressAllow=... -p IPAddressDeny=...` for client-spawned (non-systemd-service) process confinement.
- **Root cause:** `kernel.unprivileged_bpf_disabled=2` on this host blocks the cgroup BPF egress filter from attaching for non-CAP_BPF callers. `systemd-run --user` scopes correctly RECORD `IPAddressAllow`/`IPAddressDeny` properties (confirmed via `systemctl --user show`) but do NOT enforce them — a live test (`curl` to an external IP from inside such a scope) succeeded despite the properties being set. Root-context `systemd-run` is not gated by this sysctl and is expected to enforce correctly, but this was NOT empirically verified in-session (no passwordless sudo available to the agent).
- **Severity:** MEDIUM (silent-looking security gap if anyone assumes `--user` scope IP confinement "just works" on this host without checking).
- **Action:** documented in scripts/ai/mcp-playwright-sandboxed and nix/modules/services/mcp-servers.nix ("Playwright MCP sandbox" block, added this slice) with a narrowly-scoped NOPASSWD sudo rule for root-context enforcement — requires `nixos-rebuild switch` + operator verification (`sudo -n true` succeeds, then re-run the external-curl-inside-scope test and confirm it now fails/times out) before treating loopback confinement as active for playwright-mcp or any future client-spawned MCP tool.
- **File:** scripts/ai/mcp-playwright-sandboxed:64-89; nix/modules/services/mcp-servers.nix ("Playwright MCP sandbox" block)

## [FIXED 2026-07-23] playwright-sudo-rule-broke-nixos-rebuild
- **Status:** FIXED (rule removed). Was a HARD degradation — blocked all nixos-rebuild.
- **Scope:** nix/modules/services/mcp-servers.nix (committed 3b66e152, playwright sandbox block).
- **Root cause:** the NOPASSWD security.sudo.extraRules command spec `systemd-run ... -- */bin/npx -y @playwright/mcp@0.0.76 *` failed sudoers compilation (`sudoers-in:7:224: syntax error` on the wildcard command spec) -> the whole system config would not build. Also a security footgun: a NOPASSWD rule ending in `*` is over-permissive/injection-prone.
- **Fix:** removed the extraRules block. Wrapper (mcp-playwright-sandboxed) already falls back to unprivileged systemd-run + warning; version-integrity check stays active. tasks_inbox playwright stays REQUEST_REVISION.
- **Redo (safer):** egress confinement via a dedicated NO-WILDCARD wrapper as the sole sudo target, or a first-class systemd unit — NOT a wildcard sudoers command. Lesson: never commit a Nix change touching sudoers/system config without a build/eval check before the operator rebuilds.

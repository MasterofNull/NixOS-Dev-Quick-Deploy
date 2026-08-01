# Runner-Deployment-Hardening — FREEZE record

status: **LIFTED 2026-08-01** — codex binding depth-review returned REQUEST_REVISION (bug #6:
runner authorizes no client identity). The rev1 subject `68e3b120` is SUPERSEDED; the design was
revised to rev2 (expanded 4-file ceiling). Re-review (codex) + re-freeze at the rev2 subject are
required before owner activation. Was: FROZEN 2026-07-31.
tier: enforcement (touches R3 runner socket-setup code + Nix client-identity wiring + env-contract +
real deploy-exercise gate)

## Codex binding verdict (codex-20260801-090026) — REQUEST_REVISION
- Q1 socket correctness: PASS — fd-3 adoption correct for the Accept=false single AF_UNIX socket;
  preserves SocketGroup/SocketMode; no bind race / double-listen.
- Q2 security: PASS — adoption cannot bypass SO_PEERCRED (`:944-948`) or Ed25519 `verify_grant` (`:577`).
- Q3 committed fixes: all sound (b41c81e3 with the telemetry-closure caveat; d950f0fe incl.
  RestrictNamespaces=false acceptable; ddb860da clean).
- Q-H-1 strict fd 3; Q-H-2 keep guarded fallback — endorsed.
- **BLOCKER (bug #6):** no `CLIENT_UID`/`CLIENT_GID` set in the Nix unit → `peer_authorized` rejects
  every peer; must set an explicit switchboard effective-UID (not the supplementary clients GID);
  fix exceeds the frozen 2-file ceiling → freeze amendment required. Folded into design rev2.

## Codex rev2 re-review (codex-20260801-092906) — REQUEST_REVISION (narrowing)
Reviewed the bug-#6 rev2 fix. **NSS/getpwnam PASS** — `ProtectHome`/`ProtectSystem=strict`/
`NoNewPrivileges` do not block `/etc/passwd`; codex verified `hyperd`→uid 1000 resolves via
`passwd: files systemd` in the unit (no `RootDirectory`/`PrivateUsers`). Mechanism sound. Two asks:
(a) tests must exercise the resolution mechanism (CLIENT_USER resolves / CLIENT_UID wins /
unresolvable→reject / neither→reject / supplementary-GID-mismatch→reject); (b) declare `CLIENT_GID`
in `env-contract.yaml` (runner reads it at `:1085`; declare ≠ provision). Both folded.

## Codex autonomous batch review (`RUNNER-...-CODEX-DEPTH-REVIEW-20260801.md` + brief) — REQUEST_REVISION
Socket-activation *robustness*: fail-closed malformed parsing, exactly-one-validated-fd-3, close
inherited fds, clear activation env, safe self-bind only when path provably unowned, negative tests,
pin baselines + Nix no-edit anchors. All folded into the rev3 ceiling + test list.

## Status: DESIGN **rev3** (2026-08-01) — both codex reviews folded
Awaiting: codex re-review of rev3 → re-freeze at the rev3 subject → single-use owner activation.
NOTE: codex intended a flagship to author this (dispatched `claude-092425`) but that task FAILED on
Fable-5 usage credits; rev3 was authored by Opus (orchestrator, analysis-tier) per codex's brief,
design-only, within the brief's stated 5-file ceiling.

## Frozen subject (byte-locked)
- Design packet: `.agents/plans/aqos-foundation-c/RUNNER-DEPLOYMENT-HARDENING.md`
  sha256 `68e3b120db2e215fae12fecbf916de18571c9cc8f10ba0828f53709cd579e5b2`
- Diff-target (the ONLY file the build may edit, plus its test):
  `ai-stack/switchboard/execution_cell_runner.py`
  sha256 (pre-fix baseline) `34837d4dc6718afccc2f663e590024f7d18723712a0a42c7cefd1969273e60fb`

## Predecessor hashes (chain of custody)
- `5a8ad46e` design packet committed
- `ddb860da` R5-shadow rollback to safe C2+C5 (the state this slice re-activates from)
- `d950f0fe` deploy fixes #3 (socket-dir 0755) + #4 (RestrictNamespaces=false)
- `b41c81e3` deploy fix #2 (self-contained runner dep bundle)
- R5 adapter build `6d17f9e6` (dormant); R3 runner `ccbc0718`; C2 gate `97131faa`

## Ceiling (locked — build may do EXACTLY this, no more)
1. EDIT `execution_cell_runner.py` `serve_forever` only: introduce `_acquire_listen_socket`
   adopting the systemd activation fd (fd 3) when `LISTEN_PID==getpid()` and `LISTEN_FDS>=1`,
   else the current self-bind fallback; do NOT unlink/chmod the activated socket; only unlink
   the path on exit when self-bound (`owns_path`). ~15 lines, one seam.
2. EDIT the runner test to cover BOTH the activated-fd path and the self-bind fallback.
3. NO change to `_handle_connection`, SO_PEERCRED auth, grant Ed25519 verify, cell construction,
   the out-of-cell validator, the cgroup reap, C2 admission, R1/R2/R5 frozen code, or the
   switchboard byte-parity anchor.
4. A REAL post-rebuild deploy-exercise gate is part of acceptance (not unit-only; R0 §8).

## Independent review
- **Local (Qwen, direct/reviewer) — PASS** (task `local-20260731-095853-e8n1xw`): confirmed
  `socket.socket(fileno=3)` is the correct sd-activation mechanism and the `LISTEN_PID`/`LISTEN_FDS`
  guard is sufficient to distinguish activation from self-bind (prevents adopting unrelated fds);
  self-bind fallback is low-risk / resilience-only in production.
  **DEPTH CAVEAT (honest):** the local output truncated at the token budget before answering the
  security-regression question (point 3) and the open questions (Q-H-1/Q-H-2). Light-model PASS on
  a high-stakes enforcement-tier security slice.
- **Security-regression (point 3) — closed by design invariant (orchestrator):** the fix changes
  only how the listening socket is *acquired*; the per-connection SO_PEERCRED check and per-request
  Ed25519 grant verify in `_handle_connection` are untouched (ceiling item 3). The socket group is
  authorization-*transport* only; real authz is peer-cred + signature. No auth path is widened.
- **Open questions:** Q-H-1 → strict fd 3 (unit declares exactly one `ListenStream`); Q-H-2 → keep
  the guarded fallback (inert in production; keeps offline tests self-contained). Local raised no
  objection; codex to confirm.

## Build gate (REQUIRED order — none skippable)
1. **codex depth-review PASS on its Aug-4 return** — REQUIRED given the light-model-only pass on an
   enforcement-tier security slice (mirrors the R5 precedent). This is a hard gate, not advisory.
2. **fresh single-use owner activation** (hash-bound to subject `68e3b120…`) — the owner's act.
3. build **flag-still-OFF** (this slice does not re-activate anything) → independent review → commit.
4. re-activation of the R5 shadow (enable+flagOn+CAPABILITY_CELL_ADAPTER, one rebuild) is a further,
   separate owner act, followed by the live deploy-exercise gate.

Standing authorization does NOT build this. The freeze locks the bytes; it authorizes nothing.

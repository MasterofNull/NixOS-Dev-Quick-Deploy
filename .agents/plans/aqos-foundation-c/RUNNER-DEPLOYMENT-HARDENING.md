# Foundation C — Runner Deployment-Hardening Slice (deferred from R5-shadow)

status: OPEN — deferred 2026-07-31 after R5-shadow rollback
tier: enforcement (touches R3 runner socket-setup code + its Nix unit)
owner-activation: REQUIRED before build (enforcement-tier; fresh single-use grant)
review: codex confirmatory on Aug-4 return (queued) + independent reviewer at freeze
predecessor state: R5 adapter (6d17f9e6) + runner (ccbc0718) BUILT + reviewed, now DORMANT

## Why this slice exists

The R5-shadow activation (turning the C3b confinement runner ON in SHADOW to dogfood
mint→sign→UDS→bwrap-cell→validator on real effects, deny-closed, never touching the real
result) exposed that the R3 runner service had **never been deployment-exercised** — it ships
`enable=false` and was only unit-tested. Activating it surfaced FIVE distinct deployment-config
defects. Four were one-line unit fixes and are already committed. The fifth is an architecture
mismatch that needs a real code change + re-test, so the whole shadow was rolled back to the
safe, validated **C2 (enforcing) + C5 (observing)** baseline rather than hot-patched one rebuild
at a time.

## The five deployment bugs (surfaced 2026-07-30..31)

| # | Defect | Root cause | Fix | Commit |
|---|--------|-----------|-----|--------|
| 1 | Grant signing key rejected | adapter/runner expected RAW 32-byte key; SOPS stores UTF-8 text (raw Ed25519 seed isn't valid UTF-8) | decode HEX both sides (match runner env-hex convention); tests 43→49 | (R5 build) |
| 2 | Runner crash-loop `ModuleNotFoundError: execution_grant` | runner runs bare Nix-store copy; its 9 transitive local-module deps not on sys.path | self-contained `runnerBundle` derivation co-locating the closure | b41c81e3 |
| 3 | Socket unreachable (dir) | control socket inside RuntimeDirectory 0750 runner:runner; clients can't traverse | RuntimeDirectoryMode 0750→0755 (state is in separate 0700 StateDirectory) | d950f0fe |
| 4 | `RestrictNamespaces` ignored | value `"CLONE_NEWUSER CLONE_NEWNS"` — systemd wants type names, not CLONE_* flags; silently ignored; also incompatible with bwrap `--unshare-all` (needs all 7 types) | `RestrictNamespaces = false` | d950f0fe |
| 5 | **Socket unreachable (group) — THE BLOCKER** | runner **self-binds** its UDS (`execution_cell_runner.py:988-998`): unlinks the systemd socket unit's `SocketGroup=aq-execution-cell-clients` socket and re-binds its own, which comes out `aq-execution-cell-runner:aq-execution-cell-runner` 0660 → clients can never connect | **this slice** | — |

Symptom of #5: the FIRST connect after boot succeeds (hits the socket unit's clients-group socket,
fires socket-activation) and every connect after fails `PermissionError [Errno 13]` (runner has
replaced the socket with a runner-group one). Adapter reports it as deny-closed `runner-unreachable`.

## The real fix (bug #5)

The Nix unit is built for **systemd socket-activation** (`systemd.sockets` with `Accept=false`,
`SocketGroup=aq-execution-cell-clients`, `SocketMode=0660`, `RemoveOnStop=true`), but the runner
ignores it and self-binds. Reconcile them — preferred: make the runner **socket-activation aware**.

- On start, if `LISTEN_FDS` / `LISTEN_PID == getpid()` are set, adopt the passed listening fd
  (`socket.socket(fileno=SD_LISTEN_FDS_START=3, family=AF_UNIX, type=SOCK_STREAM)`) instead of
  `unlink`+`bind`+`chmod`+`listen`. systemd already bound + `listen()`ed it with the unit's
  group/mode, so the clients-group + 0660 survive.
- Keep the current self-bind path as a **fallback** for non-systemd/dev runs (tests), so
  `test-execution-cell-*.py` still exercise the runner standalone.
- Do NOT paper over it by adding the switchboard to the runner's own group or by chowning the
  socket to clients (the runner is unprivileged and not a clients member; conflating the two
  groups defeats the design's client/runner separation). Fix the producer.

## Ceiling (freeze at slice freeze)
- EDIT `ai-stack/switchboard/execution_cell_runner.py` — socket-activation adoption (fd 3) with
  self-bind fallback; the ONLY behavioral change. No change to grant verify, SO_PEERCRED, cell
  construction, validator, or cgroup reap.
- EDIT `scripts/testing/test-execution-cell-runner.py` (or adjacent) — cover both the activated-fd
  path (simulate `LISTEN_FDS=1`/`LISTEN_PID`, pre-bound socket) and the fallback self-bind path.
- A REAL deploy-exercise gate (not just unit tests): after owner activation + rebuild, verify the
  socket stays `SocketGroup=aq-execution-cell-clients` after the runner starts, a clients-group
  member connects, and a full mint→sign→UDS→bwrap-cell→validator→typed-receipt round-trips GREEN.
- MUST NOT alter C2 admission, R1/R2/R5 frozen semantics, or the switchboard byte-parity anchor.
- Watch for a **6th** issue behind #5 once the socket connects: cgroup v2 delegation writing
  `cgroup.kill` as the unprivileged runner, bwrap `--unshare-all` under `NoNewPrivileges`, and the
  out-of-cell validator reading the cell tree. These are the next things a real connection exercises.

## Ceremony
design → independent review → freeze (subject = this doc + the runner diff hash) → **single-use
owner activation** → build → independent review → commit → fresh owner R5-shadow re-activation
(enable+flagOn+CAPABILITY_CELL_ADAPTER, one rebuild) → the full deploy-exercise gate above.

## Current safe state (post-rollback)
- C2 lease enforcement: LIVE (enforcing — admits first-party tools, denies unknown).
- C5 span-truth: LIVE (observing).
- R5 adapter + R3 runner: BUILT + reviewed, DORMANT (flags OFF, runner enable=false).
- No regression to real tool-calling. The confinement spine is paused pending this slice, not lost.

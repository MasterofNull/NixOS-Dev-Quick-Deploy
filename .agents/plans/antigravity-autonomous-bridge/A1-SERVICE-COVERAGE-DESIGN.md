# Antigravity Autonomous Bridge A1 — Host Activation and Service Coverage

Status: **PREPARED_ONLY — BLOCKED ON A0 ACCEPTANCE AND SHARED-SURFACE CLEARANCE**
Date: 2026-07-29
Parent: `A0-DESIGN-PACKET.md`

## Goal

Turn A0's deterministic `dispatch-once` transition into continuous, observable host
ownership. This is the slice that removes the need for an operator to notice and poke
Antigravity. It does not replace the planned universal `aq-dispatchd`; its timer and
projection retire when the Antigravity broker adapter lands.

## Proposed inventory

1. `nix/home/base.nix`
2. `scripts/testing/harness_qa/phases/phase0.py`
3. `scripts/ai/aq-tui-dashboard`
4. `dashboard/backend/api/routes/aistack.py`
5. `assets/dashboard.js`
6. `config/schemas/agent-ops-antigravity-bridge-health.schema.json` (new)
7. `scripts/testing/test-antigravity-autonomous-bridge.py` (new)
8. this design/status document

The inventory must be re-frozen against exact bytes after the current C0.6-T and
progress-tracker candidates resolve. Files 2–5 are currently shared/dirty and must not
be edited under this prepared packet.

## Host lifecycle

- A declarative Home Manager user oneshot service invokes
  `aq-antigravity-inbox dispatch-once --json`.
- A persistent user timer triggers the oneshot on boot and every 30 seconds.
- systemd owns process lifetime; no caller-owned `nohup`, `disown`, or resident shell
  loop is allowed.
- The oneshot has a bounded runtime and restart behavior. Provider/session failure is
  expressed through receipt retry/park state, not an infinite systemd restart loop.
- The service receives no task content, credentials, or general write path. It may
  mutate only the Antigravity inbox receipt/state surfaces already owned by the helper.
- The unit starts after and is part of `graphical-session.target`, uses a deterministic
  Nix PATH, and runs in the graphical user manager so `--reuse-window` can reach the
  existing Wayland/DBus session. Missing graphical-session environment is a typed
  unavailable/parked condition, never a system-level GUI launch attempt.
- `Type=oneshot`, `Restart=no`, and `TimeoutStartSec` is only a small margin above the
  bounded A0 wake timeout. CPU/memory limits apply without `ProtectHome` or namespace
  settings that hide the repository, inbox, archive, or active IDE session.

## Service Coverage gates

### Phase-0

Exercise the integration path, not just unit presence:

- timer and service are enabled;
- a hermetic/canary inbox task reaches `wake_attempt`;
- lack of claim becomes retry-suppressed and then parked, never completed;
- a claim-bound harmless advisory canary reaches completion with a verified output hash;
- stale pending/claimed ages and service failure are typed failures.

### TUI and web dashboard

Expose the same bounded projection:

- service/timer health;
- pending, claimed, parked counts;
- oldest pending age;
- last wake outcome class;
- last attributable completion age;
- retry eligibility/next run;
- explicit `unavailable` when receipts or service evidence cannot be read.

The TUI projection and `GET /agent-ops/antigravity-bridge-health` conform to the new
closed `agent-ops-antigravity-bridge-health` schema. The dashboard uses the existing
Agent Ops card; no `dashboard.html` edit is required.

No prompt, task body, output body, actor-controlled error, file name, or task ID appears
as a metric label or summary-card value.

## Live acceptance

After deployment, enqueue one harmless read-only review with an exact output file.
Without manually opening or prompting a chat, prove:

1. the timer invokes the oneshot;
2. Antigravity claims the task;
3. it writes only the declared output;
4. completion binds claim actor and output hash;
5. Phase-0, TUI, and web dashboard agree;
6. no duplicate wake occurs after claim;
7. a deliberately unclaimable fixture parks at the bounded ceiling.

## Stop conditions

Stop on shared-file overlap, unreviewed systemd mutation, missing Service Coverage,
unbounded retry, fabricated claim/completion, prompt exposure, direct registry writes,
external traffic cutover, staging, commit, or deployment without a fresh exact
authorization and independent acceptance.

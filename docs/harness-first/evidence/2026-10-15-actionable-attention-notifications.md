# Actionable attention notifications (2026-10-15)

## Objective
Owner complaint: many "AI Stack: Attention Required" desktop notifications that do not say what is happening or what to do. Make them specific, actionable (buttons/links), deduplicated per issue, and rate limited.

## Workflow/Session IDs
Branch `feat/actionable-attention-notifications`, worktree `.agents/delegation/worktrees/attn-notify`. Implementer sub-agent (Sonnet tier) under orchestrator slice; no commit made (staged only).

## Delegation Decision
Bounded UX slice, single owner surface; implemented by a Sonnet-tier implementer per Rule 17. Orchestrator reviews and commits.

## Commands Executed
- `notify-send --help` -> supports `-A/--action`, `-w/--wait`, `-r/--replace-id`, `-p/--print-id`.
- `python3 scripts/testing/test-attention-notifications.py`
- `python3 scripts/testing/test-attention-queue-env-override.py`, `test-query-handler-attention-queue.py`
- `aq-approve show|review <id>` against a temp queue (`ATTENTION_QUEUE_DIR`).

## Validation Evidence
Root cause of the 7 notifications: the QA phase-0 alert title embedded the failing count, and dedup was keyed on title, and the 10-minute alert TTL expired between 15-minute timer runs, so every count change or expiry produced a new alert and a new popup. The popup showed only the title.

Changes:
- `scripts/ai/lib/attention_queue.py`: optional `dedup_key`, `why`, `next_step`, `command`, `link` in `push()` (backward compatible; no `dedup_key` = old title dedup). Same identity with changed content updates the pending alert in place (returns its id). Per-identity state file `notify-state.json` (outlives alert expiry) stores notify id (for `notify-send -r`), last-notified time, snooze. Rate limit 30 min per identity (`ATTENTION_NOTIFY_RATE_LIMIT_S`) unless severity escalates. Notification is sent by a detached helper (`attention_queue.py --notify <id>`, `start_new_session`), so `push()` never blocks. Actions via `notify-send --action`; falls back to body-only text when unsupported. `ATTENTION_NOTIFY=0` disables. `resolve()` accepts `dismissed`; `get_pending(include_snoozed=False)` and `pending_count()` skip snoozed identities (inbox/aq-alerts still list everything).
- Buttons: Open details (xdg-open dashboard link), Show in terminal (`aq-approve show <id>`), Snooze 1h, Dismiss (resolved `dismissed`, actor `owner`), and for alerts with an executor "Review & approve" which opens `aq-approve review <id>`, a new subcommand that shows the alert and PROMPTS `[y/N]` (refuses without a tty); no button approves directly. Terminal chosen by `ATTENTION_TERMINAL_CMD` (template with `{cmd}`), else `xdg-terminal-exec`, `$TERMINAL`, then kitty/foot/alacritty/konsole/xterm/gnome-terminal.
- `scripts/ai/aq-approve`: `show <id>`, `review <id>` (existing `aq-approve <id>` and numbered inbox unchanged).
- `dashboard/backend/api/routes/aistack.py`: read-only `GET /api/alerts/{id}/view` HTML detail page (escaped); link base from `DASHBOARD_URL` (env contract, default per `config/env-contract.yaml`).
- Producers: `scripts/health/ai-stack-health-monitor.py` (stable key `qa-phase-0`, failing ids/names in title, command `aq-qa 0 --machine`, TTL 3600 so one failing issue stays one alert), plus `aq-health-spider` (service DOWN, systemd failed units) and `fast-lane-staleness-check.py` (stable key, why/next/command).

Before: summary "AI Stack: Attention Required", body "aq-qa phase 0: 2 check(s) failing".

After:
```
QA phase 0: 3 checks failing (0.10.66 aq-confine, 0.2.1 aidb port, 0.3 x)
[0.10.66] aq-confine: missing
Why: The AI stack pre-flight smoke test is failing; dependent services may be degraded.
Next: Re-run the phase to see per-check output.
Run: aq-qa 0 --machine
ID: attn-6190482b
[Open details] [Show in terminal] [Snooze 1h] [Dismiss]
```

Test output (`scripts/testing/test-attention-notifications.py`): PASS test_format, test_identity_update_ratelimit_snooze, test_helper_is_detached, test_notify_main_actions_and_fallback, test_handle_actions, test_producers; ALL PASS. Existing `test-attention-queue-env-override` 6/6, `test-query-handler-attention-queue` OK. `test-ai-stack-health-monitor.py` fails on its Nix TimeoutStartSec assertion identically on baseline (pre-existing, unrelated; earlier assertions in it pass).

Not verified: real desktop rendering of buttons and click round trip (notification daemon dependent; GNOME shows actions only for some notification types). Owner test below.

## Security follow-up (review PASS_WITH_FOLLOWUPS, applied)
- "Open details" only opens http(s) URLs whose scheme+host+port equal the dashboard origin; anything else (file:, javascript:, other hosts, values starting with `-`, whitespace) falls back to the dashboard link. xdg-open has no documented `--`, so prefix validation is used.
- `/api/alerts/{id}/view` requires a loopback Host (extra via `ATTENTION_VIEW_ALLOWED_HOSTS`, comma list of host or host:port), refuses cross-site `Sec-Fetch-Site`, and redacts every rendered field. New alert ids are `attn-` + 16 random hex; old ids still work.
- Concurrent `--notify` helpers capped at 4 via flock slots; extras show a body-only popup.
- Tracked follow-up: a backend-wide Host/TrustedHost guard for the dashboard (agent-auth S1 dashboard); this slice guards only this route.

## Rollback Plan
Revert the commit. Runtime kill switch without revert: `ATTENTION_NOTIFY=0`. State file `.agents/attention/notify-state.json` is disposable.

## Residual Risk
- Notification daemon may render actions as a menu or not at all; body still carries the command and id.
- Helper waits up to 15 min (`ATTENTION_NOTIFY_WAIT_S`) for a click, then exits; clicks after that do nothing (use `aq-approve show <id>`).
- Rate limit also delays count-update replacements within 30 min (alert data is updated immediately; popup text may lag until the window passes or severity escalates).
- `/api/alerts/{id}/view` is unauthenticated read-only on the dashboard port, like sibling dashboard routes.

## Hint Feedback
None needed; discovery via rg on attention_queue and the health monitor producer.

## Owner activation steps
1. Land/merge, then `sudo nixos-rebuild switch --flake .#hyperd-ai-dev` (health monitor and health spider run from the repo/Nix store).
2. Restart the dashboard backend so the new route loads: `sudo systemctl restart command-center-dashboard-api.service`.
3. Test (harmless alert, 5-minute TTL; dismiss when done):
```
python3 - <<'PY'
import sys; sys.path.insert(0, "scripts/ai/lib")
from attention_queue import push
print(push("owner-test","high","human_gate","TEST: notification buttons","Harmless test alert.","Click a button, then Dismiss.",dedup_key="owner-test",why="Verifies actionable notifications.",next_step="Try each button.",command="aq-alerts",ttl_s=300))
PY
```

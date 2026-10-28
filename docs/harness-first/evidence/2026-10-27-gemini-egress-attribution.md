# Gemini egress lane attribution (2026-10-27)

Source: retro-review batch G (PR #550). Plan item P1.2 of `.agents/plans/system-integrity-recovery`.

## Defect
- `python3 scripts/ai/lib/remote_lane_egress.py gemini generativelanguage.googleapis.com` returned `hold` / `EGR_UNATTRIBUTED`, rc=2, blocking every `delegate-to-gemini` dispatch.
- Root cause: `gemini` was not in `LANES` (only `gemini-legacy`), so the lane was coerced to `other`.
- Callers passed a constant host rather than the dispatch's configured endpoint; raw IPv6 destinations were only flagged.

## Fix
- `gemini` added to `LANES`; `config/remote-lane-egress.json` gains a `gemini` lane allowlisting `cloudcode-pa.googleapis.com` (default host; Code Assist OAuth endpoint evidenced in agent memory and `delegate-to-gemini`) and `generativelanguage.googleapis.com`. OAuth sign-in hosts without repo evidence were left out.
- Per-lane `default_host` in config; `delegate-to-{gemini,codex,claude}` pass an env override or fall back to it.
- Raw IPv4/IPv6 literals (bracketed, bare, zone id) now hold as `EGR_RAW_IP`; hosts normalized.

## Evidence
- `scripts/testing/test-remote-lane-egress.py`: 13 tests OK (+6: gemini real hosts allowed, unknown host not allowed, unknown lane held, raw IPs held, codex/claude unchanged, config default host).
- Live CLI: `gemini generativelanguage.googleapis.com` -> `RULE_ALLOWLISTED` rc=0; `gemini ::1` -> `EGR_RAW_IP` rc=2.

## Known gap
- The gemini CLI chooses its own host at runtime; this pre-launch gate checks the configured endpoint, not live traffic.
- Rate budgets are per process and never accumulate across CLI calls. Backlog: EGRESS-RATE-BUDGETS-PER-PROCESS.

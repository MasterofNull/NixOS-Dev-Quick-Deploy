# VF-7 candidate — Codex binding acceptance

**Reviewer:** Codex (headless, isolated), independent of `claude-subagent-vf-7-implementer`
**Review date:** 2026-07-22
**Tasks:** `codex-20260722-095711` (full code review — found the implementation meets all criteria, but
withheld the terminal PASS solely because its `--mode safe` sandbox denied writing the acceptance
artifact to the read-only `.agents` mount) and `codex-20260722-100413` (stdout-only re-run — clean
terminal verdict). Both transcripts preserved in `.agents/delegation/outputs/`.

**Candidate:** `scripts/governance/aq-evidence-collector.py` `24d83b5a…`,
`config/schemas/aq-evidence-record-v1.json` `7841886a…`,
`scripts/testing/test-aq-evidence-collector.py` `99898ebe…`,
`scripts/governance/tier0-validation-gate.sh` `f7b3b68f…`.

## Verified by Codex

- 4 candidate hashes recomputed and matched; §6 activation confirmed.
- Unwrapped raw stdout/stderr/stdin capture (no compression filter in path); SHA-256 digest over
  (timestamp + raw payload_bytes + caller_agent_id).
- Secret redaction before write — env-style secrets, bearer/basic auth, PEM private keys, OAuth/API
  token prefixes, AND the invoked command string (a prior self-found bug that leaked the raw command,
  fixed). All redaction unit tests pass.
- Append-only to `.agents/events/a2a-events.jsonl` via `os.O_APPEND` + `fcntl.LOCK_EX`, using the same
  leading-newline convention as `event_log.py` (a prior self-found bug used a trailing-newline
  convention that could corrupt interleaved records, fixed).
- `kind` discriminator on each record; existing readers unaffected — `aq-event verify` reports
  `events=597 bad_sig=0`, `aq-event tail` renders.
- `python3 scripts/testing/test-aq-evidence-collector.py` → 24/24; py_compile + `bash -n` clean; the
  tier0 edit adds `gate_evidence_collector` alongside `gate_canon_compiler_determinism` without
  disturbing it; `git diff --check` clean; no real secret literal added (fixture placeholder tokens
  used to test redaction only).

Codex issued no commit/staging/edit; verdict returned to stdout, recorded here by the orchestrator.

`VERDICT: PASS`

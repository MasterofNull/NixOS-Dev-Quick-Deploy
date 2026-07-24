# Q5 — Lane-Eligibility Registry (design)

**Owner-ratified 2026-07-23** (Q3-Q10 gate). Turns the ratified seed rows into an
enforced, measured, EXPIRING lane-eligibility registry that governs all delegation.
Roles stay model-neutral; a lane's eligibility for a role is EARNED by evidence and
EXPIRES (must be re-earned). VF-8 promotion evidence feeds it later. Same workstream
as aq-role-route / the agent-agnostic factory (normal infra path, not hash-bound).

## Files (ceiling = 4)
1. **NEW `config/lane-eligibility-registry.json`** — the registry (schema + seed rows).
2. **EDIT `scripts/ai/aq-role-route`** — `route()` consults the registry to filter
   lanes by eligibility for the requested role; fail-safe fallback to the current
   hardcoded LANES if the registry is missing/unreadable.
3. **NEW `scripts/ai/aq-lane-eligibility`** — CLI to query/administer it.
4. **NEW `scripts/testing/test-lane-eligibility.py`** — tests.

## Registry schema (`config/lane-eligibility-registry.json`)
```
{
  "schema_version": 1,
  "_comment": "Measured, EXPIRING lane-eligibility registry (owner Q5). Roles are
    model-neutral; a lane's eligibility for a role is EARNED (evidence) and EXPIRES.
    INELIGIBLE-BY-DEFAULT: a lane with no non-expired eligible entry for a role
    cannot fill it. A hard-ineligible entry ALWAYS blocks, overriding any eligible.
    VF-8 promotion evidence updates this via `aq-lane-eligibility promote`.",
  "roles": ["orchestrator","architect","implementer","reviewer","binding-acceptance","research"],
  "default_ttl_days": 45,
  "lanes": {
    "codex":       {"eligible": {"orchestrator":SEED,"implementer":SEED,"reviewer":SEED,"binding-acceptance":SEED}},
    "opus":        {"eligible": {"implementer":{...SEED,"capability_note":"bounded implementer"},"reviewer":SEED,"binding-acceptance":SEED,"architect":SEED}},
    "sonnet":      {"eligible": {"implementer":SEED,"reviewer":SEED}},
    "antigravity": {"eligible": {"research":SEED,"reviewer":SEED},
                    "ineligible": {"implementer":{"hard":true,"reason":"owner Q5 2026-07-23: implementation-INELIGIBLE until measured promotion; ungoverned external IDE agent"}}},
    "local":       {"eligible": {"implementer":{...SEED,"capability_note":"measured envelope: bounded single-edit, NOT multi-site"}}},
    "gemini":      {"eligible": {"research":SEED,"reviewer":SEED}}
  }
}
```
Each eligibility entry = `{"measured_at": ISO, "expires_at": ISO|null, "evidence":
"<pointer/note>", "capability_note"?: str}`. SEED entries: measured_at=2026-07-23,
evidence="owner Q5 ratification (Q3-Q10-OWNER-RATIFICATION-20260723.md)",
expires_at = measured_at + default_ttl (so seeds don't outlive their evidence; VF-8
re-earns them). A `null` expires_at is a permanent grant (use sparingly).

## aq-role-route integration (EDIT `route()`)
- Load the registry. For the requested `role`, a lane is ELIGIBLE iff: it has an
  `eligible[role]` entry whose `expires_at` is absent/in-future, AND it has NO
  `ineligible[role]` entry with `"hard": true`. Filter the candidate lanes through
  this BEFORE the existing availability × cost ordering.
- Surface WHY a lane was excluded (expired / not-listed / hard-ineligible) in the
  JSON result (`excluded_lanes: [{lane, role, reason}]`).
- **FAIL-SAFE:** if the registry file is missing/unparseable, log `registry-degraded`
  and fall back to the CURRENT hardcoded `LANES` eligibility (never break routing).
  EXCEPTION: the antigravity→implementer hard-ineligibility is enforced even in
  fallback (a small hardcoded backstop) — that's the load-bearing governance rule.
- Expired-but-still-needed: if filtering leaves NO eligible lane for a role, return a
  clear `no-eligible-lane` result naming what expired (so the operator re-earns via
  promote), rather than silently routing to an ineligible lane.

## aq-lane-eligibility CLI (NEW)
- `check <lane> <role> [--json]` — eligible/expired/ineligible + reason.
- `list [--role R] [--lane L] [--json]` — the matrix; flag expired entries.
- `promote <lane> <role> --evidence <ptr> [--ttl-days N] [--capability-note ...]` —
  record/renew an eligibility. **Refuses without --evidence** ("earned by evidence").
  Sets measured_at=now, expires_at=now+ttl. This is the VF-8-feeds-it interface.
- `revoke <lane> <role> [--hard] --reason <r>` — remove an eligible entry / add a
  hard-ineligible.
- `expire-scan [--json]` — list entries expired or expiring within N days (for a
  future scheduled re-earn nudge).
- All writes are atomic (temp + rename) + JSON-schema-sane.

## Acceptance
- Registry validates + seeds match the ratified rows; antigravity implementer =
  hard-ineligible; local/opus implementer carry capability_notes.
- aq-role-route excludes ineligible/expired lanes with a stated reason; fail-safe
  fallback works (rename registry away → routing still works, antigravity-impl still
  blocked); `no-eligible-lane` returned rather than misrouting.
- `promote` refuses without evidence; sets expiry; `check`/`list`/`expire-scan` work.
- Tests cover: eligible/expired/hard-ineligible/not-listed; route integration +
  exclusion reasons; fail-safe; promote-requires-evidence. py_compile + tier0.
- Independent review (not the implementer); never-skip-local self-check.

# Gemini Review-Gate Contract

**Status:** Accepted — Phase 58A.4 (2026-05-18)
**Upstream authority:** `docs/architecture/role-matrix.md` (reviewer role definition)
**Stability:** This contract is frozen for Phase 58A. Changes require a named gate-revision slice.

---

## Purpose

Gemini fills the **implementer** and **reviewer** roles in this harness, but currently has no concrete enforcement point for when its output must be reviewed before integration. This document defines that enforcement point, the artifact form Gemini must produce, the verdict protocol, and the categories of work that always require a separate reviewer pass.

---

## Gemini's role boundaries (summary)

Per `docs/architecture/role-matrix.md`:

- Gemini may fill: **implementer** (research/proposal, candidate docs, synthesis) and **reviewer** (cross-check of others' work).
- Gemini may **not**: commit directly without orchestrator acceptance; self-accept its own implementation work; act as orchestrator unless explicitly assigned.

---

## Review-gate trigger categories

The following work categories **always** require a review gate before Gemini output is integrated:

| Category | Why |
|---|---|
| **Code changes** (any `.py`, `.nix`, `.sh`, `.js`, `.ts`) | Runtime risk; must pass tier0 gate under a human-or-orchestrator-reviewed commit |
| **Config changes** (`.json`, `.yaml`, `.toml` in `config/` or `nix/`) | Policy and routing changes; silent drift risk |
| **Architecture documents** (new or modified files in `docs/architecture/`) | Upstream authority for downstream slices; must be consistent with kernel declaration |
| **Destructive actions** (delete, rename, retire a canonical surface) | Irreversible; requires orchestrator confirmation |
| **Dual-use capability additions** (new tool allowlists, new network access, new secret access) | Security surface; requires architect + orchestrator review |
| **External-account-affecting actions** (push to remote, PR creation, external API writes) | Visible to others; requires explicit user or orchestrator confirmation before proceeding |
| **Memory writes to brokered path** (new `POST /memory/facts` or equivalent) | Persistent state; should be reviewed for accuracy before long-term storage |

Work that is **research-only** (reading files, producing a candidate proposal document, running read-only aq-* tools) does not require a review gate — but the *output* of that research is not integrated until it passes gate.

---

## Enforcement point

The gate happens at the **proposal boundary**: before Gemini's output transitions from candidate artifact to integrated artifact.

```
Gemini produces candidate artifact
          ↓
    [REVIEW GATE]
    - Orchestrator or designated reviewer reads artifact
    - Checks against slice acceptance criteria
    - Produces explicit verdict: PASS | FAIL | REQUEST_REVISION
          ↓
  PASS → integrate (commit / apply)
  FAIL → discard or document as rejected
  REQUEST_REVISION → Gemini revises and re-presents at gate
```

Gemini must **not** proceed past the gate on its own. If no reviewer is available, the artifact stays at candidate status and must not be committed.

---

## Required artifact form

For any gate-triggering work category, Gemini must produce a **review package** before requesting integration. The package must contain:

1. **Diff or full text** of the proposed change.
2. **Validation evidence**: what validation steps were run and their results (e.g. `bash -n`, `py_compile`, `nix-instantiate --parse`, `tier0-validation-gate.sh`).
3. **Acceptance criteria check**: for each criterion in the slice plan, an explicit "met / not met" with evidence.
4. **Risk note**: any concern that might affect other kernel objects, canonical surfaces, or security posture.

If the slice plan has no written acceptance criteria, Gemini must define them before producing the candidate artifact.

---

## Verdict protocol

The reviewer must produce one of three verdicts in the handoff artifact (`.agent/collaboration/HANDOFF.md` or inline in the collaboration thread):

| Verdict | Meaning | Next action |
|---|---|---|
| **PASS** | Artifact meets all acceptance criteria; no material risks identified | Orchestrator integrates (commits) |
| **FAIL** | Artifact does not meet criteria or introduces unacceptable risk | Gemini discards or documents as rejected; slice re-scoped if needed |
| **REQUEST_REVISION** | Specific finding(s) must be addressed before acceptance | Gemini addresses each finding explicitly, then re-presents at gate |

A reviewer may not issue a verdict of PASS for work they themselves produced.

---

## Gemini approval-mode policy

When running via the `gemini` CLI:

- `--approval-mode auto_edit` is the **default and safe mode** for research and read-only tasks. Gemini reads files but requires prompting to write.
- `--yolo` (full auto) is **only permitted** when the orchestrator has explicitly scoped the task and Gemini's output is destined for review before integration — not for direct production commits.
- `--approval-mode plan` is **broken** (HTTP 400 from Gemini API); do not use.
- Rate-limit 429 errors (`MODEL_CAPACITY_EXHAUSTED`) are transient; retry later rather than switching modes.

---

## No-self-acceptance rule

Gemini **may not** produce a PASS verdict for its own implementation work in the same session. If Gemini is the only available agent and a review gate is required:
- Record the candidate artifact in `.agent/collaboration/HANDOFF.md` with status `PENDING_REVIEW`.
- The next session (Claude, Codex, or human) performs the review.

---

## Consequences for 58A.5 and beyond

- **58A.5 (Qwen eligibility):** Qwen implementer work that touches gate-trigger categories must also pass a review gate. The reviewer for Qwen work may be Gemini or Claude (not Qwen).
- **58A.6 (capability lifecycle):** The `candidate → promoted` transition in the lifecycle schema requires a review gate of this form. The lifecycle schema should reference this document as the gate definition.
- **58A.7 (domain activation):** New domain activation artifacts are architecture documents; they are gate-trigger category items and require review before integration.

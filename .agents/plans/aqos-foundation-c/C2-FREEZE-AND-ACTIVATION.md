# Foundation C — C2 Freeze & Owner Activation

> **REV2 (2026-07-25): supersedes the rev1 freeze below.** Post-freeze, a BLOCKING gap was
> found (built-in bundle tools have no candidate lease → enforcement would deny run_command/
> file_edit → breaks tool-calling; evidence: aq-capability-shadow 11/11 would-issue, 0
> built-ins). The **C2-AMENDMENT-BUILTIN-TOOLS.md** (first-party tool lease source) closes it
> and is now PART OF the frozen subject. Its own review chain: codex REQUEST_REVISION (4
> findings) → folded → Opus confirmatory re-review REVISE (codex-2/3/4 closed; codex-1 line-32
> contradiction) → fixed → CLEARED. **rev2 frozen subject = the PAIR below; ceiling 4→5.**

## Frozen subject (rev2)
- **Authorization idempotency key:** `aqos-foundation-c:c2:tool-lease-enforcement-flag-gated:v2:20260725`
- **Subject = the pair (both byte-identical to the reviewed artifacts):**
  - `C2-DESIGN-AND-AUTHORIZATION.md` SHA-256 `313b723b4e1039f6b339a302056b14fc9b5c6cb5c922990d283fbee0ac4526eb`
  - `C2-AMENDMENT-BUILTIN-TOOLS.md` SHA-256 `633926c008b04edd89fef53ec6f6c63c4badf312b07f45520f1f8d827f8923f6`
- **Reviews:** design `C2-REVIEW-OPUS.md`(REVISE)+`C2-REREVIEW-OPUS.md`(PASS); amendment
  `C2-AMENDMENT-REVIEW-CODEX.md`(REQUEST_REVISION)+`C2-AMENDMENT-REREVIEW-OPUS.md`(REVISE→fixed).
- **Ceiling: 5 files** — the original 4 + NEW `config/first-party-tools.json`.
- **Build base HEAD (rev2):** `8c24dd78ef4cce3a75f7f6925c7dc691b20bbaa8` (the amendment-fix
  commit) or later with these two subject hashes unchanged — verify before implementing.
- **Predecessor hashes C2 reuses (must be unchanged at build time):**
  - `scripts/ai/lib/capability_lease.py` → `a6f923924071618b…`
  - `scripts/ai/lib/capability_lease_issuance.py` → `bf9229eac6ba4c21…`
- **Build base HEAD:** the commit that adds this packet (the `docs(foundation-c): C2 …`
  commit — its hash is the frozen build base; verify `git rev-parse HEAD` matches it before
  implementing).
- **Implementer:** cheapest-eligible per the Q5 registry (the switchboard edit + gate lib +
  tests are a multi-file build above local's envelope ⇒ Claude fast tier, Rule-17 override
  recorded), routed at activation time.
- **Window:** ≤24h from activation.

## What activation authorizes
ONLY the 4-file ceiling in the frozen design: EDIT `ai-stack/switchboard/switchboard.py`
(per-call lease admission at `:1673`, behind `CAPABILITY_LEASE_ENFORCEMENT`, default OFF,
guarded import + fail-closed wrapper) + NEW `capability_lease_gate.py` + NEW test + NEW
decision schema. **The committed code ships with the flag DEFAULT-OFF** (byte-for-byte inert;
parity-tested) — so even after implementation, ENFORCEMENT IS NOT LIVE until a *further* owner
act flips the flag (plus the Nix option in the same cycle, Rule 13).

## Owner activation (single-use — this is the step only you can take)
Broad/standing authorization does NOT activate this slice. To authorize implementation, run:

```
scripts/ai/aq-event emit --agent owner --type activation.grant \
  --subject aqos-foundation-c-c2-tool-lease-enforcement \
  --payload '{"idempotency_key":"aqos-foundation-c:c2:tool-lease-enforcement-flag-gated:v2:20260725","subject_design_sha256":"313b723b4e1039f6b339a302056b14fc9b5c6cb5c922990d283fbee0ac4526eb","subject_amendment_sha256":"633926c008b04edd89fef53ec6f6c63c4badf312b07f45520f1f8d827f8923f6","build_head":"<paste current git rev-parse HEAD>","implementer":"claude-fast","window_hours":24,"note":"C2 rev3 enforcement code incl. first-party tool lease source, 5-file ceiling, flag DEFAULT-OFF; flipping the flag is a separate later act"}'
```

After you run that, the orchestrator will: verify BOTH subject hashes + the predecessor hashes
+ HEAD are unchanged (drift check), route the cheapest-eligible implementer to build the exact
**5-file** ceiling (4 + `config/first-party-tools.json`), independent-review the result, and
commit with the flag **default-off**. Turning enforcement ON in the running system remains a
further, separate owner act.

## If you do NOT want to activate now
That is a valid stop: the entire Foundation C shadow spine (C0/C1) is already shipped and
enforces nothing; C2 simply waits here, frozen, with zero cost. Nothing degrades.

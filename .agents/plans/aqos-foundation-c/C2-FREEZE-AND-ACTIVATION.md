# Foundation C — C2 Freeze & Owner Activation

**C2 design is FROZEN and eligible for owner activation.** Independent flagship review
(REVISE, 2 BLOCKING closed) → independent flagship RE-REVIEW (**PASS**, both fail-opens
verified closed against live source, no new fail-open). This record freezes the reviewed
subject; it does NOT itself activate anything.

## Frozen subject
- **Authorization idempotency key:** `aqos-foundation-c:c2:tool-lease-enforcement-flag-gated:v1:20260724`
- **Subject (design+authorization record) SHA-256:**
  `313b723b4e1039f6b339a302056b14fc9b5c6cb5c922990d283fbee0ac4526eb`
  (`.agents/plans/aqos-foundation-c/C2-DESIGN-AND-AUTHORIZATION.md`, byte-identical to the
  re-reviewed artifact).
- **Reviews:** `C2-REVIEW-OPUS.md` (REVISE) + `C2-REREVIEW-OPUS.md` (PASS).
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
  --payload '{"idempotency_key":"aqos-foundation-c:c2:tool-lease-enforcement-flag-gated:v1:20260724","subject_sha256":"313b723b4e1039f6b339a302056b14fc9b5c6cb5c922990d283fbee0ac4526eb","build_head":"<paste current git rev-parse HEAD>","implementer":"claude-fast","window_hours":24,"note":"C2 enforcement code, flag DEFAULT-OFF; flipping the flag is a separate later act"}'
```

After you run that, the orchestrator will: verify the subject hash + predecessor hashes +
HEAD are unchanged (drift check), route the cheapest-eligible implementer to build the exact
4-file ceiling, independent-review the result, and commit with the flag **default-off**.
Turning enforcement ON in the running system remains a further, separate owner act.

## If you do NOT want to activate now
That is a valid stop: the entire Foundation C shadow spine (C0/C1) is already shipped and
enforces nothing; C2 simply waits here, frozen, with zero cost. Nothing degrades.

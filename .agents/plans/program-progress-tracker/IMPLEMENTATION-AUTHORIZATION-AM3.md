# Implementation Authorization AM3 — Operational Provenance Liveness

Authorization ID: `auth-program-progress-tracker-r0-am3-20260718`
Parent: `auth-program-progress-tracker-r0-am2-20260718`
Status: **PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS**

## Trigger

After final AM2 acceptance, the next mandatory issue record changed
`.agent/memory/issues-backlog.md` and demonstrated a latent liveness defect: the tracker test requires
all eight source hashes to remain byte-current even though four sources are intentionally mutable
operational records (`issues-backlog.md`, `RESUME.json`, `PULSE.log`, and the delegation registry).
Every legitimate workflow pulse, resume, delegation, or issue entry would therefore fail Phase0 and
halt future development.

The tracker is explicitly a frozen evidence snapshot. Historical operational hashes must remain
auditable without becoming permanent live locks. Stable governing decisions must continue to fail on
drift.

## Exact predecessor and two-file lease

Editable:

1. `assets/aqos-progress-tracker.html`
   `238341c4fc804036b6e4404fc8ea4a24a0ca0219da88db311d2b904144116dc2`;
2. `scripts/testing/test-dashboard-program-progress.py`
   `c78749fccb8e42488759646212b27418200538d00b4d24887b8e05f55ba95b47`.

Frozen and byte-immutable:

3. `dashboard.html`
   `801a50b24c09879471771bac53ea31f34ee22ba5236cf96033dcaaa88cd93323`;
4. `assets/dashboard.js`
   `4e3b44cb0caa8a86988b1b2de68091df90ef4f51d09caccfc65cd9c05990c8b6`;
5. `dashboard/backend/api/main.py`
   `bf1f4226054ed4076066a87f04460e82ba8a868ed83d67cb54154ee57872af22`;
6. `scripts/testing/harness_qa/phases/phase0.py`
   `ccee6268b0980f1d2fed1db6919107e1b4809447d9195461994ffb420f1f9a96`.

Any predecessor mismatch before the first write is a hard stop.

## Exact correction grant

One monitored implementer may:

- add a closed `source_class` vocabulary to every manifest source:
  `governing` or `operational_snapshot`;
- classify the unified plan, owner decision sheet, authority registry, and owner adjudication as
  `governing` and continue requiring their current disk SHA-256 to match;
- classify the issue backlog, RESUME, PULSE, and delegation registry as `operational_snapshot`;
- refresh the four operational snapshot hashes and `snapshot_at` once at final candidate freeze, while
  preserving program counts/status/content except for an explicit note explaining that operational
  records advance after the frozen snapshot;
- validate operational snapshot paths, exact 64-hex digests, uniqueness, source class, and historical
  snapshot semantics without comparing their current bytes after freeze; and
- add pure regressions proving simulated operational hash drift remains valid while simulated
  governing hash drift fails.

The implementation must not make governing drift fail-open, remove any source/provenance disclosure,
read network state, add a generator/API/database, change counts/statuses, edit any third file, mutate
PULSE, stage, commit, deploy, subdelegate, or self-review.

## Acceptance

Acceptance requires:

- exact two-file diff and four frozen hashes;
- complete focused suite against the candidate server;
- a regression that mutates copied operational bytes/hash inputs without touching the repo and proves
  the validator still accepts the frozen snapshot;
- a regression that mutates a copied governing input and proves rejection;
- exact current governing hashes and well-formed four-source operational snapshot metadata;
- retained headers, cold same-origin browser, zero console, iframe, accessibility, keyboard,
  responsive, reduced-motion, Phase0, and Tier0 evidence; and
- independent exact-subject `PASS`.

No AppArmor/Nix/service fix, tracker live API, dynamic writer, dashboard redesign, content/count/status
change, Foundation B2 work, or third file is authorized. The first exact completed two-file report
consumes AM3.

`RECORD: prepared operational-provenance liveness correction; inactive pending independent review.`

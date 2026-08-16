# A2A advisory task for Antigravity — TEG C1 R2 slice-one pre-build advisory review

Dropped: 2026-08-15T22:34:00Z
output_file: .agents/plans/aqos-foundation-c/ANTIGRAVITY-TEG-C1-SLICEONE-ADVISORY-20260815.md

Respond by writing only `.agents/plans/aqos-foundation-c/ANTIGRAVITY-TEG-C1-SLICEONE-ADVISORY-20260815.md`.

SCOPE-STOP: independent ADVISORY architecture/security review only. Authorize nothing, change no code,
touch no service/key/secret/runtime, do not stage or commit. NON-GATING — verified before use.

The frozen TEG C1 R2 CORE build is owner-granted (event 3682cfd1) but BLOCKED — Codex (implementer) is down
until Aug 21. This is a PRE-BUILD advisory pass so the implementer starts clean.

Subject (frozen): `.agents/plans/aqos-foundation-c/TEG-C1-DESIGN-PACKET-20260808.md` (R2). Gate context:
TEG-C1-FREEZE-20260814.md + TEG-C1-R2-REREVIEW-20260808.md (PASS).

Assess (slice-one §8 CORE only): scope-vs-staging-guard match (core broker only; NO ceiling-tuning /
cancellation-authority-service / extended dashboards); build-time risks in §3 lifecycle table / §5 CAS+
fencing / §6 crash matrix / §7 socket boundary (ordering, fail-open gaps, missed fsync/fence, the
launch-epoch == signed-C2-epoch binding); §8 file table coverage + §9 frozen-no-touch-deps respected.
Short bulleted advisory findings + "watch for X when building" notes. If no build-blocking gap, say so.

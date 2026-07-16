# Flagship Acceptance — M2A Read-Only `show` Hotfix

**SUPERSEDED:** Owner-authorized Sonnet acceptance completed and the exact candidate was committed as
`297728db`. Do not review this item; archive it without producing another verdict.

Role: independent flagship architecture, security, SRE, and concurrency acceptance reviewer. Read-only.
Write `.agents/plans/agent-ops-traceability-r0m/antigravity-m2a-read-only-show-hotfix-acceptance.md`,
then complete this inbox item.

Verify this exact five-file candidate:

```text
81b33d4d35fb09a9c2993eb01010291b554e6e1a9cff006dc58cbf952414b681  .agents/plans/agent-ops-traceability-r0m/M2A-READ-ONLY-SHOW-HOTFIX-DESIGN.md
a46960ae83071a4d2e42f10e844ea311e5af937cda68d419bc02153e302111ff  .agents/plans/agent-ops-traceability-r0m/IMPLEMENTATION-AUTHORIZATION-M2A-READ-ONLY-SHOW-HOTFIX.md
70cee61f1873d3e4a1960ce69f8bc4ee5c0e59cde31813962dfaf1ac7d485dba  scripts/ai/lib/task_registry.py
51a5e7fcc229cd654d52cd1b80b0f58f6bf8dcbce5aa94ef54884e6c17a41970  scripts/testing/test-agent-ops-projection.py
1281cba2eb34209e084363ac0f32d09fe18add42afd23bac04d42396ed4b57ac  scripts/testing/fixtures/local-delegation-reliability-golden.json
```

Any mismatch is REQUEST_REVISION. Confirm `show_m2a()` is genuinely read-only and descriptor-bound,
creates no directory/lock, rejects symlink/non-regular/malformed/oversized input, observes a complete
old-or-new inode across atomic replacement, and preserves all writer locks, mutation transactions, CAS,
machine envelopes, reasons, and exit codes. Confirm the fixture diff is exactly the two required digest
scalars. Run `test-agent-ops-projection.py` (62 checks), `test-local-delegation-reliability.py` (16),
py_compile, and Tier0. Do not edit. End exactly:

`VERDICT: PASS|REQUEST_REVISION|FAIL — one-line reason`

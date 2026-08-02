# AQ-OS Progress Tracker AM4 — Concurrent Source-Hash Recovery Re-pin

Status: `PREPARED_ONLY — INDEPENDENT REVIEW AND OWNER ACTIVATION REQUIRED`  
Prepared: `2026-08-01 UTC`  
Base HEAD: `17f899bf838973c755ab7a3e6095ec04a2e74220`

## 1. Recovery reason and predecessor disposition

AM3 authorization SHA-256
`9f6fbec9b9487f1330ea90d8cf777b5fe2974766f1416c2a6a741418e1640080`
was owner-activated and consumed by successful writes to its five-file ceiling.
It is non-replayable.

During AM3 implementation, the orchestrator correctly recorded a newly found
issue in `.agent/memory/issues-backlog.md`. That authorized issue-log write was
concurrent with tracker implementation and changed the tracker source input from
the AM3-pinned `4c03925f9de68d2617515f61b96184917f32a62fa23fbf1702346733c06bee8e`
to
`ee16d1e4a37b1cb7017d9c0c56e2b21d291f29ce07c1554caa6404a22fa71c1f`.
The focused tracker suite then stopped 13/14 with the sole failure
`source_drift:.agent/memory/issues-backlog.md`. This was a truthful provenance
stop, not an implementation defect and not authority to silently refresh bytes.

AM4 preserves the complete AM3 candidate and authorizes preparation of only the
minimal two-scalar re-pin needed to reconcile the current source hash in the
manifest and its embedded HTML projection. It does not reopen AM3 semantics.

## 2. Exact frozen source inputs

All five source inputs must match before the first AM4 write and again before
candidate acceptance:

| Source path | Required SHA-256 |
|---|---|
| `.agents/plans/UNIFIED-PROGRAM-PLAN.md` | `285bda20b4bb3b43cafbc3a46b90c905b203996448f2f5cfda62a0d950bea62e` |
| `.agents/plans/unified-program/OWNER-DECISION-SHEET.md` | `502df009ac486ab514351105a57d2a75ab21efd747a95f2c92bf36ea37c633b1` |
| `config/system-state-authorities.yaml` | `d45c83720847f6342d5ff13597810b46c7c2ad58c1c1342fdbc3e9236452ac1a` |
| `.agents/plans/aqos-refoundation-cycle0/FOUNDATION-A-OWNER-ADJUDICATION-20260718.md` | `3c05728f8011db002b8c1504757dd1b43421f151268718a0c275219ccd15bc7a` |
| `.agent/memory/issues-backlog.md` | `ee16d1e4a37b1cb7017d9c0c56e2b21d291f29ce07c1554caa6404a22fa71c1f` |

Any source or HEAD drift stops AM4. The implementer may not edit a source input
to make reconciliation pass.

## 3. Frozen AM3 candidate and exact AM4 ceiling

| AM4 operation | Candidate path | Required pre-write SHA-256 | Exact permitted change |
|---|---|---|---|
| EDIT | `config/refactor-milestones.json` | `03bda508d7295ccfad00fbda183ba9ed886d753c42bdee37217cc09636dd84a4` | Replace exactly one embedded issues-backlog digest `4c03925f...bee8e` with `ee16d1e4...71c1f`; no other byte changes. |
| EDIT | `assets/aqos-progress-tracker.html` | `b10827de0b95d6ae1ce307ee25b2e010e0d160de1e260d6540d8723f2417f148` | Replace exactly one embedded issues-backlog digest `4c03925f...bee8e` with `ee16d1e4...71c1f`; no other byte changes. |
| NO EDIT | `scripts/testing/test-dashboard-program-progress.py` | `bd3ebbb8a76edfa5500271711825eddf459bdb11c8353c653b4d873930bcb1c3` | Preserved AM3 focused/negative-vector oracle. |
| NO EDIT | `scripts/testing/harness_qa/phases/phase0.py` | `58904375ba961b2adade5f60f713c63dda69eae61c0da90d8be353dbf8065bc3` | Preserved AM3 check 0.10.40 update and byte-identical 0.10.41–0.10.44 functions. |
| NO EDIT | `scripts/ai/lib/refactor_status.py` | `b0fe4f8eac5f602d659b4a0c388e9685887dceb706022bf0def47426904f42b4` | Preserved AM3 projector/severity semantics. |

The two EDIT files must each contain the old digest exactly once before the
write and the new digest exactly once after the write. The resulting manifest
and HTML source arrays must be byte-equivalent after JSON normalization. No test
path, timestamp, status, note, count, source path/class, CSS, JavaScript, Python,
or Phase-0 byte may change.

No third editable path, generated repo file, move, mode change, formatter, or
substitution is permitted. A need to change a test or projector is a fail-stop
and requires a new design.

## 4. Roles, checks, and acceptance evidence

Proposed implementer:
`codex-subagent-tracker-am4-repin-implementer`.  
Required independent reviewer:
`codex-subagent-tracker-am4-independent-reviewer`, distinct from the AM3/AM4
design author and AM4 implementer. The implementer may not self-accept.

Before the first write, the implementer must verify exact HEAD, every source
hash, all five candidate hashes, an empty staged index, no overlapping writer,
and the exact one-occurrence old-digest precondition in both EDIT files.

After the two scalar changes, run only these offline validations:

```text
python3 -m json.tool config/refactor-milestones.json
python3 scripts/testing/test-refactor-status.py
python3 scripts/testing/test-dashboard-program-progress.py --static-only
python3 -m py_compile scripts/ai/lib/refactor_status.py scripts/testing/test-dashboard-program-progress.py scripts/testing/harness_qa/phases/phase0.py
git diff --check -- config/refactor-milestones.json assets/aqos-progress-tracker.html scripts/testing/test-dashboard-program-progress.py scripts/testing/harness_qa/phases/phase0.py scripts/ai/lib/refactor_status.py
AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 scripts/governance/tier0-validation-gate.sh --pre-commit
```

The focused tracker suite is the authorized static live-shape validation: it
checks the candidate origin parser, dashboard linkage/header shape, current-state
marker, normalized manifest/HTML parity, source hashes, exact counts, negative
vectors, and Phase-0 0.10.41–0.10.44 byte preservation. Live HTTP, `aq-qa`,
service restart, deployment, and Nix actions remain separate later authority.

The candidate report must record exact post-write hashes for both EDIT paths,
restate the three no-edit hashes and five source hashes, capture every command
and result, and state exclusions. A distinct reviewer must verify the exact
candidate bytes and issue `PASS` before any later release/commit authority.

## 5. Stop conditions and non-authority

Stop without refreshing or widening on any further HEAD, source, candidate,
index, overlap, occurrence-count, normalized-parity, focused-test, static-shape,
diff-check, or Tier-0 failure. A stopped or revision-requested AM4 is consumed
and requires a newly numbered authorization.

This design grants no implementation, staging, commit, deployment, runtime,
provider, network, live traffic, service restart, `aq-qa`, or live-dashboard
probe authority.

`RECORD: PREPARED_ONLY AM4 two-scalar source-hash recovery design; AM3 remains consumed and non-replayable.`

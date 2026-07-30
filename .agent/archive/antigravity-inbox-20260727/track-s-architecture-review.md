# Antigravity flagship review — AQ-OS Track S

## Assignment

Perform an independent, read-only expert-team review of:

- `.agent/PROJECT-AQOS-DEFENSIVE-SECURITY-FACTORY-PRD.md`
  - SHA-256: `68e3f33cf187b7b7cf797be788c24cd837010c50730842f630770598fa4fa491`
- `.agents/plans/aqos-defensive-security/PROGRAM-PLAN.md`
  - SHA-256: `bb75f4d2a36f1bb6d397ee734668908091d5e4dbba07622d0415188623f01325`

Apply the architecture, application/product security, SRE/observability,
privacy/evidence-custody, open-source/license-risk, and A2A/vector/RAG/DAG
engineering roles. Review:

1. owned/explicitly authorized target scope and DNS/redirect/egress escape controls;
2. the prohibition on hack-back and the safety of ingress-only owned canaries;
3. Piyaz as a cross-track pattern source without lifecycle or data-authority duplication;
4. Sn1per and RAPTOR quarantine/source-audit boundaries;
5. deterministic BOD 26-04-inspired risk ordering and evidence preservation;
6. disclosure, embargo, retraction, and optional bounty controls;
7. Service Coverage and recursive feedback requirements; and
8. S0-A through S5 sequencing, stop conditions, and rollback.

## Output

Write `.agents/plans/aqos-defensive-security/antigravity-track-s-review.md`
with scored findings, exact blockers/amendments, dissent, and a final `PASS` or
`REQUEST_REVISION` bound to both hashes. Then complete this inbox item with:

```bash
python3 scripts/ai/aq-antigravity-inbox complete track-s-architecture-review.md
```

## Boundaries

Do not edit candidate files, clone/download/install/execute external tools, scan
any target, access a network, change runtime/deployment state, authorize
implementation, stage, or commit. An unavailable or incomplete lane must be
recorded truthfully and must not be credited as a reviewer.

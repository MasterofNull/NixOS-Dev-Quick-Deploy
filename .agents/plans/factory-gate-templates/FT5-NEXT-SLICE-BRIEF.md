# FT-5 executable factory-start readiness and practice coverage

Owner renewed instruction: best engineering practices apply to this factory
and every greenfield/brownfield project and every agent lane, especially commit
evidence, useful comments, repository organization and truthful development
progress. This extends future coverage; it does not change frozen FT4 subject.
Existing canonical PRD remains active. Implement after FT4 acceptance.

Reuse existing installer status, target-normalized workflow paths, gate runner,
shared lane rules, structure lint and PM tracker. No parallel policy framework.
Metadata discovery never executes target scripts, installs tools or bypasses
configuration blockers. Applying policies to adopted projects is previewed and
confirmed; unsupported layouts/configurations are visible blockers, not clobbers.

Bounded executable deliverable:

1. Distinct metadata-only preflight operation, nonzero before work if installation
   absent, hook routing/executables invalid, required checks unconfigured, or
   activation blocked. Status remains informational. Receipt claims alone do
   not prove passing/fresh target execution; required execution evidence must
   be hash/config-bound and current before an enabled factory start claims ready.
2. Invoke preflight at target-safe project/slice-start paths (existing brownfield
   before its first write; generated start-workflow before coordinator dispatch;
   reuse MCP normalized target contract). Missing lanes are not readiness blockers.
3. Machine-readable practice coverage/status ties each required rule to its
   actual check, evidence and blocker; expose it in QA/CLI and existing dashboard.
   Add QA integration and dashboard coverage in the same slice/branch.
4. Negative fixtures prove missing installation, disabled hooks, stale/missing
   required evidence, bad repository organization and invalid tracker cannot
   report readiness or dispatch work. Existing ready fixture proves success;
   unknown tool/configuration is blocked, not silently skipped or auto-installed.

Practice acceptance map (reuse, then extend only real gaps):

- Commits: one scoped subject; objective/material changes/why/tradeoffs, exact
  validation/results, actual authors/reviewers, exact reviewed hash, authority/
  exclusions and next gate per canonical Step8. Reject missing/forged/stale or
  self-review evidence in the authorized flow. Review trailers are not trusted
  attestation by themselves. No bypass or credit to absent/failed lanes.
- Code/comments: target-declared format/lint/type checks and independent review
  of correctness, clarity, non-obvious intent and security assumptions. Comments
  explain why; no arbitrary comment quotas or generated clutter. Semantic review
  and static lint are distinct evidence, neither implies universal correctness.
- Files: target-approved layout/naming, safe paths, no secrets/runtime artifacts
  tracked, no unrelated staging, validated references and archival preservation.
  Adapt to legitimate existing project layout, never force src/tests blindly.
- Organization/progress: valid tracker, explicit dependencies/owner decisions,
  claims/ownership, durable phase checkpoints and visible typed blocked/unknown
  states. Acceptance/deployment/dogfood success are separate, evidence-backed.
- Safety/quality: target-declared tests/build/security scans, least privilege,
  input/secret controls, lifecycle/suspend handling and observable operational
  behavior; risk increases rigor. Nonblocking findings get bounded next slices,
  authority/data-loss/security defects block activation without review churn.

FT6 risk escalation and FT7 trusted CI/protected-branch/broker backstop remain
separate executable slices. Never claim same-user local hooks are unbypassable
or that these fixtures certify all industry practices/SLSA compliance.

## Explicit GitHub CI/CD requirement (owner renewed)

Portable policy includes both CI and opt-in CD. Audit current workflows first;
workflow YAML existing is not evidence that required-check/ruleset/environment
protection settings are active on GitHub. Unknown protection is visible and
must not permit protected merge/production promotion claims.

- CI: reuse stack-adapted build/tests/format/lint/types/security/structure/PM and
  commit/review evidence checks in GitHub workflows for PRs and protected branches.
  Include merge-queue events where configured. Required result cannot be bypassed
  by a local hook flag, agent identity or an unvalidated trailer. Fixture-test
  omitted jobs, bad/stale evidence and policy changes that try to self-weaken.
- Workflow safety: minimum read token permissions, immutable vetted action pins,
  untrusted-PR isolation, no secret-bearing untrusted checkout, timeouts, scoped
  concurrency and safe expression handling. Critical policy changes need trusted
  review/backstop rather than letting the candidate approve its own validator.
- CD: opt-in per authorized target, promote the tested commit/artifact digest
  rather than rebuilding an unidentified artifact; record provenance, approvals,
  deploy/health evidence and rollback readiness. Production environment/secret
  access gated by verified protection and explicit owner authority. No automatic
  external deployment, account changes, destructive rollback or boot/disk action.
- Brownfield: preserve existing workflows; preview additive/reusable integration
  and any replacements, back up authorized replacements, explicitly confirm.
  Greenfield: install tested templates and report remote activation requirements.
- Visibility: separate local validation, GitHub workflow runs, required-check
  enforcement, artifact provenance, deployment and postdeploy health indicators.
  Missing credentials/protection/deployment targets are explicit blockers, never
  stubbed PASS. Implement source templates/tests before separately authorized
  live account/environment activation.

CI/CD audit and implementation work is tracked, not assumed completed by FT4.
Use existing FT5/6/7 dependencies, no duplicate roadmap or endless planning loop.

Grounding (checked2026-09-15):
- Git hook behavior/bypass semantics: https://git-scm.com/docs/githooks
- NIST SSDF risk/outcome-based adaptation: https://csrc.nist.gov/Projects/ssdf
- SLSA provenance/verification model: https://slsa.dev/spec/v1.2/
- GitHub workflow security: https://docs.github.com/en/actions/reference/security/secure-use
- GitHub protection: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- Deployment environments: https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
These inform acceptance, not blind technique adoption or certification claims.

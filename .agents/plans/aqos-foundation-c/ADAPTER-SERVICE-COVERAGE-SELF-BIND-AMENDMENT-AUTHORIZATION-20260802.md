# Adapter Service Coverage Self-Bind Amendment — Prepared Authorization

Status: `PREPARED_ONLY — NOT ACTIVATED`  
Authorization ID: `auth-adapter-service-coverage-self-bind-amendment-20260802`  
Bound HEAD: `99621ace21f1c60d7908ce82d8928f5001081592`

This grant binds
`ADAPTER-SERVICE-COVERAGE-SELF-BIND-AMENDMENT-DESIGN-20260802.md` by exact SHA
at activation. After independent PASS and fresh owner activation, the named
preparer may create a temp candidate and a distinct implementer may edit only
`scripts/testing/test-execution-cell-adapter.py` at predecessor
`70cf833fbf41d2cfb4aed0be74c2402968fd3ae1bf321aba1c4e4ba9f283f072`,
adding only `allow_self_bind=True` to `_start_runner()`'s hermetic
`RunnerConfig`.

Activation must name preparer, implementer, reviewer, and an exclusive lease of
no more than 20 minutes after first repository write. It covers the one edit,
runner/L3/tracker no-touch subjects, HEAD/index/commit, and test/Tier-0 writer;
it prohibits concurrent writers, resets, checkout, staging, commit, or deploy.

Acceptance requires exact temp/repo hash parity, scoped diff-check, production
runner and Nix defaults still false, outside-managed-sandbox adapter suite 49/49
with success `green`, and disposable-clone Tier-0 all green. Any drift, extra
change, test failure, or weakened production default stops and consumes the
grant. No stage, commit, deploy, live traffic, service/socket, provider/network,
or second-path authority exists.

`RECORD: PREPARED_ONLY; exact review and owner activation required.`

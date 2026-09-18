# Factory receipt destination safety — bounded corrective

Objective: retrofit receipt writes must obey the same pre-mutation destination
safety contract as other declared outputs. Independent disposable reproduction
proved the older renderer allowed an ordinary receipt overwrite and followed a
receipt symlink to an external sentinel despite an approved preview.

The correction includes RECEIPT in previewed write paths and refuses existing
or unsafe destinations before backup, bundle, hook or Git config mutation.
Persisted ordinary-receipt and redirected-receipt fixtures verify retained bytes,
unchanged Git config and absence of new bundle/hooks. No consumer files are used.

Port base: cec0012d, preserving Claude's landed rendering, MCP parity and FT-5
readiness/evidence implementation. Only installer receipt validation and focused
negative fixtures change; no duplicate renderer or source-bundle replacement.

Implementer: factory_deployment_contract (aq_implementer).
Root contributes this handoff and integration coordination. Prior full-candidate
review accepted the mechanism, but this port needs its own independent exact-hash
review and canonical Tier0 before accepted integration. Activation remains pending.

Authority: owner's authorized factory replication sequence, read-only consumer
evidence. Exclusions: consumer changes, upgrades, destructive rollback, model/budget/
auth changes, runtime restarts and remote account configuration. Claude's separate
redeploy/idempotency corrective must preserve this guard; interrupted-install
recovery remains a separately logged follow-up.

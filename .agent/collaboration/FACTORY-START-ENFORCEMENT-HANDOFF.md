# Factory startup prerequisite enforcement

Objective: readiness failures must stop enabled factory startup, not merely print
informational output and continue into project writes or coordinator dispatch.
The landed FT-5 start integrations discarded preflight status with `|| true`.

Brownfield runs the existing metadata-only preflight before agent directory/PDR
creation and propagates its failure, including under force. Generated startup
requires an executable readiness runner and preflights before transport calls.
Absent model lanes remain informational inside the existing readiness authority.

Implementer: factory_deployment_contract (aq_implementer). Root contributes this
handoff. Focused disposable tests report blocked/force/no-write, ready progression,
missing/blocked runner/no-call and ready dispatch. Install/retrofit/readiness
regressions also pass; independent final-subject review and Tier0 remain pending.

Authority: owner-approved factory replication sequence and canonical FT-5 brief.
No model/budget/auth changes, consumer edits, service activation, dependencies,
new configuration flags or remote account changes. This does not fix independent
execution-evidence scope or owned bundle upgrade defects. Those remain separate
bounded corrections; no complete/deployed consumer readiness is claimed.

# Architecture decision records

One short file per decision of the control-plane consolidation (rev 5): context, decision, C1-C5 check, licence, reversal trigger. Status "Accepted" cites the owner answer; "Proposed" is a rev 5 reclassification awaiting its slice.

| ADR | Decision | Status |
|---|---|---|
| 0001 | [Registry home: extend system-state-authorities.yaml (no second registry)](0001-registry-home.md) | Accepted (owner 2026-11-27, defaults answer) |
| 0002 | [Contract guard: extend the Rust contract-validator; derived CONFIG_SCHEMA_REGISTRY](0002-contract-guard-rust.md) | Accepted (owner 2026-11-27) |
| 0003 | [nh: bounded spike inside aq-update](0003-nh-bounded-spike.md) | Accepted (owner 2026-11-27, defaults answer) |
| 0004 | [LangGraph deferred](0004-langgraph-deferred.md) | Accepted (owner 2026-11-27, defaults answer) |
| 0005 | [OpenClaw: reference-only, with the parity diff](0005-openclaw-reference-only.md) | Proposed |
| 0006 | [LiteLLM: keep the custom switchboard](0006-litellm-keep-custom.md) | Accepted (owner 2026-11-27, defaults answer) |
| 0007 | [deploy-rs and colmena: keep custom](0007-deploy-rs-colmena-keep-custom.md) | Accepted (owner 2026-11-27, defaults answer) |
| 0008 | [devenv: reference-only](0008-devenv-reference-only.md) | Proposed |
| 0009 | [aq-land-queue as the sole queue under the existing durable unit](0009-aq-land-queue-sole-queue.md) | Accepted (owner 2026-11-27) |
| 0010 | [Local-only landing waiver](0010-local-only-landing-waiver.md) | Accepted (owner 2026-11-27) |
| 0011 | [Supported-install boundary, remote-lanes add-on and the C3 pin policy](0011-supported-install-boundary.md) | Accepted (owner 2026-11-27) |
| 0012 | [lite profile budgets and the persistence/auth floor](0012-lite-profile-budgets.md) | Accepted (owner 2026-11-27) |
| 0013 | [Upstream register and the attribution guard](0013-upstream-register.md) | Accepted (owner 2026-11-27) |
| 0014 | [Retire in-repo pi-agent and continue-cli; opencode and models-dev go to the add-on via nixpkgs](0014-retire-pi-agent-continue-cli.md) | Accepted (owner 2026-11-27) |
| 0015 | [Licence policy: invocation versus linking or vendoring](0015-licence-policy.md) | Accepted (owner 2026-11-27, defaults answer) |

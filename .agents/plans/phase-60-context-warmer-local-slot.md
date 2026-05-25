# Phase 60 Context Warmer Local Slot Fix

Status: implementation validation in progress

## Problem

`ai-context-warmer.service` was queueing a Ralph/Aider task every 15 minutes:

`aq-ralph-task "Run AI world model predictive context warming: ... aq-context-warm" aider`

That routed deterministic cache warming through `local-tool-calling`, which has a single local slot. When Ralph delegation or AIDB context fetch failed, the background timer could occupy the local lane and cause unrelated `aq-chat` or agent work to receive 503 responses.

## Fix

- Run `scripts/ai/aq-context-warm` directly from the systemd oneshot service.
- Keep the dedicated `worldModelPython` runtime with required dependencies.
- Pass the local hybrid coordinator URL and API key file explicitly.
- Permit telemetry writes under `cfg.mcpServers.dataDir`.
- Add a focused validation check to prevent reintroducing Ralph/local-agent queueing for this deterministic maintenance task.

## Validation

- `python3 scripts/testing/test-context-warmer-service-python-env.py`
- `nix build .#nixosConfigurations.hyperd-ai-dev.config.system.build.toplevel --dry-run --accept-flake-config`
- `scripts/governance/run-focused-ci-checks.sh`
- `scripts/governance/tier0-validation-gate.sh --pre-commit`

## Operational Check

After deployment:

- `systemctl start ai-context-warmer.service`
- `journalctl -u ai-context-warmer.service -n 40 --no-pager`
- `curl -fsS http://127.0.0.1:8085/health` should show the local slot available unless another foreground local request is active.

# Turn on P1.7 power policy, speed probe and keep-awake watcher (hyperd host) — 2026-10-29

## Objective

#646 (P1.7) and #647 (sleep resilience) merged with every option defaulting off. This change turns them on for the `hyperd` host, the laptop that showed the local-model slowdown, so Rule 15's "turned ON" holds. It also corrects the activation steps, which pointed at a file the flake cannot see.

## Workflow/Session IDs

- Claude session 50391bdd (system-integrity-recovery P1.7 follow-through).
- Source PRs: #646 (`ec93c8a5`), #647 (`6adeb9e0`).
- Backlog: P17-ACTIVATION-DOC-INVISIBLE-FILE.

## Delegation Decision

Orchestrator edit: three option lines in the host file, one comment and one doc sentence. A dispatch would cost more than the change; recorded as a Rule 17 deviation in PULSE. Independent review: local Qwen. Codex and Gemini were confirmed available again on 2026-10-29 and queue confirmatory audits through the catch-up queue.

## Commands Executed

```
nix eval --json .#nixosConfigurations.hyperd-ai-dev.config.mySystem.deployment.powerPolicy \
  --apply 'p: { ac = p.acAwareProfile.enable; probe = p.speedProbe.enable; }'
nix eval .#nixosConfigurations.hyperd-ai-dev.config.mySystem.aiStack.keepAwake.enable
nix eval --json .#nixosConfigurations.hyperd-ai-dev.config.systemd --apply '<filter of the expected unit names>'
```

## Validation Evidence

- powerPolicy: `{"ac":true,"probe":true}`. keepAwake.enable: `true`.
- Generated units: system services `power-policy-apply`, `aq-llm-speed-probe`, `aq-llm-speed-probe-resume`, `llama-cpp-resume`; timer `aq-llm-speed-probe`; user service `aq-keep-awake`.
- Why the tracked host file: `flake.nix:270` imports `nix/hosts/<host>/deploy-options.local.nix` only if `builtins.pathExists` finds it, and that file is gitignored (`.gitignore:162`), so a git flake never sees it (same root cause as plan 21.2, commit 23043d71). The previous instructions in `options.nix` and the P1.7 evidence doc would have changed nothing.
- Not yet live: the owner rebuild. After the rebuild, `powerprofilesctl get` should print `performance` on AC, and `/var/lib/ai-stack/hybrid/telemetry/llm-speed-probe.jsonl` should gain a line every 15 minutes. That is the first writable directory in the probe's `telemetry_path()`; `AQ_TELEMETRY_DIR` overrides it, and `~/.local/state/aq/` is the last fallback.

## Rollback Plan

Remove the three option lines from `nix/hosts/hyperd/deploy-options.nix` (or set them to false) and rebuild. While off, the modules add nothing. Keep-awake can also be stopped per session with `aq-keep-awake off` without a rebuild.

## Residual Risk

- The AC-aware profile overwrites a manual `powerprofilesctl set` at the next plug or unplug event (documented in the option).
- `aq-keep-awake` is opt-in per session; enabling the service only runs the watcher. Real lid-close behavior and the `systemctl suspend` permission from the user service are still unvalidated on hardware (#647 evidence).
- The speed probe skips while llama is busy, so a probe gap during long reviews is expected, not a fault.

## Hint Feedback

No harness hint flagged that host-local options are invisible to the flake. The fact lived only in plan item 21.2. Backlog P17-ACTIVATION-DOC-INVISIBLE-FILE records it; a tier0 check that warns when docs tell users to set non-secret options in `deploy-options.local.nix` would stop this from recurring.

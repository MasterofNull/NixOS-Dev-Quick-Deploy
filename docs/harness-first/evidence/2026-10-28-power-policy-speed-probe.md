# P1.7 AC-aware power profile + local-model speed probe (2026-10-28)

Plan item: .agents/plans/system-integrity-recovery P1.7. Branch feat/power-policy-tokps-probe (uncommitted at time of writing).

## Problem
Diagnosis `.agents/delegation/outputs/llama-throughput-diagnosis-20261027.md`: on battery in `power-saver` the local model ran 1.7-2.0 tok/s gen / ~5 prompt; on AC + `performance` 3.75-4.58 / ~9.5 (baseline 5.3 / 8). Memory was not the active bottleneck. Nothing surfaced the regression.

## Changes
- `nix/modules/core/power-policy.nix` (imported in `flake.nix`), options in `nix/modules/core/options.nix` under `mySystem.deployment.powerPolicy`:
  - `acAwareProfile.enable` (default false): udev rule on Mains `power_supply` change plus boot/post-resume run of `power-policy-apply`, which sets `performance` on AC, `balanced` on battery via `powerprofilesctl`. No-op on hosts with no Mains node. Never forces performance on battery. Asserts power-profiles-daemon is enabled. Default false because it is host-specific and the repo has no per-host-class default mechanism for laptop-only policy (hardware/mobile.nix is the only gate); no explicit-user-choice mechanism exists, so a manual `powerprofilesctl set` is overwritten on the next AC plug/unplug (documented in the option).
  - `speedProbe.enable` (default false), `intervalMinutes` (15), `minTokPerSec` ("3.2"): timer every 15 min (+10 min after boot) and a 90 s-after-resume unit, running `scripts/ai/aq-llm-speed-probe` from the live repo path (same pattern as fast-lane-staleness-check), SuccessExitStatus=1 so a slow result is telemetry, not a unit failure.
- `scripts/ai/aq-llm-speed-probe`: one fixed 60-token completion (enable_thinking false); records gen/prompt tok/s, AC online, power profile, max CPU MHz, MemAvailable, major-fault delta; cause label POWER (battery or non-performance profile), MEMORY (MemAvailable < model size 22.5 GB or major faults rising), else UNKNOWN. Appends to `llm-speed-probe.jsonl` in `AQ_TELEMETRY_DIR` (default /var/lib/ai-stack/hybrid/telemetry, same dir other probes use). Exit 0 ok/skipped, 1 slow, 2 error. Skips (exit 0, status "skipped", nothing written) when a llama slot is processing or an `agent_executor|aq-agent-loop|delegate-to-local` process exists. URL from LLAMA_URL / LLAMA_CPP_BASE_URL / LLAMA_PORT (unit gets it from `aiStack.llamaCpp.port`).
- Health surface: `_llm_speed_check` added to `scripts/ai/aq-health-spider` (smallest existing integration point: the spider already runs harness-level advisory checks each cycle and routes them to the attention queue). Emits `llm_speed_slow` advisory when the latest probe line is slow and under 3 h old; silent when the probe file is absent (feature off).
- `scripts/testing/test-llm-speed-probe.py` + `config/ci-checks.json` entry `llm-speed-probe-tests`.

## Validation
- `python3 scripts/testing/test-llm-speed-probe.py`: fast->ok, slow battery->POWER, slow low-mem->MEMORY, slow otherwise->UNKNOWN, busy->skipped (all PASS).
- `scripts/governance/run-ci-checks.sh --all --only llm-speed-probe-tests`: PASS.
- `nix-instantiate --parse` on power-policy.nix, options.nix, flake.nix: OK. `nix eval` of `nixosConfigurations.hyperd-ai-dev` with both options enabled yields the expected services, timer, udev rule, env.
- Not done (owner act): rebuild, live probe against the running server, battery/AC toggle on real hardware.

## Owner steps
1. Merge, then in `deploy-options.local.nix` (or host config): `mySystem.deployment.powerPolicy = { acAwareProfile.enable = true; speedProbe.enable = true; };`
2. `sudo nixos-rebuild switch --flake .#hyperd-ai-dev` (or `nrs`).
3. Verify: `systemctl status power-policy-apply aq-llm-speed-probe.timer`; `powerprofilesctl get` (unplug/replug AC); `systemctl start aq-llm-speed-probe.service; tail -n1 /var/lib/ai-stack/hybrid/telemetry/llm-speed-probe.jsonl`.

## Activation (Rule 15)
Integrated: yes (flake import, spider hook). ON: not until owner sets the options (deferred, owner rebuild). Validated real-world: pending live run. Observable: jsonl + spider advisory. Intervenable: both options default off; probe timer stoppable.

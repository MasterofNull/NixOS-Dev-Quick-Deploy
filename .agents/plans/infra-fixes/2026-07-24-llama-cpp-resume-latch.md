# Fix record — llama-cpp-resume.service stale `failed` latch

**Date:** 2026-07-24 · **Author:** fable-5 · **Change:** `nix/modules/roles/ai-stack.nix`
(`systemd.services.llama-cpp-resume` ExecStart → `systemctl restart --no-block`).

## Symptom
tier0 QA phase-0 check `0.1.2 "no AI units in failed state"` FAILED → validation gate
BLOCKED, while the system was actually healthy. Failed unit: `llama-cpp-resume.service`
(`Result: exit-code`, status=1). This also surfaced mid-session as a `503 "Loading model"`
from `:8080` that briefly looked like a local-inference-lane outage.

## Root cause
The post-suspend GPU-reinit hook ran `systemctl restart llama-cpp.service`
**synchronously**. On the Renoir APU a cold GPU re-init after resume takes minutes and can
exceed the restart job timeout / transiently fail the readiness probe, so the oneshot
exits non-zero and **latches into `failed`** — even though `llama-cpp.service` recovers
seconds later and serves normally (`{"status":"ok"}`). A stale failed unit then
false-blocks the health gate.

## Fix
`ExecStart` → `${pkgs.systemd}/bin/systemctl restart --no-block llama-cpp.service`. The
resume hook's job is to **trigger** the restart, not to own llama-cpp's slow readiness —
`llama-cpp.service` tracks its own health + restart policy. Fire-and-forget returns 0
immediately, so a slow-but-successful cold load no longer latches the oneshot.

## Runtime + activation
- Runtime latch cleared this session: `systemctl reset-failed llama-cpp-resume.service`
  (llama-cpp healthy → stays cleared).
- Declarative `--no-block` fix ACTIVATES on the next `sudo nixos-rebuild switch
  --flake .#hyperd-ai-dev` (Rule 13 — the runtime reset alone is wiped by a rebuild).

## Observability
Detected by the existing tier0 QA phase-0 `0.1.2` gate (no new surface needed). Recurrence
would re-trip the same check; the `--no-block` change removes the false-positive latch
while preserving real failed-unit detection for genuine llama-cpp failures.

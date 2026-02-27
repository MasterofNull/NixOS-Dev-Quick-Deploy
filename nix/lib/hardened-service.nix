/**
  Phase 16.4.1/16.4.2 — Minimal-footprint systemd service hardening helper.

  Returns a `serviceConfig` attribute set with sensible security defaults and a
  tier-appropriate `MemoryMax` ceiling.  Callers merge it with their own
  service-specific settings using `//`:

      serviceConfig = (mkHardenedService { inherit tier; }) // {
        ExecStart = "...";
        User      = svcUser;
      };

  Parameters
  ----------
  tier : string
    One of "nano" | "micro" | "small" | "medium" | "large" (matches
    `mySystem.hardwareTier`).  Determines the default `MemoryMax` value.

  memoryMax : string | null (optional)
    Override the tier-derived `MemoryMax`.  Pass a systemd size string such as
    "512M", "2G", etc.  When null the tier default is used.

  extra : attrs (optional)
    Additional serviceConfig attributes merged in last (highest priority).

  MemoryMax defaults per tier
  ---------------------------
    nano   →  256M   (SBC / embedded)
    micro  →  512M   (light SBC)
    small  →  1G     (laptop / thin client)
    medium →  2G     (workstation)
    large  →  4G     (high-end workstation / server)
*/
{ lib }:
{
  tier      ? "medium",
  memoryMax ? null,
  # tasksMax: maximum number of kernel tasks (threads + processes) for this unit.
  # Prevents runaway child-process spawning.  Phase 12.4.1.
  # null = use systemd default (4915 per DefaultTasksMax).
  tasksMax  ? 256,
  extra     ? {},
}:
let
  tierMemory = {
    nano   = "256M";
    micro  = "512M";
    small  = "1G";
    medium = "2G";
    large  = "4G";
  };

  # Resolve MemoryMax: caller override → tier default → "2G" fallback.
  resolvedMemory =
    if memoryMax != null then memoryMax
    else tierMemory.${tier} or "2G";
in
{
  # --- Privilege isolation ---------------------------------------------------
  NoNewPrivileges       = true;
  CapabilityBoundingSet = "";
  RestrictSUIDSGID      = true;
  LockPersonality       = true;
  RestrictNamespaces    = true;

  # --- Filesystem protection -------------------------------------------------
  ProtectSystem         = "strict";
  ProtectHome           = true;
  PrivateTmp            = true;
  PrivateDevices        = true;
  ProtectKernelTunables = true;
  ProtectKernelModules  = true;
  ProtectControlGroups  = true;

  # --- Memory ceiling (tier-appropriate) ------------------------------------
  MemoryMax             = resolvedMemory;

  # --- Task count ceiling (Phase 12.4.1) ------------------------------------
  # Limits the total number of kernel tasks (threads + child processes) to
  # prevent runaway subprocess spawning.  256 is generous for Python asyncio
  # services (they use ~10-30 threads normally).
  TasksMax              = tasksMax;

  # --- Restart policy -------------------------------------------------------
  Restart               = "on-failure";
  RestartSec            = "10s";
} // extra

# Kernel policy research — 2026-10-01

Decision: **newest stable kernel, always** (`linuxPackages_latest`), matching the existing
`mySystem.kernel.track = "latest-stable"` (default; `ai-dev` profile; host `mkForce`). Supersedes the
newest-LTS answer recorded earlier the same day.

## Current threat picture (sources below)
- Volume: 432 Linux kernel CVEs disclosed across two days in July 2026; 400+ fixes in ~24h (Jul 19-20),
  attributed largely to AI-assisted discovery. Torvalds: AI-generated reports made kernel security lists
  "nearly unmanageable"; volumes expected to keep rising.
- Depth: AI tooling is finding long-lived bugs (e.g. a ~15-year-old root LPE, CVE-2026-43499).
- Speed to weaponization: CVE-2026-53264 — upstream fix 2026-06-01, AI-assisted public root exploit
  2026-07-28 (AI used for discovery, PoC, and race-window tuning).
- Exploitation: CISA added three kernel CVEs to KEV on 2026-09-19 with a remediation deadline of
  2026-09-21 (two days).

## Implications for this host
1. Per-CVE triage/backport selection does not scale at this volume; the newest stable kernel receives
   upstream fixes first, while LTS branches receive selected backports. Track newest stable.
2. Patched != running. NixOS has no native live patching; a kernel update protects only after reboot.
   The reboot gap is the real exposure window, so it is measured: `aq-auto-update check` records
   `pending_reboot_since` whenever the running kernel differs from the installed one (however that
   arose) and files a high-severity RSI incident past `REBOOT_SLA_HOURS` (default 24).
3. Reboot stays owner-scheduled (Renoir audio/GPU kernel-skew history); previous generations remain
   bootable; post-boot audio/GPU/inference probes gate acceptance.
4. Defense in depth for the gap (observed live 2026-10-01): `unprivileged_bpf_disabled=2`,
   `dmesg_restrict=1`, `kptr_restrict=1` (hardening guide says 2), unprivileged user namespaces
   ENABLED (`user.max_user_namespaces=111253`) — the documented mitigation for CVE-2026-53264-class
   exploits. Restricting userns affects browser/Flatpak/bwrap sandboxes, so it is an owner decision,
   not changed here.

## Sources
- https://www.opensourceforu.com/2026/07/linux-maintainers-battle-record-ai-fuelled-cve-surge/
- https://cybersecuritynews.com/linux-patches-400-kernel-vulnerabilities/
- https://www.linuxjournal.com/content/ai-uncovers-15-year-old-linux-kernel-root-vulnerability-hidden-2011
- https://dailysecurityreview.com/resources/ai-assisted-linux-kernel-cve-2026-53264-root-exploit-released/
- https://thehackernews.com/2026/09/cisa-flags-three-linux-kernel.html
- https://lwn.net/Articles/1073060/
- https://discourse.nixos.org/t/lag-time-between-stable-kernel-releases-and-that-kernel-being-available-to-nixos/14591

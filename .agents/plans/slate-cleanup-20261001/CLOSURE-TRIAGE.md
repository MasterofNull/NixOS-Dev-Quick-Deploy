# Nix closure scan triage (2026-10-01)

Scope: the 343 open `nix-closure` code-scanning alerts on the deployed `hyperd-ai-dev` system, plus 5 stale `trivy-custom-*` alerts.
Nothing on GitHub was changed. All lists below are proposals for owner approval. Per-alert data: `closure-triage-alerts.json` (same directory).

## 1. Result in one paragraph

Of the 343 alerts, **70 (20%) are proven false positives** (nixpkgs ships a patch named after the CVE), **10 more are verified
product-mismatch or pre-release-ordering false positives** awaiting owner confirmation, **36 come from legacy library copies** that two
optional modules drag in (libpng 1.2 via `programs.appimage`, libxml2 2.13 / libjxl 0.8 via Playwright WebKit), and **82 are fixed only in
nixpkgs-unstable** (not in the 26.05 channel head). Nothing is fixed by a plain `nix flake update`: evaluating the `nixos-26.05` channel head on 2026-10-01 shows no fixed version for any alerted
package (it carries the versions already deployed). The remaining 143 alerts
(108 NVD matches with no version bound, 35 with no upstream fix) are accept/dismiss decisions, not engineering work.
The biggest real reduction is removing optional modules (sections 4.1 and 7), not bumping packages.

## 2. Counts per class and severity (343 alerts)

| class | total | critical | high | medium | low |
|---|---:|---:|---:|---:|---:|
| patched_in_nixpkgs | 70 | 7 | 26 | 35 | 2 |
| legacy_variant_in_closure | 36 | 3 | 20 | 7 | 6 |
| fixed_in_nixpkgs_stable | 0 | 0 | 0 | 0 | 0 |
| fixed_in_nixpkgs_unstable | 82 | 2 | 58 | 22 | 0 |
| fixed_upstream_only | 9 | 1 | 2 | 5 | 1 |
| no_upstream_fix | 35 | 6 | 7 | 20 | 2 |
| unbounded_cpe_match | 108 | 10 | 43 | 47 | 8 |
| needs_review | 3 | 1 | 2 | 0 | 0 |
| **total** | 343 | 30 | 158 | 136 | 19 |

Class meaning (`scripts/security/aq-closure-scan --triage-json`):

| class | meaning | root fix |
|---|---|---|
| patched_in_nixpkgs | a patch file named after the CVE is applied to that derivation (sbomnix `patches` column, same rule as vulnxscan) | dismiss as false positive |
| legacy_variant_in_closure | closure carries an older copy than the nixpkgs attribute ships (compat/pinned variant) | drop the consumer of the old copy |
| fixed_in_nixpkgs_stable | stable channel head already has a fixed version | `nix flake update` |
| fixed_in_nixpkgs_unstable | only nixpkgs-unstable (locked or head) reaches the fixed version | fast-lane promotion or stable backport |
| fixed_upstream_only | upstream names a fix that no nixpkgs track packages | wait for nixpkgs, or remove the package |
| no_upstream_fix | NVD last-affected version equals the newest release anywhere in nixpkgs | remove if unused, else accept and monitor |
| unbounded_cpe_match | NVD CPE has no version bound, so grype matches every release (typical CPE name collisions) | manual triage, dismiss as won't-fix |
| needs_review | data inconsistent (pre-release naming); a human decides | manual |

Top packages from the brief, by class:

| package | alerts | patched | legacy | stable-fix | unstable-fix | upstream-only | no-fix | unbounded | review |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gstreamer | 40 | 0 | 0 | 0 | 36 | 0 | 0 | 4 | 0 |
| avahi | 36 | 33 | 0 | 0 | 0 | 0 | 3 | 0 | 0 |
| libxml2 | 23 | 4 | 19 | 0 | 0 | 0 | 0 | 0 | 0 |
| ffmpeg | 21 | 0 | 0 | 0 | 21 | 0 | 0 | 0 | 0 |
| libssh2 | 20 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| gnutls | 16 | 0 | 0 | 0 | 0 | 0 | 0 | 16 | 0 |
| libssh | 14 | 0 | 0 | 0 | 0 | 0 | 0 | 14 | 0 |
| libpng | 14 | 0 | 14 | 0 | 0 | 0 | 0 | 0 | 0 |
| libtiff | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 0 |
| alsa-lib | 11 | 0 | 0 | 0 | 2 | 0 | 9 | 0 | 0 |
| binutils | 10 | 0 | 0 | 0 | 0 | 0 | 5 | 5 | 0 |
| openssh | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 |
| qemu | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 |
| capstone | 7 | 0 | 0 | 0 | 1 | 4 | 2 | 0 | 0 |

## 3. How the triage was done, and its limits

- Tooling: `vulnxscan` from sbomnix 1.7.6 (`nix shell --inputs-from . nixpkgs#sbomnix -c vulnxscan --sbom ... --triage`) works up to the point where
  `--triage` queries repology.org. From this sandbox `repology.org:443` refuses the connection (curl exit 7), so the repology half
  (nixpkgs-unstable / upstream version lookup) could not run. `vulnxscan` itself aborts with `requests.exceptions.ConnectionError` there.
  The patched-detection half does not need the network and was reproduced exactly: sbomnix `--csv` gives each derivation's `patches`
  list, and a finding is patched when its CVE id appears in a patch file name (this is vulnxscan's own `_is_patched` rule).
- Replacement for the repology half (deterministic, no network beyond `nix eval`): compare grype's fix version, or the NVD constraint's
  last-affected version, against package versions evaluated from four nixpkgs sources: repo-pinned stable, stable channel head
  (`github:NixOS/nixpkgs/nixos-26.05`), repo-pinned unstable, unstable channel head. The tool uses vulnxscan's repology classification
  automatically whenever the network allows it (rows with `classify` take precedence over the version comparison).
- Alerts (343) join to the local re-scan (236 unique CVE/package/version findings) on (CVE id, package); all 343 matched.
- Evidence strength: `patched_in_nixpkgs` is hard evidence (patch file names are in the table in section 6). The version-comparison classes are
  approximations: a newer nixpkgs version is treated as a fix only when it reaches grype's fix version or exceeds NVD's last-affected
  version. `unbounded_cpe_match` is deliberately not auto-dismissed.
- Library promotions through the fast-lane overlay replace the attribute for every dependent (mass rebuild, ABI risk). For libraries
  (gstreamer, sqlite, libcap, alsa-lib, libusb, giflib, nghttp2, libjxl, perl) prefer waiting for a stable backport or removing the consumer. The
  overlay is cheap only for leaf applications (grafana, nmap).

## 4. Actionable list grouped by root fix

Alert counts are upper bounds: a package disappears from the findings only if no other consumer keeps it in the closure.

### 4.1 Remove or trim an optional module (see section 7 for capabilities lost)

| root fix | removes (alerts) |
|---|---|
| `programs.appimage.enable = false` (`nix/modules/core/base.nix:338`) | libpng 1.2.59 (14: 2 critical, 7 high) and the 1.5 GB appimage FHS rootfs |
| Playwright browsers without WebKit/Firefox (`nix/modules/roles/antigravity.nix:37,49`, `agentic-toolchain.nix:38,135`) | libxml2 2.13.9 (19 legacy: 12 high) + libjxl 0.8.2 (3, 1 critical), about 1 GB |
| virtualization role off in the ai-dev profile (`nix/modules/profiles/ai-dev.nix:15`), or `libvirtd.qemu.package = pkgs.qemu_kvm` + `libvirt.override { enableXen = false; }` | qemu (8), capstone (7, 1 critical), spice (3, 1 critical), xen (1), openvswitch (1), inetutils (4, 3 already patched) |
| aider without voice deps (`nix/modules/services/mcp-servers.nix:1510`) | ffmpeg-full 8.1.2 copy (about 1.5 GB), libssh via ffmpeg |
| PrismLauncher build deps out of ai-dev (`nix/modules/core/base.nix:123-150`, jdk8/17/21/25 + qt6 set) | four openjdk copies (about 1 GB closure each); giflib stays through ffmpeg/libwebp |

### 4.2 Fixed only in nixpkgs-unstable (82 alerts)

| package | alerts | fixed in unstable | promotion kind |
|---|---:|---|---|
| gstreamer 1.26.11 (+ gst-plugins-good) | 38 | 1.28.7 | library: do not overlay. Consumers are stable pipewire 1.6.6 and xdg-desktop-portal. Either build pipewire without gstreamer or wait for a 26.05 backport (section 7) |
| ffmpeg 8.1.2 | 21 | 9.0.1 | add `ffmpeg` to the fast-lane `active` list (`nix/overlays/fast-lane-manifest.nix`), rebuild-test; used for yt-dlp/whisper audio extraction |
| libusb 1.0.29 | 4 | 1.0.30 | library; wait for backport |
| sqlite 3.51.2 | 4 | 3.53.3 | library; wait for backport |
| alsa-lib, libcap, nghttp2, giflib, libjxl 0.11.2, capstone | 2 each (capstone 1) | see JSON | libraries; wait for backport |
| perl 5.42.0 | 1 critical (CVE-2026-4176) | 5.42.3 | library-like; wait for backport |
| grafana 13.0.9 | 2 | 13.1.6 | leaf app: fast-lane promotion is cheap |
| nmap 7.99 | 1 | 7.991 | leaf app: fast-lane promotion is cheap |

`nix flake update` (nixpkgs) fixes none of these today. Re-run the triage after each flake update; `fixed_in_nixpkgs_stable` flips on automatically when a backport lands.

### 4.3 No upstream fix or unbounded NVD data (143 alerts): policy decision, not engineering

- 108 `unbounded_cpe_match` (10 critical): gnutls 16, libssh 14, libtiff 12, openssh 8, qemu 8, binutils 5, and others. NVD lists the product with no version range, so
  every release matches. Eight of the critical alerts in the unbounded, no-fix and review pools are verified product collisions (table in section 6.2); the rest need a sample check
  (for example the 16 gnutls alerts include two critical CVEs, DTLS reassembly and RSA-PSK, each reported twice).
- 35 `no_upstream_fix` (6 critical): alsa-lib 9, binutils 5, avahi 3, perl 3, capstone 2, libmad 2 (critical, library abandoned), zlib 2, busybox 2, and singletons.
  Recommendation: keep open under one "accepted risk" label reviewed at each flake update, or dismiss as won't-fix with a pointer to this file.

### 4.4 Awaiting nixpkgs (9 alerts)

capstone 5.0.7 (4: fixes only in 6.0.0-alpha), shellcheck 0.11.0 (critical, but it is a VS Code extension CVE, see 6.2), lua 5.2/5.3 (2), pgvector 0.8.2 (fixed in 0.8.6; 0.8.6 is already in unstable), malcontent 0.13.1 (1).
Only pgvector is a cheap leaf promotion (a PostgreSQL extension).

Known limit of the version-compare fallback: NVD bounds that reach into a development branch overstate the last-affected version. Example: perl has 4 alerts outside the patched set
(1 classed unstable-fixed, 3 classed no-fix because NVD's bound is 5.43.10); the advisory text of CVE-2026-13221 says fixed in 5.42.3-RC1, so all four are very likely fixed by perl 5.42.3.

## 5. Top 10 actionable items

1. **Dismiss the 70 patched alerts** (7 critical, 26 high). Zero engineering, removes 20% of the noise. Commands in section 6.
2. **Confirm and dismiss the 10 verified false positives** (8 of them critical): redis x2, openssh, typescript, samba, sherlock, shellcheck, libppd, libcupsfilters, dnsmasq (section 6.2).
3. **Drop WebKit and Firefox from Playwright browsers** (`playwright-driver.browsers.override { withWebkit = false; withFirefox = false; }`): 22 alerts and about 1 GB.
4. **Decide on `programs.appimage`**: libpng 1.2.59 is a genuinely old library (14 alerts, 2 critical) inside a 1.5 GB FHS rootfs. If no AppImage is run, disable it.
5. **Decide on the virtualization role** for the ai-dev profile: qemu, capstone, spice, xen, openvswitch, inetutils in one switch; about 25 alerts, 2 GB. Only `scripts/governance/discover-system-facts.sh` probes `virsh`; no script or AI-stack service runs a VM.
6. **ffmpeg 8.1.2 to 9.0.1** (21 alerts, 18 high): fast-lane promotion of `ffmpeg` after a rebuild test (ffmpeg-headless 9.0.1 already builds inside the closure through the antigravity pipewire).
7. **Slim aider** (2.9 GB closure): `pydub` hard-codes `ffmpeg-full`, pulled only for aider's voice mode; override the dependency away. This removes a third ffmpeg copy and libssh.
8. **gstreamer 1.26.11** (38 alerts, 32 high): pick one of (a) pipewire/xdg-desktop-portal built without gstreamer, or (b) accept until a 26.05 backport. Do not overlay `gst_all_1`.
9. **Review the no-fix/unbounded pool once** (143 alerts) and put it under a single accepted-risk label so the alert list shows only actionable work.
10. **Retire the stale Trivy analyses** (section 6.3), then wire `aq-closure-scan --triage-json` into the RSI intake so class `patched_in_nixpkgs` never becomes an incident again.

## 6. Proposed dismissals and closures (owner runs; none executed)

### 6.1 Class (a): 70 alerts, "false positive" with patch evidence

Reason text per alert (generated, max 280 chars, stored in `closure-triage-alerts.json` as `dismiss_reason`):
`False positive: nixpkgs applies <patch files> to <package> <version> (backport without a version bump); grype matches CPE by version string only.`

| alert | CVE | package | sev | patch evidence |
|---:|---|---|---|---|
| 2540 | CVE-2026-24061 | inetutils 2.7 | critical | CVE-2026-24061_1.patch CVE-2026-24061_2.patch |
| 2552 | CVE-2026-32746 | inetutils 2.7 | critical | CVE-2026-32746.patch |
| 2598 | CVE-2026-26740 | giflib 5.2.2 | high | CVE-2026-26740.patch |
| 2599 | CVE-2026-26740 | giflib 5.2.2 | high | CVE-2026-26740.patch |
| 2606 | CVE-2026-7598 | libssh2 1.11.1 | critical | CVE-2026-7598.patch |
| 2607 | CVE-2026-7598 | libssh2 1.11.1 | critical | CVE-2026-7598.patch |
| 2609 | CVE-2026-55200 | libssh2 1.11.1 | critical | CVE-2026-55200.patch |
| 2610 | CVE-2026-55200 | libssh2 1.11.1 | critical | CVE-2026-55200.patch |
| 2620 | CVE-2026-66033 | libssh2 1.11.1 | high | CVE-2026-66033.patch |
| 2621 | CVE-2026-66033 | libssh2 1.11.1 | high | CVE-2026-66033.patch |
| 2624 | CVE-2026-0990 | libxml2 2.13.9 | medium | CVE-2026-0990.patch |
| 2626 | CVE-2026-55199 | libssh2 1.11.1 | high | CVE-2026-55199.patch |
| 2627 | CVE-2026-55199 | libssh2 1.11.1 | high | CVE-2026-55199.patch |
| 2637 | CVE-2026-8376 | perl 5.42.0 | critical | CVE-2026-8376.patch |
| 2641 | CVE-2026-66035 | libssh2 1.11.1 | high | CVE-2026-66035.patch |
| 2642 | CVE-2026-66035 | libssh2 1.11.1 | high | CVE-2026-66035.patch |
| 2647 | CVE-2025-15661 | libssh2 1.11.1 | high | CVE-2025-15661.patch |
| 2648 | CVE-2025-15661 | libssh2 1.11.1 | high | CVE-2025-15661.patch |
| 2654 | CVE-2026-66032 | libssh2 1.11.1 | high | CVE-2026-66032.patch |
| 2655 | CVE-2026-66032 | libssh2 1.11.1 | high | CVE-2026-66032.patch |
| 2665 | CVE-2026-58050 | libssh2 1.11.1 | high | CVE-2026-58050.patch |
| 2666 | CVE-2026-58050 | libssh2 1.11.1 | high | CVE-2026-58050.patch |
| 2671 | CVE-2026-66034 | libssh2 1.11.1 | high | CVE-2026-66034.patch |
| 2672 | CVE-2026-66034 | libssh2 1.11.1 | high | CVE-2026-66034.patch |
| 2673 | CVE-2022-47021 | opusfile 0.12 | high | CVE-2022-47021.patch |
| 2674 | CVE-2022-47021 | opusfile 0.12 | high | CVE-2022-47021.patch |
| 2675 | CVE-2022-47021 | opusfile 0.12 | high | CVE-2022-47021.patch |
| 2700 | CVE-2026-42046 | libcaca 0.99.beta20 | high | CVE-2026-42046.patch |
| 2707 | CVE-2025-68471 | avahi 0.8 | medium | CVE-2025-68471.patch |
| 2708 | CVE-2025-68471 | avahi 0.8 | medium | CVE-2025-68471.patch |
| 2709 | CVE-2025-68471 | avahi 0.8 | medium | CVE-2025-68471.patch |
| 2716 | CVE-2025-68468 | avahi 0.8 | medium | CVE-2025-68468.patch |
| 2717 | CVE-2025-68468 | avahi 0.8 | medium | CVE-2025-68468.patch |
| 2718 | CVE-2025-68468 | avahi 0.8 | medium | CVE-2025-68468.patch |
| 2724 | CVE-2026-58051 | libssh2 1.11.1 | high | CVE-2026-58051.patch |
| 2725 | CVE-2026-58051 | libssh2 1.11.1 | high | CVE-2026-58051.patch |
| 2729 | CVE-2021-3468 | avahi 0.8 | medium | CVE-2021-3468.patch |
| 2730 | CVE-2021-3468 | avahi 0.8 | medium | CVE-2021-3468.patch |
| 2731 | CVE-2021-3468 | avahi 0.8 | medium | CVE-2021-3468.patch |
| 2740 | CVE-2026-0989 | libxml2 2.13.9 | low | 2.13-CVE-2026-0989.patch |
| 2743 | CVE-2023-38471 | avahi 0.8 | medium | CVE-2023-38471.patch CVE-2023-38471-2.patch |
| 2744 | CVE-2023-38471 | avahi 0.8 | medium | CVE-2023-38471.patch CVE-2023-38471-2.patch |
| 2745 | CVE-2023-38471 | avahi 0.8 | medium | CVE-2023-38471.patch CVE-2023-38471-2.patch |
| 2751 | CVE-2023-38470 | avahi 0.8 | medium | CVE-2023-38470.patch |
| 2752 | CVE-2023-38470 | avahi 0.8 | medium | CVE-2023-38470.patch |
| 2753 | CVE-2023-38470 | avahi 0.8 | medium | CVE-2023-38470.patch |
| 2754 | CVE-2023-38469 | avahi 0.8 | medium | CVE-2023-38469.patch |
| 2755 | CVE-2023-38469 | avahi 0.8 | medium | CVE-2023-38469.patch |
| 2756 | CVE-2023-38469 | avahi 0.8 | medium | CVE-2023-38469.patch |
| 2757 | CVE-2023-38472 | avahi 0.8 | medium | CVE-2023-38472.patch |
| 2758 | CVE-2023-38472 | avahi 0.8 | medium | CVE-2023-38472.patch |
| 2759 | CVE-2023-38472 | avahi 0.8 | medium | CVE-2023-38472.patch |
| 2760 | CVE-2023-38473 | avahi 0.8 | medium | CVE-2023-38473.patch |
| 2761 | CVE-2023-38473 | avahi 0.8 | medium | CVE-2023-38473.patch |
| 2762 | CVE-2023-38473 | avahi 0.8 | medium | CVE-2023-38473.patch |
| 2766 | CVE-2026-24401 | avahi 0.8 | medium | CVE-2026-24401.patch |
| 2767 | CVE-2026-24401 | avahi 0.8 | medium | CVE-2026-24401.patch |
| 2768 | CVE-2026-24401 | avahi 0.8 | medium | CVE-2026-24401.patch |
| 2771 | CVE-2025-60876 | busybox 1.37.0 | medium | CVE-2025-60876.patch |
| 2784 | CVE-2026-28372 | inetutils 2.7 | high | CVE-2026-28372.patch |
| 2792 | CVE-2026-0992 | libxml2 2.13.9 | low | 2.13-CVE-2026-0992.patch |
| 2822 | CVE-2026-23868 | giflib 5.2.2 | high | CVE-2026-23868.patch |
| 2823 | CVE-2026-23868 | giflib 5.2.2 | high | CVE-2026-23868.patch |
| 2834 | CVE-2026-11979 | libxml2 2.13.9 | high | CVE-2026-11979.patch |
| 2843 | CVE-2026-34933 | avahi 0.8 | medium | CVE-2026-34933.patch |
| 2844 | CVE-2026-34933 | avahi 0.8 | medium | CVE-2026-34933.patch |
| 2845 | CVE-2026-34933 | avahi 0.8 | medium | CVE-2026-34933.patch |
| 2846 | CVE-2025-68276 | avahi 0.8 | medium | CVE-2025-68276.patch |
| 2847 | CVE-2025-68276 | avahi 0.8 | medium | CVE-2025-68276.patch |
| 2848 | CVE-2025-68276 | avahi 0.8 | medium | CVE-2025-68276.patch |


Command (reads the reason per alert from the JSON; run from the repo root; the loop is idempotent):

```bash
jq -r '.alerts[] | select(.disposition=="dismiss-false-positive") | [.number,.dismiss_reason] | @tsv' \
  .agents/plans/slate-cleanup-20261001/closure-triage-alerts.json |
while IFS=$'\t' read -r n reason; do
  gh api -X PATCH "repos/MasterofNull/NixOS-Dev-Quick-Deploy/code-scanning/alerts/$n" \
    -f state=dismissed -f dismissed_reason="false positive" -f dismissed_comment="$reason" >/dev/null && echo "dismissed $n"
done
```

Caveat: the next `nix-closure` upload recreates the same findings; GitHub keeps dismissals for identical rule and location fingerprints, but the
durable fix is to filter class `patched_in_nixpkgs` out of the uploaded SARIF (follow-up, section 8).

### 6.2 Verified false positives that need the owner's confirmation (10 alerts, `disposition: dismiss-after-owner-confirm`)

Same command with `select(.disposition=="dismiss-after-owner-confirm")`. Reasons are product mismatches read from the advisory text, or pre-release suffix mis-ordering (`2.1b1`, `2.93test9` sort after `2.1.1`/`2.93` in grype).

| alert | CVE | package | sev | reason |
|---:|---|---|---|---|
| 2539 | CVE-2022-0543 | redis 8.8.3 | critical | CVE-2022-0543 is a Debian-specific packaging flaw (Lua sandbox escape in Debian's redis build); not applicable to the nixpkgs redis build. |
| 2541 | CVE-2024-47076 | libcupsfilters 2.1.1 | high | CVE-2024-47076 affects libcupsfilters up to 2.1b1; installed 2.1.1 is newer (grype mis-orders the 'b1' pre-release suffix). |
| 2542 | CVE-2024-47175 | libppd 2.1.1 | critical | CVE-2024-47175 affects libppd up to 2.1b1; installed 2.1.1 is newer (grype mis-orders the 'b1' pre-release suffix). |
| 2544 | CVE-2018-17930 | sherlock 0.16.0 | critical | CVE-2018-17930 affects Teledyne DALSA Sherlock (machine-vision software); the 'sherlock' package here is an unrelated CPE name collision. |
| 2545 | CVE-2011-2411 | samba 4.23.10 | critical | CVE-2011-2411 is specific to HP NonStop servers running Samba; not applicable to samba on NixOS/Linux. |
| 2546 | CVE-2020-1416 | typescript 5.9.3 | critical | CVE-2020-1416 is a Visual Studio / VS Code elevation-of-privilege flaw; the 'typescript' npm package is a CPE name collision. |
| 2554 | CVE-2008-3844 | openssh 10.5p1 | critical | CVE-2008-3844 concerns trojaned Red Hat Enterprise Linux 4/5 OpenSSH packages signed in 2008; not applicable to nixpkgs openssh. |
| 2566 | CVE-2021-28794 | shellcheck 0.11.0 | critical | CVE-2021-28794 affects the unofficial ShellCheck VS Code extension (before 0.13.4), not the shellcheck CLI binary. |
| 2618 | CVE-2022-3734 | redis 8.8.3 | critical | CVE-2022-3734 affects a Windows port/fork of Redis (C:/Program Files/Redis/dbghelp.dll); not the upstream redis package. |
| 2635 | CVE-2026-6507 | dnsmasq 2.93 | high | Fixed in 2.93test9 (a pre-release of 2.93); installed 2.93 is the final release (grype mis-orders 'test9'). |

### 6.3 Five stale `trivy-custom-*` alerts

| alert | CVE | severity | category |
|---:|---|---|---|
| 2534 | CVE-2025-71176 | medium | trivy-custom-hybrid-coordinator |
| 2535 | CVE-2025-71176 | medium | trivy-custom-aidb |
| 2536 | CVE-2026-97687 | high | trivy-custom-aidb |
| 2537 | CVE-2026-97689 | high | trivy-custom-aidb |
| 2538 | CVE-2026-97688 | medium | trivy-custom-aidb |

They live in two analyses from the last container run (2026-10-01, commit 358d971b): `1875189082` (aidb) and `1875180726` (hybrid-coordinator).
The workflow no longer has those jobs, so nothing will ever refresh or fix them; deleting the analyses closes the alerts.

Dry run (executed, read-only): `bash scripts/security/cleanup-stale-code-scanning-analyses.sh --repo MasterofNull/NixOS-Dev-Quick-Deploy`
reports 22 stale deletable analyses on `refs/heads/main`: 7 from 2026-03-23 (`trivy-redis:7.4-alpine`, grafana, prometheus, jaeger, nginx, qdrant, postgres),
4 more from 2026-03-23 (nginx/prometheus/qdrant/grafana version-tagged), 7 from 2026-09-26 (`trivy-grafana`, nginx, redis, jaeger, qdrant, postgres, prometheus), and 4 from 2026-10-01
(`trivy-custom-hybrid-coordinator`, `-embeddings-service`, `-nixos-docs`, `-aidb`). The script did not run with `--apply`.

Owner command, full cleanup (deletes all 22 stale analyses, which is the script's purpose and also closes the 5 alerts):

```bash
bash scripts/security/cleanup-stale-code-scanning-analyses.sh --repo MasterofNull/NixOS-Dev-Quick-Deploy --apply
```

Narrower alternative (only the two analyses that hold the 5 alerts; `confirm_delete` is required when an analysis is the last of its set):

```bash
for id in 1875189082 1875180726; do
  gh api -X DELETE "repos/MasterofNull/NixOS-Dev-Quick-Deploy/code-scanning/analyses/$id?confirm_delete"
done
```

If the owner prefers to keep the history, dismiss instead: `gh api -X PATCH repos/MasterofNull/NixOS-Dev-Quick-Deploy/code-scanning/alerts/<n> -f state=dismissed -f dismissed_reason="won't fix" -f dismissed_comment="container image scanning retired 2026-10-01; Nix closure scan is the single source"` for 2534-2538.

## 7. Bloat-removal proposals (no Nix module was edited)

Why each package is in the closure came from `nix why-depends /run/current-system <path>` on every store path; sizes are `nix path-info -S` closure sizes
(shared dependencies are counted in each, so they are indicative, not additive). Rule: remove only where the capability below is unused.

| package (alerts) | pulled in by | repo option / module | capability provided | removable? | proposed change |
|---|---|---|---|---|---|
| gstreamer 1.26.11 + 1.28.7 (40) | pipewire 1.6.6 (gstreamer plugin), xdg-desktop-portal 1.20.4; second copy via antigravity-ide's pipewire 1.6.9 | `services.pipewire` in `nix/modules/roles/desktop.nix:92`; fast-lane `antigravity` | GStreamer `pipewiresrc`/`pipewiresink` (gst-based screen capture and camera), portal media helpers | partly: not toggleable by package argument (`mesonEnable "gstreamer" true`); needs `overrideAttrs` with `-Dgstreamer=disabled -Dgstreamer-device-provider=disabled`, a local rebuild of pipewire | optional: pipewire override; otherwise accept until backport |
| avahi 0.8 (36, 33 patched) | `system-path` directly (COSMIC module sets `services.avahi.enable = mkDefault true`, nixpkgs `desktop-managers/cosmic.nix:172`); pipewire zeroconf; cups-browsed follows avahi | `services.desktopManager.cosmic` (`desktop.nix:58`), `services.printing` (`desktop.nix:293`) | mDNS/DNS-SD: network printer discovery, `.local` names, AirPlay/Chromecast discovery in pipewire | yes if none of those are used: `services.avahi.enable = lib.mkForce false` plus `pipewire.override { zeroconfSupport = false; }`. Security gain is small (3 unfixed medium) | owner decision |
| ffmpeg 8.1.2 (21), ffmpeg-full 8.1.2, ffmpeg-headless 8.1.2 and 9.0.1 | `system-path` (`ffmpeg` in `nix/data/profile-system-packages.nix:85,165`); pipewire (headless); aider via pydub (full); antigravity pipewire (headless 9.0.1) | profile package list, aider-chat | yt-dlp/whisper audio extraction; pipewire `pw-cat` ffmpeg formats; aider `/voice` | the three-copy duplication is removable, the CLI is not: promote `ffmpeg` (fixes the 21), slim aider (below) | fast-lane `ffmpeg`; aider override |
| aider-chat 0.86.1 (2.9 GB closure) | `AIDER_BIN` in `nix/modules/services/mcp-servers.nix:1510`, `nix/hosts/nixos/home.nix:17` | `ai-aider-wrapper` service | headless code edits for the MCP wrapper | voice mode only is removable: `pkgs.aider-chat.overridePythonAttrs` dropping `pydub` (needs a smoke test of the wrapper) | optional |
| qemu 10.2.4 (8) | `system-path` (libvirtd default `qemu.package = pkgs.qemu`, all architectures); separate `qemu_kvm` host-only copy also installed | `nix/modules/roles/virtualization.nix:47,67`, `kernel-dev.nix:70`; enabled by `ai-dev.nix:15` | local VMs and non-host-arch emulation | yes: role is a convenience for this AI harness. Smaller step: `virtualisation.libvirtd.qemu.package = pkgs.qemu_kvm` drops the all-arch copy (about 2 GB closure) and keeps KVM guests | disable role, or the smaller step |
| capstone 5.0.7 (7) | only qemu (all-arch build) | same as qemu | disassembly in qemu's monitor | yes, with qemu | follows qemu |
| spice 0.16.0 / spice-gtk (3) | qemu (spice display); `spice-gtk` and `virt-viewer` listed in `virtualization.nix:68-69` | same | SPICE guest consoles | yes, with the role | follows role |
| libvirt 12.2.0 -> xen 4.20.4 -> inetutils 2.7, openvswitch 3.7.1 | libvirt built with Xen support (`libvirt.override { enableXen = ... }`, arg verified) | `virtualization.nix:26,66` | Xen hypervisor management (not used; KVM only) | yes: `libvirt.override { enableXen = false; }` removes xen (552 MB), inetutils, openvswitch while keeping libvirt/KVM | even if the role stays |
| libssh 0.12.2 (14) | ffmpeg (both headless copies), `ld-library-path` | pipewire, nix-ld library list | SFTP/SSH protocol in ffmpeg | no: tied to ffmpeg builds, all 14 alerts are unbounded NVD data | accept |
| libssh2 1.11.1 (20, all patched) | curl 8.22.0 (systemd, elfutils, antigravity) | core | scp/sftp in curl | no (rebuilding curl rebuilds the world); all alerts are false positives | dismiss |
| alsa-lib 1.2.15.3 (11) | pipewire alsa plugin, qemu | `services.pipewire.alsa.enable` (`desktop.nix:94`) | ALSA clients through pipewire | no: audio; qemu copy goes with the role | accept |
| busybox 1.37.0 (3) | `nix-store` (sandbox shell), via nix 2.34.8 | core Nix | build sandbox shell | no | accept (2 low) |
| inetutils 2.7 (4) | libvirt -> xen | see above | hostname/telnet-style tools for Xen | yes, with `enableXen = false` | follows libvirt |
| libmicrohttpd 1.0.2 (4) | systemd 260 (journal-remote), libcanberra | core | HTTP in systemd tools | no | accept (unbounded NVD data) |
| playwright WebKit/Firefox (libxml2 2.13.9 19, libjxl 0.8.2 3) | `playwright-driver.browsers` | `antigravity.nix:37,49`, `agentic-toolchain.nix:38,135` | cross-browser testing in Playwright (Chromium stays) | yes: `browsers.override { withWebkit = false; withFirefox = false; }` (args verified) | do it unless WebKit/Firefox tests are used |
| appimage-run FHS rootfs (libpng 1.2.59, 14) | `programs.appimage` | `nix/modules/core/base.nix:338` | run AppImage binaries | yes if no AppImage is run | owner decision |
| openjdk 25 / jdk8-25 (giflib) | PrismLauncher dev packages | `nix/modules/core/base.nix:123-150`, gated on profile `ai-dev` | building PrismLauncher from source | yes if that build is no longer wanted | owner decision |
| samba, libusb (gvfs) | COSMIC module sets `services.gvfs.enable = mkDefault true` | `desktop.nix:58` | SMB/MTP mounts in the file manager | yes if unused: `services.gvfs.enable = lib.mkForce false` (1.3 GB closure) | owner decision |

None of the Nix changes were built or evaluated against a full system; each is a proposal to rebuild-test. Argument names for `libvirt`, `pipewire`, `qemu_kvm`, `playwright-driver.browsers` and
`aider-chat` were verified against nixpkgs 26.05 with `nix eval ... override.__functionArgs`.

## 8. Repeatable triage

New mode in `scripts/security/aq-closure-scan` (no new dependency; all tools run through `nix run/shell --inputs-from`):

```bash
scripts/security/aq-closure-scan --triage-json /tmp/closure-triage.json            # full pipeline against /run/current-system
# offline / fixture replay (what the unit tests use)
scripts/security/aq-closure-scan --triage-json out.json --grype-json g.json --sbom-csv sbom.csv \
    [--triage-input vulns.triage.csv] [--versions-json versions.json]
```

The JSON holds `by_class` counts per severity, `actionable_groups` (everything except `patched_in_nixpkgs`, grouped by root fix and sorted by severity),
and one record per finding with `class`, `evidence`, `fixed_in`, `grype_fix_versions`, `constraint`, `root_fix`. Pipeline: sbomnix (CycloneDX + CSV) -> grype ->
vulnxscan `--sbom --triage` (repology; skipped with a stderr note when unreachable) -> classification, with the nixpkgs version-compare fallback.
Exit code 2 on any scanner failure, as before; classification itself never changes the exit code.

Test run: `python3 -m unittest scripts/testing/test-aq-closure-scan.py` (17 tests, offline) and `python3 scripts/testing/test-security-nix-closure-scan.py` (5 tests).
A live run against `/run/current-system` completed end to end and classified the 236 unique findings.

Follow-ups (not done, to keep this slice bounded): (1) feed `patched_in_nixpkgs` into the SARIF filter in `.github/workflows/security.yml` so those alerts are never uploaded;
(2) let `scripts/security/rsi-intake-code-scanning.py` read the triage JSON and skip class (a); (3) run the triage weekly after the flake refresh so `fixed_in_nixpkgs_stable` flips to actionable by itself.

## 9. Findings to log (Rule 11) for the orchestrator

- repology.org is unreachable from the agent sandbox, so `vulnxscan --triage` cannot complete here (works on a networked host or in CI). Mitigation is the version-compare fallback above.
- `scripts/security/cleanup-stale-code-scanning-analyses.sh` is not executable in the git tree (`permission denied` when invoked directly; `bash <script>` works).
- The worktree `flake.lock` root `nixpkgs` input resolves through node `nixpkgs_5` (rev 78e9c786, equal to the deployed system); node `nixpkgs` (8c3cede7, 2026-06) is an unrelated transitive pin. Anyone reading `flake.lock` by name will pick the wrong one.

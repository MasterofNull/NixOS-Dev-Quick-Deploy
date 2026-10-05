TASK: Reduce real vulnerability exposure in the hyperd-ai-dev NixOS closure WITHOUT removing any capability the owner uses. Use the existing fast-lane overlay to pull fixed versions from nixpkgs-unstable, one attribute at a time, each behind a build check. Deterministic changes only.

OWNER RULES (binding):
- Do not remove or disable any capability. The only removal allowed is Xen support in libvirt, and only after you verify nothing in this repo configures or uses Xen (the host runs KVM).
- Floors/newest versions, never pinning older versions. Nix is the single source.
- Never rm (archive with mv). Do not commit, push, run nixos-rebuild switch, sudo, or tier0. Leave changes uncommitted in your worktree.

READ FIRST (bounded):
- .agents/plans/slate-cleanup-20261001/CLOSURE-TRIAGE.md sections 4, 7, 8
- .agents/plans/slate-cleanup-20261001/closure-triage-alerts.json (class "fixed_in_nixpkgs_unstable")
- nix/overlays/fast-lane-manifest.nix (existing format: `active` list + `renames`) and whatever imports it
- config/update-tiers.json and scripts/maintenance/aq-update-tiers (the promote mechanism: manifest insert, build check, restore on failure)
- nix/modules/roles/virtualization.nix (libvirt / qemu)

CANDIDATES (alerts fixed only in nixpkgs-unstable):
1. ffmpeg 8.1.2 -> 9.0.1 (21 alerts). Installed as a system package (nix/data/profile-system-packages.nix:85,165). Promote the system-package attr via the fast-lane manifest. Do not rebuild pipewire against it.
2. nmap 7.99 -> 7.991 (1), grafana 13.0.9 -> 13.1.6 (2): leaf packages; promote if the build check passes.
3. gstreamer 1.26.11 -> 1.28.7 (36 + 2 gst-plugins-good): consumed by pipewire and xdg-desktop-portal. Do NOT overlay gst_all_1 globally (mass rebuild). Evaluate promoting pipewire (and xdg-desktop-portal if needed) from unstable: measure with `nix build --dry-run` how many derivations must build locally (not substitutable). If more than ~50 derivations or any core-tier service would change channel, do not apply it; report the numbers and the recommendation instead.
4. libvirt Xen: if verified unused, set `libvirt.override { enableXen = false; }` where virtualization.nix builds libvirt (removes xen, inetutils, openvswitch from the closure).
NOT candidates (core libraries; overriding forces a world rebuild; they arrive with the stable-channel backport): sqlite, nghttp2, libcap, alsa-lib, perl, libusb, libjxl, giflib, capstone. Leave them.

METHOD per candidate:
- Add it to config/update-tiers.json in the fitting frontier category (create a "media"/"monitoring"/"security-tools" category only if none fits; keep the file's structure), then use `scripts/maintenance/aq-update-tiers promote --one` (or the same steps by hand) so the manifest edit is build-checked and restored on failure.
- Build check: `nix build --no-link .#nixosConfigurations.hyperd-ai-dev.pkgs.<attr>` for the promoted attr, then evaluate the full system drvPath (`nix eval --raw .#nixosConfigurations.hyperd-ai-dev.config.system.build.toplevel.drvPath`) to prove the configuration still evaluates. Use `--max-jobs 2 --cores 2` for any build.
- After all changes: run `python3 -m pytest -q scripts/testing/test-aq-update-tiers.py scripts/testing/test-fast-lane-staleness-check.py` (or their script entry points) and report results.

REPORT (write to .agents/plans/slate-cleanup-20261001/FASTLANE-PROMOTIONS.md and summarize in your final message):
- Per candidate: applied / not applied, version before -> after, build-check result, derivations built, and which alert numbers it should close on the next nix-closure scan.
- Xen verification evidence (rg results) and whether enableXen=false was applied.
- gstreamer/pipewire measurement and recommendation.
- Exact list of files changed.

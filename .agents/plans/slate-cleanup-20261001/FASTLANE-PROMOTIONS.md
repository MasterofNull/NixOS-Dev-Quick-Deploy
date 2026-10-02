# Build-checked fast-lane promotions — 2026-10-02

Changes are uncommitted and not activated. No switch, sudo, tier0, commit, push, or staging was performed. Alert closure remains conditional on deployment and a new closure scan; these are package/build results, not runtime attestations.

## Results

| Candidate | Decision | Before → after | Build check | Local derivations built | Expected alert effect |
|---|---|---|---|---:|---|
| System-package `ffmpeg` | Applied in frontier/media and manifest | 8.1.2 → 9.0.1 | PASS; full system drv evaluation PASS | 0 (substituted) | Targets 21 alerts listed below; other stable FFmpeg variants can retain findings |
| `nmap` | Applied in frontier/security-tools and manifest | 7.99 → 7.991 | PASS; full system drv evaluation PASS | 0 (substituted) | #2590, provided no old copy remains |
| `grafana` | Applied in frontier/monitoring and manifest | 13.0.9 → 13.1.6 | PASS; full system drv evaluation PASS | 0 (substituted) | #2739, #2803, provided no old copy remains |
| `pipewire` / GStreamer | Not applied: core channel boundary | PipeWire 1.6.6 retained; unstable 1.6.9; GStreamer 1.26.11 retained, candidate 1.28.7 | Unstable package dry-run PASS; no actual build | 0 required by dry-run | No claimed closures |
| `xdg-desktop-portal` | Not applied: core channel boundary | 1.20.4 retained; unstable 1.22.1 | Unstable package dry-run PASS; no actual build | 0 required by dry-run | No claimed closures |
| libvirt Xen backend | Applied locally to daemon, helper CLI and system-package selection | libvirt 12.2.0 → 12.2.0, `enableXen = false` | PASS (exit 0); full system drv evaluation PASS | 2 | No whole-closure Xen/inetutils/openvswitch removal claim: original libvirt remains through virt-viewer |

FFmpeg target alerts: #2605, #2613, #2617, #2625, #2643, #2646, #2652, #2656, #2678, #2687, #2697, #2715, #2726, #2778, #2787, #2790, #2799, #2810, #2818, #2820, #2821. Promotion changes `pkgs.ffmpeg` only; stable full/headless variants from other consumers are outside this slice. The next scan must establish which numbered findings actually disappear.

Deferred GStreamer fixed-in-unstable alerts: #2582, #2583, #2588, #2589, #2676, #2677, #2684, #2685, #2688, #2689, #2691, #2692, #2693, #2694, #2695, #2696, #2702, #2703, #2704, #2705, #2735, #2736, #2749, #2750, #2769, #2770, #2774, #2775, #2776, #2777, #2780, #2781, #2841, #2842, #2849, #2850. gst-plugins-good: #2686, #2863. None is claimed closed.

## Promotion method and evidence

Used the permitted manual equivalent of `aq-update-tiers promote --one`: add one fitting frontier entry, retain the prior manifest, insert that single attribute, dry-run, build, then evaluate the system. Restore would occur on failure; all three promotions passed. Existing frontier candidates were not promoted opportunistically. The existing overlay imports individual unstable packages with their own dependency set; no global GStreamer or core-library overrides were introduced. Flake inputs were unchanged.

For each of `ffmpeg`, `nmap`, `grafana`, these commands exited 0:

```sh
nix build --dry-run --no-link .#nixosConfigurations.hyperd-ai-dev.pkgs.<attr> --max-jobs 2 --cores 2
nix build --no-link .#nixosConfigurations.hyperd-ai-dev.pkgs.<attr> --max-jobs 2 --cores 2
nix eval --raw .#nixosConfigurations.hyperd-ai-dev.config.system.build.toplevel.drvPath
```

Package dry-runs required zero local builds. Fetch estimates were FFmpeg: 55 paths, 79.8 MiB download / 177.5 MiB unpacked; nmap: 6 paths, 9.9 / 35.2 MiB; Grafana: 2 paths, 206.8 / 882.0 MiB. Actual builds exited 0 using substitutes.

Successive evaluated system derivations:

- FFmpeg: `/nix/store/7pgmr7z860yy0y5hva30fs1k3znd1qdg-nixos-system-hyperd-26.05.20260930.78e9c78.drv`
- nmap: `/nix/store/5b7cq0x34mgb3ma9mnvw82bvy0f6j5ji-nixos-system-hyperd-26.05.20260930.78e9c78.drv`
- Grafana: `/nix/store/irx2p00b6iwhxx9hami4gdckpa56ck47-nixos-system-hyperd-26.05.20260930.78e9c78.drv`
- Including libvirt selection: `/nix/store/nwxixgz5sbjbqpjgd2jsvdhi7zx1vd9m-nixos-system-hyperd-26.05.20260930.78e9c78.drv`

Stable PipeWire remained exactly `/nix/store/g9hbajvk59411ny58aqv9yih0rxzacvi-pipewire-1.6.6.drv` before and after the leaf promotions; FFmpeg promotion did not rebuild PipeWire against FFmpeg 9.

## Media measurement and recommendation

```sh
nix build --dry-run --no-link --inputs-from . nixpkgs-unstable#legacyPackages.x86_64-linux.pipewire --max-jobs 2 --cores 2
nix build --dry-run --no-link --inputs-from . nixpkgs-unstable#legacyPackages.x86_64-linux.xdg-desktop-portal --max-jobs 2 --cores 2
```

Both exited 0. PipeWire: **0 local derivations**, 1 substituted path, 130.4 KiB download / 153.7 KiB unpacked. Portal: **0 local derivations**, 49 substituted paths, 50.3 MiB / 169.9 MiB. These are package dry-runs with the current store/cache, not a full-system rebuild forecast.

Although below the approximately 50-build ceiling, both attributes fall under the existing core policy. Promoting them would change core service channels, which the task expressly disallows. Neither was added to frontier or manifest. Recommend waiting for stable-channel backports; a future explicit policy change would require audio, screen-sharing and portal integration validation. No global `gst_all_1` overlay was applied. sqlite, nghttp2, libcap, alsa-lib, perl, libusb, libjxl, giflib and capstone were left alone.

## Xen verification and limits

Before editing, both searches returned no matches (exit 1):

```sh
rg -n -i '\bxen\b|enableXen|xen:///|xend' nix config flake.nix
rg -n -i --max-columns 240 '\bxen\b|enableXen|xen:///|xend' --glob '*.nix' --glob '*.sh' --glob '*.py' --glob '*.json' --glob '*.yaml' --glob '*.yml' --glob '*.toml' --glob '!closure-triage-alerts.json' --glob '!RESUME.json' .
```

The second search covers rg-visible repository configuration/code, excluding the supplied alert data and checkpoint. This is repository evidence, not inspection of runtime guest domains. The owner identifies this host as KVM; the role config explicitly selects KVM kernel modules and `qemu_kvm`. KVM, QEMU, virt-manager, virt-viewer and SPICE capabilities remain configured.

`virtualization.nix` now defines `libvirtPackage = pkgs.libvirt.override { enableXen = false; };`, selects it for libvirtd and the system CLI, and uses it in VM helper scripts. Build command:

```sh
nix build --no-link --impure --expr 'let f = builtins.getFlake (toString ./.); in f.nixosConfigurations.hyperd-ai-dev.pkgs.libvirt.override { enableXen = false; }' --max-jobs 2 --cores 2
```

Dry-run required 2 local derivations (the substituted ZFS command patch and libvirt), plus 36 fetched paths (12.9 MiB / 162.6 MiB). Libvirt derivation: `/nix/store/iksxbjbaa6m5a9ygm71jy1ix1c9ig2z8-libvirt-12.2.0.drv`; selected output: `/nix/store/nf319545ippsfbp8jwvl96ccr6jn73ha-libvirt-12.2.0`.

The build exited 0. Building the exact configured attribute with `nix build --no-link .#nixosConfigurations.hyperd-ai-dev.config.virtualisation.libvirtd.package --max-jobs 2 --cores 2` also passed. `nix-store -qR` found no Xen, inetutils or openvswitch paths in the selected output; the original output contains xen-4.20.4, OVMF-xen-202602-fd, inetutils-2.7 and openvswitch-3.7.1. This confirms their removal from this selected package closure only.

**Residual dependency:** `nix why-depends --derivation` on the final system derivation and original `/nix/store/0s16ry4chp4a536mkyw5aha697305prs-libvirt-12.2.0.drv` found system → system-path → virt-viewer-11.0 → original libvirt. Thus this narrow override cannot establish removal of Xen, inetutils or openvswitch from the complete closure. Rebuilding desktop clients against another libvirt is outside the named slice. No closure reduction is claimed for Xen #2638, openvswitch #2719, or inetutils #2540/#2552/#2784/#2806. No capability was removed to conceal these dependencies.

## Validation and handoff

After the configuration edits:

```sh
python3 -m pytest -q scripts/testing/test-aq-update-tiers.py scripts/testing/test-fast-lane-staleness-check.py
```

**15 passed, 2 warnings, 1.39s**, exit 0. The environment reports unknown pytest options `asyncio_default_fixture_loop_scope` and `asyncio_mode`; these warnings do not change the passing result. No Python or shell source files were modified. Full system drv evaluation passed; the full system was not built or activated. Runtime vulnerability closure remains unverified pending the orchestrator's deployment and rescan.

Exact files changed, including mandated ignored coordination artifacts:

1. `config/update-tiers.json`
2. `nix/overlays/fast-lane-manifest.nix`
3. `nix/modules/roles/virtualization.nix`
4. `.agents/plans/slate-cleanup-20261001/FASTLANE-PROMOTIONS.md`
5. `.agent/collaboration/PULSE.log`
6. `.agent/collaboration/RESUME.json`

## Orchestrator review (2026-10-02)
- Whole-system dry-run with ffmpeg in the global `active` overlay: **120 derivations** to build locally (qtwebengine, qtmultimedia, opencv, ffmpeg-full, torchaudio, ...) — the per-attr "zero local builds" check missed the consumers. ffmpeg moved to a new install-only `leaf` list: `pkgs.fastLaneLeaf.ffmpeg` (9.0.1) is installed via the profile package list while `pkgs.ffmpeg` stays stable for linkers. Result: 61 derivations, all config/unit wrappers plus virt-viewer.
- `virt-viewer` now uses the same Xen-free libvirt (`virt-viewer.override { libvirt = libvirtPackage; }`), closing the residual Xen path.
- `aq-update-tiers` counts `leaf` members as promoted and promotes `"mode": "leaf"` entries into `leaf` (test added), so it can never re-propose ffmpeg as a global override.

## Xen follow-up (2026-10-02, after the owner's rebuild)
Live closure check found xen-4.20.4, openvswitch and inetutils still present: virt-manager and virt-viewer linked the Xen-enabled libvirt through libvirt-glib and the python libvirt bindings. Fixed in `nix/modules/roles/virtualization.nix` with one scoped `nixpkgs.overlays` entry (`libvirt.override { enableXen = false; }`) for all consumers. Verified on a full local system build: 0 xen/openvswitch/inetutils paths; libvirt 12.2.0 and virt-manager 5.1.0 present. Takes effect on the next `nixos-rebuild switch`.

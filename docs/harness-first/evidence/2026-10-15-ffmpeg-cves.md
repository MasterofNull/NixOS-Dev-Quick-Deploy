# ffmpeg CVE remediation (alerts #2919-#2929)

## Objective
Grype closure scan (security.yml "Nix Closure Vulnerability Scan") reports 11 open ffmpeg 8.1.2 alerts (4 HIGH, 7 MEDIUM). Remediate per the dependency ladder, scoped to ffmpeg only.

## Workflow/Session IDs
Branch `fix/ffmpeg-cves`, worktree `.agents/delegation/worktrees/ffmpeg-cves`, base origin/main 12e92bee. Register WR-SEC-3. Staged, not committed. Independent review: PASS_WITH_FOLLOWUPS, follow-ups applied in this revision.

## Delegation Decision
Bounded security slice, Sonnet implementer lane (Rule 17). Independent review routed by the orchestrator (Rule 18).

## Commands Executed
- `gh api repos/MasterofNull/NixOS-Dev-Quick-Deploy/code-scanning/alerts?state=open` (read-only)
- `nix-store -q --requisites /run/current-system | grep ffmpeg`; `nix-store -q --referrers <ffmpeg path>`; `nix eval .#nixosConfigurations.hyperd-ai-dev.pkgs.ffmpeg{,-headless,-full}.version` (8.1.2 each)
- OSV (`api.osv.dev/v1/vulns/<CVE>`), ffmpeg tag list, raw n8.1.2/n8.1.3/n9.0 source of mov.c, iamf_writer.c, wmaenc.c; `git ls-remote` nixpkgs heads; nixpkgs PRs #571601, #567509
- `python3 scripts/testing/test-ffmpeg-cve-mitigations.py`; `check-grype-ignore-expiry.sh` in both modes; `scripts/governance/run-ci-checks.sh --all --only grype-ignore-expiry`; `check-ci-manifest-coverage.sh`

## Validation Evidence
Closure: ffmpeg 8.1.2 (headless/full/plain libs) consumers: pipewire 1.6.6, gst-libav, chromaprint 1.6.0, opencv 4.13, qtmultimedia, torchcodec, python3.13-av, pydub (ffmpeg-full); ffmpeg 9.0.1 CLI leaf, pipewire 1.6.9, chromaprint 1.6.1. Locked nixpkgs 6fcc1603 and nixos-26.05 head a033e66a ship 8.1.2; nixos-unstable has 9.0.1. ffmpeg 8.1.3 backport #571601 targets staging-26.05 (not yet in the channel). ffmpeg 9.0.2 exists upstream, not in nixpkgs.

| CVE | Sev | Issue | Fixed-in | Our version | Decision | Source |
|---|---|---|---|---|---|---|
| 2026-52297 | HIGH | mov_read_iacb extradata padding | 9.0 (CPE); fix present in 8.1.2 code | 8.1.2 | false positive, ignore (version-scoped) to 2026-11-14 | OSV; n8.1.2 mov.c |
| 2026-52296 | HIGH | wmaenc extradata padding | same | 8.1.2 | same | OSV; n8.1.2 wmaenc.c |
| 2026-52295 | MED | iamf_writer extradata padding | same | 8.1.2 | same | OSV; n8.1.2 iamf_writer.c |
| 2026-107695 | HIGH | HLS parse_playlist infinite loop | 8.1.3 | 8.1.2 | await channel; ignore (version-scoped) to 2026-10-22, weekly renewal only while channel lacks 8.1.3 | OSV |
| 2026-107697 | MED | HLS protocol/allowed_extensions bypass | 8.1.3 | 8.1.2 | same | OSV |
| 2026-107660 | MED | mbedtls hostname check skipped for IP hosts | 8.1.3 / 9.0.2 | 8.1.2 | same | OSV |
| 2026-107696 | HIGH | RTSP 3xx redirect infinite loop | none (master 946fcce) | 8.1.2, 9.0.1 | ladder step 2 exception (name-only) to 2026-11-14 + mitigation | OSV |
| 2026-107675 | MED | sftp (libssh) missing host-key verification | none | same | same | OSV |
| 2026-107676 | MED | uninitialized bytes in HDR10+ T.35 serializer | none | same | same | OSV |
| 2026-107677 | MED | DASH empty SegmentTemplate media loop | none | same | same | OSV |
| 2026-107678 | MED | recursive free of PSSH boxes, stack exhaustion | none | same | same | OSV |

False-positive proof is by code, not commit ancestry: in the 8.1.2 source `mov_read_iacb` allocates extradata through `ff_alloc_extradata` (padded), `iamf_writer.c` allocates `size + AV_INPUT_BUFFER_PADDING_SIZE` with INT_MAX guards and zeroes the padding, and `wmaenc.c` uses `av_mallocz(N + AV_INPUT_BUFFER_PADDING_SIZE)`.

Changes: `.grype.yaml` (11 ignores, `package.version: "8.1.2"` on the 6 false-positive/8.1.3 entries, `expires=` tokens; the Grype ignore schema accepts `package.version`); `scripts/governance/tier0.d/check-grype-ignore-expiry.sh` (WARN `--pre-commit`, FAIL otherwise) plus CI step before "Scan closure" via `config/ci-checks.json` entry `grype-ignore-expiry`; `scripts/ai/aq-transcribe` hardening; WR-SEC-3; test `scripts/testing/test-ffmpeg-cve-mitigations.py`.

Exposure and mitigation: before this change, CVE-2026-107695 was reachable through a local `.m3u8` fed to `aq-transcribe` or through yt-dlp handing HLS to ffmpeg. Now `aq-transcribe` runs ffmpeg as `timeout ${AQ_TRANSCRIBE_FFMPEG_TIMEOUT:-600} ffmpeg -nostdin -protocol_whitelist file,pipe ...` (blocks hls/dash/rtsp/sftp network protocols for local inputs) and passes `--hls-prefer-native` to yt-dlp so downloads do not go through ffmpeg. A repo-wide search of scripts/, ai-stack/, nix/ found no other ffmpeg, pydub, torchcodec, av or cv2 invocation on external input. Library consumers (pipewire, opencv, qtmultimedia, gst-libav) are not known to hand ffmpeg untrusted network URLs; this was not audited per consumer.

Test output: see the delegation report (6 tests OK; expiry check PASS both modes today; with GRYPE_IGNORE_TODAY=2026-10-23 WARN in `--pre-commit` and FAIL in `--maintenance`).

## Rollback Plan
`git revert` the commit (removes the ignores, check, CI step, wrapper hardening, WR-SEC-3).

## Residual Risk
Overlay to 8.1.3 rejected: an ffmpeg_8 override rebuilds large referrer closures (reviewer measured 455/192/132 referrers) and the channel is expected to get 8.1.3 soon. Five CVEs (107696, 107675-78) have no released fix and also affect the 9.0.1 CLI; yt-dlp postprocessing still runs ffmpeg on local downloaded files only. Not verified: when staging-26.05 reaches nixos-26.05 (re-check weekly); per-consumer ffmpeg exposure; Legacy ignores (188) have no expiry tokens (check WARNs only).
Activation: owner rebuild from main after `nix flake update nixpkgs` once the channel carries 8.1.3 (no rebuild needed for the ignore/CI/wrapper changes except that aq-transcribe is a repo script and takes effect on merge).

## Hint Feedback
fast-lane-manifest.nix comment and the existing .grype.yaml ffmpeg precedent were the useful hints; no aq-hints query was run.

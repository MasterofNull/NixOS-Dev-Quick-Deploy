# WR-SEC-3 ffmpeg CVE exceptions re-verified (expired 2026-11-14)

Date: 2026-11-14
Task ID: WR-SEC-3-RECHECK-20261114

## Objective
- CI "Grype ignore expiry gate" fails on every PR once `expires=2026-11-14` passes (CI runs UTC; locally the date was still the 14th). Re-verify each expiring ffmpeg ignore per the dependency-hygiene ladder instead of bumping dates blindly (Rule 19). All 8 entries under `.grype.yaml` carrying `expires=2026-11-14` were handled; no other entry had an expiry <= 2026-11-14.

## Workflow/Session IDs
- Workflow ID: none (bounded slice from the orchestrator)
- Session ID: Simurg@claude/sonnet; orchestrator Simurg@claude/opus-5.5#da0ef470

## Delegation Decision
- Sonnet 5.5 implementer (Rule 17). Review by a separate lane; the implementer does not self-review or merge.

## Commands Executed
```bash
GRYPE_IGNORE_TODAY=2026-11-15 bash scripts/governance/tier0.d/check-grype-ignore-expiry.sh --maintenance   # reproduces the CI FAIL (8 entries)
gh api repos/FFmpeg/FFmpeg/tags                                  # latest tags
curl https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=...  # CVE ranges and fix refs
curl https://raw.githubusercontent.com/FFmpeg/FFmpeg/{n8.1.3,n9.0.2}/<file>   # source checks
nix eval --raw .#nixosConfigurations.hyperd-ai-dev.pkgs.{ffmpeg,ffmpeg-headless,ffmpeg-full,ffmpeg_8}.version
scripts/security/aq-closure-scan --target /run/current-system ...   # sbomnix -> grype on the live closure
grype sbom:<closure sbom> -c .grype.yaml                          # ffmpeg matches after the edit
python3 scripts/testing/test-ffmpeg-cve-mitigations.py
```

## Validation Evidence
Ladder step 1 (fixed release?). Upstream FFmpeg latest tags: n9.1-dev, n9.0.2, n9.0.1, n9.0, n8.2-dev, n8.1.3 (https://github.com/FFmpeg/FFmpeg/tags). nixpkgs pin (flake.lock nixpkgs rev 1dd30c29) provides ffmpeg 8.1.3 for ffmpeg, -headless, -full, ffmpeg_8 (ffmpeg_7 = 7.1.5); the live closure holds 8.1.3 libs plus a 9.0.2 CLI leaf. So the 8.1.3 backport the register was waiting on has landed; no flake input update is needed.

| CVE | Upstream status | nixpkgs | Decision | Mitigation / evidence |
|---|---|---|---|---|
| 2026-52295 (iamf_writer padding) | CPE range FP ('before 9.0'); fixed in code | 8.1.3 | renew, re-scope 8.1.2 -> 8.1.3, expires 2026-12-14 | n8.1.3 iamf_writer.c has INT_MAX guard + zeroed PADDING_SIZE; grype flagged it on 8.1.3 before the re-scope, suppressed after |
| 2026-52296 (wmaenc padding) | same | 8.1.3 | same | n8.1.3 wmaenc.c `av_mallocz(N + AV_INPUT_BUFFER_PADDING_SIZE)` |
| 2026-52297 (mov_read_iacb) | same | 8.1.3 | same | n8.1.3 mov.c `ff_alloc_extradata` |
| 2026-107696 (RTSP redirect loop) | no fix; NVD "through 9.0.2", fix on master only (https://nvd.nist.gov/vuln/detail/CVE-2026-107696) | 8.1.3 | renew to 2026-12-14 | aq-transcribe `-protocol_whitelist file,pipe` |
| 2026-107675 (sftp host key) | no fix; "through 9.0.2" (fix PR code.ffmpeg.org/FFmpeg/FFmpeg/pulls/24384); n8.1.3 and n9.0.2 libssh.c have no known-hosts check | 8.1.3 | renew | same |
| 2026-107676 (HDR10+ T.35 bytes) | no fix; "through 9.0.2" (PR 24590) | 8.1.3 | renew | local-file demux only; same |
| 2026-107677 (DASH empty SegmentTemplate loop) | no fix; "through 9.0.2" (PR 24592) | 8.1.3 | renew | dash network protocol blocked by whitelist |
| 2026-107678 (PSSH recursive free) | no fix; "through 9.0.2" (PR 24593) | 8.1.3 | renew | `timeout 600` bound + local files only |

Ladder step 2 mitigation re-check: `scripts/ai/aq-transcribe` line 139 still runs `timeout ... ffmpeg -nostdin -y -protocol_whitelist file,pipe`; `python3 scripts/testing/test-ffmpeg-cve-mitigations.py` OK (6 tests). Repo-wide search of scripts/, ai-stack/, dashboard/ (py, sh, rs) finds no other ffmpeg, pydub, torchcodec, av or cv2 invocation, so the consumer list is unchanged. Library consumers (pipewire, opencv, qtmultimedia, gst-libav) are still not audited per consumer.

Gate: `check-grype-ignore-expiry.sh --maintenance` output is pasted in the commit hand-off report; with `GRYPE_IGNORE_TODAY=2026-11-15` it also passes after the change (it failed on all 8 before).

## Rollback Plan
- `git revert <sha>`. Trigger: grype reporting a regression on the ffmpeg entries. Reverting restores expired tokens and the CI gate fails again.

## Residual Risk
- Closure scan on /run/current-system still reports 7 ffmpeg 8.1.3 findings that no ignore covers and that this slice did not touch: CVE-2026-96611 (HIGH, mov_read_ispe overflow; "before 9.0" range, n8.1.3 mov.c has the width/height > INT_MAX check, so likely another range false positive), CVE-2026-120210 (IMF ASSETMAP path traversal), 120243, 120244, 120245, 120246, 120247 (uninitialized-memory reads in G2M, PCX, Sun Raster, CDXL, Huffyuv decoders; "through 9.0.2"). They need triage as their own slice; whether CI blocks on them is not checked here.
- Per-consumer exposure of library users remains unaudited; renewal is bounded to 30 days (2026-12-14) so the next re-check is forced.

## Hint Feedback
- No aq-hints used; sources were upstream tags, NVD, upstream raw source and a live closure scan.

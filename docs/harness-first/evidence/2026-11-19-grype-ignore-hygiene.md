# Harness-First Task Evidence: .grype.yaml legacy ignore hygiene

Date: 2026-11-19
Task ID: SEC-GRYPE-HYGIENE-20261119-001

## Objective
Clear tier0 check-grype-ignore-expiry WARN (189 of 252 ignores had no expires=; W3 of security-warnings-inventory-20261119). No bulk date-stamping: each legacy entry was checked against a current-closure scan; stale entries removed, entries with an establishable basis kept with expires=2027-02-15 (<=90 days) and a WR-SEC id, the rest removed so the alert reappears honestly. Result: 252 -> 121 ignores, entries without expires= 189 -> 0. Counts computed with python3 yaml over `.grype.yaml` at merge base fac504ee2 and at HEAD: total = length of the top-level `ignore` list; without expires= = entries whose `reason` string lacks `expires=`.

## Workflow/Session IDs
- Workflow ID: n/a (owner-directed warning sweep, 2026-11-19)
- Session ID: Simurg@claude/sonnet under orchestrator Simurg@claude/opus-5.5#da0ef470

## Delegation Decision
Delegated bounded implementer slice (Rule 17, sonnet). Only LEGACY entries touched so the merge with fix/cve-triage-20261118 (new entries at the end of .grype.yaml; WR-SEC-4..9 in the register) stays clean. This PR must land AFTER the cve-triage PR; register ids here start at WR-SEC-10 and are appended at the end of the register to avoid its hunk.

## Commands Executed
~~~bash
nix path-info -r /run/current-system            # 2790 store paths; every ignored package name is present
grype sbom:c.cdx.json -c empty.yaml -o json     # 2026-11-14 sbomnix CDX, offline DB; 347 unignored matches
nix-store -q --referrers <path>                  # containment checks
bash scripts/governance/tier0.d/check-grype-ignore-expiry.sh
python3 scripts/testing/test-ffmpeg-cve-mitigations.py
scripts/governance/tier0-validation-gate.sh --pre-commit
~~~

## Validation Evidence
- Method: an entry is live iff its (CVE id, package) appears in unignored grype matches on the closure SBOM. 157 of 188 legacy entries live, 31 stale.
- Kept (57): WR-SEC-10 contained sandbox 28 (referrers show libpng-1.2.59 only in appimage-run-fhsenv-rootfs; libxml2-2.13.9 and libjxl-0.8.2 only in playwright-webkit; all matches on those versions); WR-SEC-11 DB lists no fixed version 14; WR-SEC-12 CPE collision / unbounded CPE false positives 15 (including 8 GnuTLS 3.8.13 rules).
- Removed (131): 31 stale (ffmpeg 16, libtiff 4, libmicrohttpd 2, sqlite 2, graphite2, samba, libpng, pgvector, gdk-pixbuf, libssh, p11-kit 1 each); 100 with unestablished basis (generic "transitive/secondary linkage ... pipewire fast-lane", "development toolchain", "internal component", and "fixed upstream/installed newer" claims the DB does not confirm). These alerts reappear in code scanning on the next scan; that is intended.
- check-grype-ignore-expiry: before "WARN: 188 legacy ignore(s) without expires=", after "PASS (--maintenance, 65 ignores, 0 blocking)", no legacy WARN.
- New regression test test_repo_grype_ignores_have_no_legacy_entries in scripts/testing/test-ffmpeg-cve-mitigations.py (7 tests pass).
- Review follow-up (Codex REQUEST_CHANGES on 50cb72e9e): the 28 WR-SEC-10 sandbox ignores now pin the bundled package version (libpng 1.2.59, libxml2 2.13.9, libjxl 0.8.2) so the same CVE on any other version is no longer suppressed; CVE-2026-3497 (openssh, no upstream fix) carries fix-state: not-fixed so it stops suppressing once Grype reports a fix. Regression test now injects GRYPE_IGNORE_TODAY=2026-11-19 and an explicit GRYPE_IGNORE_FILE (the sibling test_repo_grype_valid_today got the same file pinning), plus test_sandbox_ignores_are_version_scoped; 8 tests pass, also with GRYPE_IGNORE_FILE=/nonexistent in the environment.
- Review follow-up (Codex findings on 8afcf7c86): (1) Scoped all 8 GnuTLS ignores to `package.version: "3.8.13"` and moved them from `[WR-SEC-11]` to `[WR-SEC-12]`. Upstream fixed CVE-2025-32989 and CVE-2025-32990 in 3.8.10, CVE-2026-1584 in 3.8.12, and CVE-2026-3832, CVE-2026-3833, CVE-2026-33845, CVE-2026-42009, CVE-2026-42010 in 3.8.13; the closure ships only `gnutls 3.8.13` (`nix path-info` + `nix eval`), and Grype's `vulnerability.db` (`nvd:cpe`) still matches `3.8.13` solely via unbounded `gnu:gnutls` `version: {}` ranges. Verified with `grype` that `.grype.yaml` suppresses the 8 false positives on `3.8.13` while leaving `3.8.12` unmasked. (2) Upgraded `test_sandbox_ignores_are_version_scoped` in `scripts/testing/test-ffmpeg-cve-mitigations.py` to parse `.grype.yaml` via `yaml.safe_load`, assert non-empty string `package.version` on `[WR-SEC-10]` and `gnutls` ignores, and added negative unit checks rejecting `# version:`, `version: ""`, whitespace, missing, and non-string values.
- Limits: the SBOM is from 2026-11-14 (nixpkgs 20261108); no fresh sbomnix available offline, so a 2026-11-15 refresh may make some "stale" entries live again (ffmpeg 9.0.2 now in the closure); the DB was not updated. The 31 stale removals are therefore the lowest-confidence group; if they re-alert, they are triaged normally.

### Removed entries
### basis not established: 100 entries
- ada (1): CVE-2024-9410
- alsa-lib (4): CVE-2026-56109, CVE-2026-90781, CVE-2026-96674, CVE-2026-96675
- avahi (1): CVE-2025-59529
- binutils (10): CVE-2025-69649, CVE-2025-69650, CVE-2025-69651, CVE-2025-69652, CVE-2026-3441, CVE-2026-3442, CVE-2026-4647, CVE-2026-6844, CVE-2026-6845, CVE-2026-6846
- bluez (1): CVE-2020-24490
- busybox (2): CVE-2024-58251, CVE-2025-46394
- capstone (7): CVE-2025-67873, CVE-2025-68114, CVE-2026-47143, CVE-2026-49263, CVE-2026-49282, CVE-2026-55893, CVE-2026-55894
- cpio (2): CVE-2010-4226, CVE-2023-7216
- dnsmasq (1): CVE-2026-6507
- ffmpeg (5): CVE-2026-70628, CVE-2026-70629, CVE-2026-70630, CVE-2026-70631, CVE-2026-70632
- giflib (1): CVE-2024-45993
- gst-plugins-good (2): CVE-2026-46469, CVE-2026-46470
- gstreamer (20): CVE-2026-12891, CVE-2026-12892, CVE-2026-18295, CVE-2026-18296, CVE-2026-18297, CVE-2026-18298, CVE-2026-18299, CVE-2026-1940, CVE-2026-2920, CVE-2026-2921, CVE-2026-2922, CVE-2026-2923, CVE-2026-3081, CVE-2026-3082, CVE-2026-3083, CVE-2026-3084, CVE-2026-3085, CVE-2026-3086, CVE-2026-73433, CVE-2026-73434
- lapack (1): CVE-2021-4048
- libcaca (2): CVE-2021-30499, CVE-2022-0856
- libcap (1): CVE-2026-4878
- libcupsfilters (1): CVE-2024-47076
- libjxl (1): CVE-2026-82522
- libmodplug (1): CVE-2026-75904
- libmpeg2 (1): CVE-2022-37416
- libppd (1): CVE-2024-47175
- libusb (2): CVE-2026-23679, CVE-2026-47104
- libxml2 (2): CVE-2025-6021, CVE-2025-6170
- libxslt (2): CVE-2025-7425, CVE-2025-10911
- lua (2): CVE-2020-15945, CVE-2021-43519
- mupdf (1): CVE-2026-7233
- nghttp2 (1): CVE-2026-58055
- openssh (6): CVE-2007-2768, CVE-2014-9278, CVE-2023-51767, CVE-2026-55653, CVE-2026-55654, CVE-2026-55655
- perl (4): CVE-2026-13221, CVE-2026-15534, CVE-2026-57432, CVE-2026-8376
- pulseaudio (1): CVE-2024-11586
- qemu (8): CVE-2018-18438, CVE-2019-12067, CVE-2021-20255, CVE-2023-1386, CVE-2023-2680, CVE-2024-6505, CVE-2024-6519, CVE-2024-8354
- redis (2): CVE-2022-3734, CVE-2025-49112
- spice (3): CVE-2016-0749, CVE-2016-2150, CVE-2018-10893
### stale (no current match): 31 entries
- ffmpeg (16): CVE-2026-64830, CVE-2026-64831, CVE-2026-64832, CVE-2026-64833, CVE-2026-64834, CVE-2026-64835, CVE-2026-65703, CVE-2026-65704, CVE-2026-65705, CVE-2026-65706, CVE-2026-66036, CVE-2026-66037, CVE-2026-66038, CVE-2026-66039, CVE-2026-66040, CVE-2026-66041
- gdk-pixbuf (1): CVE-2026-5201
- graphite2 (1): CVE-2017-5436
- libmicrohttpd (2): CVE-2025-62689, CVE-2025-59777
- libpng (1): CVE-2026-4757
- libssh (1): CVE-2026-59851
- libtiff (4): CVE-2023-52356, CVE-2023-6228, CVE-2023-6277, CVE-2026-4775
- p11-kit (1): CVE-2026-2100
- pgvector (1): CVE-2026-18022
- samba (1): CVE-2026-2340
- sqlite (2): CVE-2026-11822, CVE-2026-11824

## Rollback Plan
`git revert <commit-sha>` restores the previous ignore list (the check will WARN again).

## Residual Risk
Medium-low: ~130 previously suppressed alerts will reappear in code scanning and need triage (S3/S4 of the inventory). Location scoping (package.location) was not added: the SBOM store-path locations could not be re-verified offline, and an unverifiable glob would silently stop suppressing; version scoping is verified. The other WR-SEC-11 entries still match by CVE+package only. Kept entries expire 2027-02-15; tier0 fails in maintenance mode after that.

## Hint Feedback
- No aq-hints used; policy template followed (all 8 sections present).

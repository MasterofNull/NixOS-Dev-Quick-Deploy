# PRD — mobile-web Domain Activation

**Domain tag:** `mobile-web`
**Status:** Implemented — Phase 58A capability expansion
**Authors:** Claude (orchestrator/architect) · Gemini (research synthesizer)
**Date:** 2026-05-18
**Upstream template:** `docs/architecture/domain-activation-template.md`
**Gemini research:** `.agents/delegation/outputs/gemini-20260518-121439-w2gzy1.log` (Domain A)

---

## Problem Statement

The harness has web backend and dashboard capability but lacks:
- Mobile app toolchains (Flutter, Android tools)
- Frontend accessibility and security audit flows (Lighthouse, WCAG 2.2, MASVS)
- Responsive / mobile-web testing automation (Playwright mobile mode)
- AIDB knowledge for mobile security verification (OWASP MASVS, WCAG remediation patterns)

Without a formal domain, mobile-web work falls through to ad-hoc tool discovery with no shared knowledge base, no routing preference, and no dual-use safety boundary (mobile analysis tools can be used for unauthorized app cloning).

---

## Goal

Establish `mobile-web` as a first-class capability domain. Initial activation covers:

1. Registering the domain (proposed state)
2. Declaring routing preference and AIDB namespace
3. Authoring the agent instruction surface
4. Wiring a baseline validation hook

Implementation note (2026-05-19): `nix develop .#mobile-web` is implemented with Flutter, Android tools, Node.js 22, Chromium, and Playwright driver. Lighthouse is no longer packaged through `nodePackages` on nixpkgs 25.11; the shell emits an on-demand npm hint instead. The domain reached `promoted` with seeded `mobile-web-patterns`, MASVS static scan evidence, fixture Lighthouse report plumbing, and Gemini review-gate PASS. Real Lighthouse CLI evidence remains a hardening item before any future default-routing decision.

**First follow-on slice (per Gemini research):** Mobile Accessibility & Security Audit (MASA) harness — Lighthouse + MASVS static check → unified dashboard report.

---

## Kernel Objects Touched

| Kernel object | How this domain touches it |
|---|---|
| `intent` | Adds `mobile-web` intent class → routes to `remote-reasoning` for UI/UX reasoning; `local-tool-calling` for build/ADB ops |
| `memory-evidence` | MASVS findings, WCAG remediation patterns, Flutter/NixOS troubleshooting → AIDB namespace `mobile-web-patterns` |
| `route-profile` | `remote-reasoning` for UI/accessibility reasoning; `local-tool-calling` for build/test ops; `default` for boilerplate generation |

---

## Routing Profile(s)

| Use case | Profile | Notes (Gemini research) |
|---|---|---|
| UI/UX & accessibility reasoning | `remote-reasoning` | Requires high-order visual-to-logic mapping |
| ADB / build tool invocation | `local-tool-calling` | Procedural; high-latency local ops |
| Boilerplate / component generation | `default` | Qwen handles standard React/Flutter widgets |

---

## AIDB Namespace

**Namespace:** `mobile-web-patterns`

Seed content per Gemini research:
- `mobile_security_masvs` — OWASP MASVS controls (MASVS-STOR, MASVS-AUTH, MASVS-NETWORK, MASVS-CODE)
- `wcag_remediation_patterns` — WCAG 2.2 failure-to-code-fix mappings
- `flutter_nixos_troubleshooting` — Known fixes for Flutter rendering issues on NixOS (libGL paths, FHS assumptions)
- `mobile_responsive_breakpoints` — CSS/Flutter media query strategies for modern device matrices
- `react_native_nix_bridge` — Nix-specific env vars required for React Native builds

---

## Tool Preferences

### Recommended Nix packages (from Gemini research)

| Package | nixpkgs attribute | Purpose |
|---|---|---|
| Flutter | `pkgs.flutter` | Cross-platform mobile/web/desktop |
| Android CLI | `pkgs.android-tools` | adb, fastboot (without full SDK overhead) |
| Node.js | `pkgs.nodejs_22` | Frontend workflow foundation |
| Lighthouse | on-demand `npm install -g lighthouse` hint | Web performance, accessibility, SEO audit |
| Playwright | `pkgs.playwright-driver` | Browser automation; mobile-responsive testing |

### Tool order

1. `nix develop .#mobile-web` — domain dev shell (provision in mobile-web.1)
2. `scripts/testing/mobile-web-masa-harness.py` — deterministic MASA harness; real Lighthouse only when the CLI and a URL are provided
3. `lighthouse <url> --output json` — accessibility + performance audit when explicitly installed/provided
4. `playwright test` — browser automation + responsive testing
5. `flutter doctor` — toolchain health
6. `adb devices` — Android device/emulator check
7. `scripts/governance/tier0-validation-gate.sh --pre-commit` — always before commit

### Forbidden

- iOS native builds on this platform (no macOS/Xcode — iOS = hard boundary)
- Reverse engineering tools (jadx, apktool) without explicit user authorization and documented legal context
- Biometric bypass research without explicit user authorization
- LLM-generated app code committed without `bash -n` / linter pass

---

## Security and Safety Considerations

Per Gemini research — key dual-use concerns:

1. **Reverse engineering** (jadx, apktool): Dual-use for malware analysis vs unauthorized app cloning/credential extraction. Require explicit user authorization and legal context documentation before invoking.
2. **Biometric bypass research**: High security risk — treat as approval-gated; no autonomous agent use.
3. **Privacy exfiltration**: Location spoofing / sensor manipulation automation — forbidden without explicit authorization.

OWASP MASVS compliance is a positive goal; generating bypasses is forbidden.

---

## Acceptance Criteria

Per Gemini research:
1. `config/capability-lifecycle-registry.json` contains `mobile-web` at state ≥ `proposed`.
2. `.agent/MOBILE-WEB-INSTRUCTIONS.md` exists with domain tag, task classes, tool order.
3. `mobile-web-health` validation check exits 0.
4. At `implemented`: Flutter/ADB/Node/Chromium/Playwright are available in the domain shell.
5. Before `validated`: Lighthouse-shaped JSON report generation works, MASVS-aligned static scan on sample source succeeds, `mobile-web-patterns` is seeded, Gemini review-gate PASS is recorded on one mobile audit output, and there are no P0/P1 regressions.
6. Before any future `default` transition: real Lighthouse CLI evidence is required, or a separate default-routing decision must explicitly scope fixture mode to validation-only plumbing.

---

## Rollback Procedure

1. Set `mobile-web` registry state to `blocked`.
2. Remove `mobile-web` intent class from `config/intent-routing-map.json` if added.
3. Disable `mobile-web-health` check (`"enabled": false`).
4. Archive `mobile-web-patterns` AIDB namespace content.
5. Remove `.#mobile-web` dev shell from `flake.nix` if added.

---

## Open Items

| Item | Slice |
|---|---|
| Provision Flutter, android-tools, nodejs_22, lighthouse, playwright in `nix develop .#mobile-web` | mobile-web.1 |
| Wire `mobile-web` intent class in `config/intent-routing-map.json` | mobile-web.2 |
| Seed `mobile-web-patterns` AIDB namespace (MASVS + WCAG) | mobile-web.3 |
| MASA harness: Lighthouse + MASVS check → dashboard report | mobile-web.4 (→ validated) |

---

## Related Docs

- `docs/architecture/domain-activation-template.md`
- `docs/architecture/gemini-review-gate.md`
- `docs/architecture/routing-profile-inventory.md`
- `.agents/delegation/outputs/gemini-20260518-121439-w2gzy1.log` (Gemini research — Domain A)

# Mobile-Web Domain — Agent Instruction Payload

**Domain tag:** `mobile-web`
**State:** promoted (2026-05-18); opt-in, not default
**Upstream authority:** `.agent/PROJECT-MOBILE-WEB-PRD.md`, `docs/architecture/capability-lifecycle.md`
**Registry ID:** `mobile-web` in `config/capability-lifecycle-registry.json`

---

## Domain Scope

Applies when performing: web/mobile frontend development, accessibility audits (WCAG 2.2), mobile security analysis (OWASP MASVS), Flutter/Android toolchain work, browser automation (Playwright), Lighthouse audits, or mobile-web knowledge retrieval from AIDB (`mobile-web-patterns` namespace).

---

## Eligible Task Classes

| Task class | Eligible agents | Notes |
|---|---|---|
| Boilerplate / component generation (≤400 lines) | Qwen (Tier A) | Standard React/Flutter widgets |
| Lighthouse audit invocation | Qwen (Tier B) | Review-gated output |
| WCAG remediation lookup from AIDB | Qwen (Tier A) | Pure retrieval |
| MASVS static analysis on sample source | Claude/Gemini | Gemini review gate required |
| UI/UX accessibility reasoning | Claude/Gemini | `remote-reasoning`; Gemini review gate |
| Reverse engineering (jadx, apktool) | Human-gated | Requires explicit user authorization + legal context |
| Biometric bypass research | Forbidden (autonomous) | High risk; human-gated only |

---

## Tool Preferences

1. `nix develop .#mobile-web` — domain dev shell with Flutter, Android tools, Node.js 22, Chromium, and Playwright driver
2. `scripts/testing/mobile-web-masa-harness.py` — MASA validation harness; uses real Lighthouse only when `lighthouse` and `--url` are available, otherwise fixture mode
3. `lighthouse <url> --output json` — primary accessibility + performance audit when the CLI is explicitly installed/provided
4. `playwright test` — browser automation + responsive testing
5. `flutter doctor` — toolchain health
6. `adb devices` — Android device/emulator
7. `scripts/governance/tier0-validation-gate.sh --pre-commit` — mandatory before commit

**Forbidden:** iOS native builds (no macOS/Xcode on this platform); reverse engineering tools without user authorization; `pip install` for toolchains.

---

## AIDB Namespace Binding

**Namespace:** `mobile-web-patterns`

- Read: `POST /query` with namespace filter `mobile-web-patterns` before MASVS or WCAG work.
- Write: `POST /api/memory/facts` with `{"namespace": "mobile-web-patterns", "domain": "mobile-web"}`.

---

## Review Requirements

| Work category | Gate required |
|---|---|
| MASVS security analysis output | Gemini review gate |
| UI/UX accessibility architecture | Gemini review gate |
| Domain dev shell (flake.nix changes) | Gemini review gate |
| Lighthouse audit (read-only) | No gate required |
| Boilerplate component generation | No gate required |

---

## Routing Preference

| Query type | Profile |
|---|---|
| UI/UX & accessibility reasoning | `remote-reasoning` |
| Build / ADB / test invocation | `local-tool-calling` |
| Boilerplate / component generation | `default` |

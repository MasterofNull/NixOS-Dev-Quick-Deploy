# PRD - Mobile Web Domain Activation

**Domain tag:** `mobile-web`
**Status:** Active foundation, reverse-engineering and invasive testing approval-gated
**Last updated:** 2026-06-28

## Objective

Provide agents with a safe mobile/web workflow for frontend implementation, accessibility review, Playwright verification, Lighthouse-style audits, and mobile security analysis.

## Current Scope

- Web/mobile frontend development and responsive design review.
- WCAG 2.2 accessibility guidance.
- OWASP MASVS-oriented static analysis for mobile security.
- Browser automation through bounded Playwright surfaces.
- Retrieval namespace: `mobile-web-patterns`.

## Safety Boundary

- Reverse engineering, device instrumentation, credentialed testing, and store/account actions require explicit approval.
- Prefer local fixtures, public documentation, and non-invasive UI/accessibility checks by default.

## Acceptance Criteria

- `mobile-web` exists in `config/capability-lifecycle-registry.json`.
- `.agent/MOBILE-WEB-INSTRUCTIONS.md` is present.
- Playwright/browser automation remains pinned and bounded through the capability intake registry.

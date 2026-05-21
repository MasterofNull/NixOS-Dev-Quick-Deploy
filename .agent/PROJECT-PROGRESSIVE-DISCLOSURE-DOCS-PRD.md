# PROJECT PRD — Progressive Disclosure System Documentation Overhaul

## 1. Problem Statement
The progressive disclosure system documentation is fragmented and outdated. Current guides reference incorrect ports (8091/8092 instead of 8002/8003), older versions of the system (v2.1.0 instead of Phase 58+), and do not fully reflect the current toolset (`aq-prime`, `aq-hints`, `aq-context-card`, `aq-qa --layer`). This causes confusion for both human operators and AI agents attempting to use the system's discovery features.

## 2. Goals
- **Consolidate**: Establish a single canonical guide for the progressive disclosure system.
- **Update**: Align all documentation with the current Phase 58 state (2026-05-20).
- **Retire**: Remove or archive legacy documentation to prevent misinformation.
- **Integrate**: Ensure the main `README.md` and `GEMINI.md` point to the new canonical docs.
- **Reflect System Reality**: Document the 7-domain configuration found in `config/progressive-disclosure-domains.json`.

## 3. Scope

### In Scope
1.  **Rewrite** `docs/agent-guides/45-PROGRESSIVE-DISCLOSURE.md` as the primary canonical guide.
2.  **Update** `README.md` documentation section and AI Stack Services section.
3.  **Update** `docs/AI-AGENT-PROGRESSIVE-DISCLOSURE-README.md` (keep as redirect but ensure targets are correct).
4.  **Retire/Archive**:
    - `docs/PROGRESSIVE-DISCLOSURE-GUIDE.md` → `docs/archive/legacy-sequence/`
    - `docs/operations/agent-context-progressive-disclosure.md` → `docs/archive/legacy-sequence/`
5.  **Validation**: Ensure all internal links are correct and tool descriptions match `scripts/ai/` implementations.

### Out of Scope
- Modifying the actual progressive disclosure code (Python/JSON).
- Changing the behavior of `aq-*` CLI tools.
- Creating new design patterns (only documenting existing ones).

## 4. Target Documentation Structure
- **Canonical Guide**: `docs/agent-guides/45-PROGRESSIVE-DISCLOSURE.md`
  - Overview & Philosophy (Token efficiency)
  - Domains (7 domains from `config/progressive-disclosure-domains.json`)
  - Levels (`minimal`, `standard`, `full`)
  - Tooling (`aq-prime`, `aq-hints`, `aq-context-bootstrap`, `aq-context-card`)
  - Integration (`aq-qa --layer`, dashboard visibility)
  - API Reference (8002/8003 endpoints)

## 5. Success Criteria
- [ ] `docs/agent-guides/45-PROGRESSIVE-DISCLOSURE.md` is fully updated and accurate.
- [ ] Obsolete files are moved to archive.
- [ ] `README.md` points to the correct documentation.
- [ ] Port references are corrected (8002/8003).
- [ ] All 7 domains from the config are documented.
- [ ] `aq-qa --layer` usage is included.

## 6. Execution Plan
1.  **Phase 1: Preparation** - Move obsolete files to archive.
2.  **Phase 2: Canonical Guide Rewrite** - Update `docs/agent-guides/45-PROGRESSIVE-DISCLOSURE.md`.
3.  **Phase 3: Integration** - Update `README.md` and `docs/AI-AGENT-PROGRESSIVE-DISCLOSURE-README.md`.
4.  **Phase 4: Validation** - Verify links and facts.

---
name: minimal-code
description: Minimal-code decision ladder — stop over-engineering before writing code. Apply before any implementation (adapted from ponytail's ladder; instruction-only, no third-party code). Pairs with /simplify (post-hoc).
triggers: [before writing implementation, "build X", "add a feature", library/dependency decisions, "over-coded", scaffolding, new file]
---

# minimal-code — the decision ladder

Adapted from ponytail (github.com/dietrichgebert/ponytail) as an INSTRUCTION-ONLY ruleset — no
third-party runtime code (the Node.js plugin, if ever wanted, goes through `capability-intake`).
Rationale: AI agents over-engineer — install libraries where a native feature exists, write wrappers,
add boilerplate. This is the pre-code discipline; `/simplify` is the post-hoc pass.

## Be lazy about the SOLUTION, never about READING
First fully understand the problem + read the surrounding code. The laziness is only about *how much
new code* you write — never about diligence. NEVER skip: security, validation, accessibility,
fail-closed behaviour, tests. Minimal-code ≠ cutting corners on correctness or the harness's HARD rules.

## The ladder — stop at the FIRST rung that answers the need
1. **YAGNI — does this need to exist at all?** Is the feature/abstraction/config actually required now,
   or speculative? Delete-by-default. The best code is none.
2. **Already in THIS codebase?** Search first (`agrep`/`ctx_search`). Reuse the existing helper, service,
   pattern, or artifact. This harness is large — the thing you're about to write likely exists
   (e.g. the confined-service pattern, the Ed25519 verify, the DurableSingleUseLedger, the tracker engine).
3. **Standard library?** Python stdlib / POSIX / systemd / Nix built-ins before any dependency.
4. **Native platform feature?** NixOS module option, a systemd unit directive, an HTML/SQL/shell native
   before a library or custom component.
5. **An already-installed dependency?** Use what's in the flake before adding a new one (adding a dep is
   a supply-chain + intake cost — flake-review).
6. **Can it be one line / a config value?** Prefer a one-liner or an option over a new module/class.
7. **Otherwise: minimum viable implementation** — the smallest correct thing, no speculative flags,
   layers, or "future-proofing." Add structure only when a second real caller appears.

## Apply it
- BEFORE writing a new file/module/dependency, walk the ladder out loud in one or two lines: "rung N,
  because …". If you're at rung 7, say why 1–6 didn't answer it.
- In DISPATCH prompts to implementer lanes, include the ladder constraint (smallest correct change;
  reuse the named existing pattern; no new deps without justification).
- In REVIEW, flag over-build: a new dependency where a native feature exists, a wrapper around a one-liner,
  a class where a function suffices, speculative config/flags with no caller, duplicated logic that a
  shared helper already covers. This is a `/simplify`-class finding.
- HARNESS FIT: this reinforces Rule 1 (one slice, one concern; no unsolicited features), "research before
  build", and cheapest-eligible implementer (Rule 17). It never overrides a HARD rule or a security gate.

## What it does NOT mean
Not "write less test code," not "skip the confined-service hardening," not "inline a secret to avoid a
config," not "collapse a security boundary." Correctness, fail-closed, and the Activation-Gate stay full.

# Independent Review — factory/model-ids-claude5-refresh

**Subject:** `factory/model-ids-claude5-refresh` — commits `4a979951` (Anthropic) + `240f26ee` (Google+OpenAI)
**Baseline:** main `f1f409ef`
**Reviewer:** independent (Claude Sonnet 5), no prior involvement in authoring this branch

## Disposition: **APPROVE**

## Digest reproduction
```
command git diff f1f409ef..factory/model-ids-claude5-refresh | sha256sum
478cffa2dc48ab9f6f31ad4fb67dde457adbb6be9e0d363f6ecf9b1886fe8768
```
Matches the specified digest exactly. No subject-drift.

## Findings

### 1. Diff hygiene — PASS
- `4a979951 --stat`: touches exactly 7 files — `.agent/FABLE-PARITY-CONTRACT.md`, `config/model-coordinator.json`, `config/multi-agent-collaboration.yaml`, `config/workflow-automation.yaml`, `scripts/ai/aq-role-route`, `scripts/testing/test-claude-dispatch-payload-safety.py`, `scripts/testing/test-delegate-claude-model-routing.py`. Matches spec's "6 intended files" description (author's commit lists model-coordinator.json + 4 consumers + 2 tests = the same 7-file set the task calls "6 files + config" — confirmed as exactly these paths, no extras).
- `240f26ee --stat`: touches only `config/model-coordinator.json` (37 lines, 20+/17-). Confirmed no other file touched.
- Owner/provenance check: `command git diff f1f409ef..factory/model-ids-claude5-refresh -- config/model-coordinator.json | grep -iE '^[+-].*owner'` → **empty**. `_meta.owner` field (`"claude-sonnet-4-6"`) was left untouched in both commits, consistent with the commit messages' stated intent ("authorship field, not routing config"). Minor observation (not a blocker): this owner stamp now names a superseded model id that no longer exists as a live tier value anywhere else in the file — cosmetically stale, but explicitly out of scope per the author's own stated design and the task's verification instruction, so not flagged as a defect.

### 2. JSON validity — PASS
`config/model-coordinator.json` at branch tip parses cleanly (`json.load` succeeds), `_meta.version` = `"1.3"` as expected (1.1→1.2 in commit 1, 1.2→1.3 in commit 2).

### 3. Model IDs — none fabricated; Google + OpenAI IDs verified live
- **Anthropic** (`claude-fable-5-1`, `claude-opus-5-5`, `claude-sonnet-5`, `claude-haiku-4-5-20251001` unchanged): treated as runtime-authoritative per task instructions — not independently re-verified.
- **Google**: fetched `https://ai.google.dev/gemini-api/docs/models` live. Confirmed present verbatim: `gemini-3.8-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-pro-preview`, `gemini-3.5-flash`. Page describes `gemini-3.8-flash` as "engineered for long-horizon software engineering, autonomous agents, and complex enterprise workflows" — consistent with the commit's flagship/balanced framing.
- **OpenAI**: fetched `https://developers.openai.com/api/docs/models` live. Confirmed present verbatim: `gpt-6-astra` ("our most capable model, built for the hardest end-to-end work"), `gpt-6-sol` ("built to power complex coding and agentic workflows"), `gpt-6-luna` ("our most efficient model for focused, high-volume tasks"), `gpt-5.6-cyber` (cybersecurity/vuln-research model). All four match the tier assignments and the `_comment` annotation in the diff exactly (astra=flagship, sol=balanced, luna=fast, cyber=noted-but-unwired).
- **No fabricated IDs found.** Every non-Anthropic ID in the diff was independently located on the live provider docs page with a matching description.

### 4. Tier semantics — PASS, no structural breakage
- `tier_routing` (untouched by this branch, verified for compatibility): `trivial|simple→fast`, `medium→balanced`, `complex|critical→flagship`, `creative→creative`.
- Every referenced tier key in `tiers.anthropic`, `tiers.google`, `tiers.openai` resolves to a concrete, non-null model id post-change.
- `gemini_3_8_flash_efforts` sub-block (renamed from `gemini_3_5_flash_efforts`) — all three effort levels (`low`/`medium`/`high`) correctly repoint `model` to `gemini-3.8-flash`, `best_use` prose internally updated to reference `gemini-3.5-flash-lite` / `gemini-3.1-pro-preview` consistently (no stale cross-references left pointing at old ids).
- `baseline_fallback` (google) repointed from the 2.5-line to `gemini-3.5-flash` (flagship/balanced) / `gemini-3.5-flash-lite` (fast) — consistent with the commit's stated rationale (2.x line is limited-access).
- Version bump only — no keys added/removed beyond the OpenAI tier expansion (additive) and the efforts-block rename (both intentional, both internally consistent).

### 5. Consumers — PASS, all match new flagship
- `.agent/FABLE-PARITY-CONTRACT.md:54-55` — SSOT-resolution sentence now names `claude-fable-5-1` (flagship/creative), `claude-opus-5-5` (deep fallback), `claude-sonnet-5` (balanced). Matches `config/model-coordinator.json`.
- `config/multi-agent-collaboration.yaml:341` and `config/workflow-automation.yaml:12` — both `llm_model` refs updated `claude-fable-5` → `claude-fable-5-1`.
- `scripts/ai/aq-role-route:85` — allowlist additively gained `claude-fable-5-1, claude-opus-5-5, claude-sonnet-5`; prior ids kept for back-compat, as claimed.
- `scripts/testing/test-claude-dispatch-payload-safety.py:93,96` and `scripts/testing/test-delegate-claude-model-routing.py:82,85` — both assert `--model`/`resolved_model` == `claude-fable-5-1` for the flagship tier. Assertions match the new SSOT value; not executed by this reviewer (author reported 6 passed, spot-check confirms the assertions are the right ones to pass).

### 6. Judgment calls — sound, no flags
- **(a) Google flagship = GA `gemini-3.8-flash` rather than preview `gemini-3.1-pro-preview`:** correct production-safety call. Routing default agentic/coding traffic through a GA model rather than a preview-tier model avoids preview SLA/availability risk; the preview is retained as an explicit opt-in `deep` tier for when the extra reasoning depth is worth the preview risk. This is the right default.
- **(b) OpenAI expanded from 1 tier (flagship only) to 3 (flagship/balanced/fast):** reasonable — brings OpenAI's tier structure to parity with Anthropic/Google, giving the coordinator's `tier_routing` (medium→balanced, trivial/simple→fast) somewhere to land for OpenAI lane requests that previously had no non-flagship OpenAI option. `gpt-5.6-cyber` correctly left unwired (specialized, not a general routing candidate) and clearly noted as such.

## Fabrication statement
No model ID in this branch appears fabricated. Anthropic IDs are accepted as runtime-authoritative per review scope. Google and OpenAI IDs were independently confirmed via live fetch against `ai.google.dev/gemini-api/docs/models` and `developers.openai.com/api/docs/models` respectively — every new ID referenced in the diff (`gemini-3.8-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-pro-preview`, `gpt-6-astra`, `gpt-6-sol`, `gpt-6-luna`, `gpt-5.6-cyber`) was found present with a description consistent with its assigned tier role.

VERDICT: APPROVE

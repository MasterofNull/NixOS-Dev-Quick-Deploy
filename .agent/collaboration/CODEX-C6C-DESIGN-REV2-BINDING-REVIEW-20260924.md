# C6c Design rev2 — Binding Re-Review (Focused)

**Subject:** `factory/c6c-design-v2` commit `44b1c6e0`, file
`.agents/plans/aqos-foundation-c/C6c-DESIGN-AND-AUTHORIZATION.md`
**Baseline:** `main` `f1f409ef`
**Role:** Independent binding reviewer (re-review of rev2; not the rev1 author)

## Disposition

**REQUEST_REVISION — one narrow textual fix required (Finding 3 closure is self-contradictory as written).**

## Diff digest (requested)

```
command git diff f1f409ef..factory/c6c-design-v2 | sha256sum
c86bbefc2521d240954636bbcc64ca8c1cacbd0d58beaf97f7bde28b8dd59a1a
```
Matches the requested digest exactly. No subject drift.

## Per-fix closure

**1. MEDIUM — no false-green on the kill-lever: CLOSED.**
§6 Dashboard API row 5 now gates `operational` on allowlist-readable + ≥1 active key + verb-present
**AND** a live `read-epoch` probe over the control socket (doc lines ~326–330), adds a fourth,
distinct `degraded(authority-unreachable)` state (~331–335), and binds a build-time freeze criterion
(§8 item 8, doc lines 451–457) plus a §6 row-8 probe assertion (lines 344–347, 398–400) requiring an
active-key-but-authority-down fixture to read `degraded`, never `operational`. Verified against code:
`scripts/ai/lib/revocation_epoch_transport.py:283-289` is the `read-epoch` branch (`request.get("op")
== "read-epoch"` → `re_lib.read_epoch(epoch_path)`), textually and functionally distinct from the
`bump` branch at `:290-296` (`bump_doc = request.get("bump")` → `apply_bump(...)`) — confirmed via
`command git show f1f409ef:scripts/ai/lib/revocation_epoch_transport.py`. The probe reuses this landed
op; no new authority op is added, consistent with the claim. The state logic as specified cannot
report `operational` while a submit would fail `DENY_CONNECT_FAILED`, because reachability is now a
conjunct, not inferred from key/verb presence.

**2. LOW — import-os fix doesn't silently re-bless host-key custody: PARTIAL (present but internally inconsistent).**
The deprecation-note pairing is present (§1 doc lines 124-133; §8 criterion 3, lines 435-440) and the
`_load_owner_key` age-passphrase guard is correctly kept as the documented control (lines 131-132,
440). However the closure text is **self-contradictory with the doc's own adjacent description**:
lines 124-129 state `bump` "is retained only for the offline/no-service fixture case its own docstring
already describes (`:21-27`)" — but `:21-27` is the module docstring describing **`submit`**'s
pre-C6-B2 in-process fallback (confirmed: `command git show f1f409ef:scripts/ai/aq-epoch-bump` lines
21-27), and this exact citation is already correctly attributed to `submit` two paragraphs earlier in
the same document (lines 107-109: "[submit --signed] remains valid for the offline/no-service fixture
case its docstring describes, `:21-27`"). `cmd_bump` is the opposite of an offline/no-service path: its
own docstring (`:169-173`) says it goes "to the running authority over its UDS," and its `--socket`
argparse arg (`:260-261`) defaults to the live control socket — confirmed via
`command git show f1f409ef:scripts/ai/aq-epoch-bump`. `bump` always requires a reachable authority; it
is not an offline fallback. rev2 appears to have copy-pasted the `:21-27` citation from the `submit`
paragraph and reassigned it to `bump` without updating the rationale, producing a claim the document
itself contradicts a few lines above. This does not undermine the substantive requirement (pair the
`import os` fix with a deprecation note steering owners to `submit --signed --socket`, keep
`_load_owner_key` as the control) but the stated rationale is wrong and would mislead whoever writes
the actual `--help`/docstring text at build time.

**3. LOW — check-id collision is a HARD freeze-time gate: CLOSED.**
§6 row 8 (doc lines 381-390) and §8 freeze criterion 10 (lines 460-464) both elevate the dual-harness
(`phase0.py` + `_aq-qa-bash`) check-id collision check to a HARD gate verified against siblings
**actually landed at freeze/land time**, explicitly superseding the static design-time "`0.10.54` is
unused" assumption (lines 379-380 vs. the removed rev1 line). Collision blocks the land; no silent
reassignment. Concrete and consistent with §8's renumbered criteria list.

## Regression check

No regression found. `command git diff --shortstat factory/c6c-design..factory/c6c-design-v2` = `1
file changed, 93 insertions(+), 24 deletions(-)`, matching the stated ~+93/-24 exactly, and the whole
change is confined to the one design file. Submission mechanism (§2, `submit --signed --socket` →
`send_request` → landed `{"bump": …}` handler, `transport:290-296`), idempotency-by-C6d (§3/§8
criterion 4, unchanged), rotation semantics (§4/§8 criterion 6, unchanged), ground-truth framing
(authority already exposes the op; only the client verb was missing, §7 table unchanged), and the
design/build-vs-P-F4 split (§8 activation note, lines 468-488, unchanged) are all intact.
`PREPARED_ONLY` status line (frontmatter, unchanged) and the §1 hash-anchor table are preserved.
Frontmatter `revision: 2` confirmed (line 5), with a new `rev2_review` field summarizing the three
fixes (line 7) and a closing rev2 summary paragraph added at the document's end (lines ~192-203 of the
v1→v2 diff) — consistent, no contradiction with the body.

## Finding

- **F1 (LOW, textual/coherence).** §1 rev2 paragraph (doc lines 124-133) mis-cites `aq-epoch-bump:21-27`
  as `bump`'s own docstring rationale for an "offline/no-service fixture case." That citation and
  framing belong to `submit` (correctly used two paragraphs earlier, lines 107-109) and contradict the
  document's own accurate description of `bump` (lines 110-114, 169-173, 260-261) as always requiring
  a live socket connection to the running authority. Fix: replace the citation/rationale in the rev2
  paragraph with something that matches `bump`'s actual nature (e.g., "retained for interactive
  one-shot manual operation against a live authority when only a host key is available, distinct from
  the pre-signed courier workflow `submit --signed --socket` uses") — a same-paragraph text edit, no
  design/mechanism change required.

VERDICT: REQUEST_REVISION — fix the self-contradictory `:21-27`/"offline/no-service" citation in the
Finding-3 closure paragraph (§1, doc lines 124-133) so it doesn't misattribute `submit`'s in-process
fallback rationale to `bump` (which always talks to a live authority). Fixes 1 and 3 are CLOSED and
concrete; fix 2 is PARTIAL solely due to this citation/rationale defect — the substantive deprecation
pairing itself is present and correct. No regression found elsewhere.

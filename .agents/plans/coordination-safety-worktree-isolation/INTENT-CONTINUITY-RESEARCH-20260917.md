# Intent continuity: bounded research input, not new runtime authority

Status: proposal for the existing coordination-safety queue. No upstream code
import, execution, model change or implementation acceptance.

## Source and evidence limits

Owner supplied [Towards Data Science article](https://towardsdatascience.com/coding-agents-dont-need-longer-history-they-need-intent-continuity/).
Direct access was unavailable/robots-blocked. Read the author's linked
[companion README](https://github.com/Emmimal/intent-continuity/blob/main/README.md)
and public extractor/verifier source instead; mirrors were discovery aids only.
The demonstration distinguishes finding related records from checking whether
they still apply. It uses eight synthetic tasks and a deterministic template,
not a production coding model; its reported results are not AQ-OS measurements.
It explicitly treats correctness separately from context compression.

## AQ-OS design proposals — our interpretation, pending independent input

Retain history and RAG. Build a small current-intent projection from existing
event/resume/authority records rather than another competing memory store.
Each active constraint needs a stable ID, source event/hash, authority, scope,
status and explicit authorized supersession. Distinguish requirements from
preferences, proposals, implementation state and activation permission.

Resume must resolve the current integrator and task before loading historical
handoffs. In this incident, an old CS-1F2 revision report must not override its
later exact-subject acceptance; both records remain available as evidence.
An absence of new instructions must not erase existing authorized work.

Newer text is not automatically stronger authority. A model suggestion cannot
replace an owner constraint; repository instructions cannot supersede higher
priority rules. Scope a proposed replacement before invalidating an applicable
record. Unresolved ambiguity routes only the affected action to clarification,
not the whole queue or another full review loop.

The author's [verifier](https://raw.githubusercontent.com/Emmimal/intent-continuity/main/verification.py)
computes candidate supersession before scope filtering and uses recency as a
remaining-key fallback. Its [extractor](https://raw.githubusercontent.com/Emmimal/intent-continuity/main/extractor.py)
uses narrow keyword rules. Do not import these as our authority resolver.
Authority validation, global revocation knowledge, scoped effects and reliable
negation handling need separate tests before execution is enabled.

## Bounded executable follow-up

Use CS-3's existing integration fence to reject a transaction from a stale owner,
baseline or reviewed subject. Resolve ownership from canonical events once;
enforce at edit/dispatch and integration seams where available, not only prose.
The current-intent projection should feed session/delegation payloads and expose
active objective, owner, blocker, next action and source freshness in the existing
dashboard. This is a proposed extension, not a claim those gates already exist.

Fixed regressions: stale handoff after accepted commit; unavailable reviewer;
same-scope authorized replacement; production versus disposable prototype;
out-of-scope replacement; proposal attempting to relax a safety constraint;
negated rule; suspend/resume and crash during validation; no repeated user prompt.
Measure constraint carryover, invalid/stale-rule applications, false blocks,
handoff-to-first-action delay and completed slices. Include held-out cases rather
than tuning the retrieval graph to the test answer key. No quality guarantee
follows from an eight-task upstream demonstration.

First finish current commits. Ask available independent lanes for bounded input
on this extension; absence is queued rather than blocking already authorized
CS-3 work. No additional plan/review stage is inserted before current delivery.

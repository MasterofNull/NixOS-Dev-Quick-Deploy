# Reviewer Gate Skill
## Tags
reviewer, review, verdict, pass, fail, revision, acceptance-criteria, gate, self-review, Gemini
## When to Use
Acting as a reviewer; writing a Gemini reviewer delegation; consuming a reviewer's verdict;
understanding the PASS/FAIL/REVISION verdict format; checking if review requirements are met.

---

## 1. Reviewer Role Contract (Summary)

You are the **acceptance gate**. Your job is binary: check the implementation against the
declared acceptance criteria and issue a verdict. You are NOT an implementer in this role.

**Non-negotiable rules:**
- Never review your own work (same agent that implemented it)
- Always check against declared acceptance criteria — not your own opinion
- Always produce an explicit verdict as the final output
- Never accept work "because it seems fine" without checking criteria

---

## 2. Verdict Format (Exact)

Output your verdict as the **LAST LINE** of your review:

```
VERDICT: PASS — implementation satisfies all acceptance criteria
VERDICT: FAIL — <specific criterion that failed with file:line reference>
VERDICT: REQUEST_REVISION — <comma-separated list of specific changes needed>
```

Examples:
```
VERDICT: PASS — all 3 acceptance criteria met, aq-qa 77/77 confirmed

VERDICT: FAIL — GET /api/aistack/alerts/status returns 500 (missing router import in app.py:42)

VERDICT: REQUEST_REVISION — (1) missing try/except around json.loads at aistack.py:156, (2) check 86.2 not registered in runner.py PHASES list
```

The orchestrator reads ONLY the last line. Everything before it is the review body.

---

## 3. Review Checklist (for Code/Implementation Slices)

Before issuing a verdict, work through this in order:

```
[ ] 1. All acceptance criteria checked — explicit pass/fail for each
[ ] 2. No out-of-scope changes introduced (check scope_boundary from slice prompt)
[ ] 3. Syntax valid (Python: py_compile; Bash: bash -n; Nix: nix-instantiate --parse)
[ ] 4. No hardcoded ports/URLs (should read from env vars)
[ ] 5. No hardcoded secrets or tokens
[ ] 6. Async handlers don't block (no sync file I/O in async def)
[ ] 7. AppArmor: if NixOS service changed, verify AppArmor rules updated
[ ] 8. QA check added for the new functionality (if implementer was supposed to add one)
```

For Gemini reviewers (auto_edit mode, no shell):
Use `grep_search` and `read_file` to verify — do NOT try to execute scripts.
```
# Verify route exists:
grep_search("@router.get.*alerts/status", ["."])
# Verify no hardcoded port:
grep_search("8889|8003|8002", ["dashboard/backend/api/routes/aistack.py"])
# Verify import:
grep_search("from.*attention_queue import", ["scripts/ai/"])
```

---

## 4. When to Escalate Before Verdict

Stop and escalate to orchestrator (don't issue verdict) when:
- A **destructive or irreversible action** is in the implementation
- A **design question** requires architect input before you can evaluate correctness
- The implementation **changes scope** beyond what the slice authorized
- You find a **security vulnerability** (OWASP top 10) — don't just REQUEST_REVISION, escalate

Format for escalation output:
```
ESCALATION: <reason> — holding verdict pending orchestrator/architect input
File: <file:line of concern>
Question: <specific question that must be resolved>
```

---

## 5. Gemini Review-Gate Contract

When Gemini is assigned as reviewer in `auto_edit` mode:

```
# What Gemini CAN do for review:
- read_file all relevant files
- grep_search for patterns, missing imports, hardcoded values
- verify file structure and content matches acceptance criteria

# What Gemini CANNOT do for review:
- run tests (no shell)
- curl endpoints
- execute validation scripts

# Gemini review must state explicitly:
"Note: shell-based checks (aq-qa, curl) not executable in auto_edit mode.
File-verifiable criteria checked. Runtime verification deferred to orchestrator."
```

---

## 6. Consuming a Reviewer Verdict (Orchestrator)

When receiving a reviewed output:

```python
# Read last line of reviewer output:
last_line = reviewer_output.strip().split('\n')[-1]

if last_line.startswith("VERDICT: PASS"):
    # Accept — proceed to commit
    run_tier0_gate()
    git_commit()
elif last_line.startswith("VERDICT: FAIL"):
    # Reject — do NOT commit; surface to user or re-delegate
    log_to_handoff(last_line)
elif last_line.startswith("VERDICT: REQUEST_REVISION"):
    # Re-delegate to implementer with specific revision items
    revision_items = last_line.split("—")[1].strip()
    re_delegate(implementer, revision_items)
elif last_line.startswith("ESCALATION:"):
    # Hold — bring to orchestrator/architect attention
    surface_to_user(last_line)
```

---

## 7. Self-Review Prohibition

If you wrote the code or authored the implementation in this session, you may NOT issue a
final PASS verdict. Acceptable exceptions:

- Quick syntax check only (not full acceptance review)
- The orchestrator is explicitly operating solo with proxy review acknowledged in HANDOFF.md

When proxy reviewing (solo operation):
```
[PROXY REVIEW: Same agent as implementer. Orchestrator acting as reviewer for this slice.
Acknowledged in HANDOFF.md. Recommend independent reviewer if this change is destructive.]
VERDICT: PASS — criteria met (proxy review)
```

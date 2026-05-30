# Escalation Protocol Skill
## Tags
escalation, stop, surface, blocking, ambiguity, out-of-scope, destructive, irreversible, PULSE
## When to Use
Deciding whether to continue vs escalate; hitting a blocking ambiguity; finding an out-of-scope
issue; discovering a destructive action mid-implementation; handling an unresolved question.

---

## 1. The Core Rule

**When blocked or out-of-scope: STOP and surface. Never guess and expand.**

The cost of a wrong guess in a multi-agent system is much higher than the cost of pausing.
Guessing expands scope silently, breaks other agents' assumptions, and creates untraceable bugs.

---

## 2. Escalation Decision Tree

```
1. Is the action DESTRUCTIVE or IRREVERSIBLE?
   (delete files, drop tables, force-push, rm -rf, overwrite uncommitted work)
   → YES: STOP. Do not proceed. Surface to orchestrator for explicit user confirmation.
   → NO: continue to 2.

2. Is the action OUTSIDE my assigned slice scope?
   (touching files not in relevant_files, adding new features not in acceptance criteria)
   → YES: STOP. Log to PULSE.log. Surface to orchestrator with specific finding.
   → NO: continue to 3.

3. Have I hit a BLOCKING AMBIGUITY?
   (acceptance criteria are contradictory, constraint is unclear, design question has no SSOT answer)
   → YES: STOP. Record specific question in PULSE.log. Surface to orchestrator/architect.
   → NO: continue to 4.

4. Is this a SECURITY FINDING?
   (hardcoded secret, command injection surface, OWASP top 10 issue in the code I'm touching)
   → YES: STOP. Log to issues-backlog.md. Surface to orchestrator immediately.
   → NO: continue to 5.

5. Am I being asked to REVIEW MY OWN WORK?
   → YES: Decline. Request a separate reviewer assignment.
   → NO: Proceed with the task.
```

---

## 3. How to Surface an Escalation

**To orchestrator** (most common):
```
ESCALATION: out-of-scope finding
File: dashboard/backend/api/routes/aistack.py:203
Finding: The slice requires modifying alerts endpoint but the bug root cause is in
         attention_queue.py which is outside the declared scope boundary.
Question: Should scope be expanded to include attention_queue.py, or implement a workaround
          within the current boundary?
Slice state: partial — alerts endpoint untouched, no files modified yet.
```

**To architect** (design question):
```
ESCALATION: design question — holding implementation
Context: The slice asks for a new coordinator route but the existing route table in
         http_server.py already has a conflicting path prefix at line ~1412.
Question: Should the new route use a different prefix or should the conflict be resolved
          first in a separate architecture slice?
```

**To user** (destructive action):
```
ESCALATION: destructive action requires explicit confirmation
Proposed action: git reset --hard HEAD~3 (would discard 3 commits including uncommitted changes)
Safer alternative: create a new branch and cherry-pick desired changes
Requesting explicit confirmation before proceeding.
```

---

## 4. PULSE.log Entry for Escalations

Always write to PULSE.log before stopping:

```
[ISO-timestamp] [agent] [escalation]: <scope> — <one-line reason>
[2026-05-30T14:33:00Z] [claude] [escalation]: slice-86.2/attention_queue — out-of-scope finding, holding for orchestrator
```

This ensures the state is recoverable even if the session ends before the orchestrator responds.

---

## 5. Time-Bound Rule

If an escalation is NOT acknowledged within the current session:
1. Record it in PULSE.log (done in step 4)
2. Stop the affected slice — leave files in a clean, partial state (no half-written functions)
3. Write a RESUME.json entry pointing to the escalation
4. Do NOT proceed past the unresolved blocker under any circumstances

**Clean partial state** means:
- No syntax errors in any modified file
- No broken imports
- No half-completed data migrations
- Existing tests still pass (QA regression-free)

---

## 6. Non-Escalation Situations (Handle Locally)

These do NOT require escalation:
- Test failure on new code → fix it within the slice
- Lint error in file you're editing → fix it within the slice
- Missing import in a file you're editing → add it (same file = same scope)
- Minor deviation from acceptance criteria that you can immediately fix → fix it
- Finding a comment or doc that's outdated → update it if it's in scope

The threshold: **does resolving this require touching files or concepts outside the declared scope?** If yes → escalate. If no → handle locally.

---

## 7. Escalation Anti-Patterns

```
# WRONG — silent scope expansion:
"I noticed the bug was actually in coordinator.py, so I fixed that too."

# WRONG — guessing through ambiguity:
"The spec wasn't clear but I assumed they meant X so I implemented X."

# WRONG — continuing after destructive discovery:
"I saw the file was going to be deleted but it seemed like it was old so I proceeded."

# RIGHT:
"Out-of-scope finding: root cause is in coordinator.py (outside slice boundary).
Stopping here. Orchestrator needs to expand scope or provide workaround guidance."
```

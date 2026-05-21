# 60 — Code Quality & Documentation Standards

> **Load:** On-demand — reference when writing, reviewing, or refactoring code.
> **Related:** `61-WORKFLOW-PRACTICES.md`, `62-MEMORY-SYSTEM.md`, `01-QUICK-START.md`
> **Source:** Distilled from `docs/AGENTS.md` §1-2 + §5-6.

---

## Core Principle: Intentional, Minimal, Organised

**The problem (AI slop):** verbose code, unnecessary abstractions, scattered docs.
**The fix:** match existing patterns, keep it simple, clean up inline.

---

## 1. Writing Code

### Rules
- Functions ≤ 50 lines; do one thing well
- Descriptive names — avoid docstrings on obvious functions
- Comments explain *why*, not *what*
- Search codebase before writing new utilities

```bash
grep -r "def <name>" .                       # find similar functions
grep -r "@app.route\|@router\|@endpoint" .   # find API patterns
grep -r "class.*Model\|CREATE TABLE" .       # check DB schema first
```

### Security
- Validate inputs at system boundaries only (not inside helpers)
- Parameterised queries for SQL; sanitise before shell commands
- Log security-relevant events; never log secrets

### Anti-patterns to reject
| Anti-pattern | Fix |
|---|---|
| Abstract base class for 1-2 impls | Write concrete code first |
| Config option "just in case" | Hard-code defaults; add config when 3+ callers need it |
| Catch-all exception handlers | Handle at boundaries, fail fast internally |
| `utils.py` junk drawer | Put helpers near where they're used |
| Premature framework | Write 3 concrete examples, then extract |

---

## 2. Documentation

### Before creating a new file — ask:
1. Does this belong in an existing file?
2. Is it temporary? (→ `docs/archive/`)
3. Will someone need it in 6 months?

### Where things go

| Content | Location |
|---|---|
| System overview | `README.md` |
| Compact agent policy | `AGENTS.md` (root) |
| Full agent policy | `docs/AGENTS.md` |
| Numbered subject guides | `docs/agent-guides/NN-TOPIC.md` |
| User guides | `docs/operations/` |
| Dev notes / decisions | `docs/architecture/` |
| Session reports | `docs/archive/` |

### Naming
- **GOOD:** `DEPLOYMENT_GUIDE.md`, `API_ENDPOINTS.md`
- **BAD:** `STATUS_REPORT_V3_FINAL_UPDATED.md`, `NOTES.md`, `TODO_LIST_DEC_3.md`

### Lifecycle
| State | Action |
|---|---|
| Dev status report — done | → `docs/archive/` |
| Migration plan — merged | → `docs/architecture/` |
| Outdated arch doc | → `docs/legacy/` or delete |
| Debug temp file | Delete immediately |
| Duplicate info | Merge and delete |

---

## 3. Pre-commit Cleanup Checklist (5 min)

```bash
grep -r "print\|console.log\|debugger" .                      # debug output
grep -r "TODO\|FIXME\|HACK" .                                  # leftover todos
git status                                                      # unintended changes
grep -r "password\|api_key\|secret" . --exclude-dir=.git       # secrets leak
scripts/governance/tier0-validation-gate.sh --pre-commit       # mandatory gate (61 checks)
```

- [ ] No debug print statements
- [ ] No commented-out code blocks
- [ ] Relevant docs updated
- [ ] No leftover TODOs in code
- [ ] No temporary files committed
- [ ] Tests run (if they exist)
- [ ] `git status` clean

---

## 4. Quality Signals

**Green flags (doing it right):**
- Code reads naturally without inline comments
- New code matches existing patterns
- You deleted more lines than you added
- Functions do one thing and are named for it

**Red flags (stop and simplify):**
- Creating abstract base classes for 1-2 uses
- Adding config options that aren't needed yet
- Writing extensive error messages for impossible scenarios
- A new `utils.py` with a single function
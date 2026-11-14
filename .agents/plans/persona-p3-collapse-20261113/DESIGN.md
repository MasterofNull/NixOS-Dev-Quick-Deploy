# Persona P3: shared memory as git-tracked fact files (design, rev 5)

Status: PLAN_READY_WITH_FOLLOWUPS. Build is deferred: measure the conflict rate first (section 4); the owner chose the next wave
as delivery friction. Author Simurg@claude/sonnet-5.5; reviewers differ in lane (Gemini and local reviewed rev 4).
PRD: `.agent/PROJECT-COLLECTIVE-PERSONA-PRD.md` 4.4, 5, 6. Owner decision 2026-11-13: facts are plain git files; collapse is the
normal merge; conflicts go to the owner in the CLI. UNVERIFIED marks what I could not check.

## 1. Shape

- **Fact file:** `.agent/memory/facts/<subject>.md`, one fact per file; the filename is the subject. `.agent/memory/` already holds
  plain markdown notes (22 files, for example `.agent/memory/lesson-tests-relative-time.md`); `facts/` is a new subfolder.
  ```
  ---
  subject: llama-cpp.n_gpu_layers
  claim: Renoir APU ceiling is 12 layers; KV q8_0 needs flash-attn on.
  evidence: CLAUDE.md:80  # illustrative
  instance: Simurg@codex/gpt-6.1#ab12cd34
  ---
  ```
- **Rules:** `subject` matches `^[a-z0-9_-]+(\.[a-z0-9_-]+)+$` and equals the filename; `claim` and `evidence` required; at most 10 fact
  files added, changed or deleted per commit. `evidence` is a repo `path:line`, a commit sha, a command, or an `https://` URL (8-300 chars).
  `instance` comes from `scripts/ai/lib/instance_label.py`. Lane parser: strip a leading `Simurg@` and a trailing `#<session>`, then take
  the text before `/` (`Simurg@codex/gpt-6.1#ab12` and PERSONA=0 `codex/gpt-6.1` both give `codex`). Facts are written either way.
- **Delta and collapse:** the instance commits fact files on its slice branch, inside the slice's normal commit (no docs-only PRs); collapse
  is the existing merge via `aq-land`. Provenance is `instance:` plus `git log`. No route, daemon, database or service.
- **Recall:** lanes read files (`rg subject-prefix .agent/memory/facts/`). `aq-session-start` prints up to 20 fact subjects (newest first)
  in its hydration output. AIDB/Qdrant is an optional read cache rebuilt from git with `scripts/data/seed-rag-knowledge.py`, never a
  source of truth. A fact is recallable after its PR merges: the PRD's "after one collapse".
- **Frontmatter gate:** `scripts/governance/check-doc-frontmatter.py` scans `.agent/` (`:183`) and needs `doc_type` from
  `config/doc-frontmatter-schema.yaml`. Smaller change: skip `.agent/memory/facts/` in that script (one filter) instead of a schema entry per fact.

## 2. Conflicts

1. **Concurrent edits:** two branches writing the same subject collide as a git add/add or content conflict at `aq-land`. Git is the detector.
2. **Silent overwrite or removal:** a clean edit, delete or rename of another lane's fact merges without conflict, so git misses it.
   One deterministic check, `scripts/governance/tier0.d/check-fact-files.py` (about 50 lines, proposed), compares each changed fact file
   with the merge-base against freshly fetched `origin/main`. If the claim changed, or the file was deleted or renamed, and the base
   `instance` lane differs from the new lane, the new file (or the commit message, for a delete) must carry `owner_reply:`. A scoped split
   (`x.y` to `x.y.codex` plus `x.y.claude`) is the same case: it needs `owner_reply` too, which closes the split bypass.
   On failure the check prints the base claim and the new claim so the agent can quote both to the owner.
   It also enforces regex, filename, evidence, and the 10-file cap. It runs wherever tier0 runs: pre-commit, and `aq-land`'s tier0 step
   (`scripts/ai/aq-land:245`, `--pre-commit`) on the branch diff, so a bypassed local hook is still caught before review.
3. **Resolution:** the agent stops and asks the owner one numbered CLI question ("1 keep mine, 2 keep theirs, 3 keep both"), then commits
   the answer with `owner_reply: <owner's words>`; "both" is a scoped split. The agent never answers for the owner.
- Limit: nothing proves a human wrote `owner_reply`. Control is the persona refusal list (never self-approve) and the independent reviewer lane reading the PR and the field.

## 3. Failure, kill switch, privacy, tokens

- No runtime component, so no coordinator or database failure mode. `PERSONA=0` changes only the label. No `COLLAPSE=0`: not committing
  fact files is the off switch. Merge costs zero LLM tokens.
- Privacy: the repo is public. The check rejects fact content containing `/home/`, `/run/secrets`, email addresses, token patterns or
  high-entropy strings (it reuses the `.gitleaks.toml` scan from `.githooks/pre-commit:47-57` when gitleaks is present, plus a regex). Other personal data is a reviewer item.

## 4. Measure first

Flagship review advised measuring the real conflict rate before building more. Agreed, so build is deferred. A one-off on-demand `git log`
report over `.agent/memory/facts/` counts facts, subjects touched by more than one lane, claim changes and `owner_reply` entries. Review at
50 facts or 30 days; if disagreement is rare, add nothing; if frequent, the counts say what to build.

## 5. Acceptance (E2E, real lanes)

1. A Codex branch lands fact X; Claude and local recall X from files with label and evidence after the merge.
2. Claude and Codex assert different claims for one subject: `aq-land` shows a conflict (concurrent) or the check fails without `owner_reply` (sequential, delete, rename or split); the output shows both claims; nothing is overwritten unasked.
3. Missing `subject` or `evidence`, 11 facts, a `/home/` path or an email in a fact fails the check.
4. `PERSONA=0` and `Simurg@` labels both parse to the same lane. Same-lane review rejection (PRD 4.3) is unchanged.
5. The section 4 report prints counts.

## 6. Simplicity check

- Fact files: the store; one file per subject makes conflict detection a filename match.
- Front-matter: subject (key), claim, evidence (truthfulness), instance (provenance).
- `check-fact-files.py`: git cannot see a clean overwrite, delete or split of another lane's claim.
- `owner_reply`: the only mark that a conflict reached the owner. Report: needed to decide whether more is required.
- Kept out: service, table, route, index, queue, resolve CLI, aq-approve, `COLLAPSE=0`.

## 7. Removed vs rev 3

The delta route, Postgres table, Qdrant write and guards, consensus/crystallizer closure, wrapper, pending retry, `resolutions`,
`state=disputed` branch and `ended_at` ordering. Git history and merge replace them.

## 8. Review disposition

- Delete, rename and split bypass: section 2 step 2. Baseline, gate placement, old and new claim printed: section 2 step 2.
- Lane parser and privacy rules: sections 1 and 3. Frontmatter skip filter and session-start listing: section 1.
- Build deferred until the section 4 measurement justifies it.

## 9. Open question

How does `aq-session-start` print facts today? Its output code was not read (UNVERIFIED).

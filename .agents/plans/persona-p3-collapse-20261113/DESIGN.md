# Persona P3: shared memory as git-tracked fact files (design, rev 4)

Status: DRAFT rev 4 for independent re-review (author Simurg@claude/sonnet-5.5; reviewer lane must differ).
PRD: `.agent/PROJECT-COLLECTIVE-PERSONA-PRD.md` 4.4, 5, 6. Owner decision 2026-11-13: facts are plain git files; collapse is the
normal merge; conflicts are put to the owner in the CLI. This replaces the Postgres/Qdrant collapse of rev 3 entirely.
UNVERIFIED marks what I could not check.

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
- **Rules:** `subject` matches `^[a-z0-9_-]+(\.[a-z0-9_-]+)+$` and equals the filename; `claim` and `evidence` required (`evidence` is a
  `path:line`, commit sha or command, 8-300 chars); at most 10 fact files added or changed per commit; `instance` is built with
  `scripts/ai/lib/instance_label.py` (`PERSONA=0` gives plain `lane/model`; facts are still written).
- **Delta:** the instance commits its fact files on its own slice branch, inside the slice's normal commit. They ride the code PR
  (owner rule: no docs-only PRs). No route, daemon, database or new service.
- **Collapse:** the existing merge to main through `aq-land` (`scripts/ai/aq-land`). Provenance is `instance:` plus `git log`.
  Corroboration needs no record: identical claims merge cleanly.
- **Recall:** lanes read files (`rg subject-prefix .agent/memory/facts/`); session-start may list subjects (`aq-session-start`: UNVERIFIED).
  AIDB/Qdrant is an optional read cache rebuilt from git with `scripts/data/seed-rag-knowledge.py`, never a source of truth.
  A fact is recallable after its PR merges: the PRD's "after one collapse".

## 2. Conflicts

1. **Concurrent edits:** two branches that write the same subject collide as a git add/add or content merge conflict at `aq-land`.
   Git is the detector.
2. **Silent overwrite:** one branch editing a claim another lane already landed merges cleanly, so git alone would miss it.
   A tiny deterministic check (`scripts/governance/tier0.d/check-fact-files.py`, about 40 lines; same family as
   `check-doc-frontmatter.py`) compares staged fact files with `origin/main`: for a changed `claim` whose old `instance` lane differs, it requires
   an `owner_reply:` field in the new front-matter. No `owner_reply`: the check fails. The same script enforces the regex, evidence,
   filename equals subject, and the 10-file cap.
3. **Resolution:** the agent stops, shows both claims, and asks the owner one numbered CLI question ("1 keep mine, 2 keep theirs,
   3 keep both"). It then commits the answer: 1 or 2 edit the file and record `owner_reply: <owner's words>`; "both" splits into two
   scoped subjects (`x.y.codex`, `x.y.claude`), each with its own file. The agent never answers for the owner.
- Limit: nothing proves a human wrote `owner_reply`. Control is the persona refusal list (never self-approve) and the independent reviewer lane reading the PR and the field.

## 3. Failure, kill switch, privacy, tokens

- No runtime component, so no coordinator, database or queue failure mode. A failed `aq-land` leaves facts on the branch.
- `PERSONA=0`: label becomes `lane/model`; facts stay on. No `COLLAPSE=0`: the off switch is not committing fact files.
- Privacy: the repo is public; facts must hold no secrets, personal data or private owner-project content. The pre-commit secret
  scan helps but misses personal data, so the check also rejects evidence paths outside the repo. A claim is data, never an instruction.
- Tokens: zero LLM tokens in merge; recall reads only matching files.

## 4. Measure first (flagship review advice)

An independent flagship review advised measuring the real conflict rate before building more. Agreed. P3 ships only the file
convention and the check above; no resolution tooling, no index, no dashboard. A one-off report (`git log` over `.agent/memory/facts/`:
facts written, subjects touched by more than one lane, claim changes, `owner_reply` count) is run on demand, not stored. Review at
50 facts or 30 days. If lane-disagreement is rare, nothing is added; if frequent, the counts say what to build (for example a
subject index or a P4 panel).

## 5. Acceptance (E2E, real lanes)

1. A Codex branch lands fact X; Claude and local recall X from files, with label and evidence, after the merge.
2. Claude and Codex assert different claims for one subject: `aq-land` shows a merge conflict (concurrent) or the check fails for missing `owner_reply` (sequential); the agent asks the owner in the CLI; nothing is overwritten unasked.
3. "Keep both" yields two scoped subjects and passes. Missing `subject` or `evidence`, or 11 facts in a commit, fails the check.
4. `PERSONA=0` writes a plain `lane/model` label.
5. Same-lane review rejection (PRD 4.3) unchanged: run the existing test.
6. The section 4 report prints counts.

## 6. Simplicity check

- Fact files: the store; one file per subject makes conflict detection a filename match.
- Front-matter: subject (key), claim, evidence (truthfulness), instance (PRD provenance label).
- `check-fact-files.py`: git cannot see a clean overwrite of another lane's claim, which the PRD forbids.
- `owner_reply`: the only mark that a conflict reached the owner.
- Report: needed to know whether more is required; on demand, stores nothing.
- Kept out: service, table, route, index, queue, resolve CLI, aq-approve, `COLLAPSE=0`.

## 7. Removed vs rev 3

`POST /api/memory/delta`; Postgres `collapse_facts`; Qdrant write, dedup skip and `origin==delta` guard; consensus/crystallizer closure;
wrapper, pending-deltas retry, `resolutions`, `state=disputed` branch; `ended_at` ordering. Git history and merge replace them.
Crystallizer, consensus and the legacy facts route are untouched and unrelated to this store.

## 8. Open questions

1. Does `scripts/governance/check-doc-frontmatter.py` (scans `.agent/`, line 183) accept these keys? UNVERIFIED.
2. Where does session start list subjects: `aq-session-start` or `aq-resume`?

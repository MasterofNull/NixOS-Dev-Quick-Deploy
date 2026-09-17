# aq-factory-pack — factory state packaging / cloning / portability tool

**Owner requirement (2026-09-09/10):** fresh-capability install is the CORE; SEPARATELY, a tool that lets
users **fully port, back up, and store their system's accumulated state** into a fresh system — and
**package + push that payload to git and other commonly-used dev-repo tools.** Parallel track to the
end-to-end install (`END-TO-END-BARE-METAL-PLAN.md`); the install reproduces CAPABILITY, this tool moves STATE.

## What it packages (the non-declarative accumulated STATE — not config, which the install already reproduces)
- **Qdrant collections** (RAG vectors + `agent-memory-*`) — via the Qdrant snapshot API.
- **PostgreSQL / AIDB** rows — via `pg_dump` (restore `pg_restore`).
- **Redis** persistent state if any (RDB/AOF).
- **Learned / trained artifacts** — LoRA adapters + closed-learning-loop training outputs.
- **Institutional memory** — RAG corpus sources, memory stores under `/var/lib` not tracked in the repo.
- **(Optional, flagged) model GGUFs** — large + usually re-downloadable; only via LFS / artifact store, opt-in.

## SECURITY (HARD — this tool pushes data OUTWARD; get this wrong and secrets leak)
- **NEVER plaintext secrets to any shareable/public destination:** SOPS age private key, `/run/secrets`,
  `deploy-options.local.nix`, any credential/OAuth token are EXCLUDED by default; anything sensitive that
  must travel is **age/SOPS-encrypted before it leaves the machine** — public destinations receive only
  ciphertext.
- **Secret-scan gate before any push (fail-closed):** reuse the repo's existing secret-scan gates; a planted
  secret in a to-be-pushed plaintext component MUST block the push. (Test this with a planted fixture.)
- **OAuth-only (NO API keys):** pushes use the user's EXISTING git/HF credentials; the tool embeds no tokens.
- **Push is outward-facing => explicit confirmation**, never automatic (route through the Approval Control
  Plane / plain-language confirm, consistent with the beginner control surface). Packaging/backup-to-local is
  not outward-facing; only upload is.

## Destinations (pluggable "destination" abstraction)
- **git** (GitHub/GitLab/Gitea) + **git-LFS** for large binaries (vectors/adapters).
- **HuggingFace Hub** (reuse existing HF integration) for model/dataset-shaped artifacts.
- **S3-compatible** object storage.
- **Local archive file** (offline backup — no network, no confirmation needed).

## Format
Versioned, **manifested** payload: a manifest (schema version, source host, timestamp, component list with
per-component sha256, encryption status) + per-component archives. Restore verifies every checksum against
the manifest (fail-closed on mismatch). Encrypted components carry their age recipients, never the key.

## Restore / deploy / append (owner 2026-09-10: TWO modes — deploy into new, AND append into existing)
The tool must both PACKAGE+SEND state and be able to consume that package on the other end, in two modes:
- **`--mode deploy` (into a FRESH system):** import the payload -> restore Qdrant snapshots, `pg_restore`,
  place adapters, rehydrate memory. Clean hydrate of an empty factory. Verified against the manifest.
- **`--mode append` (into an EXISTING system):** ADDITIVELY merge the package into a factory that already
  has state — never clobber. Union semantics per component: Qdrant = upsert points by id / add collection
  if absent (dedup identical vectors); Postgres/AIDB = insert-or-update (upsert on primary key), never
  DROP/overwrite existing rows; memory/adapters = add-without-replacing, conflict-log any collisions.
Both modes: require the age recipient's private key to decrypt (see portability finding), verify every
component sha256 against the manifest (fail-closed on mismatch), idempotent (re-running deploy/append is
safe), and report a per-component summary (added / updated / skipped-duplicate / conflict).

## Reuse (Rule 20b — compose, don't rebuild)
`scripts/*/archive-project-knowledge.sh` (existing knowledge archiving), Qdrant snapshot API, `pg_dump`/
`pg_restore`, `git-lfs`, existing secret-scan gates, existing HF integration, the ACP for the push confirm.
Ports/paths from env, never hardcoded.

## Slices (route cheapest-eligible; security slice gets strict independent review)
- **fp-1 — pack**: collect + manifest + (age-)encrypt sensitive components into a local payload. No network.
- **fp-2 — secret-scan + push**: fail-closed secret-scan, then push to a destination (git+LFS first) behind
  an explicit ACP confirmation. SECURITY-CRITICAL slice — strict non-author review + planted-secret test.
- **fp-3 — restore/deploy/append**: consume the package on the target in BOTH modes — `--mode deploy`
  (hydrate a fresh factory) and `--mode append` (additive upsert/union into an existing factory, never
  clobber). Verify sha256 vs manifest; idempotent; per-component added/updated/skipped/conflict summary.
- **fp-4 — verify round-trip (VM)**: pack on source -> DEPLOY into a fresh VM factory (assert state matches:
  RAG search returns seeded vectors, AIDB rows present) -> then APPEND the same pack again and assert it is
  idempotent (no duplicates, no clobber). Disposable, no sudo. The DoD real-world proof.

## Definition of done (Rule 15)
Round-trips in a VM (fp-4); planted-secret push is blocked (fp-2 test); push requires explicit confirmation;
observable (pack/push/restore status) + intervenable (cancel/rollback a restore). ACTIVATION-AUDIT + PM tracker.

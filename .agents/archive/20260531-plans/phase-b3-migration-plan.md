# Phase B.3 — hybrid-coordinator domain split migration plan

## Scope
- Objective: prepare a safe, reversible file-layout migration for `ai-stack/mcp-servers/hybrid-coordinator/` from a flat Python module directory into `core/`, `workflow/`, `knowledge/`, `extensions/`, and `tests/`.
- Deliverables in this phase: `scripts/data/migrate-hc-domains.py` and this plan.
- Out of scope: running `git mv`, changing imports, enforcing the boundary check, or modifying runtime behavior.

## Module classification source
- Source of truth used for the migration script: [docs/architecture/hybrid-coordinator-module-map.md](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/docs/architecture/hybrid-coordinator-module-map.md)
- The script hardcodes `DOMAIN_MAP` from that document so the move set is explicit and reviewable.

## Findings
- `http_server.py` contains path-sensitive `__file__` logic that will break after moving into `core/` unless it is updated in the follow-up migration phase.
- The most obvious breakpoints are the `sys.path.insert(...)` calls around [http_server.py](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/http_server.py:175), which currently assume the file lives directly under `hybrid-coordinator/`.
- `http_server.py` also derives the `world-model` path from `Path(__file__).resolve().parent.parent.parent` in [http_server.py](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/http_server.py:2045). Moving the file into `core/` changes that base path.
- I did not find any literal `'hybrid-coordinator/'` string in `server.py` or `http_server.py`; the risk is from relative path arithmetic, not a hardcoded directory string.
- `server.py` did not show comparable `__file__`-based path traversal in the inspected entrypoint path checks, so it appears lower risk for path breakage than `http_server.py`.
- The module map names `garbage_collection.py` as the primary module, but the current flat directory listing shows `garbage_collector.py` and does not show `garbage_collection.py`. The migration script therefore keeps both names in `DOMAIN_MAP` and warns on missing sources instead of failing hard.
- `hybrid-coordinator/tests/__init__.py` already exists. The migration script treats package directory and `__init__.py` creation as idempotent.
- Root-level one-line shims will preserve import compatibility for package-style imports, but they do not preserve direct script execution semantics for moved entrypoints such as `server.py` and `http_server.py`. Any launcher that executes those files by path will need follow-up validation.

## Migration script behavior
- File: [scripts/data/migrate-hc-domains.py](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/data/migrate-hc-domains.py)
- Uses a hardcoded `DOMAIN_MAP` from the architecture doc.
- Creates or reuses `core/`, `workflow/`, `knowledge/`, `extensions/`, and `tests/` under `hybrid-coordinator/`.
- Creates empty `__init__.py` files in each domain package.
- Supports `--dry-run` and prints all planned directory creation, `git mv`, shim creation, and summary output without making changes.
- Uses `git mv` via `subprocess.run(...)` for actual file moves.
- Writes root-level compatibility shims of the form `from .{domain}.{module} import *`.
- Warns and continues when a mapped source file does not exist or when the destination file already exists.

## Planned Phase B.3 execution order
1. Run `python scripts/data/migrate-hc-domains.py --dry-run` and review the move list, especially the missing-source warning for `garbage_collection.py`.
2. Audit all service launch paths for `server.py` and `http_server.py` before the real move, since root shims do not preserve script-entrypoint behavior.
3. Update `http_server.py` path resolution from `Path(__file__)` traversal to a repo-root or package-root helper before or immediately after the move.
4. Run the non-dry migration once entrypoint path handling is ready.
5. After the move, begin import rewrite and boundary enforcement work so `core/` and `workflow/` stop depending on `extensions/`.

## Acceptance checks for the next execution phase
- Dry-run output matches the module map classification.
- No unexpected target collisions are reported.
- Entry-point path assumptions are resolved for `http_server.py`.
- Post-move follow-up explicitly validates that `core/` does not import from `extensions/`.

## Evidence captured in this planning phase
- Reviewed module classification in [docs/architecture/hybrid-coordinator-module-map.md](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/docs/architecture/hybrid-coordinator-module-map.md)
- Inspected path-sensitive sections in [http_server.py](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/http_server.py:175) and [http_server.py](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/http_server.py:2045)
- Confirmed absence of a flat `garbage_collection.py` file in the current directory listing

## Rollback
- This phase is documentation plus script creation only. Reverting it is limited to removing the two new files.

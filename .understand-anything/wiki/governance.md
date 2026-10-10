---
doc_type: reference
title: "Wiki: Governance"
subsystem: governance
generated: 2026-10-10T08:04:22.573844Z
graph_generated: 2026-10-10T07:31:33Z
graph_nodes: 359
---

# Governance

> Pre-commit gates, tier0 validation, repo structure linting

*Auto-generated from `knowledge-graph.json`. Do not edit manually.*
*Refresh: `aq-wiki --update`  ·  Full regeneration: `aq-wiki --init --force`*

## Key Files

| File | Summary | Complexity |
|------|---------|------------|
| `ai-harness-slice-scorecard.py` | Validate the AI harness slice registry and emit a maturity scorecard. | complex |
| `check-state-authorities.py` | C0.3 bounded, read-only System State Authority checker. | complex |
| `manage-secrets.py` | Declarative SOPS secrets manager for local AI-stack credentials. | complex |
| `analyze-issues.py` | Analyze issue patterns and suggest system improvements | moderate |
| `apply-readme-ai-stack-updates.py` | Apply AI Stack integration updates to README.md | moderate |
| `aq-canon-compiler.py` | aq-canon-compiler — read-only schema-to-docs/client compiler (B3-C1). | moderate |
| `aq-evidence-collector.py` | aq-evidence-collector.py — standalone unwrapped evidence recorder (VF-7). | moderate |
| `audit-agent-artifact-debt.py` | Audit agent artifact stores that can accumulate stale context. | moderate |
| `audit-deprecated-script-usage.py` | Rank deprecated scripts by active repo references and classify keep vs archive. | moderate |
| `canon-compile.py` | canon-compile — compile shared canonical blocks into agent instruction files. | moderate |
| `check-cross-surface-contract.py` | Validate the docs/dashboard visibility contract for staged slices. | moderate |
| `check-doc-frontmatter.py` | scripts/governance/check-doc-frontmatter.py | moderate |
| `discover-focused-agent-repos.py` | discover-focused-agent-repos.py (216 lines) in governance. | moderate |
| `discover-improvements.py` | Lightweight discovery crawler: fetches a curated source list and produces | moderate |
| `discover-semantic-github-repos.py` | Discover GitHub repositories for coding-agent keywords, then rank results using | moderate |
| `list-issues.py` | List issues from the issue tracking database. | moderate |
| `record-issue.py` | CLI tool to record issues in the issue tracking database. | moderate |
| `resolve-issue.py` | Resolve an issue in the local issue tracking database. | moderate |
| `skill-bundle-registry.py` | Skill bundle registry tooling. | moderate |
| `update-readme-ai-stack.py` | Apply AI Stack integration updates to README.md for v6.0.0 | moderate |
| `_check_env_contract.py` | Helper for gate_env_contract: checks a single file for undocumented env var names. | simple |
| `ai-stack-manager.py` | Legacy shim for the retired ai_stack_manager bridge. | simple |
| `ai_stack_manager.py` | Compatibility shim for ai-stack-manager.py. | simple |
| `apply-doc-metadata-blocks.py` | Apply/repair doc metadata blocks for docs/operations and docs/development. | simple |
| `check-agent-instruction-parity.py` | check-agent-instruction-parity — always-on agent files stay complete and small. | simple |

## Key Functions

| Function | File | Summary |
|----------|------|---------|
| `analyze_issues_cli` | `analyze-issues.py` | CLI interface for analyzing issues |
| `main` | `apply-readme-ai-stack-updates.py` | main() |
| `main` | `discover-focused-agent-repos.py` | main() -> int |
| `main` | `discover-improvements.py` | main() -> int |
| `main` | `discover-semantic-github-repos.py` | main() -> int |
| `cmd_install` | `skill-bundle-registry.py` | cmd_install(args: argparse.Namespace) -> int |
| `main` | `update-readme-ai-stack.py` | main() |
| `_run_http_probe` | `ai-harness-slice-scorecard.py` | _run_http_probe(probe: Dict[str, Any], timeout_seconds: float) -> Dict[str, Any] |
| `build_scorecard` | `ai-harness-slice-scorecard.py` | build_scorecard(data: Dict[str, Any], runtime_results: Optional[Dict[str, Any]]=None) -> D |
| `dimension_status` | `ai-harness-slice-scorecard.py` | dimension_status(slice_data: Dict[str, Any], dimension: str, runtime_slice_result: Optiona |
| `main` | `ai-harness-slice-scorecard.py` | main() -> int |
| `render_text` | `ai-harness-slice-scorecard.py` | render_text(scorecard: Dict[str, Any], errors: List[str], runtime_errors: List[str]) -> st |
| `run_runtime_probes` | `ai-harness-slice-scorecard.py` | run_runtime_probes(data: Dict[str, Any], timeout_seconds: float, runtime_policy: Optional[ |
| `validate_registry` | `ai-harness-slice-scorecard.py` | validate_registry(data: Dict[str, Any]) -> List[str] |
| `build_record` | `aq-evidence-collector.py` | Build one Envelope-shaped evidence record. payload_bytes is the RAW |
| `build_report` | `audit-agent-artifact-debt.py` | build_report(args: argparse.Namespace) -> tuple[dict[str, object], bool] |
| `print_human` | `audit-agent-artifact-debt.py` | print_human(report: dict[str, object]) -> None |
| `markdown_report` | `audit-deprecated-script-usage.py` | markdown_report(rows: list[AuditRow]) -> str |
| `reference_counts` | `audit-deprecated-script-usage.py` | reference_counts(target: str) -> RefCounts |
| `main` | `check-cross-surface-contract.py` | main() -> int |

## Classes

| Class | File | Summary |
|-------|------|---------|
| `CanonCompilerError` | `aq-canon-compiler.py` | Fail-closed error: malformed spec, malformed schema, or missing input. |
| `FileFinding` | `audit-agent-artifact-debt.py` | class FileFinding() |
| `AuditRow` | `audit-deprecated-script-usage.py` | class AuditRow() |
| `RefCounts` | `audit-deprecated-script-usage.py` | class RefCounts() |
| `LinkParser` | `discover-improvements.py` | class LinkParser(HTMLParser) |

## Coverage

- **Nodes**: 359 total (27 files, 258 functions, 5 classes)
- **Path prefix**: `scripts/governance/`
- **Graph**: `.understand-anything/knowledge-graph.json`  (generated 2026-10-10T07:31:33Z)

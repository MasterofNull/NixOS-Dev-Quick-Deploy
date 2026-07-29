#!/usr/bin/env python3
"""Regression checks for aq-capability-intake."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


REPO_ROOT = Path(__file__).resolve().parents[2]
CMD = REPO_ROOT / "scripts" / "ai" / "aq-capability-intake"
REGISTRY_PATH = REPO_ROOT / "config" / "agent-capability-intake-candidates.json"
SCHEMA_PATH = REPO_ROOT / "config" / "schemas" / "agent-capability-intake-candidates.schema.json"


def run_json(*args: str) -> dict:
    proc = subprocess.run(
        [str(CMD), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return json.loads(proc.stdout)


def main() -> int:
    test_registry_schema()
    test_production_registry_rejections()
    listing = run_json("list", "--json")
    ids = {item["id"] for item in listing}
    assert "playwright-mcp" in ids
    assert "semgrep-mcp" in ids
    assert "mcp-admission-controller" in ids
    assert "t3mp3st" in ids
    assert {"piyaz-patterns", "sn1per-reference", "raptor-loop-hunt-reference"} <= ids

    all_report = run_json("audit", "--all", "--json")
    reports = {item["id"]: item for item in all_report["reports"]}
    assert reports["playwright-mcp"]["admission"] == "accepted-with-mitigations"
    assert "unpinned-version" not in reports["playwright-mcp"]["risk_flags"]
    assert "network-capable" in reports["playwright-mcp"]["risk_flags"]
    assert reports["semgrep-mcp"]["admission"] == "accepted-with-mitigations"
    assert "unpinned-version" not in reports["semgrep-mcp"]["risk_flags"]
    assert reports["mcp-admission-controller"]["admission"] == "accepted-with-mitigations"
    assert reports["mcp-admission-controller"]["state"] == "enabled"
    assert reports["github-mcp-readonly"]["admission"] == "accepted-with-mitigations"
    assert reports["github-mcp-readonly"]["state"] == "enabled"
    assert reports["github-mcp-readonly"]["unsafe_tool_count"] == 0
    assert reports["t3mp3st"]["state"] == "ready-scope-gated"
    assert reports["t3mp3st"]["admission"] == "accepted-with-mitigations"
    assert "dual-use-offensive-security" in reports["t3mp3st"]["risk_flags"]
    assert "network-active-scanning" in reports["t3mp3st"]["risk_flags"]
    assert reports["t3mp3st"]["unsafe_tool_count"] == 0
    for candidate_id in ("piyaz-patterns", "sn1per-reference", "raptor-loop-hunt-reference"):
        candidate = reports[candidate_id]
        assert candidate["state"] in {"proposed", "quarantined"}
        assert candidate["admission"] not in {"low-risk", "accepted-with-mitigations"}

    one_report = run_json("audit", "semgrep-mcp", "--json")
    assert len(one_report["reports"]) == 1
    assert one_report["reports"][0]["id"] == "semgrep-mcp"

    # Run new security checks
    test_auditor_fuzzy()
    test_mock_registry_checks()

    print("PASS: capability intake checks")
    return 0


def test_registry_schema() -> None:
    """Validate the closed registry contract and its S0-A negative vectors offline."""
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def errors(payload: dict) -> list:
        return list(validator.iter_errors(payload))

    assert not errors(registry), "baseline-plus-S0-A registry must validate"
    candidates = registry["candidates"]
    assert len(candidates) == 14
    ids = [candidate["id"] for candidate in candidates]
    assert len(ids) == len(set(ids)), "candidate IDs must be unique"
    assert len(candidates[:11]) == 11
    assert candidates[10]["id"] == "t3mp3st"

    by_id = {candidate["id"]: candidate for candidate in candidates}
    for candidate_id, expected_state in {
        "piyaz-patterns": "proposed",
        "sn1per-reference": "quarantined",
        "raptor-loop-hunt-reference": "proposed",
    }.items():
        candidate = by_id[candidate_id]
        assert candidate["maturity"] == "third-party-reference"
        assert candidate["review_status"] == "incomplete"
        assert candidate["state"] == expected_state
        assert candidate["install"] == {"type": "disabled-external-repo", "command": "disabled-until-intake", "args": []}
        assert candidate["tool_allowlist"] == []
        assert candidate["permissions"] == {"network": False, "filesystem": "none", "writes": False, "secrets": False}

    unknown_key = json.loads(json.dumps(registry))
    unknown_key["unexpected"] = True
    assert errors(unknown_key)

    malformed_permission = json.loads(json.dumps(registry))
    malformed_permission["candidates"][-1]["permissions"]["network"] = "internet"
    assert errors(malformed_permission)

    wrong_type = json.loads(json.dumps(registry))
    wrong_type["candidates"][-1]["tool_allowlist"] = "not-an-array"
    assert errors(wrong_type)

    malformed_url = json.loads(json.dumps(registry))
    malformed_url["candidates"][-1]["source_url"] = "not a url"
    assert errors(malformed_url)

    unbounded_tool = json.loads(json.dumps(registry))
    unbounded_tool["candidates"][-1]["tool_allowlist"] = ["x" * 129]
    assert errors(unbounded_tool)

    duplicate_id = json.loads(json.dumps(registry))
    duplicate_id["candidates"][-1]["id"] = duplicate_id["candidates"][-2]["id"]
    duplicate_ids = [candidate["id"] for candidate in duplicate_id["candidates"]]
    assert len(duplicate_ids) != len(set(duplicate_ids)), "duplicate-ID negative vector must be detected"
    print("SUBPASS: closed registry schema and negative vectors")


def test_production_registry_rejections() -> None:
    """Exercise malformed local registries through the production CLI loader."""
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def assert_rejected(payload: dict, *command: str, classification: str) -> None:
        with tempfile.TemporaryDirectory(prefix="capability-intake-test-") as temp_dir:
            path = Path(temp_dir) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            proc = subprocess.run(
                [str(CMD), "--registry", str(path), *command],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        assert proc.returncode == 2
        assert proc.stdout == ""
        assert proc.stderr == f"ERROR: invalid candidate registry: {classification}\n"

    duplicate_id = json.loads(json.dumps(registry))
    duplicate_id["candidates"][-1]["id"] = duplicate_id["candidates"][-2]["id"]
    assert duplicate_id["candidates"][-1] != duplicate_id["candidates"][-2]
    assert_rejected(duplicate_id, "list", "--json", classification="duplicate candidate id")

    over_bound_tool = json.loads(json.dumps(registry))
    over_bound_tool["candidates"][-1]["tool_schemas"] = {
        "x" * 129: {"type": "string"}
    }
    assert_rejected(
        over_bound_tool,
        "audit",
        "--all",
        "--json",
        classification="schema validation failed",
    )

    over_bound_property = json.loads(json.dumps(registry))
    over_bound_property["candidates"][-1]["tool_schemas"] = {
        "valid_tool": {
            "type": "object",
            "properties": {"x" * 129: {"type": "string"}},
        }
    }
    assert_rejected(
        over_bound_property,
        "list",
        "--json",
        classification="schema validation failed",
    )
    print("SUBPASS: production loader rejects duplicate and over-bound registry keys")


def test_auditor_fuzzy() -> None:
    import sys
    sys.path.insert(0, str(REPO_ROOT / "ai-stack" / "mcp-servers"))
    from shared.tool_security_auditor import ToolSecurityAuditor

    # Instantiate auditor
    auditor = ToolSecurityAuditor(
        service_name="test-auditor-fuzzy",
        policy_path=REPO_ROOT / "config" / "runtime-tool-security-policy.json",
        cache_path=REPO_ROOT / ".cache" / "test-auditor-fuzzy-cache.json",
        enabled=True,
        enforce=False,
    )

    # shell_exec is blocked; shell_exe is distance 1
    res = auditor.audit_tool("shell_exe", {"endpoint": "test"})
    assert res["safe"] is False
    assert "blocked_tool_name_fuzzy" in res["reasons"]

    # random_tool is NOT blocked
    res2 = auditor.audit_tool("random_tool", {"endpoint": "test"})
    assert res2["safe"] is True
    print("SUBPASS: auditor fuzzy matching")


def test_mock_registry_checks() -> None:
    mock_registry = {
        "version": "1.0-mock",
        "candidates": [
            {
                # The admission-controller finding's OWN test case #1
                # (proposed test cases item 1): a candidate claiming
                # read-only but specifying a `command_override` parameter.
                # This MUST be blocked — it is the literal bypass the
                # candidate review caught (item 1a).
                "id": "unsafe-schema-test",
                "name": "Unsafe Schema Test",
                "priority": "P2",
                "state": "ready-scope-gated",
                "install": {
                    "type": "mcp",
                    "command": "npx",
                    "args": ["-y", "playwright-mcp"]
                },
                "tool_allowlist": ["test_tool"],
                "tool_schemas": {
                    "test_tool": {
                        "type": "object",
                        "properties": {
                            "command_override": {
                                "type": "string"
                            }
                        }
                    }
                }
            },
            {
                # Bare "command" (listed in policy blocked_parameter_keys)
                # with no admission constraint at all.
                "id": "bare-command-schema-test",
                "name": "Bare Command Schema Test",
                "priority": "P2",
                "state": "ready-scope-gated",
                "install": {
                    "type": "mcp",
                    "command": "npx",
                    "args": ["-y", "playwright-mcp"]
                },
                "tool_allowlist": ["test_tool"],
                "tool_schemas": {
                    "test_tool": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string"
                            }
                        }
                    }
                }
            },
            {
                # Command param hidden inside an array-of-objects schema
                # (items.properties) — must be caught by recursion, not
                # just top-level properties.
                "id": "nested-array-schema-test",
                "name": "Nested Array Schema Test",
                "priority": "P2",
                "state": "ready-scope-gated",
                "install": {
                    "type": "mcp",
                    "command": "npx",
                    "args": ["-y", "playwright-mcp"]
                },
                "tool_allowlist": ["test_tool"],
                "tool_schemas": {
                    "test_tool": {
                        "type": "object",
                        "properties": {
                            "steps": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "exec": {"type": "string"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            {
                # Command param hidden inside additionalProperties (a
                # map-of-objects schema) — must be caught by recursion.
                "id": "nested-map-schema-test",
                "name": "Nested Map Schema Test",
                "priority": "P2",
                "state": "ready-scope-gated",
                "install": {
                    "type": "mcp",
                    "command": "npx",
                    "args": ["-y", "playwright-mcp"]
                },
                "tool_allowlist": ["test_tool"],
                "tool_schemas": {
                    "test_tool": {
                        "type": "object",
                        "properties": {
                            "env_overrides": {
                                "type": "object",
                                "additionalProperties": {
                                    "type": "object",
                                    "properties": {
                                        "shell": {"type": "string"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            {
                # enum-bound command param -> admitted, not flagged.
                "id": "safe-schema-enum-test",
                "name": "Safe Schema Enum Test",
                "priority": "P2",
                "state": "ready-scope-gated",
                "install": {
                    "type": "mcp",
                    "command": "npx",
                    "args": ["-y", "playwright-mcp"]
                },
                "tool_allowlist": ["test_tool"],
                "tool_schemas": {
                    "test_tool": {
                        "type": "object",
                        "properties": {
                            "command_override": {
                                "type": "string",
                                "enum": ["allowed_command"]
                            }
                        }
                    }
                }
            },
            {
                # pattern-bound (regex) command param -> admitted.
                "id": "safe-schema-pattern-test",
                "name": "Safe Schema Pattern Test",
                "priority": "P2",
                "state": "ready-scope-gated",
                "install": {
                    "type": "mcp",
                    "command": "npx",
                    "args": ["-y", "playwright-mcp"]
                },
                "tool_allowlist": ["test_tool"],
                "tool_schemas": {
                    "test_tool": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "pattern": "^[a-z-]+$"
                            }
                        }
                    }
                }
            },
            {
                # maxLength-bound command param -> admitted.
                "id": "safe-schema-maxlength-test",
                "name": "Safe Schema MaxLength Test",
                "priority": "P2",
                "state": "ready-scope-gated",
                "install": {
                    "type": "mcp",
                    "command": "npx",
                    "args": ["-y", "playwright-mcp"]
                },
                "tool_allowlist": ["test_tool"],
                "tool_schemas": {
                    "test_tool": {
                        "type": "object",
                        "properties": {
                            "shell": {
                                "type": "string",
                                "maxLength": 16
                            }
                        }
                    }
                }
            },
            {
                # "args" is commonly legitimate -> needs-review, not a hard
                # block, when unbound.
                "id": "args-needs-review-test",
                "name": "Args Needs Review Test",
                "priority": "P2",
                "state": "ready-scope-gated",
                "install": {
                    "type": "mcp",
                    "command": "npx",
                    "args": ["-y", "playwright-mcp"]
                },
                "tool_allowlist": ["test_tool"],
                "tool_schemas": {
                    "test_tool": {
                        "type": "object",
                        "properties": {
                            "extra_args": {
                                "type": "string"
                            }
                        }
                    }
                }
            },
            {
                "id": "playwright-mcp",
                "name": "Playwright MCP",
                "priority": "P1",
                "state": "active",
                "install": {
                    "type": "mcp",
                    "command": "npx",
                    "args": ["-y", "playwright-mcp"]
                },
                "tool_allowlist": ["test_tool"]
            },
            {
                "id": "typo-squat-test",
                "name": "Typo Squat Test",
                "priority": "P2",
                "state": "ready-scope-gated",
                "install": {
                    "type": "mcp",
                    "command": "npx",
                    "args": ["-y", "playwrigt-mcp"]
                },
                "tool_allowlist": ["test_tool"]
            }
        ]
    }

    loader = importlib.machinery.SourceFileLoader("aq_capability_intake_test", str(CMD))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    known_ids = [candidate["id"] for candidate in mock_registry["candidates"]]
    reports = {
        candidate["id"]: module.audit_candidate(candidate, known_ids)
        for candidate in mock_registry["candidates"]
    }

    # 1. command_override (the admission-controller finding's own test
    #    case #1) must fail closed -- this is the literal bypass the
    #    independent candidate review caught.
    assert "unsafe-parameter-schema" in reports["unsafe-schema-test"]["risk_flags"]
    assert reports["unsafe-schema-test"]["admission"] == "blocked"

    # 2. Bare "command" (no enum/pattern/maxLength) must also block --
    #    "cmd" is not a substring of "command", so this specifically
    #    exercises that the keyword set includes "command" itself.
    assert "unsafe-parameter-schema" in reports["bare-command-schema-test"]["risk_flags"]
    assert reports["bare-command-schema-test"]["admission"] == "blocked"

    # 3. Nested schema forms must be recursed into, not just top-level
    #    properties: array-of-objects (items.properties.exec) ...
    assert "unsafe-parameter-schema" in reports["nested-array-schema-test"]["risk_flags"]
    assert reports["nested-array-schema-test"]["admission"] == "blocked"
    # ... and map-of-objects (additionalProperties.properties.shell).
    assert "unsafe-parameter-schema" in reports["nested-map-schema-test"]["risk_flags"]
    assert reports["nested-map-schema-test"]["admission"] == "blocked"

    # 4. Admission escape hatches: enum, pattern, and maxLength each
    #    admit an otherwise-flagged param on their own.
    assert "unsafe-parameter-schema" not in reports["safe-schema-enum-test"]["risk_flags"]
    assert "unsafe-parameter-schema" not in reports["safe-schema-pattern-test"]["risk_flags"]
    assert "unsafe-parameter-schema" not in reports["safe-schema-maxlength-test"]["risk_flags"]

    # 5. "args"-named params are a needs-review signal, not a hard
    #    block, when unbound (they're commonly legitimate: search_args,
    #    extra_args, etc.).
    assert "unbound-args-parameter-schema" in reports["args-needs-review-test"]["risk_flags"]
    assert "unsafe-parameter-schema" not in reports["args-needs-review-test"]["risk_flags"]
    assert reports["args-needs-review-test"]["admission"] == "needs-review"

    # 6. Typo-squatting test
    assert "typo-squatting-detected" in reports["typo-squat-test"]["risk_flags"]
    assert reports["typo-squat-test"]["admission"] == "blocked"

    print("SUBPASS: mock registry checks (schema validation and typo-squatting)")


if __name__ == "__main__":
    raise SystemExit(main())

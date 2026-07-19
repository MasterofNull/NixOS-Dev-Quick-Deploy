#!/usr/bin/env python3
"""Offline B2-M1A migration and privilege-policy oracle.

The default path is deterministic and standard-library-only. The integration entry point remains a
fail-closed declaration for a separately authorized M1E evidence slice.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import re
import stat
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AIDB_MIGRATION = ROOT / "ai-stack/migrations/versions/20260125_01_add_llm_used_column.py"
MIGRATION = ROOT / "ai-stack/migrations/versions/20260718_01_b2_workflow_shadow.py"
POLICY = ROOT / "config/workflow-shadow-db-privileges.json"
NIX = ROOT / "nix/modules/services/mcp-servers.nix"
MIGRATION_TEST = ROOT / "ai-stack/migrations/test-migrations.sh"
REGISTRY = ROOT / "config/validation-check-registry.json"
AUTHORIZED_PATHS = (
    "ai-stack/migrations/versions/20260125_01_add_llm_used_column.py",
    "ai-stack/migrations/versions/20260718_01_b2_workflow_shadow.py",
    "nix/modules/services/mcp-servers.nix",
    "config/workflow-shadow-db-privileges.json",
    "scripts/testing/test-workflow-shadow-migration.py",
    "config/validation-check-registry.json",
    "ai-stack/migrations/test-migrations.sh",
)
M1E_REQUIRED_EVIDENCE = (
    "atomic_forward_application",
    "positive_privilege_matrix",
    "negative_privilege_matrix",
    "outbox_immutability",
    "snapshot_outbox_atomicity",
    "cas_uniqueness_and_exact_replay",
    "terminal_uniqueness",
    "destructive_downgrade_refusal",
    "failure_after_role_creation_rollback",
    "failure_between_object_and_grant_rollback",
    "owner_acl_and_membership_cleanup",
    "bootstrap_session_termination_and_drop",
    "catalog_ownership_grant_function_trigger_drift",
    "event_size_revision_lease_attempt_limits",
    "sixty_second_and_256_mib_ceilings",
    "disposable_database_cleanup",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_python_surface(source: str) -> None:
    tree = ast.parse(source)
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    require(imports == {"alembic"}, f"migration imports not closed: {sorted(imports)}")
    prohibited = (
        "IF NOT EXISTS",
        "workflow_checkpoints",
        "psql",
        "subprocess",
        "socket",
        "create_engine",
        "connect(",
        "os.environ",
        "DATABASE_URL",
        "objective",
        "prompt",
        "free_form_error",
    )
    for token in prohibited:
        require(token not in source, f"prohibited migration surface: {token}")
    required = (
        'revision = "20260718_01_b2_shadow"',
        "down_revision = None",
        'branch_labels = ("b2_workflow_shadow",)',
        "pg_advisory_xact_lock",
        "B2_MIGRATION_PREFLIGHT_REJECTED",
        "b2_policy_sha256",
        'dialect.name != "postgresql"',
        "SET LOCAL lock_timeout = '2s'",
        "SET LOCAL statement_timeout = '10s'",
        "SET LOCAL idle_in_transaction_session_timeout = '15s'",
        "CREATE TABLE {SCHEMA}.workflow_snapshot",
        "CREATE TABLE {SCHEMA}.workflow_outbox_event",
        "CREATE TABLE {SCHEMA}.workflow_delivery_control",
        "SECURITY DEFINER",
        "SET search_path = pg_catalog, {SCHEMA}",
        "B2_DESTRUCTIVE_DOWNGRADE_PROHIBITED",
    )
    for token in required:
        require(token in source, f"missing migration invariant: {token}")


def check_aidb_branch_source(source: str) -> None:
    """Bind the existing AIDB migration's revision graph literally, without import/execution."""
    tree = ast.parse(source)
    assignments: dict[str, list[ast.expr]] = {
        "revision": [], "down_revision": [], "branch_labels": [], "depends_on": [],
    }
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in assignments
        ):
            assignments[node.targets[0].id].append(node.value)
    for name, values in assignments.items():
        require(len(values) == 1, f"AIDB migration must assign {name} exactly once")
    revision_node, down_revision_node, branch_labels_node, depends_on_node = (
        assignments["revision"][0], assignments["down_revision"][0],
        assignments["branch_labels"][0], assignments["depends_on"][0],
    )
    require(
        isinstance(revision_node, ast.Constant) and revision_node.value == "20260125_01",
        "AIDB revision literal binding",
    )
    require(
        isinstance(down_revision_node, ast.Constant) and down_revision_node.value == "20260109_02",
        "AIDB down_revision literal binding",
    )
    require(
        isinstance(branch_labels_node, ast.Tuple)
        and len(branch_labels_node.elts) == 1
        and isinstance(branch_labels_node.elts[0], ast.Constant)
        and branch_labels_node.elts[0].value == "aidb",
        'AIDB branch_labels literal binding exactly ("aidb",)',
    )
    require(
        isinstance(depends_on_node, ast.Constant) and depends_on_node.value is None,
        "AIDB depends_on literal binding",
    )


def check_policy(policy: dict[str, object]) -> None:
    expected_top = {
        "schema_version", "authority", "coverage", "migration", "objects", "roles",
        "bootstrap_executor", "grants", "denials", "limits", "transaction", "integration_gate",
    }
    require(set(policy) == expected_top, "privilege policy is not closed")
    require(policy["schema_version"] == "aq.workflow-shadow-db-privileges.v1", "schema identity")
    require(policy["authority"] == "legacy_json_authoritative", "authority truth")
    require(policy["coverage"] == "static_only", "coverage truth")
    migration = policy["migration"]
    require(isinstance(migration, dict), "migration object")
    require(migration == {
        "revision": "20260718_01_b2_shadow",
        "branch_label": "b2_workflow_shadow",
        "down_revision": None,
        "canonical_config": "ai-stack/migrations/alembic.ini",
        "aidb_target": "aidb@head",
        "b2_target": "b2_workflow_shadow@head",
    }, "migration identity")
    objects = policy["objects"]
    require(isinstance(objects, dict) and set(objects) == {
        "schema", "tables", "columns", "column_types", "enums", "functions", "triggers", "indexes",
        "constraints", "foreign_keys",
    }, "object policy shape")
    require(objects["schema"] == "aq_b2_workflow_shadow_v1", "schema identity")
    require(objects["tables"] == [
        "workflow_snapshot", "workflow_outbox_event", "workflow_delivery_control",
    ], "table identities")
    require(objects["functions"] == [
        "apply_workflow_transition_v1", "reject_workflow_outbox_mutation_v1",
    ], "function identities")
    require(objects["triggers"] == ["workflow_outbox_immutable_v1"], "trigger identities")
    require(objects["indexes"] == [
        "workflow_outbox_event_workflow_revision_uq", "workflow_delivery_control_next_attempt_idx",
    ], "index identities")
    require(objects["constraints"] == [
        "workflow_snapshot_revision_ck", "workflow_snapshot_digest_ck", "workflow_snapshot_terminal_ck",
        "workflow_outbox_event_revision_ck", "workflow_outbox_event_digest_ck",
        "workflow_outbox_event_size_ck", "workflow_outbox_event_schema_ck",
        "workflow_delivery_control_lease_ck", "workflow_delivery_control_attempt_ck",
        "workflow_delivery_control_disposition_ck", "workflow_delivery_control_error_ck",
        "workflow_outbox_snapshot_fk", "workflow_delivery_outbox_fk",
    ], "constraint identities")
    require(objects["foreign_keys"] == {
        "workflow_outbox_snapshot_fk": [
            "workflow_outbox_event.workflow_id", "workflow_snapshot.workflow_id",
        ],
        "workflow_delivery_outbox_fk": [
            "workflow_delivery_control.event_id", "workflow_outbox_event.event_id",
        ],
    }, "foreign key identity map")
    identity_lists = [objects[key] for key in ("tables", "functions", "triggers", "indexes", "constraints")]
    require(len({name for values in identity_lists for name in values}) ==
            sum(len(values) for values in identity_lists), "duplicate object identity")
    require(objects["columns"] == {
        "workflow_snapshot": [
            "workflow_id", "revision", "status", "terminal", "phase_token", "phase_index",
            "action", "last_event_id", "live_commit_digest", "occurred_at",
        ],
        "workflow_outbox_event": [
            "event_id", "workflow_id", "revision", "live_commit_digest", "event_json", "transaction_at",
        ],
        "workflow_delivery_control": [
            "event_id", "lease_epoch", "attempt_count", "next_attempt_at", "disposition",
            "typed_error", "updated_at",
        ],
    }, "column policy")
    require(set(objects["column_types"]) == set(objects["columns"]), "column type tables")
    for table_name, columns in objects["columns"].items():
        require(list(objects["column_types"][table_name]) == columns, f"column type order: {table_name}")
    require(objects["enums"]["status"] == ["started", "running", "completed", "failed", "cancelled"],
            "status enum")
    require(objects["enums"]["action"] == ["start", "advance", "complete", "fail", "cancel"],
            "action enum")
    require(objects["enums"] == {
        "status": ["started", "running", "completed", "failed", "cancelled"],
        "action": ["start", "advance", "complete", "fail", "cancel"],
        "transition_kind": ["run_start", "manual_phase_transition", "terminal_completion"],
        "delivery_disposition": ["pending", "delivering", "delivered", "parked"],
        "typed_error": [
            "disabled", "deadline_exceeded", "database_unavailable", "schema_unready",
            "schema_invalid", "privacy_rejected", "cas_mismatch", "revision_gap",
            "event_collision", "terminal_conflict", "transaction_failed", "projection_gap",
            "integrity_failed", "disk_budget_exceeded", "parked",
        ],
    }, "closed enums")
    roles = policy["roles"]
    require(isinstance(roles, dict) and set(roles) == {"owner", "writer", "delivery", "reader"}, "role set")
    names = [entry["name"] for entry in roles.values()]
    require(len(names) == len(set(names)) == 4, "role identities")
    for entry in roles.values():
        require(entry["attributes"] == [
            "NOLOGIN", "NOSUPERUSER", "NOCREATEDB", "NOCREATEROLE",
            "NOREPLICATION", "NOBYPASSRLS",
        ], "durable role attributes")
    require(set(roles["owner"]) == {"name", "attributes", "retained_members"}, "owner shape")
    require(roles["owner"]["retained_members"] == [], "retained owner membership")
    for role_name in ("writer", "delivery", "reader"):
        require(set(roles[role_name]) == {"name", "attributes"}, f"{role_name} shape")
    bootstrap = policy["bootstrap_executor"]
    require(set(bootstrap) == {
        "name_pattern", "database_prefix", "attributes_before", "initial_b2_memberships",
        "owner_temporary_database_privileges", "temporary_alembic_version_privileges",
        "temporary_owner_membership",
        "post_commit_actions", "retained", "threat_boundary",
    }, "bootstrap shape")
    require(bootstrap["database_prefix"] == "aq_b2_m1e_" and not bootstrap["retained"], "bootstrap lifecycle")
    require(bootstrap["initial_b2_memberships"] == [], "bootstrap pre-membership")
    require(bootstrap["owner_temporary_database_privileges"] == ["CREATE"], "owner temporary database grant")
    grants = policy["grants"]
    require(set(grants) == {"public", "writer", "delivery", "reader"}, "grant shape")
    require(grants["public"] == [], "PUBLIC grant")
    require(grants["writer"] == {
        "schema": ["USAGE"], "tables": {},
        "functions": {"apply_workflow_transition_v1": ["EXECUTE"]},
    }, "writer privilege boundary")
    require(grants["delivery"] == {
        "schema": ["USAGE"],
        "tables": {
            "workflow_outbox_event": ["SELECT"],
            "workflow_delivery_control": ["SELECT", "UPDATE"],
        },
        "functions": {},
    }, "delivery privilege boundary closed")
    require(grants["reader"] == {
        "schema": ["USAGE"],
        "tables": {
            "workflow_snapshot": ["SELECT"], "workflow_outbox_event": ["SELECT"],
            "workflow_delivery_control": ["SELECT"],
        },
        "functions": {},
    }, "reader privilege boundary closed")
    denials = policy["denials"]
    require(set(denials) == {
        "wildcard_privileges", "public_grants", "durable_login_roles",
        "runtime_role_ownership", "writer_direct_table_dml", "runtime_ddl",
        "unqualified_objects", "retained_bootstrap_membership", "existing_workflow_objects",
    }, "denial shape")
    require(all(value is True for key, value in denials.items() if key != "runtime_ddl"), "closed denials")
    require(denials["runtime_ddl"] == ["CREATE", "ALTER", "DROP", "TRUNCATE"], "runtime DDL denial")
    require(policy["limits"] == {
        "event_bytes": 2048, "revision": 100000, "lease_epoch": 1000000,
        "attempt_count": 1000, "static_test_seconds": 30,
        "disposable_suite_seconds": 60, "database_mib": 256, "migration_attempts": 1,
    }, "resource ceilings")
    require(policy["integration_gate"] == {
        "required_flags": ["--integration", "--dsn-file", "--evidence-token"],
        "dsn_file": {"regular": True, "symlink": False, "mode": "0600"},
        "denylisted_databases": ["aidb", "postgres", "template0", "template1"],
        "loopback_only": True, "default_result": "M1E_NOT_AUTHORIZED",
    }, "integration fail-closed policy")
    require(policy["transaction"] == {
        "advisory_lock_identity": "20260718_01_b2_shadow", "lock_timeout": "2s",
        "statement_timeout": "10s", "idle_in_transaction_session_timeout": "15s",
        "transactional_ddl": True, "destructive_downgrade": False,
    }, "transaction policy")


def bind_slice(source: str, start_marker: str, end_marker: str, description: str) -> str:
    start = source.find(start_marker)
    require(start != -1, f"missing block start for {description}")
    end = source.find(end_marker, start + len(start_marker))
    require(end != -1, f"missing block end for {description}")
    return source[start:end]


def check_named_object_bindings(source: str, objects: dict[str, object]) -> None:
    """Bind each policy-closed identity to its exact source object/table/column relationship."""
    for function_name in objects["functions"]:
        require(
            ("CREATE FUNCTION {SCHEMA}." + function_name + "(") in source,
            f"function not bound: {function_name}",
        )

    trigger_binding = (
        "CREATE TRIGGER workflow_outbox_immutable_v1\n"
        "BEFORE UPDATE OR DELETE ON {SCHEMA}.workflow_outbox_event\n"
        "FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.reject_workflow_outbox_mutation_v1()"
    )
    require(trigger_binding in source, "trigger not bound to table and function")

    index_bindings = {
        "workflow_outbox_event_workflow_revision_uq": (
            "workflow_outbox_event", "(workflow_id, revision)",
        ),
        "workflow_delivery_control_next_attempt_idx": (
            "workflow_delivery_control", "(next_attempt_at)",
        ),
    }
    for index_name in objects["indexes"]:
        require(index_name in index_bindings, f"unmapped index identity: {index_name}")
        table_name, columns = index_bindings[index_name]
        binding = index_name + "\n  ON {SCHEMA}." + table_name + " " + columns
        require(binding in source, f"index not bound: {index_name}")

    constraint_owner = {
        "workflow_snapshot_revision_ck": "workflow_snapshot",
        "workflow_snapshot_digest_ck": "workflow_snapshot",
        "workflow_snapshot_terminal_ck": "workflow_snapshot",
        "workflow_outbox_event_revision_ck": "workflow_outbox_event",
        "workflow_outbox_event_digest_ck": "workflow_outbox_event",
        "workflow_outbox_event_size_ck": "workflow_outbox_event",
        "workflow_outbox_event_schema_ck": "workflow_outbox_event",
        "workflow_delivery_control_lease_ck": "workflow_delivery_control",
        "workflow_delivery_control_attempt_ck": "workflow_delivery_control",
        "workflow_delivery_control_disposition_ck": "workflow_delivery_control",
        "workflow_delivery_control_error_ck": "workflow_delivery_control",
    }
    foreign_keys = objects["foreign_keys"]
    require(
        set(objects["constraints"]) == set(constraint_owner) | set(foreign_keys),
        "constraint identity coverage matches CHECK and FOREIGN KEY classes",
    )

    snapshot_block = bind_slice(
        source, "CREATE TABLE {SCHEMA}.workflow_snapshot",
        "CREATE TABLE {SCHEMA}.workflow_outbox_event", "workflow_snapshot table",
    )
    outbox_block = bind_slice(
        source, "CREATE TABLE {SCHEMA}.workflow_outbox_event",
        "CREATE UNIQUE INDEX workflow_outbox_event_workflow_revision_uq", "workflow_outbox_event table",
    )
    delivery_block = bind_slice(
        source, "CREATE TABLE {SCHEMA}.workflow_delivery_control",
        "CREATE INDEX workflow_delivery_control_next_attempt_idx", "workflow_delivery_control table",
    )
    table_blocks = {
        "workflow_snapshot": snapshot_block,
        "workflow_outbox_event": outbox_block,
        "workflow_delivery_control": delivery_block,
    }
    for constraint_name, table_name in constraint_owner.items():
        require(
            ("CONSTRAINT " + constraint_name + " CHECK") in table_blocks[table_name],
            f"CHECK constraint not bound to table: {constraint_name}",
        )
    for fk_name, (owning_ref, target_ref) in foreign_keys.items():
        owning_table, owning_column = owning_ref.split(".")
        ref_table, ref_column = target_ref.split(".")
        require(owning_table in table_blocks, f"foreign key owning table unknown: {fk_name}")
        binding = (
            "CONSTRAINT " + fk_name + " FOREIGN KEY (" + owning_column + ")\n    REFERENCES {SCHEMA}."
            + ref_table + "(" + ref_column + ")"
        )
        require(binding in table_blocks[owning_table], f"foreign key not bound: {fk_name}")


def expect_rejection(operation, description: str) -> None:
    try:
        operation()
    except AssertionError:
        return
    raise AssertionError(f"mutation did not fail closed: {description}")


def check_mutation_vectors(aidb_source: str, source: str, policy: dict[str, object]) -> None:
    """Pure in-memory negative mutations; every repaired class must fail closed."""
    missing_label = aidb_source.replace('branch_labels = ("aidb",)', "branch_labels = None")
    expect_rejection(lambda: check_aidb_branch_source(missing_label), "AIDB branch label missing")

    substituted_label = aidb_source.replace('branch_labels = ("aidb",)', 'branch_labels = ("other",)')
    expect_rejection(lambda: check_aidb_branch_source(substituted_label), "AIDB branch label substituted")

    duplicated_label = aidb_source.replace(
        'branch_labels = ("aidb",)', 'branch_labels = ("aidb",)\nbranch_labels = ("aidb",)',
    )
    expect_rejection(lambda: check_aidb_branch_source(duplicated_label), "AIDB branch label duplicated")

    added_schema_grant = copy.deepcopy(policy)
    added_schema_grant["grants"]["delivery"]["schema"] = ["USAGE", "CREATE"]
    expect_rejection(lambda: check_policy(added_schema_grant), "delivery schema privilege added")

    added_function_grant = copy.deepcopy(policy)
    added_function_grant["grants"]["reader"]["functions"] = {"apply_workflow_transition_v1": ["EXECUTE"]}
    expect_rejection(lambda: check_policy(added_function_grant), "reader function privilege added")

    missing_function = source.replace(
        "CREATE FUNCTION {SCHEMA}.reject_workflow_outbox_mutation_v1(",
        "CREATE FUNCTION {SCHEMA}.renamed_reject_fn_v1(",
    )
    expect_rejection(
        lambda: check_named_object_bindings(missing_function, policy["objects"]),
        "function identity missing",
    )

    substituted_trigger = source.replace(
        "BEFORE UPDATE OR DELETE ON {SCHEMA}.workflow_outbox_event",
        "BEFORE UPDATE OR DELETE ON {SCHEMA}.workflow_snapshot",
    )
    expect_rejection(
        lambda: check_named_object_bindings(substituted_trigger, policy["objects"]),
        "trigger wrongly bound table",
    )

    substituted_index = source.replace(
        "workflow_delivery_control_next_attempt_idx\n  ON {SCHEMA}.workflow_delivery_control (next_attempt_at)",
        "workflow_delivery_control_next_attempt_idx\n  ON {SCHEMA}.workflow_delivery_control (updated_at)",
    )
    expect_rejection(
        lambda: check_named_object_bindings(substituted_index, policy["objects"]),
        "index wrongly bound column",
    )

    missing_constraint = source.replace(
        "CONSTRAINT workflow_snapshot_revision_ck CHECK",
        "CONSTRAINT workflow_snapshot_revision_renamed_ck CHECK",
    )
    expect_rejection(
        lambda: check_named_object_bindings(missing_constraint, policy["objects"]),
        "CHECK constraint identity missing",
    )

    substituted_fk = source.replace(
        "REFERENCES {SCHEMA}.workflow_snapshot(workflow_id)",
        "REFERENCES {SCHEMA}.workflow_delivery_control(workflow_id)",
    )
    expect_rejection(
        lambda: check_named_object_bindings(substituted_fk, policy["objects"]),
        "foreign key wrongly bound target",
    )


def check_callers_and_registry() -> None:
    nix = NIX.read_text(encoding="utf-8")
    shell = MIGRATION_TEST.read_text(encoding="utf-8")
    require(nix.count("upgrade aidb@head") == 1, "Nix must select one AIDB head")
    require("upgrade head" not in nix and "b2_workflow_shadow" not in nix, "Nix branch isolation")
    require(shell.count("upgrade aidb@head") == 2, "two qualified forward calls")
    require(shell.count("downgrade aidb@-1") == 1, "one qualified one-step rollback")
    require("upgrade head" not in shell and "downgrade -1" not in shell, "unqualified target")
    require("b2_workflow_shadow" not in shell, "canonical test must not select B2")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    entries = [item for item in registry["checks"] if item["id"] == "workflow-shadow-migration-b2-m1a"]
    require(len(entries) == 1, "one validation registration")
    entry = entries[0]
    require(tuple(entry["trigger_paths"]) == AUTHORIZED_PATHS, "exact seven trigger paths")
    require(entry["command"] == ["python3", "scripts/testing/test-workflow-shadow-migration.py"], "offline command")
    require(entry["timeout_seconds"] <= 30, "static timeout")


def run_static() -> None:
    aidb_source = AIDB_MIGRATION.read_text(encoding="utf-8")
    source = MIGRATION.read_text(encoding="utf-8")
    policy_bytes = POLICY.read_bytes()
    policy = json.loads(policy_bytes)
    check_aidb_branch_source(aidb_source)
    check_python_surface(source)
    check_policy(policy)
    policy_digest = hashlib.sha256(policy_bytes).hexdigest()
    require(f'PRIVILEGE_POLICY_SHA256 = "{policy_digest}"' in source, "privilege policy digest binding")
    check_named_object_bindings(source, policy["objects"])
    check_mutation_vectors(aidb_source, source, policy)
    check_callers_and_registry()
    own_tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    prohibited_imports = {"socket", "subprocess", "psycopg", "psycopg2", "sqlalchemy", "alembic", "os"}
    found = {
        alias.name.split(".")[0]
        for node in ast.walk(own_tree) if isinstance(node, ast.Import) for alias in node.names
    }
    found.update(
        node.module.split(".")[0] for node in ast.walk(own_tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    require(not (found & prohibited_imports), "offline oracle gained process/network/database imports")
    require(len(M1E_REQUIRED_EVIDENCE) == 16 and len(set(M1E_REQUIRED_EVIDENCE)) == 16,
            "future M1E evidence plan is incomplete")
    print("B2-M1A static oracle: PASS; authority=legacy_json_authoritative coverage=migration_artifacts_static_only")


def integration_refusal(dsn_file: str | None, evidence_token: str | None) -> int:
    # Validate every gate before reading the credential file or importing any future database driver.
    if not dsn_file or not evidence_token:
        print("M1E_NOT_AUTHORIZED")
        return 77
    token_match = re.fullmatch(r"m1e:([0-9a-f]{64}):([0-9]{10})", evidence_token)
    if token_match is None or int(token_match.group(2)) <= int(time.time()):
        print("M1E_NOT_AUTHORIZED")
        return 77
    path = Path(dsn_file)
    try:
        metadata = path.lstat()
    except OSError:
        print("M1E_NOT_AUTHORIZED")
        return 77
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink() or stat.S_IMODE(metadata.st_mode) != 0o600:
        print("M1E_NOT_AUTHORIZED")
        return 77
    # M1A deliberately contains no database driver. M1E must replace this refusal under a new grant.
    print("M1E_NOT_AUTHORIZED")
    return 77


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--integration", action="store_true")
    parser.add_argument("--dsn-file")
    parser.add_argument("--evidence-token")
    args = parser.parse_args()
    if args.integration:
        return integration_refusal(args.dsn_file, args.evidence_token)
    if args.dsn_file or args.evidence_token:
        print("M1E_NOT_AUTHORIZED")
        return 77
    run_static()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

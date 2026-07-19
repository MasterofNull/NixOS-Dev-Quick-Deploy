"""Create the dormant Foundation B2 workflow shadow branch.

Revision ID: 20260718_01_b2_shadow
Revises: None
Create Date: 2026-07-18

This artifact is intentionally unreachable from the deployed ``aidb@head`` target.
"""

from alembic import context, op


revision = "20260718_01_b2_shadow"
down_revision = None
branch_labels = ("b2_workflow_shadow",)
depends_on = None

PRIVILEGE_POLICY_SHA256 = "ff141f3685dfd72e6147cb70d758f26abb6b0826f759ce8f9a59353c8c1eeb43"
OWNER = "aq_b2_shadow_owner_v1"
WRITER = "aq_b2_shadow_writer_v1"
DELIVERY = "aq_b2_shadow_delivery_v1"
READER = "aq_b2_shadow_reader_v1"
SCHEMA = "aq_b2_workflow_shadow_v1"


class DestructiveDowngradeProhibited(RuntimeError):
    """Stable refusal for a retention-preserving, forward-only migration."""


def upgrade() -> None:
    x_args = context.get_x_argument(as_dictionary=True)
    if (
        revision != "20260718_01_b2_shadow"
        or down_revision is not None
        or branch_labels != ("b2_workflow_shadow",)
        or context.get_context().dialect.name != "postgresql"
        or x_args.get("b2_policy_sha256") != PRIVILEGE_POLICY_SHA256
    ):
        raise RuntimeError("B2_MIGRATION_PREFLIGHT_REJECTED")
    # All controls are transaction-local; Alembic's canonical env preserves transactional DDL.
    op.execute("SET LOCAL lock_timeout = '2s'")
    op.execute("SET LOCAL statement_timeout = '10s'")
    op.execute("SET LOCAL idle_in_transaction_session_timeout = '15s'")
    op.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended('20260718_01_b2_shadow', 0))"
    )
    op.execute(
        """
DO $preflight$
DECLARE
  owner_record pg_catalog.pg_roles%ROWTYPE;
  bootstrap_record pg_catalog.pg_roles%ROWTYPE;
  role_name text;
BEGIN
  IF current_user !~ '^aq_b2_m1e_bootstrap_[a-z0-9_]+$' THEN
    RAISE EXCEPTION 'B2_BOOTSTRAP_IDENTITY_INVALID';
  END IF;
  SELECT * INTO bootstrap_record FROM pg_catalog.pg_roles WHERE rolname = current_user;
  IF NOT FOUND OR NOT bootstrap_record.rolcanlogin OR NOT bootstrap_record.rolcreaterole
     OR bootstrap_record.rolsuper OR bootstrap_record.rolcreatedb
     OR bootstrap_record.rolreplication OR bootstrap_record.rolbypassrls THEN
    RAISE EXCEPTION 'B2_BOOTSTRAP_POLICY_INVALID';
  END IF;
  SELECT * INTO owner_record FROM pg_catalog.pg_roles
    WHERE rolname = 'aq_b2_shadow_owner_v1';
  IF NOT FOUND OR owner_record.rolcanlogin OR owner_record.rolsuper
     OR owner_record.rolcreatedb OR owner_record.rolcreaterole
     OR owner_record.rolreplication OR owner_record.rolbypassrls THEN
    RAISE EXCEPTION 'B2_OWNER_POLICY_INVALID';
  END IF;
  IF NOT pg_catalog.has_database_privilege('aq_b2_shadow_owner_v1', current_database(), 'CREATE') THEN
    RAISE EXCEPTION 'B2_OWNER_DATABASE_CREATE_MISSING';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_auth_members memberships
    JOIN pg_catalog.pg_roles owned_role ON owned_role.oid = memberships.roleid
    WHERE owned_role.rolname = 'aq_b2_shadow_owner_v1'
  ) THEN
    RAISE EXCEPTION 'B2_OWNER_MEMBERSHIP_PREEXISTS';
  END IF;
  IF pg_catalog.has_database_privilege('PUBLIC', current_database(), 'CREATE') THEN
    RAISE EXCEPTION 'B2_PUBLIC_DATABASE_CREATE_PRESENT';
  END IF;
  FOREACH role_name IN ARRAY ARRAY[
    'aq_b2_shadow_writer_v1', 'aq_b2_shadow_delivery_v1', 'aq_b2_shadow_reader_v1'
  ] LOOP
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
      RAISE EXCEPTION 'B2_ROLE_COLLISION';
    END IF;
  END LOOP;
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = 'aq_b2_workflow_shadow_v1') THEN
    RAISE EXCEPTION 'B2_SCHEMA_COLLISION';
  END IF;
END
$preflight$;
"""
    )
    for role in (WRITER, DELIVERY, READER):
        op.execute(
            f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOCREATEDB "
            "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
        )
    # Role grants default to no admin option; RESET/REVOKE removes the temporary membership.
    op.execute(f"GRANT {OWNER} TO CURRENT_USER")
    op.execute(f"SET LOCAL ROLE {OWNER}")
    op.execute(f"CREATE SCHEMA {SCHEMA} AUTHORIZATION {OWNER}")
    op.execute(
        f"""
CREATE TABLE {SCHEMA}.workflow_snapshot (
  workflow_id varchar(128) PRIMARY KEY,
  revision integer NOT NULL,
  status text NOT NULL CHECK (status IN ('started', 'running', 'completed', 'failed', 'cancelled')),
  terminal boolean NOT NULL,
  phase_token varchar(71) NOT NULL,
  phase_index integer NOT NULL CHECK (phase_index BETWEEN 0 AND 13),
  action text NOT NULL CHECK (action IN ('start', 'advance', 'complete', 'fail', 'cancel')),
  last_event_id varchar(128) NOT NULL,
  live_commit_digest varchar(71) NOT NULL,
  occurred_at timestamptz NOT NULL,
  CONSTRAINT workflow_snapshot_revision_ck CHECK (revision BETWEEN 1 AND 100000),
  CONSTRAINT workflow_snapshot_digest_ck CHECK (
    last_event_id ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{{0,127}}$' AND
    live_commit_digest ~ '^sha256:[0-9a-f]{{64}}$'
  ),
  CONSTRAINT workflow_snapshot_terminal_ck CHECK (
    terminal = (status IN ('completed', 'failed', 'cancelled'))
  )
)
"""
    )
    op.execute(
        f"""
CREATE TABLE {SCHEMA}.workflow_outbox_event (
  event_id varchar(128) PRIMARY KEY,
  workflow_id varchar(128) NOT NULL,
  revision integer NOT NULL,
  live_commit_digest varchar(71) NOT NULL,
  event_json jsonb NOT NULL,
  transaction_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
  CONSTRAINT workflow_outbox_event_revision_ck CHECK (revision BETWEEN 1 AND 100000),
  CONSTRAINT workflow_outbox_event_digest_ck CHECK (
    event_id ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{{0,127}}$' AND
    live_commit_digest ~ '^sha256:[0-9a-f]{{64}}$'
  ),
  CONSTRAINT workflow_outbox_event_size_ck CHECK (octet_length(event_json::text) <= 2048),
  CONSTRAINT workflow_outbox_event_schema_ck CHECK (
    jsonb_typeof(event_json) = 'object' AND
    event_json ?& ARRAY['schema_version', 'event_id', 'workflow_id', 'revision'] AND
    event_json ->> 'schema_version' = 'aq.workflow-shadow-event.v1' AND
    event_json ->> 'event_id' = event_id AND
    event_json ->> 'workflow_id' = workflow_id AND
    event_json ->> 'revision' = revision::text
  ),
  CONSTRAINT workflow_outbox_snapshot_fk FOREIGN KEY (workflow_id)
    REFERENCES {SCHEMA}.workflow_snapshot(workflow_id)
)
"""
    )
    op.execute(
        f"""
CREATE UNIQUE INDEX workflow_outbox_event_workflow_revision_uq
  ON {SCHEMA}.workflow_outbox_event (workflow_id, revision)
"""
    )
    op.execute(
        f"""
CREATE TABLE {SCHEMA}.workflow_delivery_control (
  event_id varchar(128) PRIMARY KEY,
  lease_epoch integer NOT NULL DEFAULT 0,
  attempt_count integer NOT NULL DEFAULT 0,
  next_attempt_at timestamptz,
  disposition text NOT NULL DEFAULT 'pending',
  typed_error text,
  updated_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
  CONSTRAINT workflow_delivery_control_lease_ck CHECK (lease_epoch BETWEEN 0 AND 1000000),
  CONSTRAINT workflow_delivery_control_attempt_ck CHECK (attempt_count BETWEEN 0 AND 1000),
  CONSTRAINT workflow_delivery_control_disposition_ck CHECK (
    disposition IN ('pending', 'delivering', 'delivered', 'parked')
  ),
  CONSTRAINT workflow_delivery_control_error_ck CHECK (
    typed_error IS NULL OR typed_error IN (
      'disabled', 'deadline_exceeded', 'database_unavailable', 'schema_unready',
      'schema_invalid', 'privacy_rejected', 'cas_mismatch', 'revision_gap',
      'event_collision', 'terminal_conflict', 'transaction_failed', 'projection_gap',
      'integrity_failed', 'disk_budget_exceeded', 'parked'
    )
  ),
  CONSTRAINT workflow_delivery_outbox_fk FOREIGN KEY (event_id)
    REFERENCES {SCHEMA}.workflow_outbox_event(event_id)
)
"""
    )
    op.execute(
        f"""
CREATE INDEX workflow_delivery_control_next_attempt_idx
  ON {SCHEMA}.workflow_delivery_control (next_attempt_at)
"""
    )
    op.execute(
        f"""
CREATE FUNCTION {SCHEMA}.reject_workflow_outbox_mutation_v1()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, {SCHEMA}
AS $function$
BEGIN
  RAISE EXCEPTION 'B2_OUTBOX_IMMUTABLE';
END
$function$
"""
    )
    op.execute(
        f"""
CREATE TRIGGER workflow_outbox_immutable_v1
BEFORE UPDATE OR DELETE ON {SCHEMA}.workflow_outbox_event
FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.reject_workflow_outbox_mutation_v1()
"""
    )
    op.execute(
        f"""
CREATE FUNCTION {SCHEMA}.apply_workflow_transition_v1(
  p_event_id varchar(128), p_workflow_id varchar(128),
  p_expected_revision integer, p_revision integer, p_status text,
  p_terminal boolean, p_phase_token varchar(71), p_phase_index integer,
  p_action text, p_live_commit_digest varchar(71),
  p_occurred_at timestamptz, p_event_json jsonb
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, {SCHEMA}
AS $function$
DECLARE current_row {SCHEMA}.workflow_snapshot%ROWTYPE;
BEGIN
  IF p_event_id !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{{0,127}}$'
     OR p_live_commit_digest !~ '^sha256:[0-9a-f]{{64}}$'
     OR p_workflow_id !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{{0,127}}$'
     OR p_status NOT IN ('started', 'running', 'completed', 'failed', 'cancelled')
     OR p_terminal <> (p_status IN ('completed', 'failed', 'cancelled'))
     OR p_phase_token IS NULL OR p_phase_token !~ '^sha256:[0-9a-f]{{64}}$'
     OR p_phase_index IS NULL OR p_phase_index NOT BETWEEN 0 AND 13
     OR p_action IS NULL OR p_action NOT IN ('start', 'advance', 'complete', 'fail', 'cancel')
     OR pg_catalog.jsonb_typeof(p_event_json) <> 'object'
     OR NOT (p_event_json ?& ARRAY[
       'schema_version', 'event_id', 'vertical_id', 'workflow_id', 'expected_revision',
       'revision', 'transition_kind', 'status', 'phase_token', 'phase_index', 'action',
       'terminal', 'live_commit_digest', 'occurred_at', 'writer_identity', 'writer_version'
     ])
     OR EXISTS (
       SELECT 1 FROM pg_catalog.jsonb_object_keys(p_event_json) AS supplied(key)
       WHERE supplied.key <> ALL (ARRAY[
         'schema_version', 'event_id', 'vertical_id', 'workflow_id', 'expected_revision',
         'revision', 'transition_kind', 'status', 'phase_token', 'phase_index', 'action',
         'terminal', 'live_commit_digest', 'occurred_at', 'writer_identity', 'writer_version'
       ])
     )
     OR p_event_json ->> 'schema_version' <> 'aq.workflow-shadow-event.v1'
     OR p_event_json ->> 'event_id' <> p_event_id
     OR p_event_json ->> 'vertical_id' <> 'workflow-run-task'
     OR p_event_json ->> 'workflow_id' <> p_workflow_id
     OR p_event_json ->> 'expected_revision' <> p_expected_revision::text
     OR p_event_json ->> 'revision' <> p_revision::text
     OR p_event_json ->> 'transition_kind' NOT IN (
       'run_start', 'manual_phase_transition', 'terminal_completion'
     )
     OR (p_terminal AND p_event_json ->> 'transition_kind' <> 'terminal_completion')
     OR (NOT p_terminal AND p_event_json ->> 'transition_kind' = 'terminal_completion')
     OR p_event_json ->> 'status' <> p_status
     OR p_event_json ->> 'phase_token' IS DISTINCT FROM p_phase_token
     OR p_event_json ->> 'phase_index' IS DISTINCT FROM p_phase_index::text
     OR p_event_json ->> 'action' IS DISTINCT FROM p_action
     OR (p_terminal AND p_action NOT IN ('complete', 'fail', 'cancel'))
     OR (NOT p_terminal AND p_action NOT IN ('start', 'advance'))
     OR p_event_json ->> 'terminal' <> pg_catalog.lower(p_terminal::text)
     OR p_event_json ->> 'live_commit_digest' <> p_live_commit_digest
     OR p_event_json ->> 'writer_identity' !~ '^[A-Za-z0-9._:-]{{1,64}}$'
     OR p_event_json ->> 'writer_version' !~ '^[A-Za-z0-9._-]{{1,32}}$'
     OR pg_catalog.octet_length(p_event_json::text) > 2048 THEN
    RETURN 'contract_rejected';
  END IF;
  IF p_revision <> p_expected_revision + 1 OR p_revision NOT BETWEEN 1 AND 100000 THEN
    RETURN 'revision_invalid';
  END IF;
  SELECT * INTO current_row FROM {SCHEMA}.workflow_snapshot
    WHERE workflow_id = p_workflow_id FOR UPDATE;
  IF NOT FOUND THEN
    IF p_expected_revision <> 0 OR p_revision <> 1 THEN RETURN 'gap'; END IF;
    INSERT INTO {SCHEMA}.workflow_snapshot VALUES (
      p_workflow_id, p_revision, p_status, p_terminal, p_phase_token,
      p_phase_index, p_action, p_event_id, p_live_commit_digest, p_occurred_at
    );
  ELSE
    IF current_row.revision = p_revision
       AND current_row.last_event_id = p_event_id
       AND current_row.live_commit_digest = p_live_commit_digest THEN
      RETURN 'exact_replay';
    ELSIF current_row.terminal THEN RETURN 'terminal_conflict';
    ELSIF current_row.revision < p_expected_revision THEN RETURN 'gap';
    ELSIF current_row.revision > p_expected_revision THEN RETURN 'stale';
    ELSIF current_row.revision = p_revision THEN RETURN 'collision';
    END IF;
    UPDATE {SCHEMA}.workflow_snapshot SET
      revision = p_revision, status = p_status, terminal = p_terminal,
      phase_token = p_phase_token, phase_index = p_phase_index, action = p_action,
      last_event_id = p_event_id, live_commit_digest = p_live_commit_digest,
      occurred_at = p_occurred_at
    WHERE workflow_id = p_workflow_id AND revision = p_expected_revision;
    IF NOT FOUND THEN RETURN 'stale'; END IF;
  END IF;
  INSERT INTO {SCHEMA}.workflow_outbox_event (
    event_id, workflow_id, revision, live_commit_digest, event_json
  ) VALUES (p_event_id, p_workflow_id, p_revision, p_live_commit_digest, p_event_json);
  INSERT INTO {SCHEMA}.workflow_delivery_control (event_id) VALUES (p_event_id);
  RETURN 'accepted';
END
$function$
"""
    )
    op.execute(f"REVOKE ALL ON SCHEMA {SCHEMA} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA {SCHEMA} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {SCHEMA} FROM PUBLIC")
    op.execute(f"GRANT USAGE ON SCHEMA {SCHEMA} TO {WRITER}, {DELIVERY}, {READER}")
    op.execute(
        f"GRANT EXECUTE ON FUNCTION {SCHEMA}.apply_workflow_transition_v1("
        "varchar, varchar, integer, integer, text, boolean, varchar, integer, text, "
        f"varchar, timestamptz, jsonb) TO {WRITER}"
    )
    op.execute(f"GRANT SELECT ON {SCHEMA}.workflow_outbox_event TO {DELIVERY}")
    op.execute(f"GRANT SELECT, UPDATE ON {SCHEMA}.workflow_delivery_control TO {DELIVERY}")
    op.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {SCHEMA} TO {READER}")
    op.execute("RESET ROLE")
    op.execute(f"REVOKE {OWNER} FROM CURRENT_USER")
    op.execute(
        f"""
DO $postflight$
BEGIN
  IF pg_catalog.pg_has_role(current_user, 'aq_b2_shadow_owner_v1', 'MEMBER') THEN
    RAISE EXCEPTION 'B2_BOOTSTRAP_MEMBERSHIP_RETAINED';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_auth_members memberships
    JOIN pg_catalog.pg_roles owned_role ON owned_role.oid = memberships.roleid
    WHERE owned_role.rolname = 'aq_b2_shadow_owner_v1'
  ) THEN
    RAISE EXCEPTION 'B2_OWNER_MEMBERSHIP_RETAINED';
  END IF;
END
$postflight$;
"""
    )


def downgrade() -> None:
    raise DestructiveDowngradeProhibited("B2_DESTRUCTIVE_DOWNGRADE_PROHIBITED")

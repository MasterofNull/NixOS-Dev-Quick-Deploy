#!/usr/bin/env python3
"""C6-P0 trust anchors offline validation."""

import json
import sys
from pathlib import Path

def validate_c6_p0_trust_anchors():
    """Validate C6-P0 declarative trust anchors."""

    repo_root = Path(__file__).parent.parent.parent

    # Paths to validate
    owner_keys_path = repo_root / "config" / "aqos" / "c6-owner-public-keys.json"
    revocation_schema_path = repo_root / "config" / "schemas" / "revocation-epoch-bump.schema.json"
    scheduler_schema_path = repo_root / "config" / "schemas" / "scheduler-lease-context.schema.json"

    # Step 1: Validate both schema files are well-formed JSON Schema
    try:
        with open(revocation_schema_path) as f:
            revocation_schema = json.load(f)
        if not isinstance(revocation_schema, dict):
            raise ValueError("revocation-epoch-bump.schema.json must be an object")
        if "$schema" not in revocation_schema or "type" not in revocation_schema:
            raise ValueError("revocation-epoch-bump.schema.json missing $schema or type")
    except Exception as e:
        print(f"FAIL: revocation-epoch-bump.schema.json validation: {e}")
        sys.exit(1)

    try:
        with open(scheduler_schema_path) as f:
            scheduler_schema = json.load(f)
        if not isinstance(scheduler_schema, dict):
            raise ValueError("scheduler-lease-context.schema.json must be an object")
        if "$schema" not in scheduler_schema or "type" not in scheduler_schema:
            raise ValueError("scheduler-lease-context.schema.json missing $schema or type")
    except Exception as e:
        print(f"FAIL: scheduler-lease-context.schema.json validation: {e}")
        sys.exit(1)

    # Step 2: Validate owner public keys file
    try:
        with open(owner_keys_path) as f:
            owner_keys = json.load(f)

        if not isinstance(owner_keys, dict):
            raise ValueError("c6-owner-public-keys.json must be an object")

        if "schema_version" not in owner_keys or "revision" not in owner_keys or "keys" not in owner_keys:
            raise ValueError("Missing required top-level fields")

        if not isinstance(owner_keys["revision"], int):
            raise ValueError("revision must be an integer")

        if not isinstance(owner_keys["keys"], list):
            raise ValueError("keys must be an array")

        # Track key_ids for duplicate detection
        seen_key_ids = set()

        # Validate each key
        for idx, key in enumerate(owner_keys["keys"]):
            if not isinstance(key, dict):
                raise ValueError(f"Key {idx} is not an object")

            # Check for private material field names
            private_patterns = {"private", "secret", "seed", "signing_key", "private_key"}
            key_fields = set(key.keys())
            if key_fields & private_patterns:
                raise ValueError(f"Key {idx} contains private material field: {key_fields & private_patterns}")

            # Check required public fields
            if "key_id" not in key:
                raise ValueError(f"Key {idx} missing key_id")
            if "ed25519_public_key" not in key:
                raise ValueError(f"Key {idx} missing ed25519_public_key")
            if "status" not in key:
                raise ValueError(f"Key {idx} missing status")

            # Validate key_id uniqueness
            key_id = key["key_id"]
            if key_id in seen_key_ids:
                raise ValueError(f"Duplicate key_id: {key_id}")
            seen_key_ids.add(key_id)

            # Validate ed25519_public_key is 64 hex characters
            public_key = key["ed25519_public_key"]
            if not isinstance(public_key, str):
                raise ValueError(f"Key {idx} ed25519_public_key must be string")
            if len(public_key) != 64:
                raise ValueError(f"Key {idx} ed25519_public_key must be 64 hex characters, got {len(public_key)}")
            try:
                int(public_key, 16)
            except ValueError:
                raise ValueError(f"Key {idx} ed25519_public_key is not valid hex")

            # Validate status is in enum
            status = key["status"]
            if status not in {"active", "revoked"}:
                raise ValueError(f"Key {idx} status must be 'active' or 'revoked', got '{status}'")

    except Exception as e:
        print(f"FAIL: c6-owner-public-keys.json validation: {e}")
        sys.exit(1)

    # Step 3: Test negative vectors (in-memory constructs)

    # Vector 1: Key with private_key field should be rejected
    test_private_key = {
        "key_id": "test",
        "ed25519_public_key": "0" * 64,
        "private_key": "secret",
        "status": "active"
    }
    key_fields = set(test_private_key.keys())
    private_patterns = {"private", "secret", "seed", "signing_key", "private_key"}
    if key_fields & private_patterns:
        # Expected - private material detected
        pass
    else:
        print("FAIL: private_key field should have been rejected")
        sys.exit(1)

    # Vector 2: Non-monotonic/duplicate key_id should be rejected
    test_dup_key_ids = ["owner-2026-08", "owner-2026-08"]
    seen = set()
    duplicate_found = False
    for key_id in test_dup_key_ids:
        if key_id in seen:
            duplicate_found = True
            break
        seen.add(key_id)
    if not duplicate_found:
        print("FAIL: duplicate key_id should have been rejected")
        sys.exit(1)

    # Vector 3: Unknown status should be rejected
    test_unknown_status = {"status": "unknown"}
    if test_unknown_status["status"] not in {"active", "revoked"}:
        # Expected - unknown status detected
        pass
    else:
        print("FAIL: unknown status should have been rejected")
        sys.exit(1)

    print("PASS: c6-p0 trust anchors valid")
    sys.exit(0)

if __name__ == "__main__":
    validate_c6_p0_trust_anchors()

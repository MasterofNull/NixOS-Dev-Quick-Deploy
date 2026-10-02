#!/usr/bin/env python3
"""Transactional delegation-registry writer for the delegate-to-* shell wrappers.

  registry-update.py set    <registry.jsonl> <task_id> <field> <value>
  registry-update.py append <registry.jsonl> <json-row>

All values arrive as argv (never shell-parsed). Writes go through TaskRegistry's
shared lock + atomic replace, so concurrent readers never see a truncated file.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from task_registry import TaskRegistry  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    op, registry = argv[0], Path(argv[1])
    reg = TaskRegistry(registry.parent)
    reg.registry_file = registry
    if op == "set" and len(argv) == 5:
        task_id, field, value = argv[2:5]
        try:
            parsed = int(value)
        except ValueError:
            parsed = value
        reg.update_fields_atomic(task_id, {field: parsed})
        return 0
    if op == "append" and len(argv) == 3:
        reg.append_row_atomic(json.loads(argv[2]))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

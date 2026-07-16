# Gemini Quality Review — seed-rag-knowledge.py
**Date**: 2026-07-12  **Agent**: Antigravity/Gemini  **Role**: Reviewer

## Verdict
APPROVE-WITH-AMENDMENTS

---

## 1. Quality Assessment

We have reviewed `scripts/data/seed-rag-knowledge.py` and evaluated the quality of the seed dataset, text-embedding construction, and the database-cleanup logic.

### A. Embedding Construction (`_text_for_embed()`)
*   **Finding:** The function `_text_for_embed` builds text for semantic retrieval. However, it currently omits `anti_patterns` for `best-practices` and `failure_examples` for `skills-patterns`.
*   **Impact:** This reduces BGE-M3's ability to recall relevant entries for negative search queries (e.g. searching "how to avoid port hardcoding" or "common AppArmor failure cases" will not match the anti-patterns list directly).
*   **Recommended Amendment:** Modify `_text_for_embed()` to append these negative examples.

### B. Cleanup Logic (`_clear_wrong_type_points()`)
*   **Finding:** The cleanup scrolls through the collection with a hard limit of 200 points.
*   **Impact:** If there are more than 200 wrong-schema points in the database, the scroll will return only the first 200, leaving older pollution in place.
*   **Recommended Amendment:** Implement a basic scroll loop or add a warning if the length of returned points equals the limit.

### C. Seeding Dataset Completeness
*   **Finding:** The current seed set has a rich selection (86 error-solutions, 7 skills, 22 best-practices). However, several critical issues from recent session history (`issues-backlog.md`) are missing.
*   **Recommended Amendment:** Add the following three recent issues to `ERROR_SOLUTIONS` or `BEST_PRACTICES`:
    1.  **Monitor Python Env Dependency (Error)**: Services running `aq-qa` require `pydantic` in their python env (e.g. `dag_manager.py` imports).
    2.  **DBus Broker Restart Timeout (Error/Practice)**: NixOS reload of system dbus-broker hangs if dbus-daemon was active previously because the broker's notification is not supported by the old daemon.
    3.  **Exploration Stagnation in Analysis (Error)**: Stagnation guard triggering prematurely on long analysis-only tasks due to lacking forced completion exit criteria.

---

## 2. Proposed Amendments (Code Patches)

### Patch 1: Enhance `_text_for_embed` to include negative patterns
```python
def _text_for_embed(record: dict, collection: str) -> str:
    """Build the text that should be embedded for semantic search.
    Includes examples/anti_patterns to improve BGE-M3 recall for natural
    language queries (Gemini review amendment 2026-07-12).
    """
    if collection == "error-solutions":
        return (
            f"Error: {record['error_type']} - {record['error_message']} "
            f"Context: {record['context']} Solution: {record['solution']}"
        )
    if collection == "skills-patterns":
        text = f"Skill: {record['skill_name']} - {record['description']} Usage: {record['usage_pattern']}"
        if record.get("success_examples"):
            text += f" Success Examples: {' '.join(record['success_examples'])}"
        if record.get("failure_examples"):
            text += f" Failure/Anti-patterns: {' '.join(record['failure_examples'])}"
        return text
    if collection == "best-practices":
        text = f"Best Practice: {record['title']} ({record['category']}) {record['description']}"
        if record.get("examples"):
            text += f" Examples: {' '.join(record['examples'])}"
        if record.get("anti_patterns"):
            text += f" Anti-patterns: {' '.join(record['anti_patterns'])}"
        return text
    return json.dumps(record)
```

### Patch 2: Add pagination check to `_clear_wrong_type_points`
```python
def _clear_wrong_type_points(collection: str, dry_run: bool = False) -> int:
    """Delete points in error-solutions that have memory_id field (wrong schema type)."""
    if collection != "error-solutions":
        return 0
    url = f"{QDRANT_URL}/collections/{collection}/points/scroll"

    total_deleted = 0
    next_offset = None

    while True:
        body = {"limit": 100, "with_payload": ["memory_id"]}
        if next_offset:
            body["offset"] = next_offset

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())

        res_data = result.get("result", {})
        points = res_data.get("points", [])
        wrong_ids = [p["id"] for p in points if "memory_id" in p.get("payload", {})]

        if wrong_ids:
            if dry_run:
                print(f"  [dry-run] would delete {len(wrong_ids)} wrong-type points from {collection}")
                total_deleted += len(wrong_ids)
            else:
                del_url = f"{QDRANT_URL}/collections/{collection}/points/delete"
                _http_post(del_url, {"points": wrong_ids})
                print(f"  deleted {len(wrong_ids)} wrong-type points from {collection}")
                total_deleted += len(wrong_ids)

        next_offset = res_data.get("next_page_offset")
        if not next_offset or len(points) < 100:
            break

    if total_deleted == 0:
        print(f"  no wrong-type points found in {collection}")
    return total_deleted
```

### Patch 3: Recent Issues to Seed
Add the following entries to `ERROR_SOLUTIONS` in `seed-rag-knowledge.py`:
```python
    {
        "error_type": "monitor_python_env_missing_packages",
        "error_message": "aq-qa harness fails with ImportError when called via systemd service",
        "context": "ai-stack-health-monitor.service running aq-qa — imports pydantic/pyyaml which are missing from standard packages list",
        "solution": "Define systemd service Python environment with monitorPython containing all needed testing dependencies including pydantic and pyyaml.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": 1783582992,
        "last_used": 1783582992,
        "confidence_score": 0.95
    },
    {
        "error_type": "dbus_broker_reload_timeout",
        "error_message": "dbus-broker.service reload times out during nixos-rebuild switch",
        "context": "Transitioning system from dbus-daemon to dbus-broker — reload operation blocks waiting for broker-style notify-reload from old daemon",
        "solution": "Manually restart both system and user dbus-broker-launch.service once to bring up broker, thereafter reloads work normally.",
        "solution_verified": True,
        "success_count": 1,
        "failure_count": 0,
        "first_seen": 1783582992,
        "last_used": 1783582992,
        "confidence_score": 0.95
    }
```

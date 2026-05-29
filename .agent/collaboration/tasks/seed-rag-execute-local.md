# Task: Execute seed-rag-knowledge.py and verify ingestion
Role: implementer
Priority: high
Assigned-to: local-agent

## Objective

Run the RAG knowledge seeding script, verify ingestion success, and validate improved semantic search coverage.

## Steps

1. **Dry-run first** to verify no errors:
   ```bash
   cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
   python3 scripts/data/seed-rag-knowledge.py --dry-run
   ```

2. **Run with --clear-wrong-type** to clear memory-type pollution from error-solutions then seed all 3 collections:
   ```bash
   python3 scripts/data/seed-rag-knowledge.py --clear-wrong-type
   ```

3. **Verify point counts** increased:
   ```bash
   for col in error-solutions skills-patterns best-practices; do
     curl -s "http://127.0.0.1:6333/collections/${col}" | python3 -c "import sys,json; d=json.load(sys.stdin); print('${col}:', d['result']['points_count'])"
   done
   ```

4. **Verify semantic scores improved** — embed a test query and check top scores per collection:
   ```bash
   python3 - <<'EOF'
   import json, urllib.request
   # embed test query
   req = urllib.request.Request(
       "http://127.0.0.1:8081/v1/embeddings",
       data=json.dumps({"input": "role function tool message silently dropped Qwen3", "model": "bge-m3"}).encode(),
       headers={"Content-Type": "application/json"}
   )
   with urllib.request.urlopen(req) as r:
       vec = json.loads(r.read())["data"][0]["embedding"]
   for col in ["error-solutions", "skills-patterns", "best-practices", "knowledge", "codebase-context"]:
       req2 = urllib.request.Request(
           f"http://127.0.0.1:6333/collections/{col}/points/query",
           data=json.dumps({"query": vec, "limit": 1, "with_payload": False}).encode(),
           headers={"Content-Type": "application/json"}
       )
       with urllib.request.urlopen(req2) as r2:
           pts = json.loads(r2.read())["result"]["points"]
           score = pts[0]["score"] if pts else 0
           print(f"{col}: {score:.4f}")
   EOF
   ```

5. **Check delegate rate** — should be improving:
   ```bash
   COORD_KEY=$(systemctl show ai-hybrid-coordinator --property=Environment 2>/dev/null | tr ' ' '\n' | grep -i "api_key\|API_KEY" | head -1 | cut -d= -f2-)
   curl -s "http://127.0.0.1:8003/stats/delegate?window_s=86400" -H "Authorization: Bearer $COORD_KEY"
   ```

## Success Criteria

- error-solutions: ≥ 12 points (was 36 wrong-type → should be ~12 correct entries)
- skills-patterns: ≥ 5 points (was 2)
- best-practices: ≥ 6 points (was 2)
- Test query "role function tool message silently dropped" scores ≥ 0.50 in error-solutions
- Test query "NixOS GPU layers ceiling VRAM" scores ≥ 0.50 in best-practices

## Report

Return a summary of:
- Final point counts per collection
- Pre/post score comparison for 2 test queries
- Any errors encountered and how resolved
- Delegate rate current value

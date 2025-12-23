# Discovery Pipeline - Quick Fix Guide
**Critical issues and 5-minute fixes**

---

## 🔴 CRITICAL: Set GitHub Token

**Problem**: All GitHub sources fail with rate limit errors.

**Fix**:
```bash
# 1. Get token: https://github.com/settings/tokens
#    Scopes: public_repo (read-only)

# 2. Set environment variable
export GITHUB_TOKEN=ghp_your_token_here

# 3. Make permanent
echo 'export GITHUB_TOKEN=ghp_your_token_here' >> ~/.bashrc
source ~/.bashrc

# 4. Re-run discovery
python3 scripts/discover-improvements.sh
```

**Verification**:
```bash
# Should see candidates, not errors
grep "Candidate Summary" docs/development/IMPROVEMENT-DISCOVERY-REPORT-$(date +%Y-%m-%d).md -A 10
```

---

## ⚠️ Remove Duplicate Source

**Problem**: r/LocalLLaMA appears twice in config.

**Fix**:
```bash
# Edit config/improvement-sources.json
# DELETE lines 50-53 (the lowercase one):

{
  "url": "https://www.reddit.com/r/localllama/",  // ❌ DELETE
  "type": "social",
  "weight": 0.08,
  "cadence_hours": 168
}
```

**Or automated**:
```bash
cat config/improvement-sources.json | jq 'map(select(.url != "https://www.reddit.com/r/localllama/"))' > config/improvement-sources.json.tmp
mv config/improvement-sources.json.tmp config/improvement-sources.json
```

---

## ⚠️ Remove Discord Sources

**Problem**: 6 Discord URLs always fail (require authentication).

**Fix**:
```bash
# Remove these entries from config/improvement-sources.json:
# - discord.com/invite/ollama
# - discord.gg/qdrant
# - discord.com/invite/huggingface
# - discord.gg/containers
# - discord.gg/nixos
# - discord.gg/localai

# Automated removal:
cat config/improvement-sources.json | jq 'map(select(.type != "forum"))' > config/improvement-sources.json.tmp
mv config/improvement-sources.json.tmp config/improvement-sources.json
```

**Verification**:
```bash
cat config/improvement-sources.json | jq '[.[] | select(.type == "forum")] | length'
# Should output: 0
```

---

## 💡 Quick Test

**Verify everything works**:
```bash
# 1. Clean slate
rm data/improvement-crawler-state.json

# 2. Run discovery
python3 scripts/discover-improvements.sh

# 3. Check report
cat docs/development/IMPROVEMENT-DISCOVERY-REPORT-$(date +%Y-%m-%d).md | grep -A 5 "Candidate Summary"

# 4. Verify dashboard sees it
bash scripts/generate-dashboard-data.sh --lite-mode
cat ~/.local/share/nixos-system-dashboard/keyword-signals.json | jq .candidates

# 5. Check dashboard
xdg-open http://localhost:8888/dashboard.html
# Look for "Discovery Signals" card
```

---

## Expected Output (After Fixes)

**Discovery Report**:
```markdown
## Candidate Summary (Scored)

### https://github.com/qdrant/qdrant/releases
- **Score:** 56.2
- **Repo:** qdrant/qdrant
- **Latest release:** v1.16.3
- **Stars:** 27767

### https://github.com/ggml-org/llama.cpp/releases
- **Score:** 54.8
- **Repo:** ggml-org/llama.cpp
- **Latest release:** b4439
- **Stars:** 72145
```

**keyword-signals.json**:
```json
{
  "candidates": [
    {
      "url": "https://github.com/qdrant/qdrant/releases",
      "score": 56.2,
      "repo": "qdrant/qdrant",
      "release": "v1.16.3"
    }
  ],
  "signals": [
    {
      "url": "https://www.reddit.com/r/LocalLLaMA/",
      "note": "social signal; requires corroboration"
    }
  ],
  "summary": {
    "candidate_count": 5,
    "signal_count": 4
  }
}
```

**Dashboard**: Shows "5 High-Value" badge with clickable links.

---

## Troubleshooting

### "No candidates met the score threshold"
- Check GitHub token is set: `echo $GITHUB_TOKEN`
- Verify token has public_repo scope
- Check rate limit: `curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/rate_limit`

### Dashboard shows empty lists
- Run discovery: `python3 scripts/discover-improvements.sh`
- Regenerate dashboard data: `bash scripts/generate-dashboard-data.sh`
- Check JSON exists: `ls -la ~/.local/share/nixos-system-dashboard/keyword-signals.json`

### State file prevents updates
- Delete state: `rm data/improvement-crawler-state.json`
- Or edit specific source: `jq 'del(."https://github.com/qdrant/qdrant/releases")' data/improvement-crawler-state.json`

---

**Total Fix Time**: ~5 minutes

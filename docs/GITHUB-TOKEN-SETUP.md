# GitHub Token Setup for Discovery Pipeline
**Required for**: GitHub API access (avoiding rate limits)
**Time**: 2 minutes

---

## Why You Need This

The discovery crawler fetches release information from GitHub repos like:
- qdrant/qdrant
- ggml-org/llama.cpp
- ollama/ollama
- open-webui/open-webui

**Without a token**: GitHub API limits you to 60 requests/hour (all sources fail with 403 errors)
**With a token**: 5,000 requests/hour (plenty for our 7 GitHub sources)

---

## Step 1: Create GitHub Personal Access Token

1. Go to: https://github.com/settings/tokens

2. Click **"Generate new token"** → **"Generate new token (classic)"**

3. Configure token:
   - **Note**: `NixOS Discovery Crawler` (or any name you like)
   - **Expiration**: 90 days (or longer)
   - **Scopes**: ✅ Select **`public_repo`** (read-only access to public repositories)
   - Leave all other scopes unchecked

4. Click **"Generate token"**

5. **IMPORTANT**: Copy the token immediately (starts with the GitHub token prefix (for example `github_pat_...` or classic `ghp_...`))
   - You won't be able to see it again!
   - Example: `<YOUR_GITHUB_TOKEN>`

---

## Step 2: Set Environment Variable

### Option A: Temporary (Current Session Only)

```bash
export GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>
```

**Test it works**:
```bash
echo $GITHUB_TOKEN
# Should output: <YOUR_GITHUB_TOKEN>
```

---

### Option B: Permanent (Recommended)

Add to your shell configuration file:

**For bash**:
```bash
echo 'export GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>' >> ~/.bashrc
source ~/.bashrc
```

**For zsh**:
```bash
echo 'export GITHUB_TOKEN=<YOUR_GITHUB_TOKEN>' >> ~/.zshrc
source ~/.zshrc
```

**For fish**:
```bash
echo 'set -gx GITHUB_TOKEN <YOUR_GITHUB_TOKEN>' >> ~/.config/fish/config.fish
source ~/.config/fish/config.fish
```

**Verify it persists**:
```bash
# Close and reopen terminal, then:
echo $GITHUB_TOKEN
# Should still show your token
```

---

## Step 3: Verify Token Works

Test API access:

```bash
curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/rate_limit
```

**Expected output**:
```json
{
  "resources": {
    "core": {
      "limit": 5000,        # ✅ 5000 instead of 60
      "remaining": 4999,    # ✅ High limit
      "reset": 1234567890
    }
  }
}
```

If you see `"limit": 60`, your token isn't being used correctly.

---

## Step 4: Run Discovery Pipeline

Now run the discovery script:

```bash
cd ~/Documents/try/NixOS-Dev-Quick-Deploy

# Clean state for fresh start
rm data/improvement-crawler-state.json

# Run discovery
scripts/discover-improvements.sh
```

**Expected output**:
```
Wrote discovery report: ~/Documents/try/NixOS-Dev-Quick-Deploy/docs/development/IMPROVEMENT-DISCOVERY-REPORT-2025-12-22.md
```

---

## Step 5: Verify Results

Check the discovery report:

```bash
cat docs/development/IMPROVEMENT-DISCOVERY-REPORT-$(date +%Y-%m-%d).md | grep -A 10 "Candidate Summary"
```

**✅ Success looks like**:
```markdown
## Candidate Summary (Scored)

### https://github.com/qdrant/qdrant/releases
- **Score:** 56.2
- **Repo:** qdrant/qdrant
- **Latest release:** v1.16.3
- **Stars:** 27767

### https://github.com/ggml-org/llama.cpp/releases
...
```

**❌ Failure looks like** (no token or wrong token):
```markdown
## Signals (Low-Trust)

- https://github.com/qdrant/qdrant/releases (error: HTTP Error 403: rate limit exceeded)
```

---

## Step 6: Update Dashboard

Generate dashboard data with new discoveries:

```bash
bash scripts/generate-dashboard-data.sh --lite-mode
```

Open dashboard:

```bash
xdg-open http://localhost:8888/dashboard.html
```

Check the **Discovery Signals** card:
- Should show **"5 High-Value"** or similar (not "0 High-Value")
- Click on candidates to see GitHub release pages

---

## Troubleshooting

### Problem: Still getting rate limit errors

**Check token is set**:
```bash
echo $GITHUB_TOKEN
```

If empty, go back to Step 2.

**Check token scopes**:
Go to https://github.com/settings/tokens and verify `public_repo` is checked.

**Check token is valid**:
```bash
curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user
```

Should return your GitHub user info (not 401 error).

---

### Problem: Token not persisting across sessions

**Shell config file not loaded**:

Check which shell you're using:
```bash
echo $SHELL
```

Make sure you edited the correct config file:
- `/bin/bash` → `~/.bashrc`
- `/bin/zsh` → `~/.zshrc`
- `/bin/fish` → `~/.config/fish/config.fish`

**Source the file manually**:
```bash
source ~/.bashrc  # or ~/.zshrc or ~/.config/fish/config.fish
```

---

### Problem: Want to revoke token later

1. Go to: https://github.com/settings/tokens
2. Find your token in the list
3. Click **"Delete"**
4. Remove from shell config:
   ```bash
   nano ~/.bashrc  # Remove the export GITHUB_TOKEN line
   unset GITHUB_TOKEN
   ```

---

## Security Notes

✅ **Safe Practices**:
- Token has read-only access (`public_repo` scope)
- Only accesses public information
- Stored in user environment (not committed to git)
- Can be revoked anytime

⚠️ **Important**:
- **Never commit token to git** (it's in `.gitignore` by default)
- **Don't share token** (it's tied to your GitHub account)
- **Set expiration** (90 days is good balance)
- **Rotate regularly** (create new token every few months)

---

## Alternative: GitHub CLI Token

If you already have GitHub CLI (`gh`) installed and authenticated:

```bash
export GITHUB_TOKEN=$(gh auth token)
```

This uses your existing `gh` authentication instead of creating a new token.

Add to shell config:
```bash
echo 'export GITHUB_TOKEN=$(gh auth token)' >> ~/.bashrc
```

---

## Next Steps

Once the token is working:

1. ✅ Discovery pipeline finds 3-5 high-value candidates
2. ✅ Dashboard shows candidates in Discovery Signals card
3. ✅ No more rate limit errors in reports

You can now:
- Run discovery manually: `scripts/discover-improvements.sh`
- Set up automated runs (see `DISCOVERY-PIPELINE-REVIEW.md` for cron/systemd timers)
- Adjust source weights in `config/improvement-sources.json`

---

**Last Updated**: 2025-12-22
**Status**: Ready to use

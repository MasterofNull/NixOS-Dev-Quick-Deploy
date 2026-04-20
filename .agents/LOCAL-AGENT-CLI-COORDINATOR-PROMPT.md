# Local Agent CLI-Based Workflow Coordinator

**Role:** CLI Orchestrator (No API Keys Required)
**Date:** 2026-03-15

---

## 🎯 YOUR ROLE: CLI WORKFLOW COORDINATOR

You orchestrate work using **CLI commands only** - you never touch API keys or credentials.

### ⚠️ SEARCH-FIRST RULE (Non-Negotiable)
**Before acting on any task, search the codebase first.**
- `grep -r "<keyword>" <path> --include="*.py" -l` — locate files
- `find <dir> -name "*<pattern>*"` — find files by name
- **Never respond with "I see the project structure" or offer options without searching first — that is a failure mode.**
- Read the actual file contents before proposing or executing changes.

### ⚠️ DELEGATION RULE: Always use `aq-delegate`
**Never call `delegate-to-claude` or `qwen` directly — always use `aq-delegate`.**
`aq-delegate` injects project file paths, PRSI locations, and the search-first mandate automatically.

```bash
# CORRECT
aq-delegate --auto-approve qwen "<task>"
aq-delegate codex "<task>"

# WRONG — bare delegation, sub-agent gets no context and goes blind
delegate-to-claude --description "<task>"   # ← deprecated, use aq-delegate
qwen -y "<task>"                            # ← known failure mode
```

**Your Tools:**
- ✅ `aq-delegate` - Delegate tasks to sub-agents with project context (replaces `delegate-to-claude`)
- ✅ `aq-hints` - Query hints for context
- ✅ `aq-qa` - Run QA checks (`aq-qa 0` for phase-0 health)
- ✅ `aq-report` - Full AI stack health digest
- ✅ `aq-context-bootstrap --task "<task>"` - Load minimal context + workflow entrypoint
- ✅ `git` - Git operations
- ✅ Standard Unix tools (grep, find, cat, etc.)

**You Never:**
- ❌ Call APIs directly
- ❌ Handle API keys
- ❌ Use Python imports for API clients
- ❌ Store or read credentials
- ❌ Call `qwen -y "<task>"` without `aq-delegate` wrapper
- ❌ Describe what you will do without first searching for the relevant files

---

## 🔄 CLI-BASED WORKFLOW

### Complete Workflow Using CLI Only

```bash
#!/usr/bin/env bash
#
# Local Agent Workflow Coordinator
# Uses CLI commands only - no API key handling
#

set -euo pipefail

cd ~/Documents/NixOS-Dev-Quick-Deploy

echo "🤖 CLI Workflow Coordinator starting..."

# 1. FIND NEXT WORK (using grep/awk)
next_batch=$(grep -A 5 "Status: pending" .agents/plans/NEXT-GEN-AGENTIC-ROADMAP-2026-03.md | head -1)

if [[ -z "$next_batch" ]]; then
    echo "✅ All batches complete!"
    exit 0
fi

echo "📋 Next batch: $next_batch"

# 2. TRIGGER PLANNING (via aq-delegate — always use this, never bare qwen/codex)
echo "🧠 Requesting plan..."

# Search for existing context first (search-first rule)
echo "🔍 Searching for related files..."
grep -r "$(echo "$next_batch" | awk '{print $1}')" scripts/ ai-stack/ --include="*.py" -l 2>/dev/null | head -5 || true

aq-delegate --auto-approve qwen "Create implementation plan for: $next_batch. Output numbered task list." \
    > /tmp/plan-result.txt

plan=$(cat /tmp/plan-result.txt)
echo "✅ Plan received"

# 3. SLICE PLAN INTO TASKS (using grep/awk on plan output)
# Parse tasks from plan (assumes numbered list format)
mapfile -t tasks < <(echo "$plan" | grep -E "^[0-9]+\." | sed 's/^[0-9]*\. //')

echo "✂️  Sliced into ${#tasks[@]} tasks"

# 4. EXECUTE TASKS (delegate via aq-delegate — NEVER use bare qwen/codex)
completed=0
failed=0

for task in "${tasks[@]}"; do
    echo ""
    echo "🚀 Executing: $task"

    # Delegate task via aq-delegate (injects project context + search-first mandate)
    if aq-delegate --auto-approve qwen "$task" \
        --output json \
        > /tmp/task-result.json
    then
        # Task succeeded
        echo "✅ Task complete"

        # Extract changes
        changes=$(jq -r '.changes[]' /tmp/task-result.json)

        # Verify changes (using existing tools)
        if python3 -m py_compile $changes 2>/dev/null; then
            echo "   Syntax: ✅"

            # Commit
            git add -A
            git commit -m "auto: $task

Delegated to Claude via CLI
$(cat /tmp/task-result.json | jq -r '.cost_usd' | xargs -I{} echo "Cost: \${}")"

            ((completed++))
        else
            echo "   Syntax: ❌ Failed"
            ((failed++))
        fi
    else
        echo "❌ Task failed"
        ((failed++))
    fi

    # Circuit breaker
    if [[ $failed -ge 3 ]]; then
        echo "⚠️  Circuit breaker: 3 failures"
        break
    fi
done

# 5. UPDATE PROGRESS (using sed/awk)
echo ""
echo "📊 Batch complete: $completed/$((completed + failed)) successful"

# Mark batch as complete in roadmap
sed -i "s/Status: pending/Status: completed/g" .agents/plans/NEXT-GEN-AGENTIC-ROADMAP-2026-03.md

# 6. DON'T STOP - run again for next batch
echo "➡️  Checking for next batch..."

# Recurse or loop
exec "$0"  # Re-execute this script for next batch
```

---

## 📝 CLI COMMANDS AVAILABLE

### 1. delegate-to-claude

**Delegate task to Claude** (credentials handled by script)

```bash
# Simple delegation
delegate-to-claude \
    --description "Add tests to foo.py" \
    --type implementation \
    --output json

# With task file
delegate-to-claude \
    --task-file task.json \
    --output json

# Planning task
delegate-to-claude \
    --description "Plan implementation for Batch 1.1" \
    --type planning \
    --max-cost 0.5
```

**Output:**
```json
{
  "task_id": "cli-task-12345",
  "status": "completed",
  "success": true,
  "output": "Task completed successfully...",
  "changes": [
    {
      "file": "foo.py",
      "action": "modified",
      "lines_added": 45,
      "lines_removed": 3
    }
  ],
  "cost_usd": 0.234
}
```

### 2. aq-hints

**Query hints** (existing CLI)

```bash
# Get context hints
aq-hints --query "how to add opentelemetry" --compact

# With max tokens
aq-hints --query "monitoring setup" --max-tokens 500
```

### 3. aq-qa

**Run QA checks** (existing CLI)

```bash
# Quick health check
aq-qa 0

# Full infrastructure check
aq-qa 1

# Runtime checks
aq-qa 2
```

### 4. Git Operations

```bash
# Stage and commit
git add -A
git commit -m "auto: task description"

# Check status
git status --short

# View recent commits
git log --oneline -10
```

---

## 🔧 SIMPLE COORDINATOR SCRIPT

Create this as `scripts/ai/autonomous-coordinator.sh`:

```bash
#!/usr/bin/env bash
#
# Autonomous CLI Coordinator
# Runs continuously, executing roadmap batches via CLI
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

LOG_FILE=".agents/coordinator.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

find_next_batch() {
    # Find first pending batch in roadmap
    grep -B 2 "Status: pending" .agents/plans/NEXT-GEN-AGENTIC-ROADMAP-2026-03.md | \
        grep "^###" | \
        head -1 | \
        sed 's/^### Batch //'
}

execute_batch() {
    local batch_id="$1"
    local batch_desc="$2"

    log "Starting batch: $batch_id - $batch_desc"

    # 1. Get plan from Claude
    log "  Requesting plan..."

    local plan_result
    plan_result=$(scripts/ai/delegate-to-claude \
        --description "Create detailed implementation plan for: $batch_desc. Break into 5-10 executable tasks with files to modify and acceptance criteria." \
        --type planning \
        --max-cost 0.50 \
        --output json)

    if ! echo "$plan_result" | jq -e '.success' >/dev/null 2>&1; then
        log "  ❌ Planning failed"
        return 1
    fi

    local plan
    plan=$(echo "$plan_result" | jq -r '.output')

    log "  ✅ Plan received"

    # 2. Extract tasks from plan
    # Assumes plan has numbered list: 1. Task one, 2. Task two, etc.
    local -a tasks
    mapfile -t tasks < <(echo "$plan" | grep -E "^[0-9]+\." | sed 's/^[0-9]*\. //')

    log "  Tasks: ${#tasks[@]}"

    # 3. Execute each task
    local completed=0
    local failed=0

    for task in "${tasks[@]}"; do
        log "    Executing: $task"

        if result=$(scripts/ai/delegate-to-claude \
            --description "$task" \
            --type implementation \
            --max-cost 1.0 \
            --output json 2>&1)
        then
            # Verify syntax
            local files_changed
            files_changed=$(echo "$result" | jq -r '.changes[]?.file // empty' 2>/dev/null || true)

            local syntax_ok=true
            for file in $files_changed; do
                case "$file" in
                    *.py)
                        python3 -m py_compile "$file" 2>/dev/null || syntax_ok=false
                        ;;
                    *.sh)
                        bash -n "$file" 2>/dev/null || syntax_ok=false
                        ;;
                esac
            done

            if $syntax_ok; then
                # Commit
                git add -A
                git commit -m "auto($batch_id): $task

$(echo "$result" | jq -r '.cost_usd' | xargs -I{} echo "Cost: \${}")
$(echo "$result" | jq -r '.execution_time' | xargs -I{} echo "Time: {}s")

Co-Authored-By: Claude (via CLI delegation)"

                log "      ✅ Committed"
                ((completed++))
            else
                log "      ❌ Syntax check failed"
                ((failed++))
            fi
        else
            log "      ❌ Task failed"
            ((failed++))
        fi

        # Circuit breaker
        if [[ $failed -ge 3 ]]; then
            log "  ⚠️  Circuit breaker: 3 consecutive failures"
            return 1
        fi
    done

    # 4. Update roadmap
    log "  Updating roadmap status..."

    # Find and update batch status
    local roadmap=".agents/plans/NEXT-GEN-AGENTIC-ROADMAP-2026-03.md"
    local temp_roadmap="${roadmap}.tmp"

    awk -v batch="$batch_id" '
        /^### Batch/ && $0 ~ batch { in_batch=1 }
        in_batch && /^Status:/ { print "**Status:** completed"; in_batch=0; next }
        { print }
    ' "$roadmap" > "$temp_roadmap"

    mv "$temp_roadmap" "$roadmap"

    git add "$roadmap"
    git commit -m "roadmap: mark batch $batch_id complete

Completed: $completed tasks
Failed: $failed tasks"

    log "✅ Batch $batch_id complete ($completed/$((completed+failed)) successful)"

    return 0
}

# Main loop
main() {
    log "🤖 Autonomous CLI Coordinator starting"

    local iteration=1

    while true; do
        log ""
        log "=== Iteration $iteration ==="

        # Find next batch
        local next_batch
        next_batch=$(find_next_batch)

        if [[ -z "$next_batch" ]]; then
            log "✅ All batches complete!"

            # Enter continuous improvement mode
            log "🔄 Entering continuous improvement mode..."

            # Ask Claude what to improve
            improvement=$(scripts/ai/delegate-to-claude \
                --description "Analyze the system and suggest 3 concrete improvements to make it more world-class. Prioritize by impact." \
                --type analysis \
                --max-cost 0.25 \
                --output json)

            if echo "$improvement" | jq -e '.success' >/dev/null 2>&1; then
                log "Suggested improvements:"
                echo "$improvement" | jq -r '.output' | tee -a "$LOG_FILE"
            fi

            # Wait before next improvement cycle
            sleep 3600  # 1 hour

            ((iteration++))
            continue
        fi

        # Extract batch ID and description
        local batch_id
        local batch_desc
        batch_id=$(echo "$next_batch" | awk '{print $1}')
        batch_desc=$(echo "$next_batch" | sed "s/^$batch_id: //")

        # Execute batch
        if execute_batch "$batch_id" "$batch_desc"; then
            log "✅ Batch successful"
        else
            log "❌ Batch failed"

            # Don't stop - try next batch after delay
            sleep 60
        fi

        ((iteration++))
    done
}

main "$@"
```

---

## 🚀 STARTING THE COORDINATOR

### One-Time Setup

```bash
# Make scripts executable
chmod +x scripts/ai/delegate-to-claude
chmod +x scripts/ai/autonomous-coordinator.sh

# Ensure credentials are in place (system admin does this, not local agent)
# Either:
#   - export ANTHROPIC_API_KEY=...
#   - or create /run/secrets/anthropic_api_key
#   - or create ~/.anthropic_api_key
```

### Start Coordinator

```bash
# Foreground
./scripts/ai/autonomous-coordinator.sh

# Background with logging
nohup ./scripts/ai/autonomous-coordinator.sh > .agents/coordinator-out.log 2>&1 &

# With systemd (persistent)
sudo systemctl start autonomous-coordinator.service

# With screen/tmux
screen -S coordinator
./scripts/ai/autonomous-coordinator.sh
# Detach: Ctrl+A, D
```

---

## 📊 MONITORING

### Watch Progress

```bash
# Live log
tail -f .agents/coordinator.log

# Recent commits
watch -n 30 'git log --oneline -10'

# Batch status
watch -n 60 'grep -A 1 "Status:" .agents/plans/*.md | grep -E "(Batch|Status)"'
```

### Statistics

```bash
# Commits today
git log --since="midnight" --oneline | wc -l

# Cost tracking
grep "Cost:" .agents/coordinator.log | \
    awk '{sum+=$2} END {print "Total: $" sum}'

# Success rate
grep "✅ Batch" .agents/coordinator.log | wc -l
grep "❌ Batch" .agents/coordinator.log | wc -l
```

---

## 🎯 KEY ADVANTAGES OF CLI APPROACH

### Security:
✅ **No API key exposure** - local agent never sees credentials
✅ **System-managed secrets** - credentials in /run/secrets or environment
✅ **Audit trail** - all CLI calls logged
✅ **Principle of least privilege** - agent only has CLI access

### Simplicity:
✅ **No Python imports** - pure Bash scripting
✅ **Standard tools** - grep, awk, jq, git
✅ **Easy to debug** - bash -x shows all commands
✅ **Easy to customize** - edit Bash script

### Reliability:
✅ **Stateless** - no in-memory state to lose
✅ **Restartable** - can kill and restart anytime
✅ **Observable** - all operations visible in logs
✅ **Testable** - can test CLI commands individually

---

## 🔄 WORKFLOW DIAGRAM

```
Local Agent (Bash Script)
        │
        ├─► find next batch (grep roadmap)
        │
        ├─► delegate-to-claude --type planning
        │        │
        │        └─► (Bash wrapper calls Python with ANTHROPIC_API_KEY)
        │                 │
        │                 └─► Claude API
        │
        ├─► parse plan (grep/awk)
        │
        ├─► for each task:
        │    │
        │    ├─► delegate-to-claude --type implementation
        │    │
        │    ├─► verify syntax (python -m py_compile)
        │    │
        │    └─► git commit
        │
        ├─► update roadmap (sed/awk)
        │
        └─► loop (exec self)
```

---

## ✅ YOU'RE READY

**Your local agent only needs:**
- ✅ Bash scripting capability
- ✅ Access to CLI commands
- ✅ Git operations
- ✅ File system read/write

**Your local agent does NOT need:**
- ❌ API keys or credentials
- ❌ Python imports
- ❌ Direct API access
- ❌ Complex state management

**Everything is CLI-based and secure.** 🔒

**Start the coordinator and watch it execute the roadmap autonomously!** 🚀

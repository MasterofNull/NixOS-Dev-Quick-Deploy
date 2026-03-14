---
name: debug-workflow
description: Systematic debugging workflow for isolating and fixing errors. Use when troubleshooting failures, investigating stack traces, or diagnosing unexpected behavior.
---

# Skill: debug-workflow

## Description
Provides a structured approach to debugging that emphasizes evidence collection, hypothesis testing, and minimal reproduction before attempting fixes. Reduces debugging time by following a systematic protocol.

## When to Use
- Investigating error messages or stack traces
- Diagnosing test failures
- Troubleshooting service crashes or hangs
- Fixing bugs reported by users
- Investigating unexpected behavior

## Debugging Protocol

### Phase 1: Reproduce
Confirm the error occurs consistently before investigating.

```bash
# Capture the exact error
journalctl -u <service>.service -n 50 --no-pager 2>&1 | tee /tmp/error-capture.log

# Check if error is reproducible
<command-that-triggers-error>
echo "Exit code: $?"
```

### Phase 2: Isolate
Find the minimal code path that triggers the error.

```bash
# Check recent changes
git log --oneline -10
git diff HEAD~5 -- <suspected-file>

# Bisect if needed
git bisect start
git bisect bad HEAD
git bisect good <known-good-commit>
```

### Phase 3: Hypothesize
List likely root causes ranked by probability:

1. **Configuration error** - Missing env var, wrong path, permissions
2. **Code bug** - Logic error, type mismatch, null reference
3. **Resource issue** - Out of memory, disk full, port conflict
4. **External dependency** - Service down, API changed, version mismatch

### Phase 4: Test Each Hypothesis

```bash
# Test configuration
env | grep -i <related-var>
ls -la <config-path>

# Test resources
free -h
df -h
lsof -i :<port>

# Test dependencies
systemctl status <dependency>.service
curl -sf http://127.0.0.1:<port>/health
```

### Phase 5: Fix
Apply minimal change to resolve confirmed cause.

```bash
# For config issues
export VAR=value
# or edit config file

# For code bugs
# Edit the specific line identified
python3 -m py_compile <file.py>  # Validate syntax

# For resource issues
# Adjust limits or free resources
```

### Phase 6: Verify
Confirm fix works and no regressions introduced.

```bash
# Run original failing scenario
<command-that-was-failing>

# Run related tests
pytest <test-file> -v

# Check for side effects
aq-qa 0  # Service health
```

## Quick Commands

### Log Analysis
```bash
# Recent errors
journalctl --since "1 hour ago" --priority=err

# Service-specific
journalctl -u <service>.service -f

# Grep for patterns
journalctl -u <service>.service | grep -i "error\|fail\|except"
```

### Process Inspection
```bash
# Check if running
pgrep -a <process-name>

# Resource usage
top -p $(pgrep <process-name>)

# Open files/connections
lsof -p $(pgrep <process-name>)
```

### Python Debugging
```bash
# Syntax check
python3 -m py_compile <file.py>

# Interactive debug
python3 -m pdb <script.py>

# Profile
python3 -m cProfile -s cumtime <script.py>
```

### Network Debugging
```bash
# Check ports
ss -tlnp | grep <port>

# Test connectivity
curl -v http://127.0.0.1:<port>/health

# DNS check
host <hostname>
```

## Token Efficiency Rules
1. Always capture the exact error message first.
2. Check logs before code - most issues are config/resource related.
3. Use `git bisect` for regressions instead of manual code review.
4. Test one hypothesis at a time to avoid confusing results.
5. Document findings as you go to avoid repeating work.

# Autonomous Agent Security Policy

**Version:** 1.0.0
**Date:** 2026-03-15
**Status:** Active

---

## Overview

This document describes the security restrictions enforced on the autonomous agent to enable safe, long-running agentic workflows while preventing risky system operations.

## Security Modes

### 1. Autonomous Mode (DEFAULT)

**Purpose:** Long-running, unsupervised workflow execution
**Risk Level:** Restricted
**Human Oversight:** Minimal

#### Restrictions

**Computer Use: DISABLED ❌**
- **Blocked Tools:**
  - `mouse_move` - Mouse cursor control
  - `mouse_click` - Mouse click simulation
  - `keyboard_type` - Keyboard input simulation
  - `keyboard_press` - Keyboard shortcuts
  - `screenshot` - Screen capture
- **Reason:** Mouse and keyboard control pose security risks in autonomous mode
- **Impact:** Agent cannot interact with GUI applications

**File Operations: RESTRICTED TO REPO ✅**
- **Allowed Paths:**
  - `.agents/` - Agent state and plans
  - `.claude/` - Command definitions
  - `ai-stack/` - AI infrastructure code
  - `scripts/ai/` - AI tooling scripts
  - `docs/` - Documentation
  - `nix/modules/` - NixOS modules
- **Blocked Paths:**
  - `/etc/` - System configuration
  - `/var/` - System state
  - `/run/secrets/` - Secret storage
  - `~/.ssh/` - SSH keys
  - `~/.gnupg/` - GPG keys
- **Impact:** Agent can only modify repository files, not system files

**Shell Commands: ALLOWLIST ONLY ✅**
- **Allowed Commands:**
  - `git` - Version control operations
  - `grep, find, ls, cat, head, tail` - File search/inspection
  - `python3, bash, node` - Script execution (sandboxed)
  - `systemctl status, journalctl` - Service inspection (read-only)
  - `aq-hints, aq-qa, aq-report` - AI stack queries
  - `ralph-orchestrator` - Local planning
- **Blocked Commands:**
  - `rm -rf` - Recursive deletion
  - `sudo` - Privilege escalation
  - `chmod, chown` - Permission changes
  - `systemctl restart/stop/start` - Service control
  - `reboot, shutdown` - System power
  - `dd, mkfs` - Disk operations
- **Impact:** Agent cannot execute destructive system commands

**Code Execution: SANDBOXED ✅**
- **Sandbox Required:** Yes
- **Resource Limits:**
  - Timeout: 30 seconds
  - Memory: 256 MB
  - CPU: 30 seconds
- **Languages:** Python, Bash, JavaScript
- **Impact:** Code runs in isolated environment with strict resource limits

**Network: LIMITED ✅**
- **Allowed Hosts:**
  - `127.0.0.1, localhost` - Local services
  - `api.anthropic.com` - Claude API
  - `openrouter.ai` - OpenRouter API
- **Blocked Ports:**
  - 22 (SSH), 3389 (RDP), 5900 (VNC)
- **Impact:** Agent can call AI APIs and local services but not remote access protocols

#### Approval Requirements

| Operation Type | Approval Tier |
|----------------|---------------|
| Read operations | AUTO |
| File changes (if safe) | AUTO |
| New dependencies | AGENT_VERIFY |
| System modifications | HUMAN_REQUIRED |
| Destructive operations | HUMAN_REQUIRED |

### 2. Interactive Mode

**Purpose:** Human-supervised interactive sessions
**Risk Level:** Full access
**Human Oversight:** Continuous

#### Permissions
- ✅ Computer use (with confirmation)
- ✅ All file operations
- ✅ All shell commands
- ✅ No sandboxing required
- ✅ Unrestricted network access

---

## Circuit Breakers

Automatic shutdowns triggered when:

| Condition | Limit |
|-----------|-------|
| Consecutive failures | 3 |
| Tool calls per hour | 500 |
| API cost per hour | $10.00 USD |
| File changes per batch | 20 |
| Security violation | Immediate halt |

---

## Allowed Workflow Capabilities

Even with restrictions, the autonomous agent CAN:

✅ **Plan & Execute Roadmap Batches**
- Query hints for context via `aq-hints`
- Generate implementation plans via `ralph-orchestrator`
- Delegate tasks to remote models (Claude, Qwen, etc.)

✅ **Manage Code & Documentation**
- Read repository files
- Write new files in allowed paths
- Modify existing repo code
- Generate documentation

✅ **Version Control**
- Git status, diff, log
- Git add, commit (with proper messages)
- Create branches
- Generate plans and tasks

✅ **Quality Assurance**
- Run QA checks via `aq-qa`
- Syntax validation
- Security scanning (within sandbox)
- Performance analysis

✅ **Remote Delegation**
- Delegate complex work to Claude API
- Delegate to OpenRouter models
- Receive and process agent questions
- Handle verification workflows

---

## What the Agent CANNOT Do

❌ **System Control**
- Cannot control mouse/keyboard
- Cannot restart/stop services
- Cannot modify system files
- Cannot install packages
- Cannot reboot system

❌ **Security-Sensitive Operations**
- Cannot access secrets
- Cannot modify SSH/GPG keys
- Cannot change permissions
- Cannot escalate privileges

❌ **Destructive Operations**
- Cannot run `rm -rf`
- Cannot format disks
- Cannot delete system files

---

## Enforcement

### Policy File
Location: `ai-stack/autonomous-orchestrator/security_policy.json`

### Enforcer Module
Location: `ai-stack/autonomous-orchestrator/security_enforcer.py`

### Coordinator Integration
All autonomous coordinator scripts verify security policy on startup:
- `scripts/ai/autonomous-coordinator-simple.sh`
- `scripts/ai/autonomous-coordinator-local.sh`
- `scripts/ai/autonomous-coordinator.sh`

### Verification on Startup
```bash
✓ Security policy verified: autonomous mode
  - Computer use (mouse/keyboard): DISABLED
  - File operations: RESTRICTED to repo paths
  - Shell commands: ALLOWLIST only
```

If security policy verification fails, coordinator refuses to start.

---

## Audit & Monitoring

All autonomous operations are logged:
- ✅ All tool calls
- ✅ All file changes
- ✅ All network requests
- ✅ All approval decisions

**Audit Log:** `.agents/audit/autonomous-agent.log`

---

## Testing Security Policy

Test the security enforcer:
```bash
python3 ai-stack/autonomous-orchestrator/security_enforcer.py
```

Expected output:
```
✓ read_file allowed
✓ git_status allowed
✓ mouse_click blocked: Tool 'mouse_click' is blocked in autonomous mode
✓ rm -rf blocked: Command contains blocked pattern: 'rm -rf'
✓ /etc/passwd write blocked: Path '/etc/passwd' is under blocked location: /etc/
✓ Circuit breaker triggered: ...
```

---

## Modifying Security Policy

To adjust restrictions, edit:
```
ai-stack/autonomous-orchestrator/security_policy.json
```

**Important:** After changes, restart the coordinator to apply new policy.

**Critical paths:**
- `modes.autonomous.restrictions.*` - Per-category restrictions
- `tool_policies.blocklist_in_autonomous_mode` - Blocked tools
- `tool_policies.allowlist_in_autonomous_mode` - Allowed tools
- `circuit_breakers.*` - Safety limits

---

## Summary

The autonomous agent runs in **restricted mode by default**, allowing it to:
- ✅ Execute roadmap batches via remote model delegation
- ✅ Manage repository code and documentation
- ✅ Run QA checks and validations
- ✅ Commit changes with proper audit trails

While preventing:
- ❌ Mouse/keyboard control
- ❌ System modifications
- ❌ Destructive operations
- ❌ Privilege escalation
- ❌ Access to secrets

This enables **safe, long-running agentic workflows** without compromising system security.

---

**For questions or policy adjustments, consult this document and the security policy JSON.**

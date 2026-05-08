#!/usr/bin/env python3
"""Phase 28 — unit tests for blast_radius_classifier.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))
from extensions.blast_radius_classifier import classify, batch_classify, max_tier

PASS = 0
FAIL = 0


def check(label: str, got: str, want: str) -> None:
    global PASS, FAIL
    if got == want:
        print(f"  PASS  {label}")
        PASS += 1
    else:
        print(f"  FAIL  {label}  got={got!r}  want={want!r}")
        FAIL += 1


print("=== blast_radius_classifier ===\n")

# CRITICAL tier
print("[critical]")
check("rm -rf /",                 classify("rm -rf /"),                   "critical")
check("rm -fr /tmp/x",           classify("rm -fr /tmp/x"),              "critical")
check("git push --force origin",  classify("git push --force origin"),    "critical")
check("DROP TABLE users",         classify("DROP TABLE users"),           "critical")
check("TRUNCATE TABLE logs",      classify("TRUNCATE TABLE logs"),        "critical")
check("nixos-rebuild switch",     classify("nixos-rebuild switch"),       "critical")
check("nixos-rebuild boot",       classify("nixos-rebuild boot"),         "critical")
check("dd if=/dev/zero of=/dev/sda", classify("dd if=/dev/zero of=/dev/sda"), "critical")
check("mkfs.ext4 /dev/sdb",      classify("mkfs.ext4 /dev/sdb"),         "critical")

# HIGH tier
print("\n[high]")
check("git push origin main",     classify("git push origin main"),       "high")
check("git reset --hard HEAD~1",  classify("git reset --hard HEAD~1"),    "high")
check("git branch -D old-branch", classify("git branch -D old-branch"),  "high")
check("nixos-rebuild test",       classify("nixos-rebuild test"),         "high")
check("systemctl stop nginx",     classify("systemctl stop nginx"),       "high")
check("systemctl restart app",    classify("systemctl restart app"),      "high")
check("kill -9 1234",             classify("kill -9 1234"),               "high")
check("DELETE FROM sessions",     classify("DELETE FROM sessions"),       "high")
check("redis-cli flushall",       classify("redis-cli flushall"),         "high")
check("chown root /etc/passwd",   classify("chown root /etc/passwd"),     "high")

# MEDIUM tier
print("\n[medium]")
check("git commit -m 'fix'",      classify("git commit -m 'fix'"),        "medium")
check("git add -A",               classify("git add -A"),                 "medium")
check("mkdir /tmp/mydir",         classify("mkdir /tmp/mydir"),           "medium")
check("POST /api/sessions",       classify("POST /api/sessions"),         "medium")
check("INSERT INTO logs VALUES",  classify("INSERT INTO logs VALUES"),    "medium")
check("UPDATE users SET active",  classify("UPDATE users SET active"),    "medium")
check("sed -i 's/foo/bar/' f.py", classify("sed -i 's/foo/bar/' f.py"),  "medium")
check("pip install requests",     classify("pip install requests"),       "medium")

# LOW tier
print("\n[low]")
check("GET /api/health",          classify("GET /api/health"),            "low")
check("cat README.md",            classify("cat README.md"),              "low")
check("ls -la",                   classify("ls -la"),                     "low")
check("grep -r pattern .",        classify("grep -r pattern ."),          "low")
check("git status",               classify("git status"),                 "low")
check("git log --oneline -5",     classify("git log --oneline -5"),       "low")
check("python3 -m py_compile x",  classify("python3 -m py_compile x.py"), "low")
check("aq-qa 0",                  classify("aq-qa 0"),                    "low")
check("aq-hints 'task'",          classify("aq-hints 'task'"),            "low")
check("diff a.py b.py",           classify("diff a.py b.py"),             "low")

# Edge cases
print("\n[edge cases]")
check("empty string → low",       classify(""),                           "low")
check("None-like (non-str) → low", classify(None),                        "low")  # type: ignore[arg-type]
check("case insensitive CRITICAL", classify("NIXOS-REBUILD SWITCH"),      "critical")
check("case insensitive HIGH",     classify("SYSTEMCTL STOP app"),        "high")
check("unknown action → medium",  classify("some_custom_function()"),     "medium")

# batch_classify
print("\n[batch_classify]")
result = batch_classify(["git status", "git push origin main", "rm -rf /tmp/x"])
check("batch: git status → low",      result.get("git status", "?"),         "low")
check("batch: git push → high",       result.get("git push origin main", "?"), "high")
check("batch: rm -rf /tmp/x → critical", result.get("rm -rf /tmp/x", "?"),   "critical")

# max_tier
print("\n[max_tier]")
check("max of [low, high] → high",    max_tier(["git status", "git push origin"]), "high")
check("max of [low, critical] → crit", max_tier(["cat f", "nixos-rebuild switch"]), "critical")
check("max of empty → low",           max_tier([]),                           "low")
check("max of all low → low",         max_tier(["cat f", "ls -la", "aq-qa 0"]), "low")

print(f"\n{'='*40}")
print(f"Result: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)

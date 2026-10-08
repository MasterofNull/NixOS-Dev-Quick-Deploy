# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-001

## Objective
- Restore owner/QA read access to /var/lib/llama-cpp (0700 vs declared 0750) declaratively so rebuilds keep it; unblock tier0 (PermissionError active.gguf).

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Claude Opus 5.5 direct (Rule 17 exception: 10-line Nix change blocking every gate; delegates cannot commit while tier0 is blocked).

## Commands Executed
```bash
stat -c '%A' /var/lib/llama-cpp            # drwx------
rg llama /etc/tmpfiles.d/00-nixos.conf     # d/z 0750 rules present
systemctl show -p StateDirectoryMode llama-cpp llama-cpp-embed   # 0755
nix eval --raw .#nixosConfigurations.hyperd-ai-dev.config.system.activationScripts.llamaCppStateDirMode.text
```

## Validation Evidence
- nix eval renders chmod 0750 for /var/lib/llama-cpp and /models. Live proof after rebuild: stat shows drwxr-x--- and tier0 model checks pass.

## Rollback Plan
- Revert; directory mode returns to whatever the unknown producer sets.

## Residual Risk
- Workaround registered (WR-LLAMA-STATE-DIR-MODE-0700); root cause still open.

## Hint Feedback
- No aq-hints consulted.

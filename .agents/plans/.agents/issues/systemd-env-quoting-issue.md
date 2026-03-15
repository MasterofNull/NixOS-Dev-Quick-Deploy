# SystemD Environment Quoting Issue

**Discovered:** 2026-03-15
**Severity:** Low (cosmetic warnings, no functional impact)
**Status:** Documented

## Issue Description

SystemD is logging warnings about invalid environment assignments in `/etc/systemd/system/ai-hybrid-coordinator.service`:

```
Mar 15 11:10:03 nixos systemd[1]: /etc/systemd/system/ai-hybrid-coordinator.service:106: Invalid environment assignment, ignoring: fetch)
Mar 15 11:10:03 nixos systemd[1]: /etc/systemd/system/ai-hybrid-coordinator.service:115: Invalid environment assignment, ignoring: (+respectful
Mar 15 11:10:03 nixos systemd[1]: /etc/systemd/system/ai-hybrid-coordinator.service:115: Invalid environment assignment, ignoring: bounded
Mar 15 11:10:03 nixos systemd[1]: /etc/systemd/system/ai-hybrid-coordinator.service:115: Invalid environment assignment, ignoring: browser
Mar 15 11:10:03 nixos systemd[1]: /etc/systemd/system/ai-hybrid-coordinator.service:115: Invalid environment assignment, ignoring: fetch)
```

## Root Cause

Lines 106 and 115 contain unquoted environment variable values with spaces and special characters:

**Line 106:**
```
Environment=AI_WEB_RESEARCH_USER_AGENT=nixos-dev-quick-deploy-web-research/1.0 (+respectful bounded fetch)
```

**Line 115:**
```
Environment=AI_BROWSER_RESEARCH_USER_AGENT=nixos-dev-quick-deploy-browser-research/1.0 (+respectful bounded browser fetch)
```

SystemD's `Environment=` directive requires quotes around values containing spaces or special characters.

## Solution

### Correct Format

The lines should be quoted as:

```systemd
Environment="AI_WEB_RESEARCH_USER_AGENT=nixos-dev-quick-deploy-web-research/1.0 (+respectful bounded fetch)"
Environment="AI_BROWSER_RESEARCH_USER_AGENT=nixos-dev-quick-deploy-browser-research/1.0 (+respectful bounded browser fetch)"
```

### Implementation Steps

1. **Find Source Configuration**
   - Search for NixOS module that generates this service
   - Likely in `configuration.nix` or a custom module
   - Look for `services.ai-hybrid-coordinator` or similar

2. **Update Source**
   - Add quotes to user-agent environment variables
   - Rebuild NixOS configuration: `sudo nixos-rebuild switch`

3. **Verify Fix**
   ```bash
   systemctl daemon-reload
   systemctl restart ai-hybrid-coordinator.service
   journalctl -u ai-hybrid-coordinator.service --since "1 minute ago" | grep "Invalid environment"
   # Should return no results
   ```

## Impact Assessment

- **Functional Impact:** NONE - Variables are being ignored but services work normally
- **Log Noise:** Warnings appear on every service reload/restart
- **Best Practice:** Should be fixed for clean systemd operation

## Workaround

Service functions normally despite warnings. The user-agent strings default to acceptable values even without these environment variables.

## References

- SystemD Environment Documentation: https://www.freedesktop.org/software/systemd/man/systemd.exec.html#Environment=
- NixOS Service Configuration: https://nixos.org/manual/nixos/stable/index.html#sec-writing-modules

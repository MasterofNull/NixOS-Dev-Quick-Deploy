---
doc_type: reference
id: acp-prep-copy-20260816
title: ACP prep artifacts — runbook copy, CSP, error map (local look-ahead lane, orchestrator-verified)
status: complete
parent_prd: approval-control-plane
date: 2026-08-16
---

# ACP prep artifacts (P2/P3 builds consume this)

Produced by the local (Qwen) look-ahead lane concurrently with the P1 build (empirically ~5-7 min each),
then orchestrator-verified. The P2 build uses the CSP + error map; the P3 build uses the runbook copy.

## Runbook plain-language copy (for P3 `RUNBOOK_REGISTRY` templates) — local `feau86`, verified
Impact/reversibility check: rotate-key + epoch-revoke correctly high/irreversible; epoch-revoke is the
kill-switch. Use these title/what/why/impact/reversible/human_steps verbatim as the plain-language layer.
```json
[
  {"name":"activate-signer-service","title":"Start the approval service","what":"Turns on the background program that checks and approves requests.","why":"The system cannot process new approvals until this service is running.","impact":"high","reversible":true,"human_steps":["Check if the approval service is currently stopped or inactive.","Send the start command to launch the service in the background.","Wait for the system to confirm the service has started successfully.","Verify that the service is now listed as active and healthy."]},
  {"name":"rotate-key","title":"Replace the current access key","what":"Generates a new secret code to replace the old one used for authentication.","why":"Old keys may be compromised or expired, so replacing them keeps the system secure.","impact":"high","reversible":false,"human_steps":["Generate a brand new secret key for the system to use.","Update the configuration to recognize and trust the new key immediately.","Revoke or disable the old key so it can no longer be used.","Confirm that all active sessions are updated to use the new key."]},
  {"name":"epoch-revoke","title":"Revoke all current permits","what":"Instantly invalidates every permission currently held by users or devices.","why":"This is an emergency stop to prevent any further actions if a security issue is detected.","impact":"high","reversible":false,"human_steps":["Identify the current time period for which permits are valid.","Send the revoke command to mark all active permits as expired immediately.","Wait for the system to propagate this change across all connected nodes.","Verify that no new actions can be performed with existing permits."]},
  {"name":"emit-grant","title":"Issue a single one-time permit","what":"Creates a unique permission slip that can only be used once.","why":"This allows temporary access for a specific task without granting long-term rights.","impact":"medium","reversible":true,"human_steps":["Define the specific action or resource this single permit will allow.","Generate a unique identifier for this one-time use permission.","Record the grant in the system log to track who received it.","Confirm that the permit is active and ready for immediate use."]},
  {"name":"activate-foundation-c-slice","title":"Enable the foundation component","what":"Turns on a core building block required for the system's base operations.","why":"This component must be active before higher-level features can function correctly.","impact":"medium","reversible":true,"human_steps":["Check that all dependencies for this foundation slice are installed and ready.","Load the configuration settings specific to the foundation C slice.","Activate the slice to register it with the main system coordinator.","Verify that the slice reports a healthy status in the dashboard."]}
]
```

## Kiosk CSP + launch (for P2 DOM-isolation) — local `caijxh`, verified
CSP header (use verbatim; matches the P2 clickjacking fold):
```
Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self';
```
Per-directive rationale (verified sound): `default-src 'none'` whitelist baseline; `script-src 'self'` no
inline/eval (kills DOM injection); `frame-ancestors 'none'` blocks the clickjack overlay; `connect-src
'self'` stops exfiltration of session/keystrokes; `object-src 'none'` blocks plugin escape; `base-uri`/
`form-action 'self'` stop base-tag/form redirection. Consider tightening `style-src` off `'unsafe-inline'`
if the framework allows (nonce/hash) — noted for the build.
Kiosk launch (systemd-run, dedicated uid, extensions off, ephemeral profile — verified shape; the build
must set the real approval URL/port from options.nix, and DROP `--ignore-certificate-errors`/`--allow
-insecure-localhost` unless the local origin genuinely needs them — prefer a proper local origin):
```bash
systemd-run --scope --uid=approval-user --gid=approval-users \
  chromium --kiosk http://127.0.0.1:<APPROVE_PORT>/approve \
  --no-first-run --disable-extensions --disable-default-apps \
  --disable-background-networking --disable-sync --disable-translate --no-pings \
  --user-data-dir=$(mktemp -d) --disk-cache-dir=/dev/null
```

## Plain-language WebAuthn/signer error map (for P2) — orchestrator-written (local `atxcu2` output was malformed; regenerated inline per the fast-lane adjustment)
```json
[
  {"code":"no_authenticator","plain_title":"No security key found","plain_body":"We couldn't find a security key or fingerprint reader.","physical_action":"Plug in your security key, then try again."},
  {"code":"user_verification_failed","plain_title":"Couldn't verify it's you","plain_body":"Your fingerprint or PIN didn't match.","physical_action":"Try your fingerprint or PIN again."},
  {"code":"ceremony_timeout","plain_title":"Timed out waiting","plain_body":"We stopped waiting for you to tap your key.","physical_action":"Tap Approve again and touch your key when it lights up."},
  {"code":"unregistered_key","plain_title":"Key not recognized","plain_body":"This security key isn't set up for this system.","physical_action":"Use the key you registered, or add this one in Settings."},
  {"code":"challenge_expired","plain_title":"Request expired","plain_body":"This approval sat too long and is no longer valid.","physical_action":"Start the approval again from the list."},
  {"code":"signature_invalid","plain_title":"Approval didn't go through","plain_body":"The system couldn't confirm your approval.","physical_action":"Try approving again; if it repeats, contact your admin."},
  {"code":"already_completed","plain_title":"Already done","plain_body":"This request was already approved and carried out.","physical_action":"No action needed — you can close this."},
  {"code":"connection_lost","plain_title":"Connection lost","plain_body":"We lost the connection to the system.","physical_action":"Wait a moment for it to reconnect before approving."},
  {"code":"request_expired","plain_title":"Request expired","plain_body":"This request timed out before anyone approved it.","physical_action":"Ask for a new request if you still need it."},
  {"code":"internal_error","plain_title":"Something went wrong","plain_body":"An unexpected problem stopped this approval.","physical_action":"Try again; if it keeps happening, contact your admin."}
]
```

## Measured note (local look-ahead lane)
Batch of 3 landed ~18 min after dispatch (parallel=1, ~5-7 min each), CONCURRENT with the P1 build — no
gating. 2/3 drop-in usable; 1/3 (error map) needed regen. Confirms: local prep = look-ahead lane, always
orchestrator-verified before a build consumes it. SSOT `feedback-local-continuous-slice-prep`.

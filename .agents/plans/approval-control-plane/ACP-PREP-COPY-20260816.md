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

## Batch 2 — local LEAPFROG (sequential, 5/5 landed, orchestrator-verified)
Sequential leapfrog (one-at-a-time) — no backpressure rejection, ~3-4 min each. Feeds P1b/P4/P2 + the operator guide.

### Golden test fixtures (for P2/P3 test suites) — `rl8ai3`, valid JSON
```json
[{"request_id":"01J8K9M2N3P4Q5R6S7T8U9V0W1","title":"Enable automated backup signing for daily snapshots","impact":"low","reversible":true,"runbook":"activate-signer-service"},{"request_id":"01J8K9M2N3P4Q5R6S7T8U9V0X2","title":"Revoke legacy keys and reset access tokens","impact":"high","reversible":false,"runbook":"epoch-revoke"},{"request_id":"01J8K9M2N3P4Q5R6S7T8U9V0Y3","title":"Update payment gateway endpoint configuration","impact":"medium","reversible":true,"runbook":"emit-grant"}]
```
Note: local invented an enterprise domain (fine for fixtures — structure + impact/reversible spread is what matters: low/reversible, high/irreversible, medium/reversible). Builds should re-title to AQ-OS context.

### P1b enrollment copy (first-run) — `09uflz`, clean
```json
{"title":"Setup Your Security Key","intro":"Add your physical security key to verify your identity when approving important actions.","steps":["Go to the Settings page and select 'Security Keys'.","Click 'Add New Key' and follow the on-screen prompts.","Touch the light on your key when asked to confirm it is present.","Give your key a name (like 'Home Key') so you can recognize it later."],"backup_reminder":"Please add a second key immediately in case you lose or misplace this one."}
```

### P1b recovery copy — `f81t3h` (local truncated; orchestrator-completed)
```json
{"add_backup_key":{"title":"Add a Backup Key","body":"Register a second key now so you never get locked out if you lose the first one.","steps":["Go to your account security settings.","Select 'Add another security key'.","Plug in or tap your new key to finish."]},"recover_lost_key":{"title":"Recover Lost Keys","body":"If you have no keys left, you must sit at this computer to reset access.","steps":["Sit down physically at this computer (recovery only works at the machine itself).","Open the recovery option shown on the local screen.","Register a new security key when prompted.","Add a second backup key right away so this can't happen again."]}}
```

### P4 headless CLI copy (aq-approve) — `kxkmny`, clean
```json
{"list_header":"Pending Approvals","request_line_format":"{n}. {title}","approve_prompt":"Please touch the metal button on your security key when it lights up.","success_message":"Approved successfully.","denied_message":"Request denied.","no_key_message":"No security key detected. Please plug one in and try again."}
```

### P4 FIDO2 headless reference — `3uy1e9` (local truncated; orchestrator-completed)
- `fido2.client` (Ctap2/WebAuthnClient hidraw path) produces the GetAssertion + parses `AuthenticatorAssertionResponse`.
- Human physically touches the USB key's sensor (or enters PIN) when it prompts.
- Input: base64 `challenge` (our request-bound bytes), `rp_id`, allowed `credential_ids`; output: signed assertion (signature, user handle, sign count).
- User verification via `user_verification='required'` in the get-assertion options.
- Requires a udev rule granting the invoking user hidraw access to the FIDO2 device (ship declaratively).
- Gotcha: no browser/RP-origin ceremony — the CLI IS the client, so it must derive the SAME challenge the signer expects (request_id-bound) or the assertion won't verify.

### Dashboard "Approvals" card copy (for P2) — `kj831t`, clean
```json
{"card_title":"Approvals Needed","empty_state":"All caught up! No items are waiting for your review.","pending_badge":"{n} pending","cta":"View all"}
```

### Operator guide outline (beginner, for the consolidated guide) — `v16063`, clean
7 sections: Getting Started · Watching the Dashboard · Reading the Terminal Monitor · Using the Approval Screen · Handling Common Alerts · Restarting the System · When to Call for Help. (Full text in the delegation log; use as the guide's skeleton.)

## Measured note (local look-ahead lane)
Batch of 3 landed ~18 min after dispatch (parallel=1, ~5-7 min each), CONCURRENT with the P1 build — no
gating. 2/3 drop-in usable; 1/3 (error map) needed regen. Confirms: local prep = look-ahead lane, always
orchestrator-verified before a build consumes it. SSOT `feedback-local-continuous-slice-prep`.

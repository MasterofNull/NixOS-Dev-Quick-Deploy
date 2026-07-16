# Implementation Authorization — M2A Read-Only `show` Hotfix

**Authorization ID:** `auth-agent-ops-m2a-read-show-hotfix-20260716`
**Status:** `ACTIVE — OWNER PREAUTHORIZED`
**Idempotency key:** `agent-ops-m2a-read-show-hotfix-20260716-single-use`

One Codex sub-agent may implement the exact three production/test files in the accompanying design.
The two governance files are frozen inputs. The implementer may not edit any other file, change writer
locking/CAS or machine envelopes, stage, commit, deploy, delegate, or self-accept. Any fourth
implementation file or live wrapper/route change is a hard stop.

Exact candidate hashes require independent flagship acceptance before commit.

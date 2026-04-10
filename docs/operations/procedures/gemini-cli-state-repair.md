---
Status: active
Owner: system
Updated: 2026-04-10
---

# Gemini CLI State Repair

Use this when `gemini --help` hangs under the real user home directory even
though Gemini works with a temporary clean `HOME`.

## Check

```bash
bash scripts/health/gemini-cli-health.sh --check
```

Healthy result:

```text
status=healthy
```

Repairable degraded result:

```text
status=degraded
reason=live ~/.gemini appears corrupted; copied state succeeds
```

## Repair

```bash
bash scripts/health/gemini-cli-health.sh --repair
```

Successful repair creates a timestamped backup like:

```text
/home/<user>/.gemini.pre-repair-YYYYMMDD-HHMMSS
```

## Validate

```bash
timeout 15s gemini --help
bash scripts/testing/smoke-flagship-cli-surfaces.sh
```

## Rollback

```bash
mv ~/.gemini ~/.gemini.post-repair-failed
mv ~/.gemini.pre-repair-YYYYMMDD-HHMMSS ~/.gemini
```

## Security Follow-Up

If Gemini OAuth credentials were exposed during debugging, rotate them after
repair. Gemini auth material is typically stored in `~/.gemini/oauth_creds.json`.

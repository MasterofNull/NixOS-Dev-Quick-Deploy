# Postgres Ops

Use host-local `systemd` and local connection info for Postgres operations.

## Status

```bash
systemctl status postgresql.service --no-pager
ss -ltnp | rg 5432
```

## Connect

```bash
psql -h 127.0.0.1 -p 5432 -U postgres
```

## Backup

```bash
pg_dumpall -h 127.0.0.1 -p 5432 -U postgres > /tmp/postgres-backup.sql
```

## Validation

```bash
aq-qa 0 --json
bash scripts/health/system-health-check.sh --detailed
```

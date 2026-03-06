# Phase 3 Visual Checklist (2 Minutes)

Status: Active
Owner: Operations
Last Updated: 2026-03-06

Purpose: close the remaining manual Phase 3 checks quickly.

## 1. Greeter Theme + Monitors (30s)
- Lock screen or log out to show greeter.
- Confirm greeter is visible on all connected monitors.
- Confirm theme/rendering looks correct (no blank/garbled layout).

Mark:
- `3.1 greeter/theme: PASS` or `FAIL`

## 2. Flatpak Native File Picker (45s)
- Open Firefox Flatpak.
- Trigger a file upload (`Choose file`).
- Confirm native picker dialog appears and functions.

Mark:
- `3.2 file picker: PASS` or `FAIL`

## 3. Screenshot Portal (45s)
- In a Flatpak app, trigger a screenshot/portal capture flow.
- Confirm portal opens and capture completes.

Mark:
- `3.2 screenshot portal: PASS` or `FAIL`

## Paste-Back Format

```text
3.1 greeter/theme: PASS|FAIL
3.2 file picker: PASS|FAIL
3.2 screenshot portal: PASS|FAIL
```

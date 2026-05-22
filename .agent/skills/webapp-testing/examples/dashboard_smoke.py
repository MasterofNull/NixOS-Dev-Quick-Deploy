"""dashboard_smoke.py — AI Command Center full-tab visual test.

Requires playwright in environment:
  nix develop /path/to/repo#mobile-web -- python3 examples/dashboard_smoke.py

Or set PLAYWRIGHT_BROWSERS_PATH and run directly.
"""
from playwright.sync_api import sync_playwright
import time, sys, os

BASE = "http://localhost:8889"
OUT  = "/tmp/dashboard-smoke"

TABS = [
    ("overview",     "#tab-overview",     ["vCpu","vMem","vGpu","dbBadge","svcCount"]),
    ("intelligence", "#tab-intelligence", ["coordStatus","knowledgeBadge","learningBadge","aidbBadge"]),
    ("security",     "#tab-security",     ["fwBadge","cbBadge","harnessBadge"]),
    ("operations",   "#tab-operations",   ["qaBadge","deployBadge","harnessOvBadge"]),
]

import os; os.makedirs(OUT, exist_ok=True)

errors, results = [], {}

import shutil
# NixOS: Playwright cannot install its own Chromium due to FHS incompatibility.
# Use the system Chromium installed via nix instead.
CHROMIUM = (
    os.environ.get("CHROMIUM_PATH")
    or next((p for p in [
        os.path.expanduser("~/.nix-profile/bin/chromium"),
        "/run/current-system/sw/bin/chromium",
        shutil.which("chromium") or "",
    ] if p and os.path.isfile(p)), None)
)

with sync_playwright() as p:
    launch_kwargs = dict(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    if CHROMIUM:
        launch_kwargs["executable_path"] = CHROMIUM
    browser = p.chromium.launch(**launch_kwargs)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    page.on("console", lambda m: errors.append(f"[{m.type}] {m.text}") if m.type == "error" else None)

    page.goto(BASE, wait_until="networkidle")
    time.sleep(3)  # allow XHR population

    for tab_id, tab_sel, check_ids in TABS:
        if tab_sel != "#tab-overview":
            page.click(tab_sel)
            time.sleep(3)
        page.screenshot(path=f"{OUT}/{tab_id}.png")
        tab_results = {}
        for eid in check_ids:
            el = page.query_selector(f"#{eid}")
            val = el.inner_text() if el else "MISSING"
            tab_results[eid] = val
            status = "OK" if val not in ("--", "--%", "MISSING", "") else "EMPTY"
            print(f"  [{status}] {tab_id}/{eid}: {val}")
        results[tab_id] = tab_results

    browser.close()

empties = sum(1 for t in results.values() for v in t.values() if v in ("--", "--%", "MISSING", ""))
print(f"\nScreenshots: {OUT}/")
print(f"JS errors: {len(errors)}")
print(f"Empty cells: {empties}")
sys.exit(1 if errors or empties > 5 else 0)

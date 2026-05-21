"""dashboard_smoke.py — AI Command Center full-tab visual test.

Requires playwright in environment:
  nix develop /path/to/repo#mobile-web -- python3 examples/dashboard_smoke.py

Or set PLAYWRIGHT_BROWSERS_PATH and run directly.
"""
from playwright.sync_api import sync_playwright
import time, sys

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

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
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

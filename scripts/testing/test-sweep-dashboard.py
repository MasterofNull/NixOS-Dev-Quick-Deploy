#!/usr/bin/env python3
"""sweep-dashboard: each finding class is detected from a fixture dashboard (HTML + JS + FastAPI routes), honest
cards are not flagged, and --live only ever issues GET to routes that pass the safe-GET rule. Fixtures only; the
live test talks to a throwaway localhost server, never the real dashboard. SWEEP_SCRIPT overrides the script
under test (used to confirm each assertion fails when the detector is broken)."""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = Path(os.environ.get("SWEEP_SCRIPT") or REPO / "scripts/governance/sweep-dashboard.py")
spec = importlib.util.spec_from_loader("sweep", importlib.machinery.SourceFileLoader("sweep", str(SCRIPT)))
sw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sw)

HTML = """<html><body>
<div class="card"><span class="lbl">Throughput</span><span id="okCard">--</span></div>
<div class="card"><span class="lbl">Replaced template</span><span id="tplCard">0</span></div>
<div class="card"><span class="lbl">Honest unknown</span><span id="honestCard">--</span></div>
<div class="card"><span class="lbl">Orphan</span><span id="noFetchCard">--</span></div>
<div class="card"><span class="lbl">Gates</span><span id="hardLit">53 / 53</span></div>
<div class="card"><span class="lbl">Missing route</span><span id="noRouteCard">--</span></div>
<div class="card"><span class="lbl">No writer</span><span id="noProdCard">--</span></div>
<div class="card"><span class="lbl">Silent</span><span id="silentCard">--</span></div>
<div class="card"><span class="lbl">Const</span><span id="constCard">--</span></div>
<div class="card"><span class="lbl">Js default</span><span id="jsDefaultCard">--</span></div>
<div class="card"><span class="lbl">Fake</span><span id="fakeCard">--</span></div>
<div class="card"><span class="lbl">Js fake</span><span id="jsFakeCard">--</span></div>
<div class="card"><span class="lbl">Lane</span><span id="retiredCard">ORCHESTRATOR: ANTIGRAVITY</span></div>
<div class="card"><span class="lbl">Lane ok</span><span id="retiredOk">legacy antigravity lane (retired)</span></div>
<script src="/assets/dashboard.js"></script></body></html>"""

JS = """const BASE = "";
async function apiFetch(path) {
  const r = await fetch(`${BASE}/api${path}`);
  return r.ok ? r.json() : null;
}
function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v ?? "--"; }
async function loadOk() {
  const d = await apiFetch("/ok/data");
  setText("okCard", d ? d.rate : "--");
  setText("tplCard", d ? d.count : "--");
}
async function loadHonest() {
  const d = await apiFetch("/honest/data");
  setText("honestCard", d && d.value != null ? d.value : "--");
}
async function loadMissing() {
  const d = await apiFetch("/missing/x");
  setText("noRouteCard", d.v);
}
async function loadNoProd() {
  const d = await apiFetch("/noprod/data");
  setText("noProdCard", d.v);
}
async function loadSilent() {
  const d = await apiFetch("/silent/data");
  setText("silentCard", d.status);
}
async function loadConst() {
  const d = await apiFetch("/const/data");
  setText("constCard", d.score);
}
async function loadJsDefault() {
  const d = await apiFetch("/ok/data");
  const pct = d.pct ?? 94;
  setText("jsDefaultCard", `${pct}%`);
}
async function loadJsFake() {
  const d = await apiFetch("/ok/data");
  const rows = mockRows(d);
  setText("jsFakeCard", rows.length);
}
async function loadFake() {
  const d = await apiFetch("/fake/data");
  setText("fakeCard", d.v);
}
"""

MAIN = """from fastapi import FastAPI
from api.routes import okr, honest, noprod, silent, const, fake
app = FastAPI()
app.include_router(okr.router, prefix="/api/ok")
app.include_router(honest.router, prefix="/api/honest")
app.include_router(noprod.router, prefix="/api/noprod")
app.include_router(silent.router, prefix="/api/silent")
app.include_router(const.router, prefix="/api/const")
app.include_router(fake.router, prefix="/api/fake")
"""

ROUTES = {
    "okr": '''from fastapi import APIRouter
import json
from pathlib import Path
router = APIRouter()
STATE = Path("/var/lib/fx/written.json")
@router.get("/data")
async def data():
    return json.loads(STATE.read_text())
@router.post("/reset")
async def reset():
    return {"ok": True}
''',
    "honest": '''from fastapi import APIRouter
import json
from pathlib import Path
router = APIRouter()
STATE = Path("/var/lib/fx/written.json")
@router.get("/data")
async def data():
    try:
        return json.loads(STATE.read_text())
    except OSError:
        return {"status": "unknown", "value": None}
''',
    "noprod": '''from fastapi import APIRouter
router = APIRouter()
@router.get("/data")
async def data():
    return {"v": open("/var/lib/fx/never-written-anywhere.json").read()}
''',
    "silent": '''from fastapi import APIRouter
import json
router = APIRouter()
@router.get("/data")
async def data():
    try:
        return json.load(open("/var/lib/fx/written.json"))
    except Exception:
        return {"status": "healthy", "count": 0}
''',
    "const": '''from fastapi import APIRouter
router = APIRouter()
@router.get("/data")
async def data():
    return {"score": 97, "status": "ok"}
''',
    "fake": '''from fastapi import APIRouter
router = APIRouter()
def mock_data():
    return {"v": 5}
@router.get("/data")
async def data():
    return mock_data()
''',
}


def build(root, mutate=None):
    root = Path(root)
    (root / "assets").mkdir(parents=True)
    (root / "assets/dashboard.js").write_text(JS)
    (root / "dashboard.html").write_text(HTML)
    api = root / "dashboard/backend/api/routes"
    api.mkdir(parents=True)
    (api / "__init__.py").write_text("")
    (root / "dashboard/backend/api/__init__.py").write_text("")
    (root / "dashboard/backend/api/main.py").write_text(MAIN)
    for n, src in ROUTES.items():
        (api / f"{n}.py").write_text(src)
    (root / "scripts").mkdir()
    (root / "scripts/writer.sh").write_text('#!/bin/sh\necho "{}" > /var/lib/fx/written.json\n')
    return root


def run():
    with tempfile.TemporaryDirectory() as td:
        repo = build(td)
        sw._writer_cache.clear()
        res = sw.analyse(repo)
        by = {}
        for f in res["findings"]:
            by.setdefault(f["class"], []).append(f)
        flagged = {c for f in res["findings"] for c in f["cards"]}
        flagged |= {f["subject"] for f in res["findings"]}

        def has(cls, card):
            return any(card in f["cards"] or card == f["subject"] for f in by.get(cls, []))

        assert has("NO_FETCH", "noFetchCard"), by.get("NO_FETCH")
        assert has("HARDCODED", "hardLit"), "HTML literal never replaced not detected"
        assert any(f["subject"] == "/api/missing/x" and "noRouteCard" in f["cards"] for f in by.get("NO_ROUTE", [])), by.get("NO_ROUTE")
        assert any("never-written-anywhere.json" in f["subject"] for f in by.get("NO_PRODUCER", [])), by.get("NO_PRODUCER")
        assert has("SILENT_DEFAULT", "silentCard"), by.get("SILENT_DEFAULT")
        assert has("HARDCODED", "constCard"), "constant-returning route not detected"
        assert any(f.get("js_default") == "94" and "jsDefaultCard" in f["cards"] for f in by.get("HARDCODED", [])), "JS `?? 94` default not detected"
        assert has("FAKE_FALLBACK", "fakeCard"), by.get("FAKE_FALLBACK")
        assert any(f["subject"] == "loadJsFake" and "jsFakeCard" in f["cards"] for f in by.get("FAKE_FALLBACK", [])), "JS mock data not detected"
        assert has("RETIRED_REF", "retiredCard"), by.get("RETIRED_REF")

        # honest cards carry no finding: a placeholder a fetch replaces, an unknown-on-missing route, retired wording
        for honest in ("okCard", "tplCard", "honestCard", "retiredOk"):
            assert honest not in flagged, f"honest card {honest} was flagged: {[f for f in res['findings'] if honest in f['cards']]}"
        assert not any(f["class"] == "NO_PRODUCER" and "written.json" in f["subject"] for f in res["findings"]), \
            "a file with a writer must not be NO_PRODUCER"
        # trace: card -> fetch -> route -> producer
        ok = next(c for c in res["cards"] if c["id"] == "okCard")
        assert ok["status"] == "TRACED" and "/api/ok/data" in ok["fetch"][0], ok
        assert "okr.py" in ok["route"] and "/var/lib/fx/written.json" in ok["producer"], ok
        assert next(c for c in res["cards"] if c["id"] == "noRouteCard")["status"] == "NO_ROUTE"
        # POST-only route is not a GET route
        r, st = res["_backend"].match("/api/ok/reset", "GET")
        assert st == "method-mismatch", st

        # CLI: report-only by default, --fail-on turns a class into exit 1
        base = [sys.executable, str(SCRIPT), "--repo", str(repo)]
        assert subprocess.run(base, capture_output=True).returncode == 0
        assert subprocess.run(base + ["--fail-on", "NO_FETCH"], capture_output=True).returncode == 1
        assert subprocess.run(base + ["--fail-on", "BOGUS"], capture_output=True).returncode == 2

        # --live: GET only, skips unsafe routes, recorded verbatim
        seen = []

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _any(self):
                seen.append((self.command, self.path))
                body = json.dumps({"rate": 5, "count": 2, "ts": "2000-01-01T00:00:00Z", "gap": None}).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            do_GET = do_POST = do_PUT = do_DELETE = _any

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            res2 = sw.analyse(repo)
            # add an endpoint for a handler that shells out and a verb-like path: they must be skipped, not requested
            (Path(repo) / "dashboard/backend/api/routes/okr.py").write_text(ROUTES["okr"] + '''
import subprocess
@router.get("/shell")
async def shell():
    return subprocess.run(["true"]).returncode
@router.get("/restart-now")
async def restart_now():
    return {"v": 1}
''')
            res2 = sw.analyse(repo)
            res2["_used"][("/api/ok/shell", "GET")] = [("okCard", "x", 1, "x")]
            res2["_used"][("/api/ok/restart-now", "GET")] = [("okCard", "x", 1, "x")]
            res2["_used"][("/api/ok/reset", "POST")] = [("okCard", "x", 1, "x")]
            live = sw.live_probe(res2, repo, f"http://127.0.0.1:{srv.server_address[1]}", 900, delay=0)
        finally:
            srv.shutdown()
        assert seen and all(m == "GET" for m, _ in seen), seen
        asked = {p for _, p in seen}
        assert "/api/ok/shell" not in asked and "/api/ok/restart-now" not in asked and "/api/ok/reset" not in asked, asked
        skipped = {k["endpoint"]: k["reason"] for k in live["skipped"]}
        assert "side-effect" in skipped["/api/ok/shell"], skipped
        assert "verb" in skipped["/api/ok/restart-now"], skipped
        assert "POST" in skipped["/api/ok/reset"], skipped
        p = next(p for p in live["probes"] if p["endpoint"] == "/api/ok/data")
        assert p["http"] == 200 and p["fresh"] == "stale" and "gap" in p["blank"], p
    print("PASS: sweep-dashboard detects NO_FETCH, NO_ROUTE, NO_PRODUCER, HARDCODED (html, js default, constant route), "
          "SILENT_DEFAULT, FAKE_FALLBACK, RETIRED_REF; honest cards unflagged; --live sends GET only and skips unsafe routes")


if __name__ == "__main__":
    run()

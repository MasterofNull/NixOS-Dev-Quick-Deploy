#!/usr/bin/env python3
"""In-process benchmark of the agent-auth middleware (DESIGN section 7, F10).

Two aiohttp apps with the same trivial handler: A = baseline middleware, B = A
plus the shadow authorization middleware. Interleaved blocks cancel drift.
Gate (same host): delta p50 <= 50us, p95 <= 100us, p99 <= 250us.
Usage: bench-agent-auth-middleware.py [--n 5000] [--warmup 500] [--block 500] [--strict]
"""
import argparse
import asyncio
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HC = REPO / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
sys.path[:0] = [str(HC), str(HC.parent)]
os.environ.setdefault("AI_STRICT_ENV", "false")

from aiohttp import web  # noqa: E402
from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

from middleware.authz import create_authz_middleware, load_policy  # noqa: E402

GATE_US = {"p50": 50, "p95": 100, "p99": 250}


@web.middleware
async def _baseline(request, handler):
    return await handler(request)


async def _ok(request):
    return web.json_response({"ok": True})


async def _client(middlewares):
    app = web.Application(middlewares=middlewares)
    app.router.add_get("/hints", _ok)
    c = TestClient(TestServer(app))
    await c.start_server()
    return c


async def _burst(client, count):
    out = []
    for _ in range(count):
        t = time.perf_counter_ns()
        r = await client.get("/hints")
        await r.read()
        out.append(time.perf_counter_ns() - t)
    return out


def _pct(vals, p):
    vals = sorted(vals)
    return vals[min(len(vals) - 1, int(len(vals) * p / 100))] / 1000.0


async def main_async(n, warmup, block):
    tmp = tempfile.mkdtemp()
    a = await _client([_baseline])
    b = await _client([_baseline, create_authz_middleware(
        policy=load_policy(), mode="shadow", audit_path=os.path.join(tmp, "a.jsonl"))])
    await _burst(a, warmup)
    await _burst(b, warmup)
    ra, rb = [], []
    for _ in range(max(1, n // block)):
        ra += await _burst(a, block)
        rb += await _burst(b, block)
    await a.close()
    await b.close()
    res = {}
    for name, p in (("p50", 50), ("p95", 95), ("p99", 99)):
        res[name] = (_pct(ra, p), _pct(rb, p), _pct(rb, p) - _pct(ra, p))
    print(f"n={len(ra)} per variant, mean A={statistics.mean(ra)/1000:.1f}us B={statistics.mean(rb)/1000:.1f}us")
    ok = True
    for name, (va, vb, d) in res.items():
        passed = d <= GATE_US[name]
        ok &= passed
        print(f"{name}: A={va:.1f}us B={vb:.1f}us delta={d:.1f}us gate<={GATE_US[name]}us {'PASS' if passed else 'FAIL'}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5000)
    ap.add_argument("--warmup", type=int, default=500)
    ap.add_argument("--block", type=int, default=500)
    ap.add_argument("--strict", action="store_true", help="exit 1 when the gate fails (S2/S3 acceptance)")
    args = ap.parse_args()
    ok = asyncio.run(main_async(args.n, args.warmup, args.block))
    return 0 if (ok or not args.strict) else 1


if __name__ == "__main__":
    sys.exit(main())

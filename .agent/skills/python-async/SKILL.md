# Python Async Skill
## Tags
python, async, asyncio, fastapi, aiohttp, blocking, to_thread, event_loop, mlfq, background
## When to Use
Writing FastAPI/aiohttp handlers; database calls inside async functions; file I/O in handlers;
background task spawning; MLFQ task scheduling; "event loop blocked" symptoms.

---

## 1. The Core Rule: Never Block an Async Handler

```python
# WRONG — blocks the entire event loop for all requests:
@router.get("/api/data")
async def get_data():
    with open("/var/lib/ai-stack/big-file.jsonl") as f:     # blocks
        data = f.read()
    result = requests.get("http://127.0.0.1:8003/query")    # blocks
    return data

# CORRECT — offload sync work to thread pool:
@router.get("/api/data")
async def get_data():
    data = await asyncio.to_thread(_read_file_sync, "/var/lib/ai-stack/big-file.jsonl")
    async with aiohttp.ClientSession() as session:           # async
        async with session.get("http://127.0.0.1:8003/query") as resp:
            result = await resp.json()
    return data

def _read_file_sync(path: str) -> str:
    with open(path) as f:
        return f.read()
```

**Anything blocking goes in `asyncio.to_thread()`**: file reads, JSONL iteration,
SQLite queries, subprocess calls, synchronous HTTP (`requests.get`).

---

## 2. aiohttp Session Scoping

```python
# WRONG — global session leaks connections, stale state across requests:
_SESSION = aiohttp.ClientSession()   # module-level

async def call_coordinator(payload):
    async with _SESSION.post(url, json=payload) as r:  # reuses stale session
        return await r.json()

# CORRECT — session per request (or per handler lifetime):
async def call_coordinator(payload):
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as r:
            return await r.json()
```

For high-frequency calls, use a session bound to the app lifespan (not module-level):
```python
# In app startup:
app["session"] = aiohttp.ClientSession()
# In handler:
session = request.app["session"]
# In app shutdown:
await app["session"].close()
```

---

## 3. MLFQ Background Task Spawning

When spawning background MLFQ tasks from async handlers:

```python
import asyncio

async def handle_expensive_request(request):
    # Don't await background work — fire and forget with proper tracking:
    task = asyncio.create_task(_run_background_work(request_data))
    task.add_done_callback(_handle_task_completion)
    return {"status": "accepted", "task_id": task_id}

def _handle_task_completion(task: asyncio.Task):
    """Prevents silent task drops on exception."""
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.error("Background task failed: %s", exc)
```

**Always add a done_callback** — unhandled task exceptions are silently swallowed in
Python's asyncio without it.

---

## 4. Graceful Shutdown Pattern

Background tasks must be cancelled cleanly on shutdown:

```python
# Track tasks at module level:
_background_tasks: set[asyncio.Task] = set()

def _spawn_background(coro):
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task

# In shutdown handler:
async def cleanup():
    for task in list(_background_tasks):
        task.cancel()
    await asyncio.gather(*_background_tasks, return_exceptions=True)
```

---

## 5. Logging in Switchboard / Service Code

`switchboard.py` and coordinator services use `sys.stderr` for output in some components.
Standard `logging.getLogger()` is correct for most services, but check the module convention:

```python
# Coordinator / FastAPI services — standard logging:
import logging
logger = logging.getLogger(__name__)
logger.info("message")

# Scripts / CLI tools — print to stderr:
import sys
print("status message", file=sys.stderr)
```

Don't mix them in the same module. If a service shows no log output, check if it writes to
stderr while systemd captures only stdout, or vice versa.

---

## 6. async Generator Cleanup

```python
# WRONG — exception silently drops pending work:
async def stream_results():
    async for chunk in source:
        yield chunk

# CORRECT — always use try/finally:
async def stream_results():
    try:
        async for chunk in source:
            yield chunk
    finally:
        await source.aclose()   # cleanup even on exception/cancellation
```

---

## 7. Stale .pyc Files (Not Async but Frequently Confused)

If your async fix doesn't take effect after restart, check for stale bytecode:
```bash
find dashboard/backend -name "*.pyc" -newer dashboard/backend/api/routes/aistack.py -delete
systemctl restart command-center-dashboard-api
```

Symptom: error message doesn't match the code you just fixed; `UnboundLocalError` persists
after you clearly defined the variable.

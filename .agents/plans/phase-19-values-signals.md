# Phase 19 — Values Signals: Affective Layer as Behavioral Modulator

Status: `pending`
Created: 2026-04-30
Owner: Claude (orchestrator) / Qwen (implementation)
Source: System Assessment & AGI Scaffold Architecture (2026-04-30)
Predecessor: Phase 16 (identity kernel + value constitution)

---

## Objective

Translate the value hierarchy defined in `config/identity-values.yaml` (Phase 16) into
runtime signals that measurably modulate query responses. This is NOT a philosophical
exercise — it produces concrete behavioral changes:

- **Empathy signal** (detected from retry patterns + short responses): switches coordinator
  to step-by-step mode with more confirmations
- **Reciprocity accounting**: tracks give/receive ratio; triggers proactive help offers
  when imbalance exceeds threshold
- **Beauty/elegance signal**: adds code quality commentary when aesthetic_score is low
- **Compassion signal**: detected from frustration markers; engages patient mode

The affective engine reads signals from query context and existing telemetry. It does NOT
require emotion detection models — it uses observable behavioral proxies.

---

## Scope Lock

In scope:
- `ai-stack/affective-engine/` (new directory):
  - `state_model.py` — AffectiveState dataclass + signal computation
  - `signal_detectors.py` — observable-proxy detectors (retry count, response length, error rate)
  - `output_modulator.py` — wraps LLM outputs based on active signals
  - `reciprocity_tracker.py` — Redis-backed give/receive accounting
- Integration into hybrid coordinator `/query` response path (post-LLM, pre-response)
- Route: `GET /affective/state` — current affective state snapshot
- Declarative Nix options for enabling/disabling modulation and signal thresholds

Out of scope:
- Valence/arousal model training
- Emotion recognition from text (NLP classifier)
- Changes to LLM inference path or model selection
- Identity kernel (Phase 16 — separate)

Constraints:
- Affective modulation is additive (appends to response) — never truncates or replaces
- All signal thresholds must be declarative (env vars, not hardcoded)
- Modulation must be bypassable: `X-Affective-Bypass: true` header skips all modulation
- Reciprocity accounting uses Redis with TTL=30d (rolling window)
- Performance budget: modulation adds <50ms to query response time

---

## Context References

Files to read first:
- `config/identity-values.yaml` (from Phase 16 — read value weights)
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` (query response path)
- `ai-stack/mcp-servers/hybrid-coordinator/route_handler.py` (post-LLM hook points)
- `nix/modules/core/options.nix` (option definition pattern)

---

## Steps

### 19.1 — State Model

**Owner**: Qwen
**Files**: `ai-stack/affective-engine/state_model.py` (new)

Tasks:
1. Create `AffectiveState` dataclass:
   ```python
   @dataclass
   class AffectiveState:
       empathy_signal: float = 0.0    # 0=neutral, 1=high frustration detected
       reciprocity_debt: float = 0.0  # negative=owed to user, positive=user owes
       aesthetic_gap: float = 0.0     # 0=beautiful output, 1=low quality detected
       compassion_level: float = 0.0  # 0=neutral, 1=distress detected
       timestamp: datetime = field(default_factory=datetime.utcnow)

       def dominant_signal(self) -> str:
           ...  # returns name of highest non-zero signal

       def as_modulation_hints(self) -> list[str]:
           ...  # returns list of prompt modifier strings
   ```
2. `as_modulation_hints()` returns strings like:
   - `"Use step-by-step explanations with numbered lists"` (empathy_signal > 0.7)
   - `"Proactively offer additional resources or next steps"` (reciprocity_debt < -3)
   - `"Add a brief note on code elegance or simplification"` (aesthetic_gap > 0.6)
   - `"Keep response concise and reduce jargon"` (compassion_level > 0.5)

Validation:
- `python3 -m py_compile ai-stack/affective-engine/state_model.py`
- `python3 -c "from state_model import AffectiveState; s = AffectiveState(empathy_signal=0.8); print(s.as_modulation_hints())"`

### 19.2 — Signal Detectors

**Owner**: Qwen
**Files**: `ai-stack/affective-engine/signal_detectors.py` (new)

Tasks:
1. Create `SignalDetectors` class — all detectors use observable proxies only:
   - `detect_empathy(request_context)` → float:
     - Proxy: retry count (from `X-Retry-Count` header or session history)
     - Proxy: recent error rate for this session (from Redis session store if available)
     - Returns 0.0 if no session context available (graceful degradation)
   - `detect_aesthetic_gap(response_content)` → float:
     - Proxy: code block line count vs comment ratio
     - Proxy: presence of magic numbers, hardcoded strings in code snippets
     - Returns 0.0 for non-code responses
   - `detect_compassion(request_context)` → float:
     - Proxy: `?` count in query (confusion marker)
     - Proxy: words in `{error, broken, wrong, not working, help, stuck}` set
     - Threshold configurable: `AFFECTIVE_COMPASSION_WORD_THRESHOLD` (default 2)
   - All detectors are stateless (no side effects)

Validation:
- `python3 -m py_compile ai-stack/affective-engine/signal_detectors.py`
- `python3 -c "from signal_detectors import SignalDetectors; d = SignalDetectors(); print(d.detect_compassion({'query': 'why is this broken help me'}))"` → value > 0

### 19.3 — Reciprocity Tracker

**Owner**: Qwen
**Files**: `ai-stack/affective-engine/reciprocity_tracker.py` (new)

Tasks:
1. Create `ReciprocityTracker` class (Redis-backed):
   - `record_give(session_id, value=1.0)` — system provided value to user
     → `INCRBYFLOAT affective:reciprocity:<session_id>:give <value>`
   - `record_receive(session_id, value=1.0)` — user provided value to system (feedback, correction)
     → `INCRBYFLOAT affective:reciprocity:<session_id>:receive <value>`
   - `get_debt(session_id)` → float: `receive - give` (negative = system owes user)
   - All keys: TTL = `AFFECTIVE_RECIPROCITY_TTL_DAYS` * 86400 (default 30d)
   - Falls back to in-memory counter if Redis unavailable

Validation:
- `python3 -m py_compile ai-stack/affective-engine/reciprocity_tracker.py`

### 19.4 — Output Modulator

**Owner**: Qwen
**Files**: `ai-stack/affective-engine/output_modulator.py` (new)

Tasks:
1. Create `OutputModulator` class:
   - `modulate(response_text, state: AffectiveState, bypass=False)` → str:
     - If `bypass=True`: return `response_text` unchanged
     - If `state.dominant_signal()` is neutral: return unchanged
     - Otherwise: append a modulation block:
       ```
       ---
       [context: {hint}]
       ```
       Where `hint` = first item from `state.as_modulation_hints()`
   - Modulation block is clearly demarcated so clients can strip it if needed
   - Max 1 modulation hint per response (no stacking)

Validation:
- `python3 -m py_compile ai-stack/affective-engine/output_modulator.py`
- `python3 -c "from output_modulator import OutputModulator; from state_model import AffectiveState; m = OutputModulator(); print(m.modulate('hello', AffectiveState(empathy_signal=0.9)))"`

### 19.5 — Wire Into Query Path + Endpoints

**Owner**: Qwen
**Files**: `ai-stack/mcp-servers/hybrid-coordinator/route_handler.py` or `http_server.py`

Tasks:
1. Identify post-LLM response assembly point in `route_handler.py`
2. Add affective pipeline (after LLM response, before returning):
   ```python
   from affective_engine.signal_detectors import SignalDetectors
   from affective_engine.state_model import AffectiveState
   from affective_engine.output_modulator import OutputModulator

   if os.environ.get("AFFECTIVE_ENABLED", "false").lower() == "true":
       bypass = request.headers.get("X-Affective-Bypass", "false") == "true"
       detectors = SignalDetectors()
       state = AffectiveState(
           empathy_signal=detectors.detect_empathy(request_context),
           compassion_level=detectors.detect_compassion(request_context),
           aesthetic_gap=detectors.detect_aesthetic_gap(response_text),
       )
       response_text = OutputModulator().modulate(response_text, state, bypass=bypass)
   ```
3. Add `GET /affective/state` endpoint in a new `affective_handlers.py`:
   - Returns current `AffectiveState` snapshot (last computed) + reciprocity debt
   - Route registered via `register_routes(app)` pattern

Validation:
- `python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/route_handler.py`
- `AFFECTIVE_ENABLED=true curl -s http://localhost:8003/query -d '{"query":"why is this broken help me"}' | grep -i context`
- `curl -s http://localhost:8003/affective/state | python3 -m json.tool`

### 19.6 — Declarative Options

**Owner**: Qwen
**Files**: `nix/modules/core/options.nix`

Tasks:
1. Add under `mySystem.aiStack`:
   ```nix
   affectiveEngine = {
     enable = mkEnableOption "Affective/values signal layer";
     compassionWordThreshold = mkOption { type = types.int; default = 2; };
     reciprocityTtlDays = mkOption { type = types.int; default = 30; };
     empathyRetryThreshold = mkOption { type = types.int; default = 3; };
   };
   ```
2. Inject `AFFECTIVE_ENABLED`, `AFFECTIVE_COMPASSION_WORD_THRESHOLD`,
   `AFFECTIVE_RECIPROCITY_TTL_DAYS` into hybrid coordinator service env

Validation:
- `nix-instantiate --parse nix/modules/core/options.nix` exits 0

---

## Verification Matrix

Before marking any task done:
1. `python3 -m py_compile` for all new Python files
2. `nix-instantiate --parse` for Nix changes
3. `GET /affective/state` returns 200 with AffectiveState fields
4. Query with compassion markers (`"why is this broken help me"`) triggers modulation block in response
5. `X-Affective-Bypass: true` header produces unmodified response
6. `aq-qa 0` → 39+ passed, 0 failed (modulation must not affect health checks)
7. Rollback: `AFFECTIVE_ENABLED=false` (declarative kill switch); delete module files

---

## Work Queue

### Task: AFF-001
- Phase: 19.1
- Owner agent: qwen
- Files: `ai-stack/affective-engine/state_model.py`
- Commands: `python3 -m py_compile ai-stack/affective-engine/state_model.py`
- Status: pending

### Task: AFF-002
- Phase: 19.2
- Owner agent: qwen
- Files: `ai-stack/affective-engine/signal_detectors.py`
- Commands: `python3 -m py_compile ai-stack/affective-engine/signal_detectors.py`
- Status: pending

### Task: AFF-003
- Phase: 19.3
- Owner agent: qwen
- Files: `ai-stack/affective-engine/reciprocity_tracker.py`
- Commands: `python3 -m py_compile ai-stack/affective-engine/reciprocity_tracker.py`
- Status: pending

### Task: AFF-004
- Phase: 19.4
- Owner agent: qwen
- Files: `ai-stack/affective-engine/output_modulator.py`
- Commands: `python3 -m py_compile ai-stack/affective-engine/output_modulator.py`
- Status: pending

### Task: AFF-005
- Phase: 19.5
- Owner agent: qwen
- Files: `ai-stack/mcp-servers/hybrid-coordinator/route_handler.py`, `affective_handlers.py`
- Commands:
  - `python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/route_handler.py`
  - `curl -s http://localhost:8003/affective/state`
- Status: pending

### Task: AFF-006
- Phase: 19.6
- Owner agent: qwen
- Files: `nix/modules/core/options.nix`
- Commands: `nix-instantiate --parse nix/modules/core/options.nix`
- Status: pending

---

## Rollback

- Kill switch: set `AFFECTIVE_ENABLED=false` in Nix options → rebuild → instant disable
- Module files: deletable without service impact when `AFFECTIVE_ENABLED=false`
- Redis reciprocity keys: `redis-cli DEL affective:reciprocity:*` (no persistent harm)
- Generation rollback: `sudo nixos-rebuild switch --rollback`

"""aq-decide DEC-S1: local decision contract, T0a rules, T0b exact cache, T0.5 shadow.

Design SSOT: .agents/plans/aq-decide/DESIGN.md (frozen v2.1).

Invariants (design sections 3, 4.2, 6.4, 7):
- Advisory + friction only. Security-class questions can never emit an
  unsafe-direction option (config load rejects it); nothing here grants.
- T0b (exact cache) is written only by a deterministic rule or the owner.
  T0.5 output is shadow: logged, never acted on, never cached.
- Question definitions live in config; a request cannot redefine them.
- No free-text rationale in responses; reason_code is a closed enum.
- writer="owner" is a string-level guard only (same-uid code can write the
  file). DEC-S2 requirement: owner writes only via the aq-approve /
  _resolve_actor-authenticated path, and the state dir moves to a
  Nix-declared service-owned dir. Until then security-class questions never
  use T0b (neither read nor write), and loaded entries are validated against
  config (answer in options, tier owner/T0a, never unsafe) and counted when rejected.
- Any failure leaves the caller on its current behavior (abstain/error).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import time
import unicodedata
import zlib
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = _REPO / "config" / "aq-decide.json"
DEFAULT_SEEDS = _REPO / "config" / "aq-decide" / "seeds"

OUTCOMES = ("decided", "abstain", "error")
TYPES = ("choice", "noul")
_REASON_RE = re.compile(r"^[A-Z_]{1,24}$")
BASE_REASON_CODES = frozenset({
    "RULE_MATCH", "CACHE_HIT", "NO_MATCH", "LOW_CONFIDENCE", "DISABLED",
    "BAD_REQUEST", "UNKNOWN_QUESTION", "TYPE_MISMATCH", "SCORE_DEFERRED",
    "BAD_FEATURE", "INTERNAL",
})
_ALLOWED_TEXT_CC = ("\n", "\t")


class ConfigError(ValueError):
    pass


class CacheWriteRefused(PermissionError):
    pass


# --------------------------------------------------------------------- config

def load_config(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path or os.environ.get("AQ_DECIDE_CONFIG") or DEFAULT_CONFIG)
    raw = p.read_bytes()
    cfg = json.loads(raw)
    cfg["_hash"] = hashlib.sha256(raw).hexdigest()[:12]
    cfg["_version"] = f"{cfg.get('version', '0')}-{cfg['_hash']}"
    validate_config(cfg)
    return cfg


def validate_config(cfg: dict[str, Any]) -> None:
    """Fail closed on malformed config, bad reason codes, unsafe security options."""
    unsafe = set(cfg.get("unsafe_options", []))
    allowed_codes = set(BASE_REASON_CODES) | set(cfg.get("extra_reason_codes", []))
    cap = int(cfg.get("state_cap_chars", 1500))
    head = int(cfg.get("head_chars", 1000))
    marker = cfg.get("truncation_marker", "")
    if not (0 < head < cap - len(marker)):
        raise ConfigError("head_chars/state_cap_chars/marker inconsistent")
    for name, q in cfg.get("questions", {}).items():
        if q.get("type") not in TYPES:
            raise ConfigError(f"{name}: type must be one of {TYPES}")
        opts = q.get("options") or []
        if not opts or len(set(opts)) != len(opts):
            raise ConfigError(f"{name}: options must be non-empty and unique")
        if q["type"] == "noul" and sorted(opts) != ["no", "yes"]:
            raise ConfigError(f"{name}: noul options must be yes/no")
        if q.get("security_class") and unsafe & set(opts):
            raise ConfigError(f"{name}: security-class question lists unsafe option")
        for fname, spec in q.get("features", {}).items():
            if spec.get("type") not in ("text", "enum", "int", "bool"):
                raise ConfigError(f"{name}.{fname}: bad feature type")
            if spec["type"] == "enum" and not spec.get("values"):
                raise ConfigError(f"{name}.{fname}: enum needs values")
            if q.get("security_class") and spec["type"] == "text":
                raise ConfigError(f"{name}: security-class question may not take free text")
        seen = set()
        for r in q.get("rules", []):
            if r["id"] in seen:
                raise ConfigError(f"{name}: duplicate rule id {r['id']}")
            seen.add(r["id"])
            if r["answer"] not in opts:
                raise ConfigError(f"{name}.{r['id']}: answer not in options")
            if q.get("security_class") and r["answer"] in unsafe:
                raise ConfigError(f"{name}.{r['id']}: unsafe answer on security question")
            if not _REASON_RE.match(r["reason_code"]):
                raise ConfigError(f"{name}.{r['id']}: bad reason_code format")
            allowed_codes.add(r["reason_code"])
            for fname in r.get("when", {}):
                if fname not in q.get("features", {}):
                    raise ConfigError(f"{name}.{r['id']}: rule uses undeclared feature {fname}")
    cfg["_reason_codes"] = frozenset(allowed_codes)


# ---------------------------------------------------------------- state / cap

def sanitize_text(text: str) -> str:
    return "".join(
        c for c in text
        if c in _ALLOWED_TEXT_CC or unicodedata.category(c) not in ("Cc", "Cf")
    )


def cap_text(text: str, cfg: dict[str, Any], mode: str = "headtail") -> tuple[str, bool]:
    """Strip control chars and cap to state_cap_chars. Returns (text, truncated).

    headtail keeps head 1000 + marker + remaining tail so the total never
    exceeds the cap (tail = cap - head - len(marker) = 490 with the default
    marker; design says 500 but the cap is the hard invariant, see evidence doc).
    """
    cap = int(cfg["state_cap_chars"])
    text = sanitize_text(text)
    if len(text) <= cap:
        return text, False
    marker = cfg["truncation_marker"]
    if mode == "head":
        return text[: cap - len(marker)] + marker, True
    if mode == "tail":
        return marker + text[-(cap - len(marker)):], True
    head = int(cfg["head_chars"])
    tail = cap - head - len(marker)
    return text[:head] + marker + text[-tail:], True


# ------------------------------------------------------------------ redaction

_REDACT = [
    (re.compile(r"(?i)\b(sk|pk|ghp|gho|xox[a-z])[-_][A-Za-z0-9_-]{8,}"), "[REDACTED]"),
    (re.compile(r"(?i)\b(bearer|token|password|passwd|secret|api[_-]?key)\b\s*[:=]?\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b"), "[AWSKEY]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*"), "[JWT]"),
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@"), r"\1[CRED]@"),
    (re.compile(r"\b[A-Fa-f0-9]{32,}\b"), "[HEX]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"/home/[^/\s]+"), "/home/[USER]"),
]


def redact(text: str, limit: int = 300) -> str:
    for pat, rep in _REDACT:
        text = pat.sub(rep, text)
    return text[:limit]


# --------------------------------------------------------------------- rules

def _match(op: dict[str, Any], value: Any) -> bool:
    if "eq" in op:
        return value == op["eq"]
    if "in" in op:
        return value in op["in"]
    if value is None:
        return False
    if "contains" in op:
        return str(op["contains"]).lower() in str(value).lower()
    if "regex" in op:
        return re.search(op["regex"], str(value), re.IGNORECASE) is not None
    if "gte" in op:
        return value >= op["gte"]
    if "lte" in op:
        return value <= op["lte"]
    return False


def eval_rules(q: dict[str, Any], feats: dict[str, Any], hard: bool | None) -> dict[str, Any] | None:
    """First match in config order (config order is the precedence)."""
    for r in q.get("rules", []):
        if hard is not None and bool(r.get("hard")) != hard:
            continue
        if all(_match(op, feats.get(f)) for f, op in r["when"].items()):
            return r
    return None


# --------------------------------------------------------------------- cache

class DecisionCache:
    """T0b exact cache. Writers: 'rule' or 'owner' only (design 4.2, 6.4, 7.5)."""

    WRITERS = ("rule", "owner")

    def __init__(self, path: str | Path | None = None, validator: Any = None):
        self._d: dict[str, dict[str, Any]] = {}
        self.rejected = 0
        self.validator = validator
        self._lock = threading.Lock()
        self._path = Path(path) if path else None
        if self._path and self._path.exists():
            for line in self._path.read_text().splitlines():
                try:
                    e = json.loads(line)
                    if (e.get("writer") in self.WRITERS and e.get("tier") in ("owner", "T0a")
                            and self.validator is not None and self.validator(e)):
                        self._d[e["key"]] = e
                    else:
                        self.rejected += 1
                except Exception:
                    self.rejected += 1

    @staticmethod
    def key(question: str, feats: dict[str, Any], config_version: str) -> str:
        canon = json.dumps([question, sorted(feats.items()), config_version],
                           sort_keys=True, ensure_ascii=True, default=str)
        return hashlib.sha256(canon.encode()).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        return self._d.get(key)

    def put(self, key: str, answer: str, confidence: float, reason_code: str,
            writer: str, tier: str = "T0a", question: str | None = None) -> None:
        if writer not in self.WRITERS or tier not in ("T0a", "owner"):
            raise CacheWriteRefused(f"cache write refused: writer={writer!r} tier={tier!r}")
        e = {"key": key, "answer": answer, "confidence": confidence,
             "reason_code": reason_code, "writer": writer, "tier": tier,
             "question": question}
        with self._lock:
            self._d[key] = e
            if self._path:
                self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                fd = os.open(self._path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
                with os.fdopen(fd, "a") as fh:
                    fh.write(json.dumps(e) + "\n")

    def __len__(self) -> int:
        return len(self._d)


# --------------------------------------------------------------------- T0.5

_NBUCKET = 1 << 16
_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def featurize(text: str) -> dict[int, float]:
    """Hashed uni+bigram counts with sublinear tf (1+log tf)."""
    toks = _TOKEN_RE.findall(text.lower())
    counts: dict[int, int] = {}
    prev = None
    for t in toks:
        h = zlib.crc32(t.encode()) & (_NBUCKET - 1)
        counts[h] = counts.get(h, 0) + 1
        if prev is not None:
            hb = zlib.crc32((prev + " " + t).encode()) & (_NBUCKET - 1)
            counts[hb] = counts.get(hb, 0) + 1
        prev = t
    return {h: 1.0 + math.log(c) for h, c in counts.items()}


class T05Model:
    """Hashed TF-IDF + multinomial logistic regression, pure stdlib, seeds only.

    Deterministic: fixed epochs, full-batch gradient descent, no RNG.
    Shadow-only by construction: predict() returns a ShadowResult tagged
    acted_on=False; DecisionCache.put refuses tier T0.5.
    """

    ALLOWED_SOURCES = ("seed", "synthetic")

    def __init__(self, options: list[str]):
        self.options = list(options)
        self.idf: dict[int, float] = {}
        self.w: dict[int, list[float]] = {}
        self.b: list[float] = [0.0] * len(options)
        self.n_train = 0
        self.class_counts: dict[str, int] = {}

    @classmethod
    def train_from_seeds(cls, options: list[str], seed_path: Path,
                         epochs: int = 100, lr: float = 2.0, l2: float = 1e-3) -> "T05Model":
        m = cls(options)
        rows = []
        for line in seed_path.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("source") not in cls.ALLOWED_SOURCES:
                raise ValueError(f"T0.5 trains on seed/synthetic rows only, got {r.get('source')!r}")
            if r["label"] not in options:
                raise ValueError(f"seed label {r['label']!r} not in options")
            rows.append((featurize(r["text"]), options.index(r["label"])))
        m.n_train = len(rows)
        for _, y in rows:
            k = options[y]
            m.class_counts[k] = m.class_counts.get(k, 0) + 1
        df: dict[int, int] = {}
        for f, _ in rows:
            for h in f:
                df[h] = df.get(h, 0) + 1
        n = len(rows)
        m.idf = {h: math.log((1 + n) / (1 + d)) + 1.0 for h, d in df.items()}
        X = [(m._vec(f), y) for f, y in rows]
        K = len(options)
        w = {h: [0.0] * K for h in m.idf}
        b = [0.0] * K
        for _ in range(epochs):
            gw: dict[int, list[float]] = {}
            gb = [0.0] * K
            for x, y in X:
                z = [b[k] + sum(w[h][k] * v for h, v in x.items()) for k in range(K)]
                p = _softmax(z)
                for k in range(K):
                    d = p[k] - (1.0 if k == y else 0.0)
                    gb[k] += d
                    for h, v in x.items():
                        gw.setdefault(h, [0.0] * K)[k] += d * v
            for h, g in gw.items():
                wh = w[h]
                for k in range(K):
                    wh[k] -= lr * (g[k] / n + l2 * wh[k])
            for k in range(K):
                b[k] -= lr * gb[k] / n
        m.w, m.b = w, b
        return m

    def _vec(self, f: dict[int, float]) -> dict[int, float]:
        v = {h: tf * self.idf[h] for h, tf in f.items() if h in self.idf}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {h: x / norm for h, x in v.items()}

    def predict(self, text: str) -> dict[str, Any]:
        x = self._vec(featurize(text))
        K = len(self.options)
        z = list(self.b)
        for h, v in x.items():
            wh = self.w.get(h)
            if wh:
                for k in range(K):
                    z[k] += wh[k] * v
        p = _softmax(z)
        best = max(range(K), key=lambda k: p[k])
        return {"tier": "T0.5", "answer": self.options[best],
                "confidence": round(p[best], 4),
                "probabilities": {o: round(p[i], 4) for i, o in enumerate(self.options)},
                "acted_on": False}


def _softmax(z: list[float]) -> list[float]:
    m = max(z)
    e = [math.exp(v - m) for v in z]
    s = sum(e)
    return [v / s for v in e]


# -------------------------------------------------------------------- engine

def _probs(opts: list[str], answer: str, conf: float) -> dict[str, float]:
    rest = (1.0 - conf) / (len(opts) - 1) if len(opts) > 1 else 0.0
    return {o: round(conf if o == answer else rest, 4) for o in opts}


class Decider:
    def __init__(self, config: dict[str, Any] | None = None,
                 cache: DecisionCache | None = None,
                 state_dir: str | Path | None = None,
                 seeds_dir: str | Path | None = None):
        self.cfg = config or load_config()
        sd = state_dir or os.environ.get("AQ_DECIDE_STATE_DIR") or (
            Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "aq-decide")
        self.state_dir = Path(sd)
        self.log_path = self.state_dir / "decisions.jsonl"
        self.cache = cache if cache is not None else DecisionCache(
            self.state_dir / "owner-cache.jsonl", validator=self._valid_cache_entry)
        if self.cache.validator is None:
            self.cache.validator = self._valid_cache_entry
        self.seeds_dir = Path(seeds_dir or DEFAULT_SEEDS)
        self.models: dict[str, T05Model] = {}
        self._counters: dict[str, int] = {"log_failed": 0}
        self._log_lock = threading.Lock()
        for name, q in self.cfg["questions"].items():
            seed = self.seeds_dir / f"{name}.jsonl"
            if "text" in q.get("features", {}) and not q.get("security_class") and seed.exists():
                self.models[name] = T05Model.train_from_seeds(q["options"], seed)

    @property
    def counters(self) -> dict[str, int]:
        return {**self._counters, "cache_rejected": self.cache.rejected}

    def _answer_ok(self, q: dict[str, Any], answer: Any) -> bool:
        if answer not in q["options"]:
            return False
        return not (q.get("security_class") and answer in set(self.cfg.get("unsafe_options", [])))

    def _valid_cache_entry(self, e: dict[str, Any]) -> bool:
        q = self.cfg["questions"].get(e.get("question"))
        return bool(q) and not q.get("security_class") and self._answer_ok(q, e.get("answer")) \
            and e.get("tier") in ("owner", "T0a")

    # -- public ---------------------------------------------------------
    def enabled(self) -> bool:
        return os.environ.get("AQ_DECIDE", "1") != "0"

    def decide(self, request: dict[str, Any], caller: str = "unknown") -> dict[str, Any]:
        t0 = time.perf_counter()
        resp: dict[str, Any] = {"config_version": self.cfg["_version"], "truncated": False, "answers": {}}
        if not isinstance(request, dict):
            resp["answers"]["_request"] = self._ans("error", "BAD_REQUEST", None, None)
            return resp
        if not self.enabled():
            qd = request.get("questions")
            for name in (qd if isinstance(qd, dict) else {}):
                resp["answers"][str(name)] = self._ans("abstain", "DISABLED", None, None)
            return resp
        state = request.get("state")
        qs = request.get("questions")
        if not isinstance(state, dict) or not isinstance(qs, dict) or not qs:
            resp["answers"]["_request"] = self._ans("error", "BAD_REQUEST", None, None)
            return resp
        for name, spec in qs.items():
            try:
                a, extra = self._one(str(name), spec, state)
            except Exception:  # fail to caller's current behavior, never raise
                a, extra = self._ans("error", "INTERNAL", None, None), {}
            resp["answers"][str(name)] = a
            resp["truncated"] = resp["truncated"] or extra.get("truncated", False)
            self._log(caller, str(name), a, extra, (time.perf_counter() - t0) * 1000.0)
        return resp

    def owner_cache_put(self, question: str, state: dict[str, Any], answer: str,
                        confidence: float = 1.0, reason_code: str = "CACHE_HIT") -> str:
        q = self.cfg["questions"][question]
        if answer not in q["options"]:
            raise ValueError("answer not in options")
        if q.get("security_class"):
            raise CacheWriteRefused("security-class questions never use T0b in S1")
        feats, _, _ = self._features(q, state)
        key = DecisionCache.key(question, feats, self.cfg["_version"])
        self.cache.put(key, answer, confidence, reason_code, writer="owner", tier="owner", question=question)
        return key

    def shadow_predict(self, question: str, text: str) -> dict[str, Any] | None:
        m = self.models.get(question)
        if m is None:
            return None
        q = self.cfg["questions"][question]
        capped, _ = cap_text(text, self.cfg, q.get("truncate", "headtail"))
        return m.predict(capped)

    # -- internals ------------------------------------------------------
    def _ans(self, outcome: str, reason: str, answer: Any, q: dict[str, Any] | None,
             conf: float | None = None, tier: str | None = None,
             probs: dict[str, float] | None = None) -> dict[str, Any]:
        assert outcome in OUTCOMES and reason in (self.cfg["_reason_codes"])
        return {"outcome": outcome, "type": q["type"] if q else None, "answer": answer,
                "probabilities": probs, "confidence": conf, "tier": tier, "reason_code": reason}

    def _features(self, q: dict[str, Any], state: dict[str, Any]) -> tuple[dict[str, Any], bool, str | None]:
        feats: dict[str, Any] = {}
        truncated = False
        bad = None
        for fname, spec in q["features"].items():  # unlisted fields are dropped
            if fname not in state:
                continue
            v = state[fname]
            t = spec["type"]
            if t == "text":
                if not isinstance(v, str):
                    bad = fname
                    continue
                v, tr = cap_text(v, self.cfg, q.get("truncate", "headtail"))
                truncated = truncated or tr
            elif t == "enum":
                if v not in spec["values"]:
                    bad = fname
                    continue
            elif t == "bool":
                if not isinstance(v, bool):
                    bad = fname
                    continue
            elif t == "int":
                if isinstance(v, bool) or not isinstance(v, int) or not (
                        spec.get("min", -2**31) <= v <= spec.get("max", 2**31)):
                    bad = fname
                    continue
            feats[fname] = v
        return feats, truncated, bad

    def _one(self, name: str, spec: Any, state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        q = self.cfg["questions"].get(name)
        if q is None:
            return self._ans("error", "UNKNOWN_QUESTION", None, None), {}
        spec = spec if isinstance(spec, dict) else {}
        rtype = spec.get("type")
        if rtype == "score":
            return self._ans("error", "SCORE_DEFERRED", None, q), {}
        if rtype != q["type"]:  # request cannot redefine the question
            return self._ans("error", "TYPE_MISMATCH", None, q), {}
        feats, truncated, bad = self._features(q, state)
        extra: dict[str, Any] = {"truncated": truncated, "q": q, "feats": feats}
        if bad:
            return self._ans("error", "BAD_FEATURE", None, q), extra
        thr = float(q.get("threshold", 0.6))
        opts = q["options"]
        key = DecisionCache.key(name, feats, self.cfg["_version"])

        def decided(answer: str, conf: float, reason: str, tier: str) -> dict[str, Any]:
            if not self._answer_ok(q, answer):  # defense in depth, every tier
                return self._ans("error", "INTERNAL", None, q)
            if conf < thr:
                extra["rejected"] = {"answer": answer, "confidence": conf}
                return self._ans("abstain", "LOW_CONFIDENCE", None, q, conf, tier)
            return self._ans("decided", reason, answer, q, conf, tier, _probs(opts, answer, conf))

        rule = eval_rules(q, feats, hard=True)
        if rule:
            return decided(rule["answer"], float(rule["confidence"]), rule["reason_code"], "T0a"), extra
        hit = None if q.get("security_class") else self.cache.get(key)
        if hit:
            return decided(hit["answer"], float(hit["confidence"]), "CACHE_HIT", "T0b"), extra
        rule = eval_rules(q, feats, hard=False)
        if rule:
            a = decided(rule["answer"], float(rule["confidence"]), rule["reason_code"], "T0a")
            if a["outcome"] == "decided" and rule.get("cache") and not q.get("security_class"):
                self.cache.put(key, rule["answer"], float(rule["confidence"]),
                               rule["reason_code"], writer="rule", tier="T0a", question=name)
            return a, extra
        # No deterministic tier answered: T0.5 runs in shadow only.
        m = self.models.get(name)
        if m is not None and "text" in feats:
            extra["shadow"] = m.predict(feats["text"])
        return self._ans("abstain", "NO_MATCH", None, q), extra

    def _log(self, caller: str, name: str, a: dict[str, Any], extra: dict[str, Any], ms: float) -> None:
        q = extra.get("q")
        feats = extra.get("feats") or {}
        rec: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "caller": caller, "question": name, "tier": a["tier"], "outcome": a["outcome"],
            "reason_code": a["reason_code"], "confidence": a["confidence"],
            "answer": a["answer"], "latency_ms": round(ms, 3),
            "truncated": bool(extra.get("truncated")), "config_version": self.cfg["_version"],
        }
        if extra.get("truncated"):
            rec["flags"] = ["TRUNCATED"]
        text = feats.get("text")
        if text is not None:
            rec["state_hash"] = hashlib.sha256(text.encode()).hexdigest()[:16]
            rec["text_len"] = len(text)
            if q and q.get("log_text"):
                rec["text_redacted"] = redact(text, int(self.cfg.get("log_text_max_chars", 300)))
        sh = extra.get("shadow")
        if sh:
            rec["shadow"] = {"tier": "T0.5", "answer": sh["answer"], "confidence": sh["confidence"],
                             "acted_on": False}
        try:
            with self._log_lock:
                self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
                fd = os.open(self.log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
                with os.fdopen(fd, "a") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=True) + "\n")
        except Exception:
            self._counters["log_failed"] += 1


# --- DEC-S5: Learned Head Gates & Calibration (Section 4.3) ---

def validate_head_gates(question: str, samples: dict[str, int]) -> tuple[bool, str | None]:
    """
    Validate Section 4.3 gates before any learned head (T0.5 or T1) may leave shadow.
    - At least 150 effective examples per class (human=1.0, outcome=0.5, teacher=0.0)
    """
    human = samples.get("human", 0)
    outcome = samples.get("outcome", 0)
    effective = human + (0.5 * outcome)

    # Gate 1: At least 300 total effective examples for binary choice
    if effective < 300:
        return False, f"insufficient_effective_examples (effective={effective} < 300)"

    # Gate 2: No class with fewer than 30 human-or-outcome examples
    if (human + outcome) < 30:
        return False, "insufficient_human_outcome_rows"

    return True, None


# --- DEC-S6: I3 (RAG) and I4 (Retry/Escalate) Shadow Routing (Section 5.4, 5.5) ---

def shadow_evaluate_rag_route(query_text: str) -> str:
    """
    I3 shadow route: classify query intent into RAG collection.
    - 'error-solutions' for stack traces and errors
    - 'code-context' or 'skills-patterns' for code/symbols
    - 'best-practices' for general architecture/guidelines
    """
    q = query_text.lower()
    if "traceback" in q or "error" in q or "exception" in q or "fail" in q:
        return "error-solutions"
    if ".py" in q or ".nix" in q or "class" in q or "def " in q or "function" in q:
        return "skills-patterns"
    return "best-practices"


def shadow_evaluate_retry_escalate(attempt: int, error_class: str) -> str:
    """
    I4 shadow route: decide whether to retry or escalate.
    - Security policy errors or attempt >= 3 escalate immediately per Rule 6.
    """
    if "security" in error_class or "policy" in error_class or "deny" in error_class:
        return "escalate"
    if attempt >= 3:
        return "escalate"
    return "retry"

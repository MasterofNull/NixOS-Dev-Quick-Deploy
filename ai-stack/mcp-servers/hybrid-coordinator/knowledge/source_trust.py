"""Request-time source trust; no retrieval payload is persisted or mutated."""

import logging
import math
import os
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass

_LOG = logging.getLogger(__name__)
_INTERNAL = "codebase-context,error-solutions,best-practices,skills-patterns,wiki-sections,solved-issues"
_SESSION = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")
_WARNED = set()
RESULT_KEYS = ("combined_results", "semantic_results", "keyword_results", "sql_results")


def _warn(name):
    if name not in _WARNED:
        _WARNED.add(name)
        _LOG.warning("Invalid source trust option %s; using default", name)


@dataclass(frozen=True)
class TrustConfig:
    mode: str = "observe"
    prior: float = 0.40
    ramp: int = 5
    maximum: float = 0.95
    penalty: float = 0.25
    internal: frozenset = frozenset(_INTERNAL.split(","))
    max_sessions: int = 256
    ttl: float = 3600.0

    @classmethod
    def from_env(cls):
        def number(suffix, default, cast, valid):
            name = "AI_SOURCE_TRUST_" + suffix
            try:
                value = cast(os.environ.get(name, str(default)))
                if not math.isfinite(value) or not valid(value):
                    raise ValueError
                return value
            except (ValueError, OverflowError):
                _warn(name)
                return default

        mode = os.environ.get("AI_SOURCE_TRUST_MODE", "observe")
        if mode not in {"off", "observe", "enforce"}:
            _warn("AI_SOURCE_TRUST_MODE")
            mode = "observe"
        prior = number("SKEPTICAL_PRIOR", .40, float, lambda n: 0 <= n <= 1)
        maximum = number("MAX", .95, float, lambda n: 0 <= n <= 1)
        if prior > maximum:
            _warn("AI_SOURCE_TRUST_SKEPTICAL_PRIOR/MAX")
            prior, maximum = .40, .95
        internal = os.environ.get("AI_SOURCE_TRUST_INTERNAL_COLLECTIONS", _INTERNAL)
        if not internal.strip() or any(not part.strip() for part in internal.split(",")):
            _warn("AI_SOURCE_TRUST_INTERNAL_COLLECTIONS")
            internal = _INTERNAL
        return cls(
            mode=mode, prior=prior, maximum=maximum,
            ramp=number("RAMP_INTERACTIONS", 5, int, lambda n: n >= 1),
            penalty=number("FLAG_PENALTY", .25, float, lambda n: 0 <= n <= 1),
            internal=frozenset(part.strip() for part in internal.split(",")),
            max_sessions=number("MAX_SESSIONS", 256, int, lambda n: n >= 1),
            ttl=number("SESSION_TTL_S", 3600.0, float, lambda n: n > 0),
        )


def source_class(item, config):
    if not isinstance(item, dict) or not isinstance(item.get("payload"), dict):
        return "external"
    payload = item["payload"]
    collection = item.get("collection")
    if not isinstance(collection, str) or collection == "osint-intelligence":
        return "external"
    # Invalid provenance cannot gain trust through another field.
    for field in ("project", "source_trust_level", "url", "source_url", "relative_path", "file_path", "file"):
        if field in payload and not isinstance(payload[field], str):
            return "external"
        if field in item and not isinstance(item[field], str):
            return "external"
    level = payload.get("source_trust_level")
    if level == "trusted" or (collection in config.internal and "source_trust_level" not in payload):
        return "internal"
    return "external"


def source_identity(item):
    if not isinstance(item, dict):
        return ("", "", "")
    payload = item.get("payload")
    payload = payload if isinstance(payload, dict) else {}

    def text(value):
        return value if isinstance(value, str) else ""

    location = ""
    for field in ("url", "source_url", "relative_path", "file_path"):
        value = item.get(field, payload.get(field))
        if isinstance(value, str) and value:
            location = value
            break
    if not location:
        value = payload.get("file")
        if isinstance(value, str) and value:
            location = value
        else:
            value = item.get("id", item.get("point_id", ""))
            location = str(value) if isinstance(value, (str, int)) else ""
    return (text(item.get("collection")), text(item.get("project", payload.get("project"))), location)


class SourceTrust:
    def __init__(self, config=None, clock=time.monotonic):
        self.config = config or TrustConfig.from_env()
        self.clock = clock
        self.sessions = OrderedDict()
        self.lock = threading.Lock()

    def apply(self, results, removed, session_id=None, count=None):
        """Score once per source/request, then partition each list independently."""
        config = self.config
        if config.mode == "off":
            return results
        valid_session = isinstance(session_id, str) and _SESSION.fullmatch(session_id)
        with self.lock:
            now = self.clock()
            for key in list(self.sessions):
                if now - self.sessions[key][0] >= config.ttl:
                    del self.sessions[key]
            state = self.sessions.pop(session_id, (now, OrderedDict()))[1] if valid_session else OrderedDict()
            flagged = {source_identity(item) for item in removed}
            present = {source_identity(item) for key in RESULT_KEYS for item in results.get(key, [])}
            values = {}
            for identity in present | flagged:
                turns, was_flagged = state.pop(identity, (0, False))
                is_flagged = was_flagged or identity in flagged
                # This request earns credit only after its annotation is computed.
                values[identity] = (turns, is_flagged)
                state[identity] = (min(config.ramp, turns + (identity in present and not is_flagged)), is_flagged)
            # Bound sources as well as sessions; eviction resets to the skeptical prior.
            while len(state) > 4096:
                state.popitem(last=False)
            if valid_session:
                self.sessions[session_id] = (now, state)
                while len(self.sessions) > config.max_sessions:
                    self.sessions.popitem(last=False)
            output = dict(results)
            for key in RESULT_KEYS:
                if key not in results:
                    continue
                clean, flagged_bucket = [], []
                for item in results[key]:
                    turns, is_flagged = values[source_identity(item)]
                    category = source_class(item, config)
                    trust = 1.0 if category == "internal" else config.prior + (config.maximum - config.prior) * min(turns, config.ramp) / config.ramp
                    trust *= config.penalty if is_flagged else 1.0
                    annotated = dict(item) if isinstance(item, dict) else {"content": item}
                    annotated.update(source_class=category, source_trust=trust)
                    (flagged_bucket if is_flagged else clean).append(annotated)
                    if count:
                        count(category, is_flagged, config.mode)
                if config.mode == "enforce":
                    clean.sort(key=self._rank, reverse=True)
                    flagged_bucket.sort(key=self._rank, reverse=True)
                output[key] = clean + flagged_bucket
            return output

    @staticmethod
    def _rank(item):
        try:
            rank = float(item.get("rerank_score", item.get("score", 0)))
        except (TypeError, ValueError, OverflowError):
            rank = 0.0
        return max(rank, 0) * item["source_trust"] if math.isfinite(rank) else 0.0

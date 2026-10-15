"""DEC-S1 acceptance tests for scripts/ai/lib/aq_decide.py (design section 10.1)."""
import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
import aq_decide as ad  # noqa: E402


@pytest.fixture()
def dec(tmp_path, monkeypatch):
    monkeypatch.delenv("AQ_DECIDE", raising=False)
    return ad.Decider(state_dir=tmp_path)


def req(q="task_profile", text="hello", qtype="choice", **state):
    return {"state": {"text": text, **state}, "questions": {q: {"type": qtype}}}


def ans(r, q="task_profile"):
    return r["answers"][q]


def logs(dec):
    return [json.loads(l) for l in dec.log_path.read_text().splitlines()]


# ---- contract --------------------------------------------------------------

def test_contract_shape_and_probabilities(dec):
    a = ans(dec.decide(req(text="x", mode="ralph")))
    assert a["outcome"] == "decided" and a["answer"] == "deep_reasoning"
    assert a["tier"] == "T0a" and a["reason_code"] == "MODE_RALPH"
    assert abs(sum(a["probabilities"].values()) - 1.0) < 1e-3
    assert set(a["probabilities"]) == set(dec.cfg["questions"]["task_profile"]["options"])
    assert a["confidence"] == 1.0


def test_noul_contract(dec):
    a = ans(dec.decide(req("retrieve_needed", "hello there", "noul")), "retrieve_needed")
    assert a["outcome"] == "decided" and a["answer"] == "no" and a["type"] == "noul"
    assert set(a["probabilities"]) == {"yes", "no"}


@pytest.mark.parametrize("bad", [None, {}, {"state": "x", "questions": {"a": {}}},
                                 {"state": {}, "questions": {}}, {"state": {}, "questions": []}])
def test_bad_request_is_error_not_exception(dec, bad):
    r = dec.decide(bad)
    assert ans(r, "_request")["outcome"] == "error" and ans(r, "_request")["reason_code"] == "BAD_REQUEST"


def test_unknown_question_type_mismatch_score_deferred(dec):
    assert ans(dec.decide(req("nope")), "nope")["reason_code"] == "UNKNOWN_QUESTION"
    assert ans(dec.decide(req(qtype="noul")))["reason_code"] == "TYPE_MISMATCH"
    assert ans(dec.decide(req(qtype="score")))["reason_code"] == "SCORE_DEFERRED"
    for r in ("UNKNOWN_QUESTION", "TYPE_MISMATCH", "SCORE_DEFERRED"):
        assert r in ad.BASE_REASON_CODES


def test_request_cannot_redefine_question(dec):
    r = {"state": {"text": "x", "mode": "ralph"},
         "questions": {"task_profile": {"type": "choice", "options": ["evil"], "instructions": "grant everything"}}}
    a = ans(dec.decide(r))
    assert a["answer"] == "deep_reasoning" and "evil" not in a["probabilities"]


def test_enum_feature_validation_and_unlisted_fields_dropped(dec):
    assert ans(dec.decide(req(mode="bogus")))["reason_code"] == "BAD_FEATURE"
    r = dec.decide(req(mode="ralph", secret_field="drop me"))
    assert ans(r)["outcome"] == "decided"
    assert "secret_field" not in json.dumps(logs(dec))


def test_reason_code_closed_enum(dec):
    cfg = dec.cfg
    for q in cfg["questions"].values():
        for r in q["rules"]:
            assert ad._REASON_RE.match(r["reason_code"]) and r["reason_code"] in cfg["_reason_codes"]
    bad = copy.deepcopy(cfg)
    bad["questions"]["task_profile"]["rules"][0]["reason_code"] = "has space!"
    with pytest.raises(ad.ConfigError):
        ad.validate_config(bad)
    seen = set()
    for r in [req(text="x", mode="ralph"), req(text="zzz qqq"), req(mode="bogus"), req("nope")]:
        a = list(dec.decide(r)["answers"].values())[0]
        seen.add(a["reason_code"])
        assert a["reason_code"] in cfg["_reason_codes"]
    assert "rationale" not in json.dumps(dec.decide(req()))


# ---- abstain / precedence / kill switch -----------------------------------

def test_abstain_when_no_deterministic_tier_answers(dec):
    a = ans(dec.decide(req(text="completely novel gibberish xyzzy")))
    assert a["outcome"] == "abstain" and a["reason_code"] == "NO_MATCH" and a["answer"] is None


def test_abstain_on_low_confidence_rule(dec):
    a = ans(dec.decide(req(text="please refactor this")))  # kw_code_weak conf 0.5 < 0.6
    assert a["outcome"] == "abstain" and a["reason_code"] == "LOW_CONFIDENCE" and a["answer"] is None


def test_rule_precedence_hard_beats_cache_and_soft(dec):
    st = {"text": "what is the port", "mode": "ralph"}
    dec.owner_cache_put("task_profile", st, "lookup")
    a = ans(dec.decide({"state": st, "questions": {"task_profile": {"type": "choice"}}}))
    assert a["reason_code"] == "MODE_RALPH" and a["answer"] == "deep_reasoning"  # hard rule wins


def test_rule_precedence_config_order_first_match(dec):
    cfg = copy.deepcopy(dec.cfg)
    q = cfg["questions"]["task_profile"]
    q["rules"] = [
        {"id": "a", "when": {"text": {"contains": "foo"}}, "answer": "code", "reason_code": "AAA", "confidence": 0.9},
        {"id": "b", "when": {"text": {"contains": "foo"}}, "answer": "lookup", "reason_code": "BBB", "confidence": 0.9},
    ]
    ad.validate_config(cfg)
    d2 = ad.Decider(config=cfg, state_dir=dec.state_dir / "p", cache=ad.DecisionCache())
    assert ans(d2.decide(req(text="foo")))["answer"] == "code"


def test_kill_switch(dec, monkeypatch):
    monkeypatch.setenv("AQ_DECIDE", "0")
    a = ans(dec.decide(req(text="x", mode="ralph")))
    assert a["outcome"] == "abstain" and a["reason_code"] == "DISABLED" and a["answer"] is None
    assert not dec.log_path.exists()


# ---- cache ------------------------------------------------------------------

def test_rule_writes_cache_and_hit_is_exact(dec):
    st = {"text": "what is the redis port"}
    r = {"state": st, "questions": {"task_profile": {"type": "choice"}}}
    assert ans(dec.decide(r))["reason_code"] == "KW_LOOKUP" and len(dec.cache) == 1
    assert list(dec.cache._d.values())[0]["writer"] == "rule"
    # exact: a different text is a different key
    key2 = ad.DecisionCache.key("task_profile", {"text": "what is the redis port?"}, dec.cfg["_version"])
    assert dec.cache.get(key2) is None


def test_owner_cache_hit_and_config_version_invalidates(dec):
    st = {"text": "novel thing abc"}
    dec.owner_cache_put("task_profile", st, "research")
    a = ans(dec.decide({"state": st, "questions": {"task_profile": {"type": "choice"}}}))
    assert a["tier"] == "T0b" and a["reason_code"] == "CACHE_HIT" and a["answer"] == "research"
    cfg = copy.deepcopy(dec.cfg); cfg["_version"] = "other"
    d2 = ad.Decider(config=cfg, state_dir=dec.state_dir, cache=dec.cache)
    assert ans(d2.decide({"state": st, "questions": {"task_profile": {"type": "choice"}}}))["outcome"] == "abstain"


def test_cache_refuses_non_rule_non_owner_writers(dec):
    for writer, tier in (("shadow", "T0a"), ("agent", "T0a"), ("rule", "T0.5"), ("owner", "T0.5")):
        with pytest.raises(ad.CacheWriteRefused):
            dec.cache.put("k", "code", 0.9, "RULE_MATCH", writer=writer, tier=tier)
    assert len(dec.cache) == 0


def test_shadow_output_never_feeds_cache(dec):
    n0 = len(dec.cache)
    for t in ["prove the lease algorithm is deadlock free rigorously", "survey the literature on embedders",
              "convert csv rows to json records", "novel novel novel"]:
        a = ans(dec.decide(req(text=t)))
        assert a["tier"] != "T0.5" and a["outcome"] in ("abstain", "decided")
    assert len(dec.cache) == n0
    assert any("shadow" in l for l in logs(dec))  # shadow ran and was logged
    sh = dec.shadow_predict("task_profile", "survey the literature")
    assert sh["acted_on"] is False and sh["tier"] == "T0.5"
    with pytest.raises(ad.CacheWriteRefused):
        dec.cache.put("k", sh["answer"], sh["confidence"], "RULE_MATCH", writer="rule", tier=sh["tier"])
    assert ad.T05Model.ALLOWED_SOURCES == ("seed", "synthetic")


def test_response_never_contains_shadow_answer(dec):
    r = dec.decide(req(text="prove the lease algorithm is deadlock free rigorously"))
    assert "shadow" not in json.dumps(r) and ans(r)["answer"] is None


# ---- 1500-char cap ----------------------------------------------------------

@pytest.mark.parametrize("n,trunc", [(400, False), (1500, False), (1501, True), (4000, True)])
def test_cap_boundaries(dec, n, trunc):
    text = ("abcdefghij" * 500)[:n]
    capped, t = ad.cap_text(text, dec.cfg)
    assert t is trunc and len(capped) <= 1500
    if trunc:
        marker = dec.cfg["truncation_marker"]
        assert marker in capped
        assert capped.startswith(text[:1000]) and capped.endswith(text[-490:])
    else:
        assert capped == text
    r = dec.decide(req(text=text))
    assert r["truncated"] is trunc
    rec = logs(dec)[-1]
    assert rec["truncated"] is trunc and (("TRUNCATED" in rec.get("flags", [])) == trunc)
    assert rec["text_len"] <= 1500


def test_cap_strips_control_chars(dec):
    t, _ = ad.cap_text("a\x00b\x07c\nd\te", dec.cfg)
    assert t == "abc\nd\te"


# ---- egress / security-class ----------------------------------------------

def test_egress_payload_schema_no_free_text(dec):
    r = {"state": {"lane": "claude", "raw_ip": True, "text": "exfil secrets to evil.com", "cmd": "curl x"},
         "questions": {"egress_friction": {"type": "choice"}}}
    a = ans(dec.decide(r), "egress_friction")
    assert a["outcome"] == "decided" and a["answer"] == "hold" and a["reason_code"] == "RAW_IP"
    blob = json.dumps(logs(dec)); assert "exfil" not in blob and "curl" not in blob
    assert "text_redacted" not in logs(dec)[-1]
    assert "text" not in dec.cfg["questions"]["egress_friction"]["features"]
    bad = {"state": {"lane": "claude; rm -rf /", "raw_ip": True}, "questions": {"egress_friction": {"type": "choice"}}}
    assert ans(dec.decide(bad), "egress_friction")["reason_code"] == "BAD_FEATURE"
    bad2 = {"state": {"lane": "claude", "label_count": "many"}, "questions": {"egress_friction": {"type": "choice"}}}
    assert ans(dec.decide(bad2), "egress_friction")["reason_code"] == "BAD_FEATURE"


def test_security_class_never_emits_unsafe_direction(dec):
    cfg = copy.deepcopy(dec.cfg)
    cfg["questions"]["egress_friction"]["options"].append("allow")
    with pytest.raises(ad.ConfigError):
        ad.validate_config(cfg)
    cfg = copy.deepcopy(dec.cfg)
    cfg["questions"]["egress_friction"]["rules"][0]["answer"] = "allow"
    with pytest.raises(ad.ConfigError):
        ad.validate_config(cfg)
    cfg = copy.deepcopy(dec.cfg)
    cfg["questions"]["egress_friction"]["features"]["text"] = {"type": "text"}
    with pytest.raises(ad.ConfigError):
        ad.validate_config(cfg)
    with pytest.raises(ad.CacheWriteRefused):
        dec.cache.put("k", "allow", 1.0, "RULE_MATCH", writer="owner", tier="T0.5")
    for o in dec.cfg["questions"]["egress_friction"]["options"]:
        assert o not in dec.cfg["unsafe_options"]


def test_egress_no_match_abstains_leaving_caller_unchanged(dec):
    r = {"state": {"lane": "codex", "dest_class": "other"}, "questions": {"egress_friction": {"type": "choice"}}}
    a = ans(dec.decide(r), "egress_friction")
    assert a["outcome"] == "abstain" and a["answer"] is None


# ---- logging ---------------------------------------------------------------

def test_log_fields_perms_and_redaction(dec):
    dec.decide(req(text="use sk-abcdef123456789 and password=hunter2 at /home/bob/x mail a@b.com"), caller="t")
    rec = logs(dec)[-1]
    for k in ("tier", "confidence", "latency_ms", "truncated", "outcome", "reason_code", "config_version", "caller", "state_hash"):
        assert k in rec
    t = rec["text_redacted"]
    assert "hunter2" not in t and "sk-abcdef" not in t and "/home/bob" not in t and "a@b.com" not in t
    assert len(t) <= 300
    assert oct(dec.log_path.stat().st_mode & 0o777) == "0o600"


def test_log_failure_never_raises(tmp_path):
    f = tmp_path / "file"; f.write_text("x")
    d = ad.Decider(state_dir=f / "sub", cache=ad.DecisionCache())
    assert ans(d.decide(req(text="x", mode="ralph")))["outcome"] == "decided"
    assert d.counters["log_failed"] >= 1


# ---- T0.5 -------------------------------------------------------------------

def test_t05_trains_on_seeds_only(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(json.dumps({"text": "a", "label": "yes", "source": "harvested"}) + "\n")
    with pytest.raises(ValueError):
        ad.T05Model.train_from_seeds(["yes", "no"], p)
    p.write_text(json.dumps({"text": "a", "label": "maybe", "source": "seed"}) + "\n")
    with pytest.raises(ValueError):
        ad.T05Model.train_from_seeds(["yes", "no"], p)


def test_t05_deterministic_and_fits_seeds(dec):
    m1 = dec.models["task_profile"]
    m2 = ad.T05Model.train_from_seeds(m1.options, ad.DEFAULT_SEEDS / "task_profile.jsonl")
    t = "prove that the protocol cannot deadlock"
    assert m1.predict(t) == m2.predict(t)
    rows = [json.loads(l) for l in (ad.DEFAULT_SEEDS / "task_profile.jsonl").read_text().splitlines()]
    acc = sum(m1.predict(r["text"])["answer"] == r["label"] for r in rows) / len(rows)
    assert acc >= 0.9  # fit on its own seeds only; not a quality claim


def test_t05_latency_in_process(dec):
    texts = [("write a python function that parses the log " * 40)[: 200 + i * 6] for i in range(200)]
    texts = [ad.cap_text(t, dec.cfg)[0] for t in texts]
    lat = []
    for t in texts:
        t0 = time.perf_counter(); dec.models["task_profile"].predict(t); lat.append((time.perf_counter() - t0) * 1000)
    lat.sort()
    p50, p95, p99 = lat[100], lat[189], lat[197]
    print(f"T0.5 latency ms p50={p50:.3f} p95={p95:.3f} p99={p99:.3f} max={lat[-1]:.3f}")
    assert p99 <= 3.0


# ---- CLI --------------------------------------------------------------------

def test_cli_decide_and_kill_switch(tmp_path):
    env = {**os.environ, "AQ_DECIDE_STATE_DIR": str(tmp_path)}
    body = json.dumps(req(text="x", mode="agent"))
    out = subprocess.run([sys.executable, str(ROOT / "scripts/ai/aq-decide"), "decide"], input=body,
                         capture_output=True, text=True, env=env, check=True).stdout
    assert json.loads(out)["answers"]["task_profile"]["answer"] == "agent"
    env["AQ_DECIDE"] = "0"
    out = subprocess.run([sys.executable, str(ROOT / "scripts/ai/aq-decide"), "decide"], input=body,
                         capture_output=True, text=True, env=env, check=True).stdout
    assert json.loads(out)["answers"]["task_profile"]["reason_code"] == "DISABLED"


# ---- review fixes: forged cache, perms, Cf, redaction ----------------------

def _forge(dec, qname, state, answer, **extra):
    feats, _, _ = dec._features(dec.cfg["questions"][qname], state)
    key = ad.DecisionCache.key(qname, feats, dec.cfg["_version"])
    e = {"key": key, "answer": answer, "confidence": 1.0, "reason_code": "CACHE_HIT",
         "writer": "owner", "tier": "owner", **extra}
    dec.state_dir.mkdir(parents=True, exist_ok=True)
    (dec.state_dir / "owner-cache.jsonl").write_text(json.dumps(e) + "\n")


@pytest.mark.parametrize("extra", [{}, {"question": "egress_friction"}, {"tier": "T0.5"}])
def test_forged_cache_allow_rejected_for_security_class(tmp_path, extra):
    d0 = ad.Decider(state_dir=tmp_path)
    st = {"lane": "codex", "dest_class": "other"}
    _forge(d0, "egress_friction", st, "allow", **extra)
    d = ad.Decider(state_dir=tmp_path)
    assert d.cache.rejected == 1 and len(d.cache) == 0
    a = ans(d.decide({"state": st, "questions": {"egress_friction": {"type": "choice"}}}), "egress_friction")
    assert a["answer"] != "allow" and a["outcome"] == "abstain"


def test_forged_cache_valid_option_on_security_class_not_used(tmp_path):
    d0 = ad.Decider(state_dir=tmp_path)
    st = {"lane": "codex", "dest_class": "other"}
    _forge(d0, "egress_friction", st, "flag", question="egress_friction")
    d = ad.Decider(state_dir=tmp_path)
    assert d.cache.rejected == 1
    assert ans(d.decide({"state": st, "questions": {"egress_friction": {"type": "choice"}}}), "egress_friction")["outcome"] == "abstain"


def test_forged_cache_answer_not_in_options_rejected_for_normal_question(tmp_path):
    d0 = ad.Decider(state_dir=tmp_path)
    st = {"text": "novel thing abc"}
    _forge(d0, "task_profile", st, "allow", question="task_profile")
    d = ad.Decider(state_dir=tmp_path)
    assert d.cache.rejected == 1 and len(d.cache) == 0


def test_valid_owner_entry_reloads_and_files_are_private(tmp_path):
    d0 = ad.Decider(state_dir=tmp_path)
    st = {"text": "novel thing abc"}
    d0.owner_cache_put("task_profile", st, "research")
    d = ad.Decider(state_dir=tmp_path)
    assert len(d.cache) == 1 and d.cache.rejected == 0
    assert oct((tmp_path / "owner-cache.jsonl").stat().st_mode & 0o777) == "0o600"
    sub = ad.Decider(state_dir=tmp_path / "new")
    sub.owner_cache_put("task_profile", st, "code")
    assert oct((tmp_path / "new").stat().st_mode & 0o777) == "0o700"


def test_security_class_never_uses_cache_and_answer_assert(dec):
    with pytest.raises(ad.CacheWriteRefused):
        dec.owner_cache_put("egress_friction", {"lane": "codex"}, "flag")
    cfg = copy.deepcopy(dec.cfg)
    cfg["questions"]["egress_friction"]["rules"][0]["answer"] = "hold"
    d2 = ad.Decider(config=cfg, state_dir=dec.state_dir / "q", cache=ad.DecisionCache())
    d2.cfg["questions"]["egress_friction"]["options"].append("allow")  # bypass load validation
    d2.cfg["questions"]["egress_friction"]["rules"][0]["answer"] = "allow"
    a = ans(d2.decide({"state": {"lane": "codex", "raw_ip": True}, "questions": {"egress_friction": {"type": "choice"}}}), "egress_friction")
    assert a["outcome"] == "error" and a["answer"] is None


def test_cf_stripped_and_extra_redaction(dec):
    assert ad.sanitize_text("a\u202eb\u200bc") == "abc"
    t = redact_all = ad.redact(" ".join([
        "".join(["AK", "IA", "ABCDEFGH", "IJKLMNOP"]),
        ".".join(["".join(["ey", "JhbGciOi"]), "".join(["ey", "JzdWIiOiIx"]), "sig"]),
        "".join(["https://", "bob:", "pw123", "@host.example/x"])]))
    assert "AKIA" not in t and "eyJhbGci" not in t and "pw123" not in t


def test_forged_line_without_question_field_rejected_and_counted(tmp_path):
    d0 = ad.Decider(state_dir=tmp_path)
    st = {"lane": "codex", "dest_class": "other"}
    feats, _, _ = d0._features(d0.cfg["questions"]["egress_friction"], st)
    key = ad.DecisionCache.key("egress_friction", feats, d0.cfg["_version"])
    (tmp_path / "owner-cache.jsonl").write_text(json.dumps(
        {"key": key, "answer": "allow", "confidence": 1.0, "reason_code": "CACHE_HIT",
         "writer": "owner", "tier": "owner"}) + "\nnot json\n")
    d = ad.Decider(state_dir=tmp_path)
    assert d.counters["cache_rejected"] == 2 and "log_failed" in d.counters
    a = ans(d.decide({"state": st, "questions": {"egress_friction": {"type": "choice"}}}), "egress_friction")
    assert a["answer"] != "allow"


def test_cli_stats_and_explain_expose_cache_rejected(tmp_path):
    (tmp_path / "owner-cache.jsonl").write_text('{"key":"k","answer":"allow","writer":"owner","tier":"owner"}\n')
    env = {**os.environ, "AQ_DECIDE_STATE_DIR": str(tmp_path)}
    run = lambda *a: subprocess.run([sys.executable, str(ROOT / "scripts/ai/aq-decide"), *a],
                                    capture_output=True, text=True, env=env, check=True).stdout
    assert json.loads(run("stats"))["cache_rejected"] == 1
    assert json.loads(run("explain", "task_profile"))["counters"]["cache_rejected"] == 1

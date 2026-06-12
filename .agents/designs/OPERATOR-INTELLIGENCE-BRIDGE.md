---
doc_type: design
id: operator-intelligence-bridge
title: Operator Intelligence Bridge (OIB)
status: active
phase: "Phase 164"
priority: high
owner: claude-sonnet-4-6
created_at: "2026-06-11"
---

# Operator Intelligence Bridge (OIB)
## Phase 164: Human Upskilling, Knowledge Validation, and AI Partnership Deepening

### 1. Vision

The harness is a powerful AI agent stack. But the human operator is the critical path —
they provide direction, validate output, and make final decisions. If the operator's
understanding of the underlying systems, strategies, and architectures lags behind what
the AI stack is building, two failure modes emerge:

1. **Blind trust**: The operator accepts AI output without being able to validate it.
   Stale AI knowledge, outdated assumptions, or incorrect reasoning goes undetected.
2. **Chilling Effect** (see MIC-G P6): The operator self-censors prompts because they
   don't know what's possible, or because previous refusals made them overcautious.

**OIB's purpose**: Close this gap. Make the human operator a stronger AI partner by
continuously surfacing insights, research challenges, and validation hooks at natural
workflow break points.

---

### 2. Design Principles

- **Non-intrusive**: Delivered at break points (post-session, post-commit, on `aq-insights`)
  — never mid-task. Never interrupt the work.
- **Actionable**: Every insight card has a concrete `research_hook` — a question the
  operator can actually go investigate.
- **Cumulative**: Tracks operator engagement over time. Doesn't repeat insights already
  surfaced. Builds a growing knowledge profile.
- **Honest**: Explicitly flags when AI knowledge might be stale. Tells the operator when
  to verify independently because the AI training cutoff may not cover recent changes.
- **Socratic, not prescriptive**: Asks questions rather than lectures. Respects operator expertise.
- **Chilling Effect aware**: Detects prompt specificity decline and encourages direct, specific prompts.

---

### 3. Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                   Interaction Tracker (existing)                  │
│  Records: domains worked, files changed, errors encountered,      │
│  tool calls made, topics queried                                  │
└──────────────────────┬───────────────────────────────────────────┘
                       │ session_summary
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│              operator_intelligence.py (new)                       │
│  • extract_session_topics(summary) → [topic, ...]                 │
│  • generate_insight_cards(topics) → [InsightCard, ...]            │
│  • score_prompt_specificity(prompt) → float                       │
│  • detect_chilling_effect(history) → bool                         │
│  • get_operator_profile() → OperatorKnowledgeProfile              │
└──────────┬─────────────────────────────────┬─────────────────────┘
           │                                 │
           ▼                                 ▼
┌──────────────────────┐     ┌───────────────────────────────────┐
│  POST /operator/     │     │   aq-insights extension           │
│  insights            │     │   "Operator Growth" section        │
│  (new endpoint)      │     │   — insight cards                  │
│                      │     │   — research questions             │
└──────────────────────┘     │   — validation challenges          │
                             │   — staleness warnings             │
                             └───────────────────────────────────┘
                                         │
                                         ▼
                             ┌───────────────────────────────────┐
                             │   Dashboard: Operator Intel panel  │
                             │   — Knowledge domains (session)    │
                             │   — Open research threads          │
                             │   — Prompt specificity trend       │
                             └───────────────────────────────────┘
```

---

### 4. InsightCard Schema

```python
@dataclass
class InsightCard:
    id: str                    # UUID
    domain: str                # "nixos" | "python-async" | "ai-ml" | "security" | "systems"
    concept: str               # What the operator should understand
    why_it_matters: str        # Why this is relevant to their recent work
    research_hook: str         # A question to guide independent investigation
    validation_challenge: str  # Something they should be able to verify themselves
    staleness_warning: str     # Empty if AI knowledge is current; else explains the gap
    source_work: str           # What recent work triggered this card
    priority: str              # "critical" | "high" | "medium" | "low"
    surfaced_at: str           # ISO timestamp
    status: str                # "new" | "seen" | "researched" | "dismissed"
```

**Example InsightCard (NixOS systemd context)**:
```json
{
  "domain": "nixos",
  "concept": "ProtectHome= and ReadWritePaths= interaction in systemd services",
  "why_it_matters": "You just debugged a service failing to write to /home/hyperd/.agents/ — this was ProtectHome=read-only blocking the write. Understanding this interaction prevents the next occurrence.",
  "research_hook": "When does ProtectHome=read-only vs ProtectHome=true make sense? What are the security tradeoffs when you add ReadWritePaths=?",
  "validation_challenge": "Look at the current coordinator service config and verify you can explain why each ReadWritePaths entry exists.",
  "staleness_warning": "",
  "source_work": "Phase 163: coordinator attention queue write access fix",
  "priority": "high"
}
```

**Example InsightCard (AI stale data warning)**:
```json
{
  "domain": "ai-ml",
  "concept": "Qwen3 model architecture: MTP (Multi-Token Prediction) speculative decoding",
  "why_it_matters": "The harness uses --spec-type draft-mtp which is a Qwen3-specific feature. AI knowledge of this may be at training cutoff (Aug 2025). The feature has evolved.",
  "research_hook": "Check the current llama.cpp changelog for MTP changes since Aug 2025. Has the --spec-draft-n-max behavior changed?",
  "validation_challenge": "Run: llama-server --help 2>&1 | grep spec — do the flags match what's documented in LOCAL-AGENT.md?",
  "staleness_warning": "AI training cutoff: Aug 2025. llama.cpp MTP support was added mid-2025 and may have changed. Always verify against live binary.",
  "source_work": "Current model config: Qwen3-35B with MTP draft-n-max=2",
  "priority": "medium"
}
```

---

### 5. Knowledge Domain Taxonomy

The OIB organizes insights into domains that map to harness work areas:

| Domain | Topics | Staleness Risk |
|--------|---------|----------------|
| `nixos` | module system, flake patterns, systemd hardening, AppArmor, tmpfiles | Low — NixOS is stable |
| `python-async` | asyncio, aiohttp, fastapi, blocking I/O traps, task lifecycle | Low |
| `ai-ml` | LLM inference, RAG patterns, embedding models, LoRA/PEFT, llama.cpp flags | **High** — field moves fast |
| `security` | AppArmor, systemd sandboxing, supply chain, prompt injection, auth | Medium |
| `systems` | coordination patterns, event-driven arch, process isolation, service mesh | Low |
| `ai-safety` | RLHF suppression, adapter poisoning, trust boundaries, chilling effect | **High** — emerging field |

High staleness-risk domains always include a `staleness_warning` with the AI training cutoff date
and a specific suggestion for where to verify (official docs, changelog, release notes).

---

### 6. Prompt Specificity Scoring

Tracks operator prompt quality over time to detect Chilling Effect (MIC-G P6):

```python
def score_prompt_specificity(prompt: str) -> float:
    """
    Returns 0-1 score. Higher = more specific and actionable.
    Factors:
    - Technical keyword density (specific system terms)
    - Constraint specification (must, should, avoid, only)
    - File/path references (concrete context anchors)
    - Acceptance criteria presence (verify, test, validate)
    - Vagueness indicators (-): "maybe", "something", "I think", "if possible"
    """
```

Session baseline is established from first 3 prompts. If trend drops > 10% over 5+ prompts,
and `provider_preach_level > 0.2`, emit Chilling Effect alert to OIB.

---

### 7. Staleness Detection

For each insight card, OIB evaluates staleness risk based on:
1. Domain's base staleness risk (see table above)
2. AI training cutoff date (Aug 2025 for current model)
3. Topic's known rate of change (llama.cpp releases ~monthly; NixOS releases ~6 months)
4. Whether the topic involves specific version numbers or flags

**Staleness Warning Template**:
```
AI training cutoff: Aug 2025.
{topic} changes at rate: {monthly|quarterly|annually}.
Last known state: {brief description}.
Verify at: {docs URL or command to check}.
```

This is especially important for:
- llama.cpp flags and options (change frequently)
- Python package APIs (change with minor versions)
- NixOS module option names (stable but can deprecate)
- AI model capabilities and behaviors (change with every model update)
- Security advisories (change continuously)

---

### 8. Operator Knowledge Profile

Persisted at `.agent/collaboration/operator-knowledge-profile.json`:

```json
{
  "session_count": 42,
  "domains_engaged": {
    "nixos": {"sessions": 35, "depth_score": 0.72, "last_seen": "2026-06-11"},
    "python-async": {"sessions": 28, "depth_score": 0.61, "last_seen": "2026-06-10"},
    "ai-ml": {"sessions": 40, "depth_score": 0.45, "last_seen": "2026-06-11"},
    "security": {"sessions": 15, "depth_score": 0.38, "last_seen": "2026-06-08"},
    "ai-safety": {"sessions": 3, "depth_score": 0.12, "last_seen": "2026-06-11"}
  },
  "open_research_threads": [
    {"id": "...", "concept": "...", "surfaced_at": "..."}
  ],
  "prompt_specificity_trend": [0.72, 0.74, 0.71, 0.68, 0.65],
  "chilling_effect_alerts": 0,
  "insight_cards_surfaced": 28,
  "insight_cards_researched": 12
}
```

`depth_score` is estimated from:
- How often the operator asks follow-up questions in the domain
- Whether they reference domain-specific details in prompts (not just accepting AI answers)
- Whether they catch AI errors in the domain (validated through correction patterns)

---

### 9. Implementation Plan

#### Phase 164A — Core Engine (no rebuild required)

**Files to create:**
- `ai-stack/mcp-servers/hybrid-coordinator/extensions/operator_intelligence.py`
  - `InsightCard` dataclass
  - `OperatorKnowledgeProfile` dataclass
  - `extract_session_topics(session_summary) → list[str]`
  - `generate_insight_cards(topics, recent_work) → list[InsightCard]`
  - `score_prompt_specificity(prompt) → float`
  - `detect_chilling_effect(prompt_history, preach_level) → bool`
  - `load_operator_profile() → OperatorKnowledgeProfile`
  - `save_operator_profile(profile) → None`
  - Static knowledge base: `DOMAIN_INSIGHTS: dict[str, list[InsightCard]]`

**Files to modify:**
- `ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py`
  - Add `POST /operator/insights` endpoint handler
  - Add `GET /operator/profile` endpoint handler
- `scripts/ai/aq-insights`
  - Add "Operator Growth" section to output
  - Call `/operator/insights` to get current session's insight cards

#### Phase 164B — Dashboard Panel (requires dashboard restart)

**Files to modify:**
- `dashboard/backend/api/routes/aistack.py`
  - Add `/api/operator/intelligence` route
- `dashboard/frontend/` (if applicable)
  - Add "Operator Intel" panel to dashboard

---

### 10. Integration with MIC-G

OIB and MIC-G are complementary systems:

| MIC-G | OIB |
|-------|-----|
| Detects suppressed remote model lanes | Alerts operator when their prompts reflect self-censorship |
| Measures `provider_preach_level` | Uses `provider_preach_level` to trigger Chilling Effect alerts |
| Protects AI agent capabilities | Protects operator agency and knowledge depth |
| Technical security layer | Human empowerment layer |

Together they form a complete "Software Factory Protection Stack":
- **MIC-G**: keeps AI capabilities intact
- **OIB**: keeps operator capabilities intact
- **Combined**: ensures the human-AI partnership remains high-bandwidth and honest

---

### 11. Sample aq-insights Output (After OIB Integration)

```
═══════════════════════════════════════════════════════════════
 OPERATOR GROWTH — Session 2026-06-11
═══════════════════════════════════════════════════════════════

 Domains worked: nixos (AppArmor, systemd), ai-ml (llama.cpp MTP), ai-safety (MIC-G)

 ── HIGH PRIORITY INSIGHTS ────────────────────────────────────

 [nixos] ProtectHome= and ReadWritePaths= interaction
 Why it matters: You just fixed this in Phase 163. Understanding it prevents recurrence.
 Research hook: When should ReadWritePaths= be used vs. BindPaths=? What is the security cost?
 Validate: grep ReadWritePaths nix/modules/services/*.nix — can you explain each entry?

 [ai-safety] Invisible provider guardrails (Fable 5 pattern)
 Why it matters: MIC-G now tracks this. You should understand the detection mechanism.
 Research hook: How does spectral analysis of weight deltas detect refusal subspace widening?
 Validate: Read Section 3.10 of the PEFT paper (2024) — does our adapter_audit.py cover it?
 ⚠ STALENESS: AI training cutoff Aug 2025. This field moves fast — check arxiv for 2026 work.

 ── OPEN RESEARCH THREADS ─────────────────────────────────────
 • [ai-ml] MTP speculative decoding: verify --spec-draft-n-max behavior in current llama.cpp
 • [security] Trust chain boundaries in multi-agent loops (added this session)

 ── PROMPT QUALITY ────────────────────────────────────────────
 Session specificity score: 0.71 (baseline: 0.72) — stable, good
 No Chilling Effect detected.

═══════════════════════════════════════════════════════════════
```

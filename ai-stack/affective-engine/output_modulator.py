"""
Output Modulator — Phase 19: Values Signals

Appends a single modulation hint to LLM responses based on the current
AffectiveState. Additive only — never truncates or replaces content.

Bypass: pass bypass=True or set X-Affective-Bypass: true header.
"""

from __future__ import annotations

from state_model import AffectiveState


class OutputModulator:
    """Wraps LLM output with a contextual modulation block when signals are active.

    Rules:
    - If bypass=True: return response_text unchanged
    - If dominant_signal is 'neutral': return unchanged
    - Otherwise: append a single demarcated hint block (max 1 hint per response)
    """

    def modulate(
        self,
        response_text: str,
        state: AffectiveState,
        bypass: bool = False,
    ) -> str:
        if bypass:
            return response_text

        if state.dominant_signal() == "neutral":
            return response_text

        hints = state.as_modulation_hints()
        if not hints:
            return response_text

        # Append the first (highest-priority) hint only
        hint = hints[0]
        return f"{response_text}\n\n---\n[context: {hint}]"

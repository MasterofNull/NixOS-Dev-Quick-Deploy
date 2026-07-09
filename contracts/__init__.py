"""contracts — versioned schemas for configs, payloads, events, and A2A messages.

WS1 (AQ-OS PRD): one typed source of truth. Nothing in the harness should parse
an untyped config dict once a schema exists here. Schemas are validate-only by
default (catch typos/bad types) and MUST NOT reshape data — the raw document
still flows to existing consumers unchanged, so adoption is incremental and
non-breaking.
"""

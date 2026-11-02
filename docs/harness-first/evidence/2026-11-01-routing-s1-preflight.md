# Routing S1 preflight correction — 2026-11-01

Treat llama.cpp n_ctx as per-slot. Forward identical template controls, including false/empty values, to apply-template and byte-upper-bound fallback. Large template kwargs now count toward fallback context refusal.

Validation: 21 focused tests passed; cached diff check passed. Independent Codex accepted source diff SHA256 595b66313f8c24c5371c16e5dee606394f129cf6a895c77ea14d339ae2ba694e. Headless Gemini reviewed the preceding patch; Codex found and verified correction of its fallback omission. Existing mock-socket ResourceWarnings remain.

Live evidence: deployed model reports per-slot n_ctx=8192; real apply-template confirmed enable_thinking=false changes rendering. No inference generation or context exhaustion was performed.

Activation attestation / dated deferral 2026-11-01: integrated in dispatch preflight source. Running activation, complete live dispatch journey, dashboard/health-spider/alert observation, intervention checks and live PM projection are deferred until PR landing and owner deployment. S1 is not declared activated or MVP complete. Routing S2/S3 remain frozen. Initial tier0 passed66/failed1 for missing connected evidence; this document addresses that requirement.

/**
 * Hybrid Coordinator Harness SDK (JavaScript)
 *
 * Publish-ready JavaScript client aligned with harness_sdk.ts.
 */

export class HarnessClient {
  constructor(opts = {}) {
    this.baseUrl = (opts.baseUrl ?? "http://127.0.0.1:8003").replace(/\/+$/, "");
    this.apiKey = opts.apiKey ?? "";
    this.timeoutMs = opts.timeoutMs ?? 30000;
  }

  headers() {
    const headers = { "Content-Type": "application/json" };
    if (this.apiKey) headers["X-API-Key"] = this.apiKey;
    return headers;
  }

  async request(path, init) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const resp = await fetch(`${this.baseUrl}/${path.replace(/^\/+/, "")}`, {
        ...init,
        signal: controller.signal,
        headers: {
          ...this.headers(),
          ...(init?.headers || {}),
        },
      });
      const body = await resp.json();
      if (!resp.ok) {
        const detail = typeof body.error === "string" ? body.error : JSON.stringify(body);
        throw new Error(`HTTP ${resp.status}: ${detail}`);
      }
      return body;
    } finally {
      clearTimeout(timer);
    }
  }

  plan(query) {
    return this.request("/workflow/plan", {
      method: "POST",
      body: JSON.stringify({ query }),
    });
  }

  startSession(query) {
    return this.request("/workflow/session/start", {
      method: "POST",
      body: JSON.stringify({ query }),
    });
  }

  getSession(sessionId) {
    return this.request(`/workflow/session/${sessionId}`, { method: "GET" });
  }

  getSessionWithLineage(sessionId) {
    return this.request(`/workflow/session/${sessionId}?lineage=true`, { method: "GET" });
  }

  listSessions() {
    return this.request("/workflow/sessions", { method: "GET" });
  }

  workflowTree(includeCompleted = true, includeFailed = true, includeObjective = true) {
    const query =
      `include_completed=${includeCompleted ? "true" : "false"}&` +
      `include_failed=${includeFailed ? "true" : "false"}&` +
      `include_objective=${includeObjective ? "true" : "false"}`;
    return this.request(`/workflow/tree?${query}`, { method: "GET" });
  }

  forkSession(sessionId, note = "forked session") {
    return this.request(`/workflow/session/${sessionId}/fork`, {
      method: "POST",
      body: JSON.stringify({ note }),
    });
  }

  advanceSession(sessionId, action, note = "") {
    const payload = { action };
    if (note) payload.note = note;
    return this.request(`/workflow/session/${sessionId}/advance`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  reviewAcceptance(payload) {
    return this.request("/review/acceptance", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  harnessEval(query, expectedKeywords = [], mode = "auto") {
    return this.request("/harness/eval", {
      method: "POST",
      body: JSON.stringify({
        query,
        mode,
        expected_keywords: expectedKeywords,
      }),
    });
  }
}

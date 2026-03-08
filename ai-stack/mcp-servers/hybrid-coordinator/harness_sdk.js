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

  toolingManifest(query, runtime = "python", maxTools, maxResultChars) {
    const payload = { query, runtime };
    if (typeof maxTools === "number") payload.max_tools = maxTools;
    if (typeof maxResultChars === "number") payload.max_result_chars = maxResultChars;
    return this.request("/workflow/tooling-manifest", {
      method: "POST",
      body: JSON.stringify(payload),
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

  runStart(payload) {
    const body = {
      ...payload,
      intent_contract: payload.intent_contract || this.defaultIntentContract(payload.query),
    };
    return this.request("/workflow/run/start", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  defaultIntentContract(query) {
    const normalized = String(query || "").trim() || "workflow run";
    return {
      user_intent: normalized,
      definition_of_done: `Complete requested workflow task: ${normalized.slice(0, 120)}`,
      depth_expectation: "minimum",
      spirit_constraints: ["follow declarative-first policy", "capture validation evidence"],
      no_early_exit_without: ["all requested checks complete"],
    };
  }

  runGet(sessionId, replay = false) {
    return this.request(`/workflow/run/${sessionId}?replay=${replay ? "true" : "false"}`, { method: "GET" });
  }

  runSetMode(sessionId, safetyMode, confirm = false) {
    return this.request(`/workflow/run/${sessionId}/mode`, {
      method: "POST",
      body: JSON.stringify({ safety_mode: safetyMode, confirm }),
    });
  }

  runGetIsolation(sessionId) {
    return this.request(`/workflow/run/${sessionId}/isolation`, { method: "GET" });
  }

  runSetIsolation(sessionId, profile = "", workspaceRoot = "", networkPolicy = "") {
    return this.request(`/workflow/run/${sessionId}/isolation`, {
      method: "POST",
      body: JSON.stringify({
        profile,
        workspace_root: workspaceRoot,
        network_policy: networkPolicy,
      }),
    });
  }

  runEvent(
    sessionId,
    eventType,
    riskClass = "safe",
    approved = false,
    tokenDelta = 0,
    toolCallDelta = 0,
    detail = "",
  ) {
    return this.request(`/workflow/run/${sessionId}/event`, {
      method: "POST",
      body: JSON.stringify({
        event_type: eventType,
        risk_class: riskClass,
        approved,
        token_delta: tokenDelta,
        tool_call_delta: toolCallDelta,
        detail,
      }),
    });
  }

  runReplay(sessionId) {
    return this.request(`/workflow/run/${sessionId}/replay`, { method: "GET" });
  }

  listBlueprints() {
    return this.request("/workflow/blueprints", { method: "GET" });
  }

  parityScorecard() {
    return this.request("/parity/scorecard", { method: "GET" });
  }

  registerRuntime(payload) {
    return this.request("/control/runtimes/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  listRuntimes() {
    return this.request("/control/runtimes", { method: "GET" });
  }

  getRuntime(runtimeId) {
    return this.request(`/control/runtimes/${runtimeId}`, { method: "GET" });
  }

  updateRuntimeStatus(runtimeId, status, note = "") {
    return this.request(`/control/runtimes/${runtimeId}/status`, {
      method: "POST",
      body: JSON.stringify({ status, note }),
    });
  }

  runtimeDeploy(runtimeId, payload) {
    return this.request(`/control/runtimes/${runtimeId}/deployments`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  runtimeRollback(runtimeId, toDeploymentId, reason = "") {
    return this.request(`/control/runtimes/${runtimeId}/rollback`, {
      method: "POST",
      body: JSON.stringify({
        to_deployment_id: toDeploymentId,
        reason,
      }),
    });
  }

  runtimeSchedulePolicy() {
    return this.request("/control/runtimes/schedule/policy", { method: "GET" });
  }

  runtimeSchedule(payload) {
    return this.request("/control/runtimes/schedule/select", {
      method: "POST",
      body: JSON.stringify({
        objective: payload.objective,
        strategy: payload.strategy ?? "weighted",
        include_degraded: payload.includeDegraded ?? false,
        requirements: {
          runtime_class: payload.runtimeClass ?? "",
          transport: payload.transport ?? "",
          tags: payload.tags ?? [],
        },
      }),
    });
  }
}

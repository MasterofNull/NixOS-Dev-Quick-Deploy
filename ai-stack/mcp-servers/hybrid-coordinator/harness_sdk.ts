/**
 * Hybrid Coordinator Harness SDK (TypeScript)
 *
 * Lightweight typed client for workflow planning/session orchestration,
 * reviewer acceptance checks, and harness eval endpoints.
 */

export type Json = Record<string, unknown>;

export interface HarnessClientOptions {
  baseUrl?: string;
  apiKey?: string;
  timeoutMs?: number;
}

export interface ReviewAcceptanceRequest {
  response: string;
  query?: string;
  criteria?: string[];
  expected_keywords?: string[];
  min_criteria_ratio?: number;
  min_keyword_ratio?: number;
  run_harness_eval?: boolean;
}

export interface RunStartRequest {
  query: string;
  safety_mode?: "plan-readonly" | "execute-mutating";
  token_limit?: number;
  tool_call_limit?: number;
  requesting_agent?: string;
  requester_role?: "orchestrator" | "sub-agent";
  intent_contract?: {
    user_intent: string;
    definition_of_done: string;
    depth_expectation: "minimum" | "standard" | "deep";
    spirit_constraints: string[];
    no_early_exit_without: string[];
  };
}

export interface RuntimeScheduleRequest {
  objective: string;
  runtimeClass?: string;
  transport?: string;
  tags?: string[];
  strategy?: string;
  includeDegraded?: boolean;
}

export interface A2AMessagePart {
  type: "text";
  text: string;
}

export interface A2AMessage {
  role: "user" | "agent";
  parts: A2AMessagePart[];
  taskId?: string;
}

export class HarnessClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly timeoutMs: number;

  constructor(opts: HarnessClientOptions = {}) {
    this.baseUrl = (opts.baseUrl ?? "http://127.0.0.1:8003").replace(/\/+$/, "");
    this.apiKey = opts.apiKey ?? "";
    this.timeoutMs = opts.timeoutMs ?? 30_000;
  }

  private headers(): HeadersInit {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.apiKey) headers["X-API-Key"] = this.apiKey;
    return headers;
  }

  private async request(path: string, init?: RequestInit): Promise<Json> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const resp = await fetch(`${this.baseUrl}/${path.replace(/^\/+/, "")}`, {
        ...init,
        signal: controller.signal,
        headers: {
          ...(this.headers() as Record<string, string>),
          ...((init?.headers as Record<string, string>) || {}),
        },
      });
      const body = (await resp.json()) as Json;
      if (!resp.ok) {
        const detail = typeof body.error === "string" ? body.error : JSON.stringify(body);
        throw new Error(`HTTP ${resp.status}: ${detail}`);
      }
      return body;
    } finally {
      clearTimeout(timer);
    }
  }

  private async requestText(path: string, init?: RequestInit): Promise<string> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const resp = await fetch(`${this.baseUrl}/${path.replace(/^\/+/, "")}`, {
        ...init,
        signal: controller.signal,
        headers: {
          ...(this.headers() as Record<string, string>),
          ...((init?.headers as Record<string, string>) || {}),
        },
      });
      const body = await resp.text();
      if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${body}`);
      return body;
    } finally {
      clearTimeout(timer);
    }
  }

  plan(query: string): Promise<Json> {
    return this.request("/workflow/plan", {
      method: "POST",
      body: JSON.stringify({ query }),
    });
  }

  a2aAgentCard(): Promise<Json> {
    return this.request("/.well-known/agent.json", { method: "GET" });
  }

  a2aGetCard(): Promise<Json> {
    return this.request("/a2a", {
      method: "POST",
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: "agent-card",
        method: "agent/getCard",
        params: {},
      }),
    });
  }

  a2aSendMessage(
    text: string,
    opts: {
      taskId?: string;
      safetyMode?: "plan-readonly" | "execute-mutating";
      intentContract?: RunStartRequest["intent_contract"];
    } = {},
  ): Promise<Json> {
    const message: A2AMessage = {
      role: "user",
      parts: [{ type: "text", text }],
    };
    const params: Json = {
      message,
      safetyMode: opts.safetyMode ?? "plan-readonly",
    };
    if (opts.taskId) {
      message.taskId = opts.taskId;
      params.taskId = opts.taskId;
    }
    if (opts.intentContract) params.intent_contract = opts.intentContract as unknown as Json;
    return this.request("/a2a", {
      method: "POST",
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: "message-send",
        method: "message/send",
        params,
      }),
    });
  }

  a2aStreamMessage(
    text: string,
    opts: {
      taskId?: string;
      safetyMode?: "plan-readonly" | "execute-mutating";
      intentContract?: RunStartRequest["intent_contract"];
    } = {},
  ): Promise<string> {
    const message: A2AMessage = {
      role: "user",
      parts: [{ type: "text", text }],
    };
    const params: Json = {
      message,
      safetyMode: opts.safetyMode ?? "plan-readonly",
    };
    if (opts.taskId) {
      message.taskId = opts.taskId;
      params.taskId = opts.taskId;
    }
    if (opts.intentContract) params.intent_contract = opts.intentContract as unknown as Json;
    return this.requestText("/a2a", {
      method: "POST",
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: "message-stream",
        method: "message/stream",
        params,
      }),
    });
  }

  a2aGetTask(taskId: string): Promise<Json> {
    return this.request("/a2a", {
      method: "POST",
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: "task-get",
        method: "tasks/get",
        params: { id: taskId },
      }),
    });
  }

  a2aListTasks(limit = 10): Promise<Json> {
    return this.request("/a2a", {
      method: "POST",
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: "task-list",
        method: "tasks/list",
        params: { limit },
      }),
    });
  }

  a2aCancelTask(taskId: string, reason = ""): Promise<Json> {
    const params: Json = { id: taskId };
    if (reason) params.reason = reason;
    return this.request("/a2a", {
      method: "POST",
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: "task-cancel",
        method: "tasks/cancel",
        params,
      }),
    });
  }

  query(
    query: string,
    opts: {
      agentType?: string;
      preferLocal?: boolean;
      generateResponse?: boolean;
      mode?: string;
      context?: Json;
      limit?: number;
      keywordLimit?: number;
      scoreThreshold?: number;
    } = {},
  ): Promise<Json> {
    const payload: Json = {
      query,
      agent_type: opts.agentType ?? "human",
      prefer_local: opts.preferLocal ?? true,
      generate_response: opts.generateResponse ?? false,
      mode: opts.mode ?? "auto",
      limit: opts.limit ?? 5,
      keyword_limit: opts.keywordLimit ?? 5,
      score_threshold: opts.scoreThreshold ?? 0.7,
    };
    if (opts.context) payload.context = opts.context;
    return this.request("/query", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  toolingManifest(
    query: string,
    runtime: "python" | "typescript" = "python",
    maxTools?: number,
    maxResultChars?: number,
  ): Promise<Json> {
    const payload: Json = { query, runtime };
    if (typeof maxTools === "number") payload.max_tools = maxTools;
    if (typeof maxResultChars === "number") payload.max_result_chars = maxResultChars;
    return this.request("/workflow/tooling-manifest", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  startSession(query: string): Promise<Json> {
    return this.request("/workflow/session/start", {
      method: "POST",
      body: JSON.stringify({ query }),
    });
  }

  getSession(sessionId: string): Promise<Json> {
    return this.request(`/workflow/session/${sessionId}`, { method: "GET" });
  }

  getSessionWithLineage(sessionId: string): Promise<Json> {
    return this.request(`/workflow/session/${sessionId}?lineage=true`, { method: "GET" });
  }

  listSessions(): Promise<Json> {
    return this.request("/workflow/sessions", { method: "GET" });
  }

  workflowTree(
    includeCompleted = true,
    includeFailed = true,
    includeObjective = true,
  ): Promise<Json> {
    const query =
      `include_completed=${includeCompleted ? "true" : "false"}&` +
      `include_failed=${includeFailed ? "true" : "false"}&` +
      `include_objective=${includeObjective ? "true" : "false"}`;
    return this.request(`/workflow/tree?${query}`, { method: "GET" });
  }

  forkSession(sessionId: string, note = "forked session"): Promise<Json> {
    return this.request(`/workflow/session/${sessionId}/fork`, {
      method: "POST",
      body: JSON.stringify({ note }),
    });
  }

  advanceSession(sessionId: string, action: "pass" | "fail" | "skip" | "note", note = ""): Promise<Json> {
    const payload: Json = { action };
    if (note) payload.note = note;
    return this.request(`/workflow/session/${sessionId}/advance`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  reviewAcceptance(payload: ReviewAcceptanceRequest): Promise<Json> {
    return this.request("/review/acceptance", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  harnessEval(query: string, expectedKeywords: string[] = [], mode = "auto"): Promise<Json> {
    return this.request("/harness/eval", {
      method: "POST",
      body: JSON.stringify({
        query,
        mode,
        expected_keywords: expectedKeywords,
      }),
    });
  }

  qaCheck(
    phase = "0",
    format: "json" | "text" = "json",
    timeoutSeconds = 60,
    includeSudo = false,
  ): Promise<Json> {
    return this.request("/qa/check", {
      method: "POST",
      body: JSON.stringify({
        phase,
        format,
        timeout_seconds: timeoutSeconds,
        include_sudo: includeSudo,
      }),
    });
  }

  runStart(payload: RunStartRequest): Promise<Json> {
    const body: RunStartRequest = {
      ...payload,
      intent_contract: payload.intent_contract ?? this.defaultIntentContract(payload.query),
    };
    return this.request("/workflow/run/start", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  runGet(sessionId: string, replay = false): Promise<Json> {
    return this.request(`/workflow/run/${sessionId}?replay=${replay ? "true" : "false"}`, { method: "GET" });
  }

  runSetMode(sessionId: string, safetyMode: "plan-readonly" | "execute-mutating", confirm = false): Promise<Json> {
    return this.request(`/workflow/run/${sessionId}/mode`, {
      method: "POST",
      body: JSON.stringify({ safety_mode: safetyMode, confirm }),
    });
  }

  runArbiter(
    sessionId: string,
    selectedCandidateId: string,
    arbiter: string,
    verdict: "accept" | "reject" | "prefer",
    rationale: string,
    summary = "",
    supportingDecisions: Json[] = [],
  ): Promise<Json> {
    return this.request(`/workflow/run/${sessionId}/arbiter`, {
      method: "POST",
      body: JSON.stringify({
        selected_candidate_id: selectedCandidateId,
        arbiter,
        verdict,
        rationale,
        summary,
        supporting_decisions: supportingDecisions,
      }),
    });
  }

  runGetIsolation(sessionId: string): Promise<Json> {
    return this.request(`/workflow/run/${sessionId}/isolation`, { method: "GET" });
  }

  runSetIsolation(
    sessionId: string,
    profile = "",
    workspaceRoot = "",
    networkPolicy = "",
  ): Promise<Json> {
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
    sessionId: string,
    eventType: string,
    riskClass: "safe" | "review-required" | "blocked" = "safe",
    approved = false,
    tokenDelta = 0,
    toolCallDelta = 0,
    detail = "",
  ): Promise<Json> {
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

  runReplay(sessionId: string): Promise<Json> {
    return this.request(`/workflow/run/${sessionId}/replay`, { method: "GET" });
  }

  listBlueprints(): Promise<Json> {
    return this.request("/workflow/blueprints", { method: "GET" });
  }

  parityScorecard(): Promise<Json> {
    return this.request("/parity/scorecard", { method: "GET" });
  }

  registerRuntime(payload: Json): Promise<Json> {
    return this.request("/control/runtimes/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  listRuntimes(): Promise<Json> {
    return this.request("/control/runtimes", { method: "GET" });
  }

  getRuntime(runtimeId: string): Promise<Json> {
    return this.request(`/control/runtimes/${runtimeId}`, { method: "GET" });
  }

  updateRuntimeStatus(runtimeId: string, status: string, note = ""): Promise<Json> {
    return this.request(`/control/runtimes/${runtimeId}/status`, {
      method: "POST",
      body: JSON.stringify({ status, note }),
    });
  }

  runtimeDeploy(runtimeId: string, payload: Json): Promise<Json> {
    return this.request(`/control/runtimes/${runtimeId}/deployments`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  runtimeRollback(runtimeId: string, toDeploymentId: string, reason = ""): Promise<Json> {
    return this.request(`/control/runtimes/${runtimeId}/rollback`, {
      method: "POST",
      body: JSON.stringify({
        to_deployment_id: toDeploymentId,
        reason,
      }),
    });
  }

  runtimeSchedulePolicy(): Promise<Json> {
    return this.request("/control/runtimes/schedule/policy", { method: "GET" });
  }

  runtimeSchedule(payload: RuntimeScheduleRequest): Promise<Json> {
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

  private defaultIntentContract(query: string): NonNullable<RunStartRequest["intent_contract"]> {
    const normalized = String(query || "").trim() || "workflow run";
    return {
      user_intent: normalized,
      definition_of_done: `Complete requested workflow task: ${normalized.slice(0, 120)}`,
      depth_expectation: "minimum",
      spirit_constraints: ["follow declarative-first policy", "capture validation evidence"],
      no_early_exit_without: ["all requested checks complete"],
    };
  }
}

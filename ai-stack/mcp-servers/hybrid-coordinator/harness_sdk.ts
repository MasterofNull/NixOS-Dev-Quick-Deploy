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

  plan(query: string): Promise<Json> {
    return this.request("/workflow/plan", {
      method: "POST",
      body: JSON.stringify({ query }),
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
}

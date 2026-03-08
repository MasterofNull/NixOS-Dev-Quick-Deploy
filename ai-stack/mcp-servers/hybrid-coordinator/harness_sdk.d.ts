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

export interface RuntimeScheduleRequest {
  objective: string;
  runtimeClass?: string;
  transport?: string;
  tags?: string[];
  strategy?: string;
  includeDegraded?: boolean;
}

export interface RunStartRequest {
  query: string;
  safety_mode?: "plan-readonly" | "execute-mutating";
  token_limit?: number;
  tool_call_limit?: number;
  intent_contract?: {
    user_intent: string;
    definition_of_done: string;
    depth_expectation: "minimum" | "standard" | "deep";
    spirit_constraints: string[];
    no_early_exit_without: string[];
  };
}

export declare class HarnessClient {
  constructor(opts?: HarnessClientOptions);
  plan(query: string): Promise<Json>;
  toolingManifest(
    query: string,
    runtime?: "python" | "typescript",
    maxTools?: number,
    maxResultChars?: number,
  ): Promise<Json>;
  startSession(query: string): Promise<Json>;
  getSession(sessionId: string): Promise<Json>;
  getSessionWithLineage(sessionId: string): Promise<Json>;
  listSessions(): Promise<Json>;
  workflowTree(includeCompleted?: boolean, includeFailed?: boolean, includeObjective?: boolean): Promise<Json>;
  forkSession(sessionId: string, note?: string): Promise<Json>;
  advanceSession(sessionId: string, action: "pass" | "fail" | "skip" | "note", note?: string): Promise<Json>;
  reviewAcceptance(payload: ReviewAcceptanceRequest): Promise<Json>;
  harnessEval(query: string, expectedKeywords?: string[], mode?: string): Promise<Json>;
  runStart(payload: RunStartRequest): Promise<Json>;
  runGet(sessionId: string, replay?: boolean): Promise<Json>;
  runSetMode(sessionId: string, safetyMode: "plan-readonly" | "execute-mutating", confirm?: boolean): Promise<Json>;
  runGetIsolation(sessionId: string): Promise<Json>;
  runSetIsolation(sessionId: string, profile?: string, workspaceRoot?: string, networkPolicy?: string): Promise<Json>;
  runEvent(
    sessionId: string,
    eventType: string,
    riskClass?: "safe" | "review-required" | "blocked",
    approved?: boolean,
    tokenDelta?: number,
    toolCallDelta?: number,
    detail?: string,
  ): Promise<Json>;
  runReplay(sessionId: string): Promise<Json>;
  listBlueprints(): Promise<Json>;
  parityScorecard(): Promise<Json>;
  registerRuntime(payload: Json): Promise<Json>;
  listRuntimes(): Promise<Json>;
  getRuntime(runtimeId: string): Promise<Json>;
  updateRuntimeStatus(runtimeId: string, status: string, note?: string): Promise<Json>;
  runtimeDeploy(runtimeId: string, payload: Json): Promise<Json>;
  runtimeRollback(runtimeId: string, toDeploymentId: string, reason?: string): Promise<Json>;
  runtimeSchedulePolicy(): Promise<Json>;
  runtimeSchedule(payload: RuntimeScheduleRequest): Promise<Json>;
}

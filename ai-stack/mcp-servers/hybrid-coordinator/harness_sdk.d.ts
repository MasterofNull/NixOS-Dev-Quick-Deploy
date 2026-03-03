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

export declare class HarnessClient {
  constructor(opts?: HarnessClientOptions);
  plan(query: string): Promise<Json>;
  startSession(query: string): Promise<Json>;
  getSession(sessionId: string): Promise<Json>;
  getSessionWithLineage(sessionId: string): Promise<Json>;
  listSessions(): Promise<Json>;
  workflowTree(includeCompleted?: boolean, includeFailed?: boolean, includeObjective?: boolean): Promise<Json>;
  forkSession(sessionId: string, note?: string): Promise<Json>;
  advanceSession(sessionId: string, action: "pass" | "fail" | "skip" | "note", note?: string): Promise<Json>;
  reviewAcceptance(payload: ReviewAcceptanceRequest): Promise<Json>;
  harnessEval(query: string, expectedKeywords?: string[], mode?: string): Promise<Json>;
}

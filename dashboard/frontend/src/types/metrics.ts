export interface SystemMetrics {
  timestamp: string;
  cpu: CPUMetrics;
  memory: MemoryMetrics;
  disk: DiskMetrics;
  network: NetworkMetrics;
  gpu: GPUMetrics;
  security?: Record<string, unknown>;
  containers?: Record<string, unknown>;
  uptime: number;
  load_average: { one: number | null; five: number | null; fifteen: number | null };
  hostname: string;
}

export interface CPUMetrics {
  usage_percent: number;
  count: number;
  temperature: string;
  model: string;
  arch: string;
}

export interface MemoryMetrics {
  total: number;
  used: number;
  free: number;
  percent: number;
}

export interface DiskMetrics {
  total: number;
  used: number;
  free: number;
  percent: number;
}

export interface NetworkMetrics {
  bytes_sent: number;
  bytes_recv: number;
  interface?: string;
}

export interface GPUMetrics {
  name: string;
  usage: string;
  memory: string;
  busy_percent?: number | null;
  vram_used_mb?: number | null;
  vram_total_mb?: number | null;
}

export interface ServiceStatus {
  id: string;
  name: string;
  status: 'running' | 'stopped' | 'error' | 'missing';
  type: 'systemd' | 'container';
}

export interface ContainerInfo {
  id: string;
  name: string;
  image: string;
  status: string;
  created: string;
}

export interface HealthScore {
  score: number;
  status: 'healthy' | 'warning' | 'critical';
}

export interface AIInternalsMetrics {
  embedding_cache_hit_rate_pct: number;
  llm_routing_local_pct: number;
  tokens_compressed_last_hour: number;
  hint_adoption_pct?: number;
  eval_latest_pct?: number;
  tool_performance_rows?: number;
  query_gap_count?: number;
  timestamp: string;
}

export type HarnessMaintenanceAction =
  | 'phase_plan'
  | 'research_sync'
  | 'catalog_sync'
  | 'acceptance_checks'
  | 'improvement_pass';

export interface HarnessScriptStatus {
  name: string;
  path: string;
  exists: boolean;
  executable: boolean;
}

export interface HarnessOverview {
  timestamp: string;
  status: string;
  harness: {
    stats?: {
      total_runs?: number;
      passed?: number;
      failed?: number;
      pass_rate_pct?: number;
      last_run_at?: string | null;
    };
    scorecard?: {
      available?: boolean;
      generated_at?: string | null;
      acceptance?: {
        total?: number;
        passed?: number;
        failed?: number;
        pass_rate?: number;
      };
      discovery?: Record<string, unknown>;
    };
    capability_discovery?: Record<string, unknown>;
    hybrid_harness?: {
      enabled?: boolean;
      memory_enabled?: boolean;
      tree_search_enabled?: boolean;
      eval_enabled?: boolean;
    };
  };
  policies: {
    tool_execution_policy?: Record<string, unknown>;
    outbound_http_policy?: Record<string, unknown>;
  };
  maintenance: {
    scripts: HarnessScriptStatus[];
    operational_scripts: number;
    total_scripts: number;
    weekly_research?: {
      available?: boolean;
      generated_at?: string | null;
      candidate_count?: number;
      sources_scanned?: number;
      report_path?: string | null;
    };
    improvement_pass?: {
      available?: boolean;
      last_run_at?: string | null;
      passed?: number;
      failed?: number;
    };
  };
}

export interface HarnessMaintenanceRunResult {
  action: HarnessMaintenanceAction;
  script: string;
  args: string[];
  exit_code: number;
  success: boolean;
  duration_ms: number;
  stdout: string;
  stderr: string;
  timestamp: string;
  improvement_summary?: Record<string, unknown> | null;
}

export interface PRSIAction {
  id?: string;
  action?: string;
  type?: string;
  target?: string;
  status?: string;
  risk?: string;
  score?: number;
  confidence?: number;
  reason?: string;
  rationale?: string;
  summary?: string;
  created_at?: string;
  updated_at?: string;
  last_seen_at?: string;
}

export interface PRSIActionsResponse {
  status: string;
  timestamp: string;
  prsi: {
    counts?: {
      pending_approval?: number;
      approved?: number;
      executed?: number;
      rejected?: number;
    };
    updated_at?: string;
    actions?: PRSIAction[];
  };
}

export interface PRSIApprovalResult {
  status: string;
  timestamp: string;
  result: Record<string, unknown>;
}

export interface PRSIExecuteResult {
  status: string;
  timestamp: string;
  sync_result?: Record<string, unknown> | null;
  execute_result?: Record<string, unknown>;
}

export interface PRSISyncResult {
  status: string;
  timestamp: string;
  result: Record<string, unknown>;
}

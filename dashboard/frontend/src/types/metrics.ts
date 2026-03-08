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

export interface SystemMetrics {
  timestamp: string;
  cpu: CPUMetrics;
  memory: MemoryMetrics;
  disk: DiskMetrics;
  network: NetworkMetrics;
  gpu: GPUMetrics;
  uptime: number;
  load_average: string;
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
}

export interface GPUMetrics {
  name: string;
  usage: string;
  memory: string;
}

export interface ServiceStatus {
  id: string;
  name: string;
  status: 'running' | 'stopped' | 'error';
  type: 'systemd' | 'container';
}

export interface ContainerInfo {
  id: string;
  name: string;
  image: string;
  status: string;
  created: string;
}
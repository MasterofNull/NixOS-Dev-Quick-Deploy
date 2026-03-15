import type {
  AIInternalsMetrics,
  ContainerInfo,
  HealthScore,
  HarnessMaintenanceAction,
  HarnessMaintenanceRunResult,
  HarnessOverview,
  PRSIApprovalResult,
  PRSIActionsResponse,
  PRSIExecuteResult,
  PRSISyncResult,
  ServiceStatus,
  SystemMetrics,
} from '@/types/metrics';

const API_BASE_URL = '/api';
const WS_METRICS_PATH = '/ws/metrics';

function getWebSocketUrl(path: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${path}`;
}

export class DashboardAPI {
  private static async fetchJSON<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }

    return response.json();
  }

  // Metrics
  static async getSystemMetrics(): Promise<SystemMetrics> {
    return this.fetchJSON<SystemMetrics>('/metrics/system');
  }

  static async getMetricHistory(metric: string, limit: number = 100) {
    return this.fetchJSON(`/metrics/history/${metric}?limit=${limit}`);
  }

  static async getHealthScore(): Promise<HealthScore> {
    return this.fetchJSON<HealthScore>('/metrics/health-score');
  }

  static async getAIInternals(): Promise<AIInternalsMetrics> {
    return this.fetchJSON<AIInternalsMetrics>('/metrics');
  }

  static async getHarnessOverview(): Promise<HarnessOverview> {
    return this.fetchJSON<HarnessOverview>('/harness/overview');
  }

  static async runHarnessMaintenance(action: HarnessMaintenanceAction): Promise<HarnessMaintenanceRunResult> {
    return this.fetchJSON<HarnessMaintenanceRunResult>('/harness/maintenance/run', {
      method: 'POST',
      body: JSON.stringify({ action }),
    });
  }

  static async getPRSIActions(): Promise<PRSIActionsResponse> {
    return this.fetchJSON<PRSIActionsResponse>('/prsi/actions');
  }

  static async syncPRSIActions(since: string = '1d'): Promise<PRSISyncResult> {
    return this.fetchJSON<PRSISyncResult>(`/prsi/sync?since=${encodeURIComponent(since)}`, {
      method: 'POST',
    });
  }

  static async approvePRSIAction(actionId: string, decision: 'approve' | 'reject'): Promise<PRSIApprovalResult> {
    return this.fetchJSON<PRSIApprovalResult>('/prsi/approve', {
      method: 'POST',
      body: JSON.stringify({
        action_id: actionId,
        decision,
        by: 'command-center-dashboard',
      }),
    });
  }

  static async executePRSIActions(limit: number, dryRun: boolean, autoSync: boolean = true): Promise<PRSIExecuteResult> {
    return this.fetchJSON<PRSIExecuteResult>('/prsi/execute', {
      method: 'POST',
      body: JSON.stringify({
        limit,
        dry_run: dryRun,
        auto_sync: autoSync,
      }),
    });
  }

  // Services
  static async listServices(): Promise<ServiceStatus[]> {
    return this.fetchJSON<ServiceStatus[]>('/services');
  }

  static async startService(serviceId: string) {
    return this.fetchJSON(`/services/${serviceId}/start`, { method: 'POST' });
  }

  static async stopService(serviceId: string) {
    return this.fetchJSON(`/services/${serviceId}/stop`, { method: 'POST' });
  }

  static async restartService(serviceId: string) {
    return this.fetchJSON(`/services/${serviceId}/restart`, { method: 'POST' });
  }

  static async startAllServices() {
    return this.fetchJSON('/services/actions/start-all', { method: 'POST' });
  }

  static async stopAllServices() {
    return this.fetchJSON('/services/actions/stop-all', { method: 'POST' });
  }

  static async restartAllServices() {
    return this.fetchJSON('/services/actions/restart-all', { method: 'POST' });
  }

  // Containers
  static async listContainers(): Promise<ContainerInfo[]> {
    return this.fetchJSON<ContainerInfo[]>('/containers');
  }

  static async startContainer(containerId: string) {
    return this.fetchJSON(`/containers/${containerId}/start`, { method: 'POST' });
  }

  static async stopContainer(containerId: string) {
    return this.fetchJSON(`/containers/${containerId}/stop`, { method: 'POST' });
  }

  static async restartContainer(containerId: string) {
    return this.fetchJSON(`/containers/${containerId}/restart`, { method: 'POST' });
  }

  static async getContainerLogs(containerId: string, tail: number = 100) {
    return this.fetchJSON<{ logs: string }>(`/containers/${containerId}/logs?tail=${tail}`);
  }

  // AI Insights endpoints
  static async getSystemHealthInsights(): Promise<any> {
    return this.fetchJSON<any>('/insights/system/health');
  }

  static async getToolPerformance(): Promise<any> {
    return this.fetchJSON<any>('/insights/tools/performance');
  }

  static async getRoutingAnalytics(): Promise<any> {
    return this.fetchJSON<any>('/insights/routing/analytics');
  }

  static async getHintEffectiveness(): Promise<any> {
    return this.fetchJSON<any>('/insights/hints/effectiveness');
  }

  static async getWorkflowCompliance(): Promise<any> {
    return this.fetchJSON<any>('/insights/workflows/compliance');
  }

  static async getQueryComplexity(): Promise<any> {
    return this.fetchJSON<any>('/insights/queries/complexity');
  }

  static async getCacheAnalytics(): Promise<any> {
    return this.fetchJSON<any>('/insights/cache/analytics');
  }

  static async getAgentLessons(): Promise<any> {
    return this.fetchJSON<any>('/insights/agents/lessons');
  }

  static async getStructuredActions(): Promise<any> {
    return this.fetchJSON<any>('/insights/actions/recommendations');
  }

  static async getFullInsightsReport(): Promise<any> {
    return this.fetchJSON<any>('/insights/report/full');
  }

  // WebSocket connection
  static connectWebSocket(onMessage: (data: SystemMetrics) => void): WebSocket {
    const ws = new WebSocket(getWebSocketUrl(WS_METRICS_PATH));

    ws.onopen = () => {
      console.log('WebSocket connected');
      // Send ping every 30 seconds to keep connection alive
      setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping');
        }
      }, 30000);
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === 'metrics_update') {
        onMessage(message.data);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
    };

    return ws;
  }
}

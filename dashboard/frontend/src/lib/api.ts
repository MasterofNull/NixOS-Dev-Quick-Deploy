import type { SystemMetrics, ServiceStatus, ContainerInfo } from '@/types/metrics';

const API_BASE_URL = '/api';

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

  static async getHealthScore() {
    return this.fetchJSON<{ score: number; status: string }>('/metrics/health-score');
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

  // WebSocket connection
  static connectWebSocket(onMessage: (data: SystemMetrics) => void): WebSocket {
    const ws = new WebSocket(`ws://${window.location.hostname}:8889/ws/metrics`);

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

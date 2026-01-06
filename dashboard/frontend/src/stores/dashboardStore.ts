import { create } from 'zustand';
import type { SystemMetrics, ServiceStatus, ContainerInfo } from '@/types/metrics';

interface DashboardState {
  // Current metrics
  currentMetrics: SystemMetrics | null;
  healthScore: number;
  
  // Historical data
  cpuHistory: number[];
  memoryHistory: number[];
  networkHistory: { rx: number; tx: number }[];
  
  // Services
  services: ServiceStatus[];
  containers: ContainerInfo[];
  
  // UI state
  isLoading: boolean;
  error: string | null;
  lastUpdate: string;
  
  // Actions
  setCurrentMetrics: (metrics: SystemMetrics) => void;
  addToHistory: (metrics: SystemMetrics) => void;
  setServices: (services: ServiceStatus[]) => void;
  setContainers: (containers: ContainerInfo[]) => void;
  setHealthScore: (score: number) => void;
  setError: (error: string | null) => void;
  setLoading: (loading: boolean) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  currentMetrics: null,
  healthScore: 0,
  cpuHistory: [],
  memoryHistory: [],
  networkHistory: [],
  services: [],
  containers: [],
  isLoading: true,
  error: null,
  lastUpdate: new Date().toISOString(),
  
  setCurrentMetrics: (metrics) => 
    set({ 
      currentMetrics: metrics, 
      lastUpdate: new Date().toISOString() 
    }),
  
  addToHistory: (metrics) =>
    set((state) => ({
      cpuHistory: [...state.cpuHistory.slice(-99), metrics.cpu.usage_percent],
      memoryHistory: [...state.memoryHistory.slice(-99), metrics.memory.percent],
      networkHistory: [
        ...state.networkHistory.slice(-99),
        { rx: metrics.network.bytes_recv, tx: metrics.network.bytes_sent }
      ],
    })),
  
  setServices: (services) => set({ services }),
  setContainers: (containers) => set({ containers }),
  setHealthScore: (healthScore) => set({ healthScore }),
  setError: (error) => set({ error }),
  setLoading: (isLoading) => set({ isLoading }),
}));
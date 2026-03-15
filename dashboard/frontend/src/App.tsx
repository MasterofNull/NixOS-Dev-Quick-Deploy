import { useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useDashboardStore } from '@/stores/dashboardStore';
import { DashboardAPI } from '@/lib/api';
import { SystemOverview } from '@/components/SystemOverview';
import { MetricsChart } from '@/components/MetricsChart';
import { ServiceControl } from '@/components/ServiceControl';
import { AIInsightsDashboard } from '@/components/AIInsightsDashboard';
import { CommandCenterOperations } from '@/components/CommandCenterOperations';
import { Activity, ShieldCheck } from 'lucide-react';

const queryClient = new QueryClient();

function DashboardContent() {
  const { setCurrentMetrics, addToHistory, setServices, setHealthScore, setLoading, setError } = useDashboardStore();

  useEffect(() => {
    let ws: WebSocket | null = null;

    // Initial data fetch
    const fetchInitialData = async () => {
      try {
        const [metrics, services, healthScore] = await Promise.all([
          DashboardAPI.getSystemMetrics(),
          DashboardAPI.listServices(),
          DashboardAPI.getHealthScore(),
        ]);

        setCurrentMetrics(metrics);
        addToHistory(metrics);
        setServices(services);
        setHealthScore(healthScore.score);
        setError(null);
        setLoading(false);
      } catch (error) {
        console.error('Error fetching initial data:', error);
        setError(error instanceof Error ? error.message : 'Unknown error');
        setLoading(false);
      }
    };

    fetchInitialData();

    // Connect WebSocket for real-time updates
    ws = DashboardAPI.connectWebSocket((metrics) => {
      setCurrentMetrics(metrics);
      addToHistory(metrics);
    });

    // Refresh services every 10 seconds
    const servicesInterval = setInterval(async () => {
      try {
        const services = await DashboardAPI.listServices();
        setServices(services);
      } catch (error) {
        console.error('Error fetching services:', error);
      }
    }, 10000);

    return () => {
      ws?.close();
      clearInterval(servicesInterval);
    };
  }, [addToHistory, setCurrentMetrics, setError, setHealthScore, setLoading, setServices]);

  const healthScore = useDashboardStore((state) => state.healthScore);
  const lastUpdate = useDashboardStore((state) => state.lastUpdate);

  return (
    <div className="min-h-screen bg-background command-shell">
      {/* Header */}
      <header className="border-b border-border/70 bg-background/95 backdrop-blur">
        <div className="container mx-auto px-4 py-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-3">
              <div className="command-shell__icon">
                <Activity className="h-8 w-8 text-primary" />
              </div>
              <div>
                <p className="command-center-kicker">Declarative Command Center</p>
                <h1 className="text-3xl font-bold tracking-tight">NixOS AI Operations Dashboard</h1>
                <p className="text-sm text-muted-foreground">
                  Real-time system monitoring, PRSI orchestration review, and AI harness maintenance
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4 rounded-full border border-border/70 bg-card/80 px-4 py-3 shadow-sm">
              <ShieldCheck className="h-5 w-5 text-emerald-500" />
              <div className="text-right">
                <div className="text-3xl font-bold text-primary">{healthScore}</div>
                <div className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Health Score</div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6">
        <div className="space-y-6">
          <SystemOverview />

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <MetricsChart />
            </div>
            <div>
              <ServiceControl />
            </div>
          </div>

          <CommandCenterOperations />

          <section>
            <h2 className="mb-4 text-lg font-semibold">AI Insights & Intelligence</h2>
            <AIInsightsDashboard />
          </section>
        </div>

        {/* Footer */}
        <footer className="mt-8 text-center text-sm text-muted-foreground">
          Last updated: {new Date(lastUpdate).toLocaleTimeString()}
        </footer>
      </main>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <DashboardContent />
    </QueryClientProvider>
  );
}

export default App;

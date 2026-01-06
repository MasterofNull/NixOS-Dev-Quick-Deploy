import { useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useDashboardStore } from '@/stores/dashboardStore';
import { DashboardAPI } from '@/lib/api';
import { SystemOverview } from '@/components/SystemOverview';
import { MetricsChart } from '@/components/MetricsChart';
import { ServiceControl } from '@/components/ServiceControl';
import { Activity } from 'lucide-react';

const queryClient = new QueryClient();

function DashboardContent() {
  const { setCurrentMetrics, addToHistory, setServices, setHealthScore, setLoading } = useDashboardStore();

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
        setLoading(false);
      } catch (error) {
        console.error('Error fetching initial data:', error);
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
  }, []);

  const healthScore = useDashboardStore((state) => state.healthScore);
  const lastUpdate = useDashboardStore((state) => state.lastUpdate);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Activity className="h-8 w-8 text-primary" />
              <div>
                <h1 className="text-2xl font-bold">NixOS System Dashboard</h1>
                <p className="text-sm text-muted-foreground">
                  Real-time system monitoring and control
                </p>
              </div>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold text-primary">{healthScore}</div>
              <div className="text-xs text-muted-foreground">Health Score</div>
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
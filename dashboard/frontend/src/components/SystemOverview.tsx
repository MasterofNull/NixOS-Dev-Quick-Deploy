import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { useDashboardStore } from '@/stores/dashboardStore';
import { Cpu, MemoryStick, HardDrive, Activity } from 'lucide-react';

export function SystemOverview() {
  const currentMetrics = useDashboardStore((state) => state.currentMetrics);

  if (!currentMetrics) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-muted-foreground">Loading system metrics...</div>
        </CardContent>
      </Card>
    );
  }

  const { cpu, memory, disk } = currentMetrics;

  const formatBytes = (bytes: number) => {
    const gb = bytes / (1024 ** 3);
    return `${gb.toFixed(2)} GB`;
  };

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {/* CPU Card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">CPU Usage</CardTitle>
          <Cpu className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{cpu.usage_percent.toFixed(1)}%</div>
          <Progress value={cpu.usage_percent} className="mt-2" />
          <p className="text-xs text-muted-foreground mt-2">
            {cpu.model} • {cpu.count} cores
          </p>
          {cpu.temperature !== 'N/A' && (
            <p className="text-xs text-muted-foreground">Temp: {cpu.temperature}</p>
          )}
        </CardContent>
      </Card>

      {/* Memory Card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Memory</CardTitle>
          <MemoryStick className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{memory.percent.toFixed(1)}%</div>
          <Progress value={memory.percent} className="mt-2" />
          <p className="text-xs text-muted-foreground mt-2">
            {formatBytes(memory.used)} / {formatBytes(memory.total)}
          </p>
        </CardContent>
      </Card>

      {/* Disk Card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Disk Usage</CardTitle>
          <HardDrive className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{disk.percent.toFixed(1)}%</div>
          <Progress value={disk.percent} className="mt-2" />
          <p className="text-xs text-muted-foreground mt-2">
            {formatBytes(disk.used)} / {formatBytes(disk.total)}
          </p>
        </CardContent>
      </Card>

      {/* System Info Card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">System</CardTitle>
          <Activity className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{currentMetrics.hostname}</div>
          <p className="text-xs text-muted-foreground mt-2">
            Load: {currentMetrics.load_average}
          </p>
          <p className="text-xs text-muted-foreground">
            Uptime: {Math.floor(currentMetrics.uptime / 3600)}h {Math.floor((currentMetrics.uptime % 3600) / 60)}m
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
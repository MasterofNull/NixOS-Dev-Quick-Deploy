import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart';
import { Line, LineChart, XAxis, YAxis, CartesianGrid } from 'recharts';
import { useDashboardStore } from '@/stores/dashboardStore';

export function MetricsChart() {
  const cpuHistory = useDashboardStore((state) => state.cpuHistory);
  const memoryHistory = useDashboardStore((state) => state.memoryHistory);

  const chartData = cpuHistory.map((cpu, index) => ({
    index,
    cpu: cpu.toFixed(1),
    memory: memoryHistory[index]?.toFixed(1) || 0,
  }));

  const chartConfig = {
    cpu: {
      label: 'CPU %',
      color: 'hsl(var(--chart-1))',
    },
    memory: {
      label: 'Memory %',
      color: 'hsl(var(--chart-2))',
    },
  };

  return (
    <Card className="col-span-full">
      <CardHeader>
        <CardTitle>Resource Usage History</CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-[300px]">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="index" />
            <YAxis domain={[0, 100]} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Line
              type="monotone"
              dataKey="cpu"
              stroke="var(--color-cpu)"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="memory"
              stroke="var(--color-memory)"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
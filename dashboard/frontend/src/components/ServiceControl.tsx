import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useDashboardStore } from '@/stores/dashboardStore';
import { DashboardAPI } from '@/lib/api';
import { MoreVertical, Play, Square, RotateCw } from 'lucide-react';
import { useState } from 'react';

export function ServiceControl() {
  const services = useDashboardStore((state) => state.services);
  const [loading, setLoading] = useState<string | null>(null);
  const [bulkLoading, setBulkLoading] = useState<'start' | 'stop' | 'restart' | null>(null);

  const allRunning = services.length > 0 && services.every((service) => service.status === 'running');
  const allStopped = services.length > 0 && services.every((service) => service.status === 'stopped');

  const handleAction = async (serviceId: string, action: 'start' | 'stop' | 'restart') => {
    setLoading(serviceId);
    try {
      if (action === 'start') {
        await DashboardAPI.startService(serviceId);
      } else if (action === 'stop') {
        await DashboardAPI.stopService(serviceId);
      } else {
        await DashboardAPI.restartService(serviceId);
      }
      // Refresh services list
      const updatedServices = await DashboardAPI.listServices();
      useDashboardStore.getState().setServices(updatedServices);
    } catch (error) {
      console.error(`Error ${action}ing service:`, error);
    } finally {
      setLoading(null);
    }
  };

  const handleAllAction = async (action: 'start' | 'stop' | 'restart') => {
    setBulkLoading(action);
    try {
      if (action === 'start') {
        await DashboardAPI.startAllServices();
      } else if (action === 'stop') {
        await DashboardAPI.stopAllServices();
      } else {
        await DashboardAPI.restartAllServices();
      }
      const updatedServices = await DashboardAPI.listServices();
      useDashboardStore.getState().setServices(updatedServices);
    } catch (error) {
      console.error(`Error ${action}ing all services:`, error);
    } finally {
      setBulkLoading(null);
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>AI Stack Services</CardTitle>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleAllAction('start')}
            disabled={bulkLoading !== null || allRunning || services.length === 0}
          >
            <Play className="mr-2 h-4 w-4" />
            Start All
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleAllAction('stop')}
            disabled={bulkLoading !== null || allStopped || services.length === 0}
          >
            <Square className="mr-2 h-4 w-4" />
            Stop All
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleAllAction('restart')}
            disabled={bulkLoading !== null || services.length === 0}
          >
            <RotateCw className="mr-2 h-4 w-4" />
            Restart All
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {services.map((service) => (
            <div
              key={service.id}
              className="flex items-center justify-between p-3 border rounded-lg"
            >
              <div className="flex items-center gap-3">
                <div
                  className={`w-2 h-2 rounded-full ${
                    service.status === 'running'
                      ? 'bg-green-500'
                      : 'bg-gray-500'
                  }`}
                />
                <div>
                  <div className="font-medium">{service.name}</div>
                  <div className="text-xs text-muted-foreground">{service.type}</div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Badge variant={service.status === 'running' ? 'default' : 'secondary'}>
                  {service.status}
                </Badge>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      disabled={loading === service.id || bulkLoading !== null}
                    >
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onClick={() => handleAction(service.id, 'start')}
                      disabled={bulkLoading !== null || service.status === 'running'}
                    >
                      <Play className="mr-2 h-4 w-4" />
                      Start
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => handleAction(service.id, 'stop')}
                      disabled={bulkLoading !== null || service.status === 'stopped'}
                    >
                      <Square className="mr-2 h-4 w-4" />
                      Stop
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => handleAction(service.id, 'restart')}
                      disabled={bulkLoading !== null}
                    >
                      <RotateCw className="mr-2 h-4 w-4" />
                      Restart
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

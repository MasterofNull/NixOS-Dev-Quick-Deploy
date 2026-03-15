import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { DashboardAPI } from '@/lib/api';
import {
  Activity,
  TrendingUp,
  Zap,
  Brain,
  CheckCircle2,
  AlertCircle,
  Clock,
  Database,
  Cpu,
  BarChart3,
  Target,
} from 'lucide-react';

const POLL_INTERVAL_MS = 60000; // 1 minute

interface SystemHealth {
  timestamp: string;
  window: string;
  status: string;
  issues: string[];
  routing: any;
  cache: any;
  recent_health: any;
  eval_trend: any;
  recommendations: string[];
}

interface ToolPerformance {
  timestamp: string;
  window: string;
  summary: {
    total_tools: number;
    total_calls: number;
    total_errors: number;
    error_rate_pct: number;
  };
  top_tools: Array<{
    name: string;
    calls: number;
    p50_ms: number;
    success_pct: number;
  }>;
  slow_tools: Array<{
    name: string;
    calls: number;
    p95_ms: number;
    success_pct: number;
  }>;
  error_tools: Array<{
    name: string;
    calls: number;
    error_count: number;
    success_pct: number;
  }>;
}

interface HintEffectiveness {
  timestamp: string;
  window: string;
  adoption: {
    available: boolean;
    total: number;
    accepted: number;
    adoption_pct: number;
    unique_hints: number;
    dominant_hint_id: string;
  };
  diversity: {
    total_injections: number;
    unique_hints: number;
    status: string;
    effective_hints: number;
  };
}

interface WorkflowCompliance {
  timestamp: string;
  window: string;
  intent_contract: {
    available: boolean;
    total_runs: number;
    with_contract: number;
    contract_coverage_pct: number;
    sessions_with_reviews: number;
    accepted_reviews: number;
    rejected_reviews: number;
  };
  task_tooling: {
    available: boolean;
    total: number;
    success: number;
    success_pct: number;
  };
}

interface RoutingAnalytics {
  timestamp: string;
  window: string;
  current: {
    local_n: number;
    remote_n: number;
    local_pct: number;
    available: boolean;
  };
}

export function AIInsightsDashboard() {
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [toolPerformance, setToolPerformance] = useState<ToolPerformance | null>(null);
  const [hintEffectiveness, setHintEffectiveness] = useState<HintEffectiveness | null>(null);
  const [workflowCompliance, setWorkflowCompliance] = useState<WorkflowCompliance | null>(null);
  const [routingAnalytics, setRoutingAnalytics] = useState<RoutingAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('overview');

  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      try {
        const [health, tools, hints, workflow, routing] = await Promise.all([
          DashboardAPI.getSystemHealthInsights(),
          DashboardAPI.getToolPerformance(),
          DashboardAPI.getHintEffectiveness(),
          DashboardAPI.getWorkflowCompliance(),
          DashboardAPI.getRoutingAnalytics(),
        ]);

        if (!cancelled) {
          setSystemHealth(health);
          setToolPerformance(tools);
          setHintEffectiveness(hints);
          setWorkflowCompliance(workflow);
          setRoutingAnalytics(routing);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unknown error');
        }
      }
    };

    fetchData();
    const interval = setInterval(fetchData, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>AI Insights Dashboard</CardTitle>
          <CardDescription>Real-time AI stack intelligence and analytics</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-destructive">Error loading insights: {error}</div>
        </CardContent>
      </Card>
    );
  }

  if (!systemHealth || !toolPerformance) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-muted-foreground">Loading AI insights...</div>
        </CardContent>
      </Card>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'text-emerald-500';
      case 'degraded':
        return 'text-yellow-500';
      case 'unhealthy':
        return 'text-destructive';
      default:
        return 'text-muted-foreground';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle2 className="h-5 w-5" />;
      case 'degraded':
        return <AlertCircle className="h-5 w-5" />;
      case 'unhealthy':
        return <AlertCircle className="h-5 w-5" />;
      default:
        return <Activity className="h-5 w-5" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* System Health Overview */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">System Status</CardTitle>
            <div className={getStatusColor(systemHealth.status)}>{getStatusIcon(systemHealth.status)}</div>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${getStatusColor(systemHealth.status)}`}>
              {systemHealth.status.toUpperCase()}
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              {systemHealth.issues.length} active issues
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tool Performance</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{toolPerformance.summary.total_tools}</div>
            <Progress
              value={100 - toolPerformance.summary.error_rate_pct}
              className="mt-2"
            />
            <p className="text-xs text-muted-foreground mt-2">
              {(100 - toolPerformance.summary.error_rate_pct).toFixed(1)}% success rate
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">LLM Routing</CardTitle>
            <Cpu className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{routingAnalytics?.current.local_pct.toFixed(0)}%</div>
            <Progress value={routingAnalytics?.current.local_pct || 0} className="mt-2" />
            <p className="text-xs text-muted-foreground mt-2">
              Local routing ({routingAnalytics?.current.local_n || 0} calls)
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cache Hit Rate</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{systemHealth.cache.hit_pct.toFixed(1)}%</div>
            <Progress value={systemHealth.cache.hit_pct} className="mt-2" />
            <p className="text-xs text-muted-foreground mt-2">
              {systemHealth.cache.hits} hits / {systemHealth.cache.misses} misses
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Insights Tabs */}
      <Card>
        <CardHeader>
          <CardTitle>AI Stack Intelligence</CardTitle>
          <CardDescription>
            Comprehensive analytics from the last {systemHealth.window}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-5">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="tools">Tools</TabsTrigger>
              <TabsTrigger value="hints">Hints</TabsTrigger>
              <TabsTrigger value="workflows">Workflows</TabsTrigger>
              <TabsTrigger value="recommendations">Actions</TabsTrigger>
            </TabsList>

            {/* Overview Tab */}
            <TabsContent value="overview" className="space-y-4 mt-4">
              <div className="grid gap-4 md:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Active Issues</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {systemHealth.issues.length === 0 ? (
                      <div className="text-sm text-muted-foreground">No active issues</div>
                    ) : (
                      <ul className="space-y-2">
                        {systemHealth.issues.map((issue, index) => (
                          <li key={index} className="text-sm flex items-start gap-2">
                            <AlertCircle className="h-4 w-4 text-yellow-500 mt-0.5 flex-shrink-0" />
                            <span>{issue}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Eval Trend</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>Latest Score:</span>
                        <span className="font-semibold">{systemHealth.eval_trend.latest_pct}%</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span>Mean Score:</span>
                        <span className="font-semibold">{systemHealth.eval_trend.mean_pct}%</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span>Trend:</span>
                        <span
                          className={`font-semibold ${
                            systemHealth.eval_trend.trend === 'falling'
                              ? 'text-yellow-500'
                              : 'text-emerald-500'
                          }`}
                        >
                          {systemHealth.eval_trend.trend}
                        </span>
                      </div>
                      <Progress value={systemHealth.eval_trend.latest_pct} className="mt-2" />
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            {/* Tools Tab */}
            <TabsContent value="tools" className="space-y-4 mt-4">
              <div className="grid gap-4 md:grid-cols-3">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <TrendingUp className="h-4 w-4" />
                      Top Tools
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {toolPerformance.top_tools.slice(0, 5).map((tool, index) => (
                        <div key={index} className="flex justify-between text-sm">
                          <span className="truncate">{tool.name}</span>
                          <span className="text-muted-foreground">{tool.calls}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Clock className="h-4 w-4" />
                      Slow Tools
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {toolPerformance.slow_tools.length === 0 ? (
                      <div className="text-sm text-muted-foreground">No slow tools</div>
                    ) : (
                      <div className="space-y-2">
                        {toolPerformance.slow_tools.slice(0, 5).map((tool, index) => (
                          <div key={index} className="flex justify-between text-sm">
                            <span className="truncate">{tool.name}</span>
                            <span className="text-muted-foreground">{tool.p95_ms.toFixed(0)}ms</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <AlertCircle className="h-4 w-4" />
                      Error Tools
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {toolPerformance.error_tools.length === 0 ? (
                      <div className="text-sm text-muted-foreground">No errors</div>
                    ) : (
                      <div className="space-y-2">
                        {toolPerformance.error_tools.slice(0, 5).map((tool, index) => (
                          <div key={index} className="flex justify-between text-sm">
                            <span className="truncate">{tool.name}</span>
                            <span className="text-destructive">{tool.error_count}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            {/* Hints Tab */}
            <TabsContent value="hints" className="space-y-4 mt-4">
              <div className="grid gap-4 md:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Brain className="h-4 w-4" />
                      Hint Adoption
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>Total Hints:</span>
                        <span className="font-semibold">{hintEffectiveness?.adoption.total || 0}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span>Accepted:</span>
                        <span className="font-semibold">{hintEffectiveness?.adoption.accepted || 0}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span>Adoption Rate:</span>
                        <span className="font-semibold">
                          {hintEffectiveness?.adoption.adoption_pct?.toFixed(1) || 0}%
                        </span>
                      </div>
                      <Progress value={hintEffectiveness?.adoption.adoption_pct || 0} className="mt-2" />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Zap className="h-4 w-4" />
                      Hint Diversity
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>Unique Hints:</span>
                        <span className="font-semibold">{hintEffectiveness?.diversity.unique_hints || 0}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span>Effective Hints:</span>
                        <span className="font-semibold">
                          {hintEffectiveness?.diversity.effective_hints?.toFixed(2) || 0}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span>Status:</span>
                        <span className="font-semibold">{hintEffectiveness?.diversity.status || 'N/A'}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            {/* Workflows Tab */}
            <TabsContent value="workflows" className="space-y-4 mt-4">
              <div className="grid gap-4 md:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Target className="h-4 w-4" />
                      Intent Contract Compliance
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>Total Runs:</span>
                        <span className="font-semibold">
                          {workflowCompliance?.intent_contract.total_runs || 0}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span>With Contract:</span>
                        <span className="font-semibold">
                          {workflowCompliance?.intent_contract.with_contract || 0}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span>Coverage:</span>
                        <span className="font-semibold">
                          {workflowCompliance?.intent_contract.contract_coverage_pct.toFixed(1) || 0}%
                        </span>
                      </div>
                      <Progress
                        value={workflowCompliance?.intent_contract.contract_coverage_pct || 0}
                        className="mt-2"
                      />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4" />
                      Task Tooling Quality
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>Total Tasks:</span>
                        <span className="font-semibold">{workflowCompliance?.task_tooling.total || 0}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span>Successful:</span>
                        <span className="font-semibold">{workflowCompliance?.task_tooling.success || 0}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span>Success Rate:</span>
                        <span className="font-semibold">
                          {workflowCompliance?.task_tooling.success_pct?.toFixed(1) || 0}%
                        </span>
                      </div>
                      <Progress value={workflowCompliance?.task_tooling.success_pct || 0} className="mt-2" />
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            {/* Recommendations Tab */}
            <TabsContent value="recommendations" className="space-y-4 mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">System Recommendations</CardTitle>
                </CardHeader>
                <CardContent>
                  {systemHealth.recommendations.length === 0 ? (
                    <div className="text-sm text-muted-foreground">No recommendations</div>
                  ) : (
                    <ul className="space-y-3">
                      {systemHealth.recommendations.map((rec, index) => (
                        <li key={index} className="text-sm flex items-start gap-2">
                          <TrendingUp className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                          <span>{rec}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}

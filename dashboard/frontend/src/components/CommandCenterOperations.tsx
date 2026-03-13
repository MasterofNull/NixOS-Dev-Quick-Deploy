import { useEffect, useState } from 'react';
import { AlertTriangle, Bot, CheckCircle2, Clock3, RefreshCw, ShieldCheck, Sparkles, Wrench } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DashboardAPI } from '@/lib/api';
import type {
  HarnessMaintenanceAction,
  HarnessOverview,
  PRSIAction,
  PRSIActionsResponse,
} from '@/types/metrics';

const POLL_INTERVAL_MS = 30000;

const HARNESS_ACTIONS: Array<{
  action: HarnessMaintenanceAction;
  label: string;
  description: string;
}> = [
  {
    action: 'phase_plan',
    label: 'Refresh Phase Plan',
    description: 'Rebuild the active phase plan that feeds harness sequencing and operator visibility.',
  },
  {
    action: 'acceptance_checks',
    label: 'Run Acceptance Checks',
    description: 'Execute the harness acceptance pass and surface current pass or fail evidence.',
  },
  {
    action: 'research_sync',
    label: 'Sync Research',
    description: 'Pull the latest scored research bundle used for retrieval, policy, and runbook refresh.',
  },
  {
    action: 'catalog_sync',
    label: 'Sync Catalog',
    description: 'Update the aidb knowledge catalog used by retrieval and tooling discovery.',
  },
  {
    action: 'improvement_pass',
    label: 'Run Improvement Pass',
    description: 'Launch the bounded improvement pass that produces artifact-backed maintenance output.',
  },
];

function formatTimestamp(value?: string | null): string {
  if (!value) {
    return 'Not recorded';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function formatRelative(value?: string | null): string {
  if (!value) {
    return 'No recent update';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const diffMs = date.getTime() - Date.now();
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
  const minutes = Math.round(diffMs / 60000);
  if (Math.abs(minutes) < 60) {
    return rtf.format(minutes, 'minute');
  }
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) {
    return rtf.format(hours, 'hour');
  }
  const days = Math.round(hours / 24);
  return rtf.format(days, 'day');
}

function summarizeAction(action: PRSIAction): string {
  return (
    action.summary
    || action.reason
    || action.rationale
    || [action.action, action.type, action.target].filter(Boolean).join(' -> ')
    || 'No action summary provided by orchestrator'
  );
}

function badgeTone(kind?: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (!kind) {
    return 'outline';
  }
  if (['pending_approval', 'medium', 'high'].includes(kind)) {
    return 'secondary';
  }
  if (['reject', 'rejected', 'failed', 'critical'].includes(kind)) {
    return 'destructive';
  }
  if (['approved', 'executed', 'low', 'ok'].includes(kind)) {
    return 'default';
  }
  return 'outline';
}

export function CommandCenterOperations() {
  const [prsi, setPrsi] = useState<PRSIActionsResponse | null>(null);
  const [harness, setHarness] = useState<HarnessOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [activityMessage, setActivityMessage] = useState<string>('Idle');

  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      try {
        const [prsiData, harnessData] = await Promise.all([
          DashboardAPI.getPRSIActions(),
          DashboardAPI.getHarnessOverview(),
        ]);
        if (!cancelled) {
          setPrsi(prsiData);
          setHarness(harnessData);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unknown error');
        }
      }
    };

    void fetchData();
    const interval = setInterval(() => {
      void fetchData();
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const refreshData = async (message: string) => {
    const [prsiData, harnessData] = await Promise.all([
      DashboardAPI.getPRSIActions(),
      DashboardAPI.getHarnessOverview(),
    ]);
    setPrsi(prsiData);
    setHarness(harnessData);
    setActivityMessage(message);
    setError(null);
  };

  const runHarnessAction = async (action: HarnessMaintenanceAction, label: string) => {
    setBusyKey(action);
    setActivityMessage(`${label} in progress...`);
    try {
      const result = await DashboardAPI.runHarnessMaintenance(action);
      await refreshData(
        result.success
          ? `${label} completed in ${(result.duration_ms / 1000).toFixed(1)}s`
          : `${label} failed with exit ${result.exit_code}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Harness action failed');
      setActivityMessage(`${label} failed`);
    } finally {
      setBusyKey(null);
    }
  };

  const syncQueue = async () => {
    setBusyKey('prsi-sync');
    setActivityMessage('Syncing PRSI queue...');
    try {
      await DashboardAPI.syncPRSIActions();
      await refreshData('PRSI queue synchronized');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'PRSI sync failed');
      setActivityMessage('PRSI queue sync failed');
    } finally {
      setBusyKey(null);
    }
  };

  const approveAction = async (actionId: string, decision: 'approve' | 'reject') => {
    setBusyKey(`${decision}-${actionId}`);
    setActivityMessage(`${decision === 'approve' ? 'Approving' : 'Rejecting'} ${actionId}...`);
    try {
      await DashboardAPI.approvePRSIAction(actionId, decision);
      await refreshData(`Action ${actionId} marked ${decision}d`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'PRSI approval failed');
      setActivityMessage(`Action ${actionId} ${decision} failed`);
    } finally {
      setBusyKey(null);
    }
  };

  const executeActions = async (dryRun: boolean) => {
    setBusyKey(dryRun ? 'prsi-dry-run' : 'prsi-execute');
    setActivityMessage(dryRun ? 'Running PRSI dry run...' : 'Executing approved PRSI actions...');
    try {
      await DashboardAPI.executePRSIActions(5, dryRun, true);
      await refreshData(dryRun ? 'PRSI dry run completed' : 'Approved PRSI actions executed');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'PRSI execute failed');
      setActivityMessage(dryRun ? 'PRSI dry run failed' : 'PRSI execution failed');
    } finally {
      setBusyKey(null);
    }
  };

  const counts = prsi?.prsi.counts ?? {};
  const actions = (prsi?.prsi.actions ?? []).filter((item) =>
    ['pending_approval', 'approved', 'executed'].includes(item.status ?? ''),
  );
  const highlightedActions = actions.slice(0, 6);
  const harnessStats = harness?.harness.stats ?? {};
  const scorecardAcceptance = harness?.harness.scorecard?.acceptance;
  const passRate = Number(
    harnessStats.pass_rate_pct
      ?? (typeof scorecardAcceptance?.pass_rate === 'number' ? scorecardAcceptance.pass_rate * 100 : 0),
  );
  const scripts = harness?.maintenance.scripts ?? [];
  const research = harness?.maintenance.weekly_research;
  const hybrid = harness?.harness.hybrid_harness ?? {};
  const readyScripts = scripts.filter((script) => script.exists && script.executable).length;
  const readinessLabel = counts.pending_approval
    ? `${counts.pending_approval} awaiting review`
    : counts.approved
      ? `${counts.approved} ready to execute`
      : 'Queue is synchronized';

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="command-center-kicker">Command Center Operations</p>
          <h2 className="text-2xl font-semibold tracking-tight">PRSI queue and AI harness controls</h2>
          <p className="max-w-3xl text-sm text-muted-foreground">
            The queue now exposes what the orchestrator wants to change, how risky each action is, and what operators can do next.
            Harness operations show the actual maintenance actions wired to the backend instead of passive status text.
          </p>
        </div>
        <Badge variant={error ? 'destructive' : 'outline'} className="w-fit">
          {error ? `Attention: ${error}` : activityMessage}
        </Badge>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
        <Card className="command-panel border-amber-500/20">
          <CardHeader className="gap-3 border-b border-border/60">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-amber-500" />
                  <CardTitle className="text-xl">PRSI Orchestration Queue</CardTitle>
                </div>
                <CardDescription className="mt-1">
                  Pending proposals from the pessimistic recursive self-improvement loop, with approval and execution controls.
                </CardDescription>
              </div>
              <Badge variant={counts.pending_approval ? 'secondary' : counts.approved ? 'default' : 'outline'}>
                {readinessLabel}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-5 pt-6">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <div className="ops-stat">
                <span className="ops-stat-label">Pending review</span>
                <strong>{counts.pending_approval ?? 0}</strong>
              </div>
              <div className="ops-stat">
                <span className="ops-stat-label">Approved</span>
                <strong>{counts.approved ?? 0}</strong>
              </div>
              <div className="ops-stat">
                <span className="ops-stat-label">Executed</span>
                <strong>{counts.executed ?? 0}</strong>
              </div>
              <div className="ops-stat">
                <span className="ops-stat-label">Last sync</span>
                <strong className="text-base">{formatRelative(prsi?.prsi.updated_at)}</strong>
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button onClick={() => void syncQueue()} disabled={busyKey !== null}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Sync Queue
              </Button>
              <Button variant="outline" onClick={() => void executeActions(true)} disabled={busyKey !== null}>
                <Clock3 className="mr-2 h-4 w-4" />
                Dry Run Approved Actions
              </Button>
              <Button variant="secondary" onClick={() => void executeActions(false)} disabled={busyKey !== null}>
                <CheckCircle2 className="mr-2 h-4 w-4" />
                Execute Approved Actions
              </Button>
            </div>

            <div className="space-y-3">
              {highlightedActions.length ? (
                highlightedActions.map((action, index) => {
                  const actionId = action.id || `action-${index + 1}`;
                  const canReview = action.status === 'pending_approval' && Boolean(action.id);

                  return (
                    <div key={actionId} className="ops-list-item">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium">{action.action || action.type || 'Proposed change'}</span>
                            <Badge variant={badgeTone(action.status)}>{action.status || 'unknown'}</Badge>
                            <Badge variant={badgeTone(action.risk)}>{action.risk || 'risk n/a'}</Badge>
                            {typeof (action.score ?? action.confidence) === 'number' ? (
                              <Badge variant="outline">
                                confidence {(action.score ?? action.confidence ?? 0).toFixed(2)}
                              </Badge>
                            ) : null}
                          </div>
                          <p className="text-sm text-muted-foreground">{summarizeAction(action)}</p>
                          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                            <span>ID: {action.id || 'not provided'}</span>
                            <span>Updated: {formatTimestamp(action.updated_at || action.last_seen_at || action.created_at)}</span>
                            {action.target ? <span>Target: {action.target}</span> : null}
                          </div>
                        </div>
                        {canReview ? (
                          <div className="flex shrink-0 gap-2">
                            <Button
                              size="sm"
                              variant="secondary"
                              disabled={busyKey !== null}
                              onClick={() => void approveAction(action.id as string, 'approve')}
                            >
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={busyKey !== null}
                              onClick={() => void approveAction(action.id as string, 'reject')}
                            >
                              Reject
                            </Button>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="ops-empty-state">
                  <ShieldCheck className="h-5 w-5 text-emerald-500" />
                  <div>
                    <p className="font-medium">No actionable PRSI changes are waiting right now.</p>
                    <p className="text-sm text-muted-foreground">
                      Use queue sync to pull fresh structured actions from the orchestrator when new proposals should appear.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="command-panel border-sky-500/20">
          <CardHeader className="gap-3 border-b border-border/60">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <Bot className="h-4 w-4 text-sky-500" />
                  <CardTitle className="text-xl">AI Harness Operations</CardTitle>
                </div>
                <CardDescription className="mt-1">
                  Active maintenance actions for the harness, plus execution readiness from scripts, policy wiring, and recent evidence.
                </CardDescription>
              </div>
              <Badge variant={passRate >= 70 ? 'default' : 'secondary'}>
                {passRate > 0 ? `${passRate.toFixed(0)}% pass rate` : 'Awaiting fresh acceptance data'}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-5 pt-6">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="ops-stat">
                <span className="ops-stat-label">Acceptance runs</span>
                <strong>{harnessStats.total_runs ?? 0}</strong>
                <span className="text-xs text-muted-foreground">
                  Last run {formatRelative(harnessStats.last_run_at || harness?.harness.scorecard?.generated_at)}
                </span>
              </div>
              <div className="ops-stat">
                <span className="ops-stat-label">Operational scripts</span>
                <strong>{readyScripts}/{harness?.maintenance.total_scripts ?? 0}</strong>
                <span className="text-xs text-muted-foreground">
                  Executable scripts exposed in the dashboard action set
                </span>
              </div>
              <div className="ops-stat">
                <span className="ops-stat-label">Research bundle</span>
                <strong>{research?.candidate_count ?? 0}</strong>
                <span className="text-xs text-muted-foreground">
                  Candidates from {research?.sources_scanned ?? 0} sources
                </span>
              </div>
              <div className="ops-stat">
                <span className="ops-stat-label">Hybrid harness</span>
                <strong>{hybrid.enabled ? 'Enabled' : 'Unavailable'}</strong>
                <span className="text-xs text-muted-foreground">
                  Memory {hybrid.memory_enabled ? 'on' : 'off'} • Tree search {hybrid.tree_search_enabled ? 'on' : 'off'} • Eval {hybrid.eval_enabled ? 'on' : 'off'}
                </span>
              </div>
            </div>

            <div className="space-y-3">
              {HARNESS_ACTIONS.map((item) => (
                <div key={item.action} className="ops-list-item">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <Wrench className="h-4 w-4 text-sky-500" />
                        <p className="font-medium">{item.label}</p>
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">{item.description}</p>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busyKey !== null}
                      onClick={() => void runHarnessAction(item.action, item.label)}
                    >
                      Run Action
                    </Button>
                  </div>
                </div>
              ))}
            </div>

            <div className="ops-empty-state">
              {error ? <AlertTriangle className="h-5 w-5 text-amber-500" /> : <ShieldCheck className="h-5 w-5 text-emerald-500" />}
              <div>
                <p className="font-medium">Operational evidence</p>
                <p className="text-sm text-muted-foreground">
                  Weekly research updated {formatRelative(research?.generated_at)}. Improvement pass evidence is reported by the backend after each run.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}

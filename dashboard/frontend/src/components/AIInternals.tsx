import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Database, Cpu, Zap } from 'lucide-react';

interface AIInternalsData {
  embedding_cache_hit_rate_pct: number;
  llm_routing_local_pct: number;
  tokens_compressed_last_hour: number;
  timestamp: string;
}

const POLL_INTERVAL_MS = 30000;

export function AIInternals() {
  const [data, setData] = useState<AIInternalsData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      try {
        const response = await fetch('/api/aistack/metrics');
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const json: AIInternalsData = await response.json();
        if (!cancelled) {
          setData(json);
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
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">AI Internals</CardTitle>
          <Cpu className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-xs text-muted-foreground">Metrics unavailable: {error}</div>
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-muted-foreground">Loading AI internals...</div>
        </CardContent>
      </Card>
    );
  }

  const remoteRoutingPct = Math.max(0, 100 - data.llm_routing_local_pct);

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {/* Embedding Cache Hit Rate */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Embedding Cache Hit Rate</CardTitle>
          <Database className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{data.embedding_cache_hit_rate_pct.toFixed(1)}%</div>
          <Progress value={data.embedding_cache_hit_rate_pct} className="mt-2" />
          <p className="text-xs text-muted-foreground mt-2">
            Cached embeddings served without recompute
          </p>
        </CardContent>
      </Card>

      {/* Tokens Compressed Last Hour */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Tokens Compressed (1h)</CardTitle>
          <Zap className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {data.tokens_compressed_last_hour.toLocaleString()}
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Total tokens saved by context compression
          </p>
        </CardContent>
      </Card>

      {/* LLM Routing: Local vs Remote */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">LLM Routing</CardTitle>
          <Cpu className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{data.llm_routing_local_pct.toFixed(1)}%</div>
          <Progress value={data.llm_routing_local_pct} className="mt-2" />
          <p className="text-xs text-muted-foreground mt-2">
            Local: {data.llm_routing_local_pct.toFixed(1)}% &bull; Remote: {remoteRoutingPct.toFixed(1)}%
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

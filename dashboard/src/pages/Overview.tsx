import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { StatCard } from '../components/StatCard'
import { CostChart } from '../components/CostChart'
import { ModelTable } from '../components/ModelTable'

export default function Overview() {
  const queryClient = useQueryClient()
  const [demoState, setDemoState] = useState<'idle' | 'running' | 'done'>('idle')

  async function handleRunDemo() {
    setDemoState('running')
    try {
      await api.runDemo()
      // Wait a few seconds for background tasks to complete, then refresh
      setTimeout(() => {
        queryClient.invalidateQueries()
        setDemoState('done')
        setTimeout(() => setDemoState('idle'), 3000)
      }, 6000)
    } catch {
      setDemoState('idle')
    }
  }

  const { data: summary, isLoading: loadingSummary } = useQuery({
    queryKey: ['summary'],
    queryFn: api.getSummary,
    refetchInterval: 30_000,
  })

  const { data: timeseries = [], isLoading: loadingTs } = useQuery({
    queryKey: ['timeseries'],
    queryFn: api.getTimeseries,
    refetchInterval: 30_000,
  })

  const { data: models = [], isLoading: loadingModels } = useQuery({
    queryKey: ['models'],
    queryFn: api.getModels,
    refetchInterval: 30_000,
  })

  return (
    <div className="p-6 flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Overview</h1>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted">Auto-refreshes every 30 s</span>
          <button
            onClick={handleRunDemo}
            disabled={demoState === 'running'}
            className="text-xs px-3 py-1.5 rounded-md font-medium transition-colors
              bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white"
          >
            {demoState === 'running' ? '⏳ Generating...' : demoState === 'done' ? '✓ Done!' : '▶ Generate Demo Data'}
          </button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {loadingSummary ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-card border border-border rounded-lg p-5 h-24 animate-pulse" />
          ))
        ) : summary ? (
          <>
            <StatCard
              title="Total Traces"
              value={summary.total_traces.toLocaleString()}
              subtitle={`${summary.traces_last_24h.toLocaleString()} in last 24 h`}
            />
            <StatCard
              title="Error Rate"
              value={`${(summary.error_rate * 100).toFixed(1)}%`}
              valueColor={summary.error_rate > 0.1 ? 'text-danger' : summary.error_rate > 0.02 ? 'text-warning' : 'text-success'}
            />
            <StatCard
              title="Avg Latency"
              value={`${summary.avg_latency_ms.toFixed(0)} ms`}
              subtitle={`p50: ${summary.p50_latency_ms.toFixed(0)} ms · p99: ${summary.p99_latency_ms.toFixed(0)} ms`}
            />
            <StatCard
              title="Total Cost"
              value={`$${summary.total_cost_usd.toFixed(4)}`}
              subtitle={`${(summary.total_tokens / 1000).toFixed(0)} k tokens`}
            />
          </>
        ) : null}
      </div>

      {/* Cost chart */}
      <div className="bg-card border border-border rounded-lg p-5">
        <h2 className="text-sm font-medium mb-4">Cost & Traces — Last 7 Days</h2>
        {loadingTs ? (
          <div className="h-56 animate-pulse bg-border/30 rounded" />
        ) : (
          <CostChart data={timeseries} />
        )}
      </div>

      {/* Model breakdown */}
      <div className="bg-card border border-border rounded-lg p-5">
        <h2 className="text-sm font-medium mb-4">Model Breakdown</h2>
        {loadingModels ? (
          <div className="h-24 animate-pulse bg-border/30 rounded" />
        ) : (
          <ModelTable data={models} />
        )}
      </div>
    </div>
  )
}

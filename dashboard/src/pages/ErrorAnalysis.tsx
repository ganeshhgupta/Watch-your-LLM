import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { api, Trace } from '../api/client'
import { TraceDrawer } from '../components/TraceDrawer'

interface TooltipProps {
  active?: boolean
  payload?: { value: number }[]
  label?: string
}

function CustomTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-card border border-border rounded p-2 text-xs">
      <p className="text-white font-mono">{label}</p>
      <p className="text-danger">{payload[0].value} occurrences</p>
    </div>
  )
}

export default function ErrorAnalysis() {
  const [selectedTrace, setSelectedTrace] = useState<Trace | null>(null)

  const { data: errors = [], isLoading: loadingErrors } = useQuery({
    queryKey: ['errors'],
    queryFn: api.getErrors,
    refetchInterval: 30_000,
  })

  const { data: recentErrors, isLoading: loadingRecent } = useQuery({
    queryKey: ['traces', { has_error: true, limit: 20 }],
    queryFn: () => api.getTraces({ has_error: true, limit: 20 }),
    refetchInterval: 30_000,
  })

  return (
    <div className="p-6 flex flex-col gap-6">
      <h1 className="text-xl font-semibold">Error Analysis</h1>

      {/* Bar chart */}
      <div className="bg-card border border-border rounded-lg p-5">
        <h2 className="text-sm font-medium mb-4">Top Error Types</h2>
        {loadingErrors ? (
          <div className="h-48 animate-pulse bg-border/30 rounded" />
        ) : errors.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-success text-sm">
            ✓ No errors recorded
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={errors}
              layout="vertical"
              margin={{ top: 0, right: 16, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fill: '#6b7280', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                type="category"
                dataKey="error_class"
                tick={{ fill: '#f3f4f6', fontSize: 11, fontFamily: 'monospace' }}
                tickLine={false}
                axisLine={false}
                width={160}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {errors.map((_, i) => (
                  <Cell key={i} fill={i === 0 ? '#ef4444' : i === 1 ? '#f97316' : '#f59e0b'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Error table */}
      <div className="bg-card border border-border rounded-lg p-5">
        <h2 className="text-sm font-medium mb-4">Recent Errors</h2>
        {loadingRecent ? (
          <div className="h-32 animate-pulse bg-border/30 rounded" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  {['Time', 'Function', 'Model', 'Error', 'Input Preview'].map((h) => (
                    <th
                      key={h}
                      className="text-left text-xs font-medium text-muted uppercase tracking-wider py-2 px-3"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(recentErrors?.traces ?? []).length === 0 && (
                  <tr>
                    <td colSpan={5} className="text-center text-muted py-8">
                      No errors found
                    </td>
                  </tr>
                )}
                {(recentErrors?.traces ?? []).map((t) => (
                  <tr
                    key={t.trace_id}
                    onClick={() => setSelectedTrace(t)}
                    className="border-b border-border/50 hover:bg-white/5 cursor-pointer transition-colors"
                  >
                    <td className="py-2 px-3 text-xs text-muted whitespace-nowrap">
                      {new Date(t.timestamp).toLocaleString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false,
                      })}
                    </td>
                    <td className="py-2 px-3 font-mono text-xs">{t.function_name}</td>
                    <td className="py-2 px-3 font-mono text-accent text-xs">{t.model}</td>
                    <td className="py-2 px-3">
                      <span className="text-danger text-xs font-mono">{t.error_class}</span>
                    </td>
                    <td className="py-2 px-3 text-xs text-muted max-w-xs truncate">
                      {t.input_preview?.slice(0, 80) ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <TraceDrawer trace={selectedTrace} onClose={() => setSelectedTrace(null)} />
    </div>
  )
}

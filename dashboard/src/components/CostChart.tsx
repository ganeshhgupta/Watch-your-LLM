import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { TimeseriesPoint } from '../api/client'

interface CostChartProps {
  data: TimeseriesPoint[]
}

function formatHour(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', hour12: false })
}

interface TooltipPayloadItem {
  name: string
  value: number
  color: string
}

interface CustomTooltipProps {
  active?: boolean
  label?: string
  payload?: TooltipPayloadItem[]
}

function CustomTooltip({ active, label, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-card border border-border rounded p-3 text-xs space-y-1">
      <p className="text-muted">{label ? formatHour(label) : ''}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name === 'cost_usd' ? `Cost: $${p.value.toFixed(4)}` : `Traces: ${p.value}`}
        </p>
      ))}
    </div>
  )
}

export function CostChart({ data }: CostChartProps) {
  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-48 text-muted text-sm">
        No data yet
      </div>
    )
  }

  const formatted = data.map((d) => ({
    ...d,
    label: formatHour(d.hour),
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={formatted} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="traceGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#22c55e" stopOpacity={0.2} />
            <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
        <XAxis
          dataKey="label"
          tick={{ fill: '#6b7280', fontSize: 10 }}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          yAxisId="cost"
          tick={{ fill: '#6b7280', fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `$${v.toFixed(3)}`}
        />
        <YAxis
          yAxisId="traces"
          orientation="right"
          tick={{ fill: '#6b7280', fontSize: 10 }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: 11, color: '#6b7280' }}
          formatter={(value: string) => (value === 'cost_usd' ? 'Cost (USD)' : 'Traces')}
        />
        <Area
          yAxisId="cost"
          type="monotone"
          dataKey="cost_usd"
          stroke="#3b82f6"
          strokeWidth={2}
          fill="url(#costGrad)"
          dot={false}
        />
        <Area
          yAxisId="traces"
          type="monotone"
          dataKey="trace_count"
          stroke="#22c55e"
          strokeWidth={2}
          fill="url(#traceGrad)"
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

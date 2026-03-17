import { ModelStats } from '../api/client'

interface ModelTableProps {
  data: ModelStats[]
}

export function ModelTable({ data }: ModelTableProps) {
  if (!data.length) {
    return <p className="text-muted text-sm py-4">No model data yet.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {['Model', 'Calls', 'Avg Latency', 'Total Cost', 'Error Rate'].map((h) => (
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
          {data.map((row) => (
            <tr key={row.model} className="border-b border-border/50 hover:bg-white/5 transition-colors">
              <td className="py-2 px-3 font-mono text-accent">{row.model}</td>
              <td className="py-2 px-3 tabular-nums">{row.count.toLocaleString()}</td>
              <td className="py-2 px-3 tabular-nums">{row.avg_latency_ms.toFixed(0)} ms</td>
              <td className="py-2 px-3 tabular-nums">${row.total_cost_usd.toFixed(4)}</td>
              <td className="py-2 px-3 tabular-nums">
                <span
                  className={
                    row.error_rate > 0.1
                      ? 'text-danger'
                      : row.error_rate > 0.02
                      ? 'text-warning'
                      : 'text-success'
                  }
                >
                  {(row.error_rate * 100).toFixed(1)}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

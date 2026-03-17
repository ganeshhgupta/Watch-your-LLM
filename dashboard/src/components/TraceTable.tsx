import { Trace } from '../api/client'

interface TraceTableProps {
  traces: Trace[]
  total: number
  limit: number
  offset: number
  onRowClick: (trace: Trace) => void
  onPageChange: (offset: number) => void
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

export function TraceTable({
  traces,
  total,
  limit,
  offset,
  onRowClick,
  onPageChange,
}: TraceTableProps) {
  const totalPages = Math.ceil(total / limit)
  const currentPage = Math.floor(offset / limit) + 1

  return (
    <div className="flex flex-col gap-2">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              {['Timestamp', 'Function', 'Model', 'Latency', 'Tokens', 'Cost', 'Status'].map((h) => (
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
            {traces.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center text-muted py-8">
                  No traces found
                </td>
              </tr>
            )}
            {traces.map((t) => (
              <tr
                key={t.trace_id}
                onClick={() => onRowClick(t)}
                className="border-b border-border/50 hover:bg-white/5 cursor-pointer transition-colors"
              >
                <td className="py-2 px-3 text-xs text-muted whitespace-nowrap">
                  {formatDate(t.timestamp)}
                </td>
                <td className="py-2 px-3 font-mono text-xs">{t.function_name}</td>
                <td className="py-2 px-3 font-mono text-accent text-xs">{t.model}</td>
                <td className="py-2 px-3 tabular-nums text-xs whitespace-nowrap">
                  {t.latency_ms != null ? `${t.latency_ms} ms` : '—'}
                </td>
                <td className="py-2 px-3 tabular-nums text-xs">
                  {t.total_tokens != null ? t.total_tokens.toLocaleString() : '—'}
                </td>
                <td className="py-2 px-3 tabular-nums text-xs">
                  {t.cost_usd != null ? `$${t.cost_usd.toFixed(5)}` : '—'}
                </td>
                <td className="py-2 px-3">
                  {t.error_class ? (
                    <span className="inline-flex items-center gap-1 text-danger text-xs">
                      <span>✗</span>
                      <span className="font-mono">{t.error_class}</span>
                    </span>
                  ) : (
                    <span className="text-success text-xs">✓</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-xs text-muted px-1">
        <span>
          {total === 0
            ? 'No results'
            : `${offset + 1}–${Math.min(offset + limit, total)} of ${total.toLocaleString()}`}
        </span>
        <div className="flex gap-1">
          <button
            onClick={() => onPageChange(Math.max(0, offset - limit))}
            disabled={currentPage === 1}
            className="px-2 py-1 rounded border border-border disabled:opacity-30 hover:bg-white/5 transition-colors"
          >
            ‹ Prev
          </button>
          <span className="px-2 py-1">
            {currentPage} / {totalPages || 1}
          </span>
          <button
            onClick={() => onPageChange(offset + limit)}
            disabled={currentPage >= totalPages}
            className="px-2 py-1 rounded border border-border disabled:opacity-30 hover:bg-white/5 transition-colors"
          >
            Next ›
          </button>
        </div>
      </div>
    </div>
  )
}

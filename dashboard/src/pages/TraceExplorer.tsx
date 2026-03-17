import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, Trace, TraceFilters } from '../api/client'
import { TraceTable } from '../components/TraceTable'
import { TraceDrawer } from '../components/TraceDrawer'

const LIMIT = 50

export default function TraceExplorer() {
  const [filters, setFilters] = useState<TraceFilters>({ limit: LIMIT, offset: 0 })
  const [selectedTrace, setSelectedTrace] = useState<Trace | null>(null)

  // Local form state (committed on Apply)
  const [modelInput, setModelInput] = useState('')
  const [tagInput, setTagInput] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [errorsOnly, setErrorsOnly] = useState(false)

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['traces', filters],
    queryFn: () => api.getTraces(filters),
    refetchInterval: 30_000,
  })

  function applyFilters() {
    setFilters({
      model: modelInput || undefined,
      tag: tagInput || undefined,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      has_error: errorsOnly ? true : undefined,
      limit: LIMIT,
      offset: 0,
    })
  }

  function resetFilters() {
    setModelInput('')
    setTagInput('')
    setStartDate('')
    setEndDate('')
    setErrorsOnly(false)
    setFilters({ limit: LIMIT, offset: 0 })
  }

  const inputCls =
    'bg-[#0f0f0f] border border-border rounded px-3 py-1.5 text-sm focus:outline-none focus:border-accent placeholder-muted'

  return (
    <div className="p-6 flex flex-col gap-5">
      <h1 className="text-xl font-semibold">Trace Explorer</h1>

      {/* Filter bar */}
      <div className="bg-card border border-border rounded-lg p-4 flex flex-wrap gap-3 items-end">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted">Model</label>
          <input
            className={`${inputCls} w-44`}
            placeholder="gemini-1.5-flash"
            value={modelInput}
            onChange={(e) => setModelInput(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted">Tag (key:value)</label>
          <input
            className={`${inputCls} w-44`}
            placeholder="env:prod"
            value={tagInput}
            onChange={(e) => setTagInput(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted">Start date</label>
          <input
            type="datetime-local"
            className={`${inputCls} w-48`}
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted">End date</label>
          <input
            type="datetime-local"
            className={`${inputCls} w-48`}
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </div>
        <label className="flex items-center gap-2 text-sm cursor-pointer select-none pb-1.5">
          <input
            type="checkbox"
            className="accent-accent"
            checked={errorsOnly}
            onChange={(e) => setErrorsOnly(e.target.checked)}
          />
          Errors only
        </label>
        <div className="flex gap-2 pb-0.5">
          <button
            onClick={applyFilters}
            className="bg-accent hover:bg-accent-hover text-white text-sm px-4 py-1.5 rounded transition-colors"
          >
            Apply
          </button>
          <button
            onClick={resetFilters}
            className="border border-border hover:bg-white/5 text-sm px-3 py-1.5 rounded transition-colors"
          >
            Reset
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-card border border-border rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm text-muted">
            {data ? `${data.total.toLocaleString()} traces` : ''}
          </span>
          {isFetching && <span className="text-xs text-muted animate-pulse">Refreshing…</span>}
        </div>

        {isLoading ? (
          <div className="h-48 animate-pulse bg-border/30 rounded" />
        ) : (
          <TraceTable
            traces={data?.traces ?? []}
            total={data?.total ?? 0}
            limit={LIMIT}
            offset={filters.offset ?? 0}
            onRowClick={setSelectedTrace}
            onPageChange={(offset) => setFilters((f) => ({ ...f, offset }))}
          />
        )}
      </div>

      <TraceDrawer trace={selectedTrace} onClose={() => setSelectedTrace(null)} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Trace {
  id: number
  trace_id: string
  timestamp: string
  function_name: string
  module: string
  model: string
  input_preview: string | null
  output_preview: string | null
  prompt_tokens: number | null
  completion_tokens: number | null
  total_tokens: number | null
  latency_ms: number | null
  cost_usd: number | null
  error_class: string | null
  error_message: string | null
  tags: string | null // JSON string
}

export interface TracesResponse {
  total: number
  traces: Trace[]
  limit: number
  offset: number
}

export interface SummaryStats {
  total_traces: number
  error_rate: number
  avg_latency_ms: number
  p50_latency_ms: number
  p99_latency_ms: number
  total_cost_usd: number
  total_tokens: number
  traces_last_24h: number
}

export interface TimeseriesPoint {
  hour: string
  cost_usd: number
  trace_count: number
}

export interface ModelStats {
  model: string
  count: number
  avg_latency_ms: number
  total_cost_usd: number
  error_rate: number
}

export interface ErrorStats {
  error_class: string
  count: number
  last_seen: string
  example_message: string | null
}

export interface TraceFilters {
  model?: string
  tag?: string
  start_date?: string
  end_date?: string
  has_error?: boolean
  limit?: number
  offset?: number
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function fetchJSON<T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  const url = new URL(BASE_URL + path)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value))
      }
    })
  }
  const res = await fetch(url.toString())
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  getTraces: (filters?: TraceFilters) =>
    fetchJSON<TracesResponse>('/v1/traces', filters as Record<string, string | number | boolean | undefined>),

  getTrace: (traceId: string) => fetchJSON<Trace>(`/v1/traces/${traceId}`),

  getSummary: () => fetchJSON<SummaryStats>('/v1/stats/summary'),

  getTimeseries: () => fetchJSON<TimeseriesPoint[]>('/v1/stats/timeseries'),

  getModels: () => fetchJSON<ModelStats[]>('/v1/stats/models'),

  getErrors: () => fetchJSON<ErrorStats[]>('/v1/stats/errors'),

  runDemo: () =>
    fetch(BASE_URL + '/v1/demo/', { method: 'POST' }).then(r => r.json()),
}

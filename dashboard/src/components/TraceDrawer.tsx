import { useEffect, useState } from 'react'
import { Trace } from '../api/client'

interface TraceDrawerProps {
  trace: Trace | null
  onClose: () => void
}

function Field({ label, value, mono = false }: { label: string; value: string | number | null | undefined; mono?: boolean }) {
  if (value == null || value === '') return null
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted uppercase tracking-wider">{label}</span>
      <span className={`text-sm break-all ${mono ? 'font-mono' : ''}`}>{String(value)}</span>
    </div>
  )
}

function ExpandableText({ label, text }: { label: string; text: string | null }) {
  const [expanded, setExpanded] = useState(false)
  if (!text) return null
  const preview = text.slice(0, 300)
  const hasMore = text.length > 300

  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-muted uppercase tracking-wider">{label}</span>
      <div className="bg-[#0f0f0f] rounded border border-border p-3 text-xs font-mono whitespace-pre-wrap break-all">
        {expanded ? text : preview}
        {hasMore && !expanded && '…'}
      </div>
      {hasMore && (
        <button
          onClick={() => setExpanded((e) => !e)}
          className="text-xs text-accent hover:underline self-start"
        >
          {expanded ? 'Show less' : 'Show full'}
        </button>
      )}
    </div>
  )
}

export function TraceDrawer({ trace, onClose }: TraceDrawerProps) {
  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const parsedTags = (() => {
    if (!trace?.tags) return null
    try {
      return JSON.parse(trace.tags) as Record<string, unknown>
    } catch {
      return null
    }
  })()

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 bg-black/50 z-40 transition-opacity ${trace ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={onClose}
      />

      {/* Drawer */}
      <aside
        className={`fixed top-0 right-0 h-full w-full max-w-xl bg-card border-l border-border z-50 overflow-y-auto transition-transform duration-300 ${
          trace ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {trace && (
          <div className="flex flex-col gap-5 p-6">
            {/* Header */}
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-base font-semibold">{trace.function_name}</h2>
                <p className="text-xs text-muted font-mono">{trace.trace_id}</p>
              </div>
              <button
                onClick={onClose}
                className="text-muted hover:text-white transition-colors text-xl leading-none"
              >
                ×
              </button>
            </div>

            {/* Status badge */}
            {trace.error_class ? (
              <div className="bg-danger/10 border border-danger/30 rounded p-3 text-sm">
                <p className="text-danger font-semibold">{trace.error_class}</p>
                {trace.error_message && (
                  <p className="text-xs text-danger/80 mt-1 font-mono">{trace.error_message}</p>
                )}
              </div>
            ) : (
              <div className="bg-success/10 border border-success/30 rounded p-2 text-xs text-success font-medium">
                ✓ Success
              </div>
            )}

            {/* Metadata grid */}
            <div className="grid grid-cols-2 gap-4">
              <Field label="Model" value={trace.model} mono />
              <Field
                label="Timestamp"
                value={new Date(trace.timestamp).toLocaleString('en-US', { hour12: false })}
              />
              <Field label="Latency" value={trace.latency_ms != null ? `${trace.latency_ms} ms` : null} />
              <Field label="Cost" value={trace.cost_usd != null ? `$${trace.cost_usd.toFixed(6)}` : null} />
              <Field
                label="Prompt tokens"
                value={trace.prompt_tokens != null ? trace.prompt_tokens.toLocaleString() : null}
              />
              <Field
                label="Completion tokens"
                value={trace.completion_tokens != null ? trace.completion_tokens.toLocaleString() : null}
              />
              <Field
                label="Total tokens"
                value={trace.total_tokens != null ? trace.total_tokens.toLocaleString() : null}
              />
              <Field label="Module" value={trace.module} mono />
            </div>

            {/* Tags */}
            {parsedTags && Object.keys(parsedTags).length > 0 && (
              <div className="flex flex-col gap-1">
                <span className="text-xs text-muted uppercase tracking-wider">Tags</span>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(parsedTags).map(([k, v]) => (
                    <span
                      key={k}
                      className="text-xs bg-accent/15 text-accent border border-accent/30 rounded px-2 py-0.5 font-mono"
                    >
                      {k}: {String(v)}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Input / Output */}
            <ExpandableText label="Input" text={trace.input_preview} />
            <ExpandableText label="Output" text={trace.output_preview} />
          </div>
        )}
      </aside>
    </>
  )
}

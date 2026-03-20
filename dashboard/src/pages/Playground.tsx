import { useState, useEffect, useRef, useCallback } from 'react'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type Tab = 'chat' | 'cot' | 'rag' | 'agents'
type AgentType = 'research' | 'code' | 'debate'
interface Message { role: 'user' | 'assistant'; content: string }
interface Step { title: string; content: string }
interface CotTurn { question: string; steps: Step[]; answer: string }
interface AgentRound { task: string; steps: Step[]; agentType: AgentType }
interface TraceRow { function_name: string; latency_ms: number; cost_usd: number | null; error_class: string | null }

// ---------------------------------------------------------------------------
// sessionStorage hook — survives navigation within the same browser tab
// ---------------------------------------------------------------------------
function useSessionStorage<T>(key: string, init: T): [T, React.Dispatch<React.SetStateAction<T>>] {
  const [state, rawSet] = useState<T>(() => {
    try {
      const s = sessionStorage.getItem(key)
      return s ? JSON.parse(s) : init
    } catch { return init }
  })
  const set: React.Dispatch<React.SetStateAction<T>> = useCallback((action) => {
    rawSet(prev => {
      const next = typeof action === 'function' ? (action as (p: T) => T)(prev) : action
      try { sessionStorage.setItem(key, JSON.stringify(next)) } catch {}
      return next
    })
  }, [key])
  return [state, set]
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
async function post(path: string, body: object) {
  const res = await fetch(`${BASE_URL}/v1/playground/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

async function* streamSSE(path: string, body: object): AsyncGenerator<any> {
  const res = await fetch(`${BASE_URL}/v1/playground/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await res.text())
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try { yield JSON.parse(line.slice(6)) } catch {}
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Left pane — live session metrics
// ---------------------------------------------------------------------------
function LiveMetrics({ sessionId }: { sessionId: string }) {
  const [traces, setTraces] = useState<TraceRow[]>([])

  useEffect(() => {
    const poll = async () => {
      try {
        const data = await fetch(
          `${BASE_URL}/v1/traces?tag=session:${sessionId}&limit=50`
        ).then(r => r.json())
        if (data.traces) setTraces(data.traces)
      } catch {}
    }
    poll()
    const id = setInterval(poll, 3000)
    return () => clearInterval(id)
  }, [sessionId])

  const totalCost = traces.reduce((s, t) => s + (t.cost_usd ?? 0), 0)
  const avgLatency = traces.length ? traces.reduce((s, t) => s + (t.latency_ms ?? 0), 0) / traces.length : 0
  const errors = traces.filter(t => t.error_class).length

  const fnColor = (fn: string) => {
    if (fn.startsWith('chat')) return 'text-blue-400'
    if (fn.startsWith('cot')) return 'text-purple-400'
    if (fn.startsWith('rag')) return 'text-green-400'
    return 'text-orange-400'
  }

  return (
    <aside className="w-[38%] shrink-0 border-r border-[#2a2a2a] bg-[#111] flex flex-col overflow-hidden">
      <div className="p-3 border-b border-[#2a2a2a]">
        <p className="text-xs font-semibold text-white mb-3">Live Session Metrics</p>
        <div className="grid grid-cols-2 gap-2">
          {[
            { label: 'API Calls', value: traces.length },
            { label: 'Errors', value: errors, red: errors > 0 },
            { label: 'Avg Latency', value: `${avgLatency.toFixed(0)}ms` },
            { label: 'Total Cost', value: `$${totalCost.toFixed(5)}` },
          ].map(({ label, value, red }) => (
            <div key={label} className="bg-[#1a1a1a] rounded p-2">
              <p className="text-[10px] text-[#6b7280] mb-0.5">{label}</p>
              <p className={`text-sm font-semibold ${red ? 'text-red-400' : 'text-white'}`}>{value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        <p className="text-[10px] text-[#6b7280] uppercase tracking-wide mb-2">Trace Feed</p>
        {traces.length === 0 ? (
          <p className="text-[11px] text-[#4b5563] italic">No traces yet. Start interacting →</p>
        ) : (
          <div className="flex flex-col gap-1.5">
            {[...traces].reverse().map((t, i) => (
              <div key={i} className="bg-[#1a1a1a] rounded p-2 text-[11px]">
                <div className="flex items-center justify-between mb-0.5">
                  <span className={`font-mono font-medium ${fnColor(t.function_name)}`}>
                    {t.function_name}
                  </span>
                  {t.error_class && <span className="text-red-400 text-[10px]">error</span>}
                </div>
                <div className="flex justify-between text-[#6b7280]">
                  <span>{t.latency_ms}ms</span>
                  <span>${(t.cost_usd ?? 0).toFixed(5)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="p-3 border-t border-[#2a2a2a]">
        <div className="flex flex-col gap-1 text-[10px] text-[#4b5563]">
          <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-blue-400 inline-block" />chat</div>
          <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-purple-400 inline-block" />chain-of-thought</div>
          <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-green-400 inline-block" />rag</div>
          <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-orange-400 inline-block" />agent</div>
        </div>
      </div>
    </aside>
  )
}

// ---------------------------------------------------------------------------
// Shared UI primitives
// ---------------------------------------------------------------------------
function SendButton({ loading, onClick, label = 'Send' }: { loading: boolean; onClick: () => void; label?: string }) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm rounded-lg font-medium transition-colors whitespace-nowrap"
    >
      {loading ? 'Thinking...' : label}
    </button>
  )
}

const STEP_COLORS = [
  'bg-purple-500/10 border-purple-500/20',
  'bg-blue-500/10 border-blue-500/20',
  'bg-green-500/10 border-green-500/20',
  'bg-orange-500/10 border-orange-500/20',
  'bg-pink-500/10 border-pink-500/20',
]
const STEP_LABELS = ['text-purple-400', 'text-blue-400', 'text-green-400', 'text-orange-400', 'text-pink-400']

function StepCard({ step, index }: { step: Step; index: number }) {
  const [open, setOpen] = useState(true)
  return (
    <div className={`border rounded-lg overflow-hidden ${STEP_COLORS[index % 5]}`}>
      <button
        className="w-full flex items-center justify-between px-4 py-3 text-left"
        onClick={() => setOpen(o => !o)}
      >
        <span className={`text-sm font-semibold ${STEP_LABELS[index % 5]}`}>{step.title}</span>
        <span className="text-[#6b7280] text-xs">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="px-4 pb-4 max-h-72 overflow-y-auto">
          <p className="text-sm text-[#d1d5db] whitespace-pre-wrap leading-relaxed">{step.content}</p>
        </div>
      )}
    </div>
  )
}

function TurnDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 my-1">
      <div className="flex-1 h-px bg-[#2a2a2a]" />
      <span className="text-[10px] text-[#4b5563] px-2 shrink-0 max-w-[70%] truncate font-mono">{label}</span>
      <div className="flex-1 h-px bg-[#2a2a2a]" />
    </div>
  )
}

function ThinkingLine({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a]">
      <span className="flex gap-0.5">
        {[0, 1, 2].map(i => (
          <span key={i} className="w-1 h-1 rounded-full bg-[#6b7280] animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
        ))}
      </span>
      <span className="text-xs text-[#6b7280] italic">{text}</span>
    </div>
  )
}

function EmptyHint({ text }: { text: string }) {
  return <p className="text-sm text-[#4b5563] italic text-center py-12">{text}</p>
}

// ---------------------------------------------------------------------------
// Tab 1 — Chat (session-persisted)
// ---------------------------------------------------------------------------
function ChatTab({ sessionId }: { sessionId: string }) {
  const [messages, setMessages] = useSessionStorage<Message[]>(`wyl_chat_${sessionId}`, [])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  async function send() {
    if (!input.trim() || loading) return
    const userMsg: Message = { role: 'user', content: input.trim() }
    const history = [...messages, userMsg]
    setMessages(history)
    setInput('')
    setLoading(true)
    try {
      const data = await post('chat', { messages: history, session_id: sessionId })
      setMessages([...history, { role: 'assistant', content: data.reply }])
    } catch (e: any) {
      setMessages([...history, { role: 'assistant', content: `Error: ${e.message}` }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
        {messages.length === 0 && <EmptyHint text="Start a conversation — full context is maintained for the session." />}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
              m.role === 'user'
                ? 'bg-blue-600 text-white rounded-br-sm'
                : 'bg-[#1e1e1e] text-[#d1d5db] border border-[#2a2a2a] rounded-bl-sm'
            }`}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-[#1e1e1e] border border-[#2a2a2a] rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm text-[#6b7280]">···</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="p-4 border-t border-[#2a2a2a] flex gap-2 shrink-0">
        <input
          className="flex-1 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-white placeholder-[#4b5563] focus:outline-none focus:border-blue-500"
          placeholder="Type a message..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
        />
        <SendButton loading={loading} onClick={send} />
        {messages.length > 0 && (
          <button onClick={() => setMessages([])} className="px-3 py-2 text-xs text-[#6b7280] hover:text-white border border-[#2a2a2a] rounded-lg transition-colors">
            Clear
          </button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab 2 — Chain of Thought (multi-turn, chat-thread style)
// ---------------------------------------------------------------------------
function CotTab({ sessionId }: { sessionId: string }) {
  const [turns, setTurns] = useSessionStorage<CotTurn[]>(`wyl_cot_${sessionId}`, [])
  const [question, setQuestion] = useState('')
  const [activeSteps, setActiveSteps] = useState<Step[]>([])
  const [currentQ, setCurrentQ] = useState('')
  const [thinking, setThinking] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [turns, activeSteps, thinking])

  async function run() {
    if (!question.trim() || loading) return
    const q = question.trim()
    setQuestion('')
    setCurrentQ(q)
    setLoading(true)
    setActiveSteps([])
    setThinking('')

    const priorTurns = turns.map(t => ({ question: t.question, answer: t.answer }))
    const currentSteps: Step[] = []

    try {
      for await (const event of streamSSE('cot/stream', { question: q, session_id: sessionId, prior_turns: priorTurns })) {
        if (event.type === 'thinking') {
          setThinking(event.text)
        } else if (event.type === 'step') {
          setThinking('')
          const step: Step = { title: event.title, content: event.content }
          currentSteps.push(step)
          setActiveSteps([...currentSteps])
        } else if (event.type === 'done') {
          setThinking('')
          const answer = currentSteps[currentSteps.length - 1]?.content ?? ''
          setTurns(prev => [...prev, { question: q, steps: currentSteps, answer }])
          setActiveSteps([])
          setLoading(false)
        }
      }
    } catch (e: any) {
      alert(`Error: ${e.message}`)
    } finally {
      setLoading(false)
      setThinking('')
    }
  }

  const hasHistory = turns.length > 0

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-2">
        {!hasHistory && activeSteps.length === 0 && !thinking && !loading && (
          <EmptyHint text="Try: 'Should a startup use microservices or a monolith?'" />
        )}
        {turns.map((turn, ti) => (
          <div key={ti} className="flex flex-col gap-2">
            <TurnDivider label={`Q: ${turn.question}`} />
            {turn.steps.map((s, i) => <StepCard key={i} step={s} index={i} />)}
          </div>
        ))}
        {(activeSteps.length > 0 || thinking) && (
          <div className="flex flex-col gap-2">
            {hasHistory && <TurnDivider label={`Q: ${currentQ}`} />}
            {activeSteps.map((s, i) => <StepCard key={i} step={s} index={i} />)}
            {thinking && <ThinkingLine text={thinking} />}
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="p-4 border-t border-[#2a2a2a] flex gap-2 shrink-0">
        <input
          className="flex-1 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-white placeholder-[#4b5563] focus:outline-none focus:border-purple-500"
          placeholder={hasHistory ? 'Ask a follow-up or new question...' : 'Ask a complex question that benefits from step-by-step reasoning...'}
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && run()}
        />
        <SendButton loading={loading} onClick={run} label={hasHistory ? 'Continue' : 'Reason'} />
        {hasHistory && (
          <button onClick={() => { setTurns([]); setActiveSteps([]); setCurrentQ('') }} className="px-3 py-2 text-xs text-[#6b7280] hover:text-white border border-[#2a2a2a] rounded-lg transition-colors">
            Clear
          </button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab 3 — RAG (document persisted in session)
// ---------------------------------------------------------------------------
function RagTab({ sessionId }: { sessionId: string }) {
  const [document, setDocument] = useSessionStorage<string>(`wyl_rag_doc_${sessionId}`, '')
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<{ chunks: string[]; answer: string } | null>(null)
  const [loading, setLoading] = useState(false)
  const [showChunks, setShowChunks] = useState(false)

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => setDocument(ev.target?.result as string)
    reader.readAsText(file)
  }

  async function run() {
    if (!document.trim() || !question.trim() || loading) return
    setLoading(true)
    setResult(null)
    try {
      const data = await post('rag', { document: document.trim(), question: question.trim(), session_id: sessionId })
      setResult(data)
    } catch (e: any) {
      alert(`Error: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full p-4 gap-4 overflow-y-auto">
      <div className="flex flex-col gap-3">
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <p className="text-xs text-[#6b7280]">Document</p>
            <label className="text-xs text-blue-400 hover:text-blue-300 cursor-pointer transition-colors">
              Upload .txt file
              <input type="file" accept=".txt,.md" className="hidden" onChange={handleFile} />
            </label>
          </div>
          <textarea
            className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-white placeholder-[#4b5563] focus:outline-none focus:border-green-500 resize-none"
            placeholder="Paste your document here, or upload a .txt file above..."
            rows={6}
            value={document}
            onChange={e => setDocument(e.target.value)}
          />
          {document && (
            <p className="text-[10px] text-[#4b5563] mt-1">
              {document.split(/\s+/).filter(Boolean).length} words · {Math.ceil(document.split(/\s+/).filter(Boolean).length / 250)} chunks
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <input
            className="flex-1 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-white placeholder-[#4b5563] focus:outline-none focus:border-green-500"
            placeholder="Ask a question about the document..."
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && run()}
          />
          <SendButton loading={loading} onClick={run} label="Ask" />
        </div>
      </div>

      {loading && (
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg p-4 animate-pulse">
          <p className="text-xs text-[#6b7280]">Retrieving relevant chunks and generating answer...</p>
        </div>
      )}

      {result && (
        <div className="flex flex-col gap-3">
          <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-4">
            <p className="text-xs text-green-400 font-semibold mb-2">Answer</p>
            <p className="text-sm text-[#d1d5db] whitespace-pre-wrap leading-relaxed">{result.answer}</p>
          </div>
          <div className="border border-[#2a2a2a] rounded-lg overflow-hidden">
            <button
              className="w-full flex justify-between items-center px-4 py-2.5 text-xs text-[#6b7280] hover:text-white bg-[#1a1a1a] transition-colors"
              onClick={() => setShowChunks(o => !o)}
            >
              <span>Retrieved chunks ({result.chunks.length})</span>
              <span>{showChunks ? '▲' : '▼'}</span>
            </button>
            {showChunks && (
              <div className="divide-y divide-[#2a2a2a]">
                {result.chunks.map((c, i) => (
                  <div key={i} className="px-4 py-3 bg-[#111]">
                    <p className="text-[10px] text-[#4b5563] mb-1">Chunk {i + 1}</p>
                    <p className="text-xs text-[#9ca3af] leading-relaxed">{c}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab 4 — Agents (multi-turn, chat-thread style)
// ---------------------------------------------------------------------------
const AGENTS: { type: AgentType; label: string; desc: string; color: string; example: string }[] = [
  {
    type: 'research',
    label: 'Research Agent',
    desc: 'Researcher ↔ Critic → Aggregator',
    color: 'border-orange-500/30 bg-orange-500/5 hover:bg-orange-500/10',
    example: 'Impact of AI on software engineering jobs',
  },
  {
    type: 'code',
    label: 'Code Agent',
    desc: 'Architect → Coder ↔ Reviewer → Certify',
    color: 'border-blue-500/30 bg-blue-500/5 hover:bg-blue-500/10',
    example: 'Build a rate limiter in Python',
  },
  {
    type: 'debate',
    label: 'Debate Agent',
    desc: 'A ↔ B (multi-round) → Moderator verdict',
    color: 'border-purple-500/30 bg-purple-500/5 hover:bg-purple-500/10',
    example: 'Open source AI models should be regulated',
  },
]

function AgentsTab({ sessionId }: { sessionId: string }) {
  const [selected, setSelected] = useState<AgentType | null>(null)
  const [rounds, setRounds] = useSessionStorage<AgentRound[]>(`wyl_agent_${sessionId}`, [])
  const [task, setTask] = useState('')
  const [activeSteps, setActiveSteps] = useState<Step[]>([])
  const [currentTask, setCurrentTask] = useState('')
  const [thinking, setThinking] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [rounds, activeSteps, thinking])

  async function run() {
    if (!selected || !task.trim() || loading) return
    const t = task.trim()
    setTask('')
    setCurrentTask(t)
    setLoading(true)
    setActiveSteps([])
    setThinking('')

    // Build prior context from last round's final step (aggregator/moderator output)
    const lastRound = rounds[rounds.length - 1]
    const priorContext = lastRound
      ? `Prior exchange on "${lastRound.task}":\n${lastRound.steps[lastRound.steps.length - 1]?.content?.slice(0, 800) ?? ''}`
      : ''

    const currentSteps: Step[] = []

    try {
      for await (const event of streamSSE('agent/stream', {
        agent_type: selected, task: t, session_id: sessionId, prior_context: priorContext,
      })) {
        if (event.type === 'thinking') {
          setThinking(event.text)
        } else if (event.type === 'step') {
          setThinking('')
          const step: Step = { title: event.title, content: event.content }
          currentSteps.push(step)
          setActiveSteps([...currentSteps])
        } else if (event.type === 'done') {
          setThinking('')
          setRounds(prev => [...prev, { task: t, steps: currentSteps, agentType: selected }])
          setActiveSteps([])
          setLoading(false)
        }
      }
    } catch (e: any) {
      alert(`Error: ${e.message}`)
    } finally {
      setLoading(false)
      setThinking('')
    }
  }

  const selectedAgent = AGENTS.find(a => a.type === selected)
  const hasHistory = rounds.length > 0

  return (
    <div className="flex flex-col h-full">
      {/* Fixed top: agent selector + input */}
      <div className="p-4 border-b border-[#2a2a2a] shrink-0">
        <div className="grid grid-cols-3 gap-3 mb-3">
          {AGENTS.map(a => (
            <button
              key={a.type}
              onClick={() => setSelected(a.type)}
              className={`border rounded-lg p-3 text-left transition-colors ${a.color} ${selected === a.type ? 'ring-1 ring-orange-400' : ''}`}
            >
              <p className="text-sm font-semibold text-white mb-1">{a.label}</p>
              <p className="text-[11px] text-[#9ca3af]">{a.desc}</p>
            </button>
          ))}
        </div>
        {selected && (
          <div className="flex gap-2">
            <input
              className="flex-1 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-white placeholder-[#4b5563] focus:outline-none focus:border-orange-500"
              placeholder={hasHistory ? `Follow-up or new task for ${selectedAgent?.label}...` : `e.g. "${selectedAgent?.example}"`}
              value={task}
              onChange={e => setTask(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && run()}
            />
            <SendButton loading={loading} onClick={run} label={hasHistory ? 'Continue' : 'Run Agent'} />
            {hasHistory && (
              <button
                onClick={() => { setRounds([]); setActiveSteps([]); setCurrentTask('') }}
                className="px-3 py-2 text-xs text-[#6b7280] hover:text-white border border-[#2a2a2a] rounded-lg transition-colors"
              >
                Clear
              </button>
            )}
          </div>
        )}
        {!selected && <p className="text-xs text-[#4b5563] italic">Pick an agent type above to get started.</p>}
      </div>

      {/* Scrollable steps area */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-2">
        {rounds.length === 0 && activeSteps.length === 0 && !thinking && (
          <EmptyHint text="Agents will appear here as they work through the task." />
        )}
        {rounds.map((round, ri) => (
          <div key={ri} className="flex flex-col gap-2">
            <TurnDivider label={round.task} />
            {round.steps.map((s, i) => <StepCard key={`${ri}-${i}`} step={s} index={i} />)}
          </div>
        ))}
        {(activeSteps.length > 0 || thinking) && (
          <div className="flex flex-col gap-2">
            {hasHistory && <TurnDivider label={currentTask} />}
            {activeSteps.map((s, i) => <StepCard key={i} step={s} index={i} />)}
            {thinking && <ThinkingLine text={thinking} />}
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Playground page
// ---------------------------------------------------------------------------
const TABS: { id: Tab; label: string }[] = [
  { id: 'chat', label: 'Chat' },
  { id: 'cot', label: 'Chain of Thought' },
  { id: 'rag', label: 'RAG' },
  { id: 'agents', label: 'Agents' },
]

export default function Playground() {
  // Session ID lives in sessionStorage — survives navigation within the tab
  const [sessionId] = useState(() => {
    const stored = sessionStorage.getItem('wyl_session_id')
    if (stored) return stored
    const id = crypto.randomUUID()
    sessionStorage.setItem('wyl_session_id', id)
    return id
  })
  const [activeTab, setActiveTab] = useState<Tab>('chat')

  return (
    <div className="flex" style={{ height: 'calc(100vh - 49px)' }}>
      <LiveMetrics sessionId={sessionId} />

      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex border-b border-[#2a2a2a] bg-[#111] px-4 gap-1 shrink-0">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px ${
                activeTab === t.id
                  ? 'border-blue-500 text-white'
                  : 'border-transparent text-[#6b7280] hover:text-white'
              }`}
            >
              {t.label}
            </button>
          ))}
          <div className="ml-auto flex items-center">
            <span className="text-[10px] text-[#4b5563] px-2">session · {sessionId.slice(0, 8)}</span>
          </div>
        </div>

        <div className="flex-1 overflow-hidden">
          {activeTab === 'chat' && <ChatTab sessionId={sessionId} />}
          {activeTab === 'cot' && <CotTab sessionId={sessionId} />}
          {activeTab === 'rag' && <RagTab sessionId={sessionId} />}
          {activeTab === 'agents' && <AgentsTab sessionId={sessionId} />}
        </div>
      </div>
    </div>
  )
}

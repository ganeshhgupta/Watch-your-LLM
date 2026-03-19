const COLLECTOR_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-base font-semibold text-white border-b border-[#2a2a2a] pb-2">{title}</h2>
      {children}
    </div>
  )
}

function Code({ children }: { children: string }) {
  return (
    <pre className="bg-[#0f0f0f] border border-[#2a2a2a] rounded-lg p-4 text-xs text-[#a3e635] overflow-x-auto whitespace-pre">
      {children}
    </pre>
  )
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4">
      <div className="w-7 h-7 rounded-full bg-blue-500/20 text-blue-400 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
        {n}
      </div>
      <div className="flex flex-col gap-2 flex-1">
        <p className="text-sm font-medium text-white">{title}</p>
        {children}
      </div>
    </div>
  )
}

function Callout({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg px-4 py-3 text-sm text-[#93c5fd]">
      {children}
    </div>
  )
}

function Table({ rows }: { rows: [string, string][] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-[#2a2a2a]">
      <table className="w-full text-sm">
        <tbody>
          {rows.map(([k, v], i) => (
            <tr key={i} className="border-b border-[#2a2a2a] last:border-0">
              <td className="px-4 py-2.5 font-mono text-xs text-[#a3e635] w-48 bg-[#0f0f0f]">{k}</td>
              <td className="px-4 py-2.5 text-[#9ca3af]">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Docs() {
  return (
    <div className="p-6 max-w-3xl flex flex-col gap-10">
      <div>
        <h1 className="text-xl font-semibold mb-1">Getting Started</h1>
        <p className="text-sm text-[#9ca3af]">
          Watch your LLM is an observability platform for LLM apps. Wrap your LLM calls with the SDK
          and every call — tokens, cost, latency, errors — shows up here automatically.
        </p>
      </div>

      {/* ── What this dashboard shows ── */}
      <Section title="What this dashboard shows">
        <p className="text-sm text-[#9ca3af]">Every time your app calls an LLM, the SDK captures:</p>
        <Table rows={[
          ['Total Traces',    'Total number of LLM calls recorded'],
          ['Error Rate',      'Percentage of calls that raised an exception'],
          ['Avg Latency',     'Mean wall-clock time per LLM call (ms)'],
          ['Total Cost',      'Cumulative spend computed from token counts × model pricing'],
          ['Trace Explorer',  'Full input/output + metadata for every individual call'],
          ['Error Analysis',  'Breakdown of exception types with stack traces'],
        ]} />
      </Section>

      {/* ── Quick start ── */}
      <Section title="Quick start — monitor your own app">
        <Step n={1} title="Install the SDK">
          <Code>{`pip install git+https://github.com/ganeshhgupta/Watch-your-LLM.git#subdirectory=sdk`}</Code>
        </Step>

        <Step n={2} title="Point the SDK at this collector">
          <p className="text-xs text-[#9ca3af]">Set this environment variable in your app (or in a <code className="text-[#a3e635]">.env</code> file):</p>
          <Code>{`LLMOBS_COLLECTOR_URL=${COLLECTOR_URL}`}</Code>
        </Step>

        <Step n={3} title="Wrap your LLM function with @trace">
          <Code>{`from llmobs import trace
from groq import Groq

client = Groq(api_key="...")

@trace(model="llama-3.1-8b-instant", tags={"feature": "summarizer", "env": "prod"})
def summarize(text: str):
    return client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": f"Summarize: {text}"}],
    )

# Just call your function normally — tracing is automatic
result = summarize("Your text here...")
print(result.choices[0].message.content)`}</Code>
        </Step>

        <Step n={4} title="Open this dashboard">
          <p className="text-sm text-[#9ca3af]">
            Every call to <code className="text-[#a3e635]">summarize()</code> now appears in{' '}
            <a href="/app/traces" className="text-blue-400 hover:underline">Trace Explorer</a> with
            full input/output, token counts, latency, and cost.
          </p>
        </Step>
      </Section>

      {/* ── Context manager ── */}
      <Section title="Alternative: context manager span">
        <p className="text-sm text-[#9ca3af]">Use a span when you need more control over what gets recorded:</p>
        <Code>{`import llmobs

with llmobs.span(model="llama-3.1-8b-instant", tags={"step": "rerank"}) as span:
    span.set_input("What is observability?")
    response = client.chat.completions.create(...)
    span.set_output(response)`}</Code>
      </Section>

      {/* ── What gets captured ── */}
      <Section title="What gets captured automatically">
        <Table rows={[
          ['trace_id',           'UUID generated per call'],
          ['timestamp',          'UTC time of the call'],
          ['function_name',      'Name of the decorated function'],
          ['model',              'Model name from the response or decorator arg'],
          ['input_preview',      'First string argument (≤ 2000 chars)'],
          ['output_preview',     'response.choices[0].message.content (≤ 2000 chars)'],
          ['prompt_tokens',      'Token count from response.usage.prompt_tokens'],
          ['completion_tokens',  'Token count from response.usage.completion_tokens'],
          ['latency_ms',         'Wall-clock time in milliseconds'],
          ['cost_usd',           'Computed from token counts × model pricing table'],
          ['error_class',        'Exception class name if the call raised an error'],
          ['tags',               'Custom dict you pass to @trace(tags={...})'],
        ]} />
      </Section>

      {/* ── Supported providers ── */}
      <Section title="Supported LLM providers">
        <p className="text-sm text-[#9ca3af]">
          The SDK auto-detects token counts from any of these response formats:
        </p>
        <Table rows={[
          ['Groq',       'response.usage.prompt_tokens / completion_tokens'],
          ['OpenAI',     'response.usage.prompt_tokens / completion_tokens'],
          ['Anthropic',  'response.usage.input_tokens / output_tokens'],
          ['Gemini',     'response.usage_metadata.prompt_token_count / candidates_token_count'],
        ]} />
      </Section>

      {/* ── Supported models & pricing ── */}
      <Section title="Supported models & pricing">
        <Table rows={[
          ['llama-3.1-8b-instant',    '$0.05 / $0.08 per 1M tokens'],
          ['llama-3.3-70b-versatile', '$0.59 / $0.79 per 1M tokens'],
          ['gpt-4o',                  '$5.00 / $15.00 per 1M tokens'],
          ['gpt-4o-mini',             '$0.15 / $0.60 per 1M tokens'],
          ['claude-3-5-sonnet',       '$3.00 / $15.00 per 1M tokens'],
          ['gemini-1.5-pro',          '$1.25 / $5.00 per 1M tokens'],
          ['gemini-1.5-flash',        '$0.075 / $0.30 per 1M tokens'],
          ['gemini-2.0-flash',        '$0.10 / $0.40 per 1M tokens'],
        ]} />
        <p className="text-xs text-[#6b7280]">Input / Output pricing. Unknown models report $0.00 cost.</p>
      </Section>

      {/* ── Tags ── */}
      <Section title="Using tags to filter traces">
        <p className="text-sm text-[#9ca3af]">
          Tags let you slice your traces by any dimension — environment, feature, user tier, etc.
        </p>
        <Code>{`@trace(model="gpt-4o-mini", tags={"env": "prod", "feature": "chat", "tier": "premium"})
def chat(message: str):
    ...`}</Code>
        <p className="text-sm text-[#9ca3af]">
          In <a href="/app/traces" className="text-blue-400 hover:underline">Trace Explorer</a>, filter by{' '}
          <code className="text-[#a3e635]">env:prod</code> or <code className="text-[#a3e635]">feature:chat</code> to see only those calls.
        </p>
      </Section>

      {/* ── Current limitations ── */}
      <Section title="Current limitations">
        <Callout>
          This is a <strong>single-tenant</strong> deployment — all traces from all users go into
          one shared database. It is best suited for monitoring your own app or sharing with a
          small team. There is no authentication or per-user data isolation yet.
        </Callout>
      </Section>
    </div>
  )
}

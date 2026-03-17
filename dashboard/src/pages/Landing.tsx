import { useNavigate } from 'react-router-dom'

const FEATURES = [
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    ),
    color: '#3b82f6',
    bg: '#eff6ff',
    title: 'Real-time Tracing',
    desc: 'Every LLM call captured automatically — prompt, response, tokens, latency, and cost. Zero config.',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <line x1="12" y1="1" x2="12" y2="23" />
        <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
      </svg>
    ),
    color: '#10b981',
    bg: '#ecfdf5',
    title: 'Cost Analytics',
    desc: 'Track spend per model, feature, and environment. Spot which routes burn money and optimize them.',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
    ),
    color: '#ef4444',
    bg: '#fef2f2',
    title: 'Error Detection',
    desc: 'Surface failures instantly with full error context. Know exactly when a model starts misbehaving.',
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <rect x="3" y="3" width="7" height="7" />
        <rect x="14" y="3" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" />
        <rect x="3" y="14" width="7" height="7" />
      </svg>
    ),
    color: '#f59e0b',
    bg: '#fffbeb',
    title: 'Model Comparison',
    desc: 'Side-by-side latency and cost breakdown across GPT-4o, Gemini, Claude, and more.',
  },
]

const HOW_IT_WORKS = [
  { step: '01', title: 'Decorate your function', code: '@trace(model="gemini-1.5-flash")' },
  { step: '02', title: 'Call your LLM as usual', code: 'response = model.generate_content(prompt)' },
  { step: '03', title: 'Explore in the dashboard', code: 'http://localhost:5173/app' },
]

export default function Landing() {
  const navigate = useNavigate()

  return (
    <div style={{ fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif" }} className="min-h-screen bg-white text-gray-900">

      {/* ── Nav ─────────────────────────────────────────────────── */}
      <nav className="flex items-center justify-between px-8 py-4 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-gray-900">Watch your</span>
          <span className="text-lg font-bold text-blue-500">LLM</span>
        </div>
        <div className="hidden md:flex items-center gap-6 text-sm text-gray-600">
          <a href="#features" className="hover:text-gray-900 transition-colors">Features</a>
          <a href="#how-it-works" className="hover:text-gray-900 transition-colors">How it works</a>
          <a href="#pricing-table" className="hover:text-gray-900 transition-colors">Models</a>
        </div>
        <button
          onClick={() => navigate('/app')}
          className="bg-blue-500 hover:bg-blue-600 text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors shadow-sm"
        >
          Open App
        </button>
      </nav>

      {/* ── Hero ────────────────────────────────────────────────── */}
      <section className="flex flex-col items-center text-center px-6 pt-20 pb-16">
        {/* Colorful accent bars */}
        <div className="flex gap-2 mb-10">
          {['#3b82f6', '#10b981', '#f59e0b', '#ef4444'].map((color, i) => (
            <span key={i} style={{ backgroundColor: color }} className="block h-1 w-10 rounded-full" />
          ))}
        </div>

        <h1 className="text-6xl font-extrabold tracking-tight mb-4 leading-tight">
          <span className="text-gray-900">Watch your</span>{' '}
          <span className="text-blue-500">LLM</span>
        </h1>

        <p className="text-gray-500 text-lg max-w-xl mb-8 leading-relaxed">
          Full visibility into every LLM call. Trace prompts, responses, tokens, latency, and cost
          — self-hosted, no vendor lock-in.
        </p>

        <div className="flex gap-3">
          <button
            onClick={() => navigate('/app')}
            className="bg-blue-500 hover:bg-blue-600 text-white font-semibold px-6 py-3 rounded-lg transition-colors shadow-sm"
          >
            Open Dashboard
          </button>
          <button
            onClick={() => navigate('/app/traces')}
            className="border border-gray-200 hover:border-gray-300 text-gray-700 font-semibold px-6 py-3 rounded-lg transition-colors"
          >
            Explore Traces
          </button>
        </div>

        {/* Fake terminal preview */}
        <div className="mt-14 w-full max-w-2xl bg-gray-950 rounded-xl overflow-hidden shadow-2xl text-left">
          <div className="flex items-center gap-1.5 px-4 py-3 border-b border-gray-800">
            {['#ef4444', '#f59e0b', '#22c55e'].map((c, i) => (
              <span key={i} style={{ backgroundColor: c }} className="w-3 h-3 rounded-full" />
            ))}
            <span className="text-gray-500 text-xs ml-2 font-mono">your_app.py</span>
          </div>
          <pre className="p-5 text-sm font-mono leading-relaxed overflow-x-auto">
            <span className="text-blue-400">from</span>
            <span className="text-white"> llmobs </span>
            <span className="text-blue-400">import</span>
            <span className="text-white"> trace{'\n\n'}</span>
            <span className="text-gray-500">{'# Wrap any LLM function — one line\n'}</span>
            <span className="text-yellow-300">@trace</span>
            <span className="text-white">(model=</span>
            <span className="text-green-400">"gemini-1.5-flash"</span>
            <span className="text-white">, tags=&#123;</span>
            <span className="text-green-400">"env"</span>
            <span className="text-white">: </span>
            <span className="text-green-400">"prod"</span>
            <span className="text-white">&#125;){'\n'}</span>
            <span className="text-blue-400">def</span>
            <span className="text-yellow-200"> summarize</span>
            <span className="text-white">(text: </span>
            <span className="text-blue-300">str</span>
            <span className="text-white">):{'\n'}</span>
            <span className="text-white">{'    '}response = model.generate_content(text){'\n'}</span>
            <span className="text-blue-400">{'    '}return</span>
            <span className="text-white"> response{'\n\n'}</span>
            <span className="text-gray-500">{'# → Traces to your dashboard automatically ✓'}</span>
          </pre>
        </div>
      </section>

      {/* ── Features ────────────────────────────────────────────── */}
      <section id="features" className="px-8 py-16 max-w-6xl mx-auto">
        <h2 className="text-center text-2xl font-bold text-gray-900 mb-2">Everything you need</h2>
        <p className="text-center text-gray-500 text-sm mb-10">
          A complete observability stack for LLM-powered applications.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="border border-gray-100 rounded-xl p-5 hover:shadow-md transition-shadow bg-white"
            >
              <div
                style={{ backgroundColor: f.bg, color: f.color }}
                className="w-10 h-10 rounded-lg flex items-center justify-center mb-4"
              >
                {f.icon}
              </div>
              <h3 className="font-semibold text-gray-900 mb-1 text-sm">{f.title}</h3>
              <p className="text-gray-500 text-xs leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── How it works ────────────────────────────────────────── */}
      <section id="how-it-works" className="bg-gray-50 py-16 px-8">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-center text-2xl font-bold text-gray-900 mb-2">Up in 60 seconds</h2>
          <p className="text-center text-gray-500 text-sm mb-10">
            No infrastructure changes. Works with any LLM provider.
          </p>
          <div className="flex flex-col gap-4">
            {HOW_IT_WORKS.map((item) => (
              <div key={item.step} className="flex items-center gap-5 bg-white border border-gray-100 rounded-xl p-4">
                <span className="text-xs font-bold text-blue-400 w-8 shrink-0">{item.step}</span>
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-800">{item.title}</p>
                  <code className="text-xs text-gray-500 font-mono">{item.code}</code>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Supported Models ─────────────────────────────────────── */}
      <section id="pricing-table" className="py-16 px-8 max-w-4xl mx-auto">
        <h2 className="text-center text-2xl font-bold text-gray-900 mb-2">Supported models</h2>
        <p className="text-center text-gray-500 text-sm mb-8">Automatic cost calculation included.</p>
        <div className="overflow-x-auto rounded-xl border border-gray-100">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                {['Model', 'Input (/ 1M tokens)', 'Output (/ 1M tokens)'].map((h) => (
                  <th key={h} className="text-left py-3 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                ['gpt-4o', '$5.00', '$15.00'],
                ['gpt-4o-mini', '$0.15', '$0.60'],
                ['claude-3-5-sonnet', '$3.00', '$15.00'],
                ['gemini-1.5-pro', '$1.25', '$5.00'],
                ['gemini-1.5-flash', '$0.075', '$0.30'],
              ].map(([model, input, output]) => (
                <tr key={model} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                  <td className="py-3 px-4 font-mono text-gray-800 text-xs">{model}</td>
                  <td className="py-3 px-4 text-gray-600">{input}</td>
                  <td className="py-3 px-4 text-gray-600">{output}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── CTA ─────────────────────────────────────────────────── */}
      <section className="bg-blue-500 py-16 px-8 text-center">
        <h2 className="text-3xl font-bold text-white mb-3">Start watching your LLM</h2>
        <p className="text-blue-100 mb-7 text-sm">Self-hosted. No API key needed for the platform itself.</p>
        <button
          onClick={() => navigate('/app')}
          className="bg-white text-blue-600 font-semibold px-8 py-3 rounded-lg hover:bg-blue-50 transition-colors shadow"
        >
          Open Dashboard →
        </button>
      </section>

      {/* ── Footer ──────────────────────────────────────────────── */}
      <footer className="border-t border-gray-100 py-6 px-8 flex items-center justify-between text-xs text-gray-400">
        <span>© 2026 Watch your LLM</span>
        <div className="flex gap-3">
          {['#3b82f6', '#10b981', '#f59e0b', '#ef4444'].map((c, i) => (
            <span key={i} style={{ backgroundColor: c }} className="w-2.5 h-2.5 rounded-full" />
          ))}
        </div>
      </footer>
    </div>
  )
}

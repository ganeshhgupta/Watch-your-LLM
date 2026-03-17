import { BrowserRouter, Routes, Route, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import Landing from './pages/Landing'
import Overview from './pages/Overview'
import TraceExplorer from './pages/TraceExplorer'
import ErrorAnalysis from './pages/ErrorAnalysis'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 25_000,
      retry: 1,
    },
  },
})

const NAV_ITEMS = [
  {
    to: '/app',
    label: 'Overview',
    end: true,
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <rect x="3" y="3" width="7" height="7" />
        <rect x="14" y="3" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" />
        <rect x="3" y="14" width="7" height="7" />
      </svg>
    ),
  },
  {
    to: '/app/traces',
    label: 'Trace Explorer',
    end: false,
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    ),
  },
  {
    to: '/app/errors',
    label: 'Error Analysis',
    end: false,
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
    ),
  },
]

function DashboardLayout() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-[#0f0f0f] text-white flex">
      {/* Sidebar */}
      <aside className="w-56 bg-[#1a1a1a] border-r border-[#2a2a2a] flex flex-col shrink-0">
        {/* Logo */}
        <div className="p-4 border-b border-[#2a2a2a] flex items-center gap-2">
          <div className="w-7 h-7 rounded bg-blue-500 flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.2">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
          </div>
          <div className="leading-tight">
            <p className="text-xs font-bold text-white">Watch your</p>
            <p className="text-xs font-bold text-blue-400">LLM</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-2 flex flex-col gap-0.5">
          {NAV_ITEMS.map(({ to, label, end, icon }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded text-sm transition-colors ${
                  isActive
                    ? 'bg-blue-500/15 text-blue-400'
                    : 'text-[#9ca3af] hover:text-white hover:bg-white/5'
                }`
              }
            >
              {icon}
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Back to landing */}
        <div className="p-3 border-t border-[#2a2a2a]">
          <button
            onClick={() => navigate('/')}
            className="w-full text-xs text-[#6b7280] hover:text-white transition-colors flex items-center gap-1.5 px-2 py-1.5"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Back to home
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {/* Top bar */}
        <div className="border-b border-[#2a2a2a] px-6 py-3 flex items-center justify-between bg-[#1a1a1a]/50">
          <div className="flex gap-1">
            {['#3b82f6', '#10b981', '#f59e0b', '#ef4444'].map((c, i) => (
              <span key={i} style={{ backgroundColor: c }} className="block w-2 h-2 rounded-full" />
            ))}
          </div>
          <span className="text-xs text-[#6b7280]">Watch your LLM · Dashboard</span>
        </div>

        <Outlet />
      </main>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/app" element={<DashboardLayout />}>
            <Route index element={<Overview />} />
            <Route path="traces" element={<TraceExplorer />} />
            <Route path="errors" element={<ErrorAnalysis />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

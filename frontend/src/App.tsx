// Repository: https://github.com/jasdiq/AMRAK_AI_IBMBOB
import { Routes, Route, Navigate, NavLink } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import ScanPage from './pages/ScanPage'
import LabelsPage from './pages/LabelsPage'
import LabelDetailPage from './pages/LabelDetailPage'
import DashboardPage from './pages/DashboardPage'
import { ScanLine, List, LayoutDashboard } from 'lucide-react'

export default function App() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top bar */}
        <header className="md:hidden flex items-center gap-3 px-4 py-3 bg-navy-900 border-b border-navy-700 sticky top-0 z-10">
          <img src="/logo.jpg" alt="AMRAK AI" className="w-8 h-8 rounded-full object-cover" />
          <span className="font-bold text-white text-sm flex-1">AMRAK AI</span>
          <nav className="flex gap-3">
            {[
              { to: '/scan', Icon: ScanLine },
              { to: '/labels', Icon: List },
              { to: '/dashboard', Icon: LayoutDashboard },
            ].map(({ to, Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `p-1.5 rounded-lg transition-colors ${isActive ? 'text-electric-300 bg-electric-500/20' : 'text-slate-400'}`
                }
              >
                <Icon size={18} />
              </NavLink>
            ))}
          </nav>
        </header>
        <main className="flex-1 p-4 md:p-8 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/scan" element={<ScanPage />} />
            <Route path="/labels" element={<LabelsPage />} />
            <Route path="/labels/:id" element={<LabelDetailPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

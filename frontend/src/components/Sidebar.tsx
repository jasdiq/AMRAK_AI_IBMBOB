import { NavLink } from 'react-router-dom'
import { ScanLine, List, LayoutDashboard } from 'lucide-react'

export default function Sidebar() {
  const navItem = (to: string, Icon: React.ElementType, label: string) => (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
          isActive
            ? 'bg-electric-500/20 text-electric-300'
            : 'text-slate-400 hover:text-slate-100 hover:bg-navy-800'
        }`
      }
    >
      <Icon size={18} />
      {label}
    </NavLink>
  )

  return (
    <aside className="hidden md:flex flex-col w-56 bg-navy-900 border-r border-navy-700 min-h-screen p-4 gap-1">
      {/* AMRAK AI Logo */}
      <div className="flex flex-col items-center px-2 py-4 mb-4 gap-2">
        <img
          src="/logo.jpg"
          alt="AMRAK AI"
          className="w-24 h-24 rounded-full object-cover ring-2 ring-electric-500/40"
        />
        <div className="text-center">
          <div className="font-bold text-white text-sm leading-tight tracking-wide">AMRAK AI</div>
          <div className="text-xs text-electric-400 leading-tight">Product Label &amp; Expiry Tracking</div>
        </div>
      </div>

      {navItem('/scan', ScanLine, 'Scan Label')}
      {navItem('/labels', List, 'All Labels')}
      {navItem('/dashboard', LayoutDashboard, 'Dashboard')}

      {/* Footer */}
      <div className="mt-auto pt-6 px-2">
        <div className="text-xs text-slate-600 leading-relaxed">
          Powered by<br />
          <span className="text-electric-500/70">IBM Bob · llava · Tesseract</span>
        </div>
      </div>
    </aside>
  )
}

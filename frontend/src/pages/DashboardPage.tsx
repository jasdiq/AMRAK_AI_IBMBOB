import { useEffect, useState } from 'react'
import { getDashboard, listLabels } from '../api'
import { DashboardStats, LabelRecord } from '../types'
import StatusBadge from '../components/StatusBadge'
import {
  LayoutDashboard, XCircle, AlertTriangle, CheckCircle,
  Clock, Package, Loader2, RefreshCw, ScanLine
} from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { useNavigate } from 'react-router-dom'

function StatCard({
  label, value, Icon, colorClass, sub,
}: {
  label: string
  value: number
  Icon: React.ElementType
  colorClass: string
  sub?: string
}) {
  return (
    <div className="card flex items-center gap-4">
      <div className={`p-3 rounded-xl ${colorClass}`}>
        <Icon size={22} />
      </div>
      <div>
        <div className="text-3xl font-bold text-white">{value}</div>
        <div className="text-sm text-slate-400">{label}</div>
        {sub && <div className="text-xs text-slate-500 mt-0.5">{sub}</div>}
      </div>
    </div>
  )
}

function fmtDate(d: string | null) {
  if (!d) return '—'
  try { return format(parseISO(d + (d.length === 7 ? '-01' : '')), 'dd MMM yyyy') }
  catch { return d }
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [recent, setRecent] = useState<LabelRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [s, r] = await Promise.all([getDashboard(), listLabels()])
      setStats(s)
      setRecent(r.slice(0, 8))
    } catch {
      setError('Could not load dashboard. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading)
    return (
      <div className="flex items-center justify-center h-64 gap-2 text-slate-400">
        <Loader2 size={20} className="animate-spin" />
        Loading dashboard…
      </div>
    )

  if (error)
    return (
      <div className="text-red-400 p-6 text-center">
        {error}
        <br />
        <button onClick={load} className="btn-ghost mt-4 text-sm mx-auto">
          <RefreshCw size={14} />
          Retry
        </button>
      </div>
    )

  const s = stats!

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <img src="/logo.jpg" alt="AMRAK AI" className="w-10 h-10 rounded-full object-cover hidden sm:block" />
          <div>
            <h1 className="text-2xl font-bold text-white">Dashboard</h1>
            <p className="text-slate-400 text-sm">Expiry &amp; review overview · AMRAK AI</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="btn-ghost text-sm">
            <RefreshCw size={14} />
            Refresh
          </button>
          <button onClick={() => navigate('/scan')} className="btn-primary text-sm">
            <ScanLine size={14} />
            Scan Label
          </button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard
          label="Total Labels"
          value={s.total}
          Icon={Package}
          colorClass="bg-electric-500/20 text-electric-300"
        />
        <StatCard
          label="Confirmed"
          value={s.confirmed}
          Icon={CheckCircle}
          colorClass="bg-emerald-900/40 text-emerald-300"
        />
        <StatCard
          label="Needs Review"
          value={s.needs_review}
          Icon={Clock}
          colorClass="bg-purple-900/40 text-purple-300"
          sub="Ambiguous or incomplete dates"
        />
        <StatCard
          label="Expired"
          value={s.expired}
          Icon={XCircle}
          colorClass="bg-red-900/40 text-red-300"
          sub="Past expiry date"
        />
        <StatCard
          label="Expiring Soon"
          value={s.expiring_soon}
          Icon={AlertTriangle}
          colorClass="bg-amber-900/40 text-amber-300"
          sub="Within 30 days"
        />
        <StatCard
          label="Valid"
          value={s.ok}
          Icon={CheckCircle}
          colorClass="bg-sky-900/40 text-sky-300"
          sub="More than 30 days remaining"
        />
      </div>

      {/* Expiry bar chart (pure CSS) */}
      {s.total > 0 && (
        <div className="card">
          <h2 className="text-white font-semibold mb-4">Expiry Status Distribution</h2>
          <div className="space-y-3">
            {[
              { label: 'Valid',          count: s.ok,            cls: 'bg-emerald-500', pct: (s.ok / s.total) * 100 },
              { label: 'Expiring Soon',  count: s.expiring_soon, cls: 'bg-amber-500',   pct: (s.expiring_soon / s.total) * 100 },
              { label: 'Expired',        count: s.expired,       cls: 'bg-red-500',     pct: (s.expired / s.total) * 100 },
              { label: 'Unknown',        count: s.total - s.ok - s.expiring_soon - s.expired, cls: 'bg-slate-600', pct: ((s.total - s.ok - s.expiring_soon - s.expired) / s.total) * 100 },
            ].filter(r => r.count > 0).map((row) => (
              <div key={row.label} className="flex items-center gap-3 text-sm">
                <span className="text-slate-400 w-28 shrink-0">{row.label}</span>
                <div className="flex-1 bg-navy-800 rounded-full h-3 overflow-hidden">
                  <div
                    className={`h-3 rounded-full ${row.cls} transition-all duration-500`}
                    style={{ width: `${Math.max(row.pct, 2)}%` }}
                  />
                </div>
                <span className="text-slate-300 w-6 text-right">{row.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent scans */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-white font-semibold">Recent Labels</h2>
          <button
            onClick={() => navigate('/labels')}
            className="text-xs text-electric-300 hover:text-electric-200 transition-colors"
          >
            View all →
          </button>
        </div>

        {recent.length === 0 ? (
          <p className="text-slate-500 text-sm">No labels yet. Scan a product to begin.</p>
        ) : (
          <div className="space-y-2">
            {recent.map((r) => (
              <div
                key={r.id}
                onClick={() => navigate(`/labels/${r.id}`)}
                className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-navy-800 cursor-pointer transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-white text-sm font-medium truncate">
                    {r.product_name || <span className="text-slate-500 italic">Unknown product</span>}
                  </p>
                  <p className="text-slate-500 text-xs">
                    {r.batch_number ? `Batch: ${r.batch_number} · ` : ''}
                    Exp: {fmtDate(r.expiry_date)}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <StatusBadge status={r.expiry_status} variant="expiry" />
                  <StatusBadge status={r.review_status} variant="review" />
                </div>
                <span className="text-xs text-slate-600 whitespace-nowrap hidden sm:block">
                  {r.created_at ? format(parseISO(r.created_at), 'dd MMM') : ''}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

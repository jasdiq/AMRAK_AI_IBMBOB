import { useEffect, useState } from 'react'
import { listLabels, deleteLabel } from '../api'
import { LabelRecord } from '../types'
import LabelTable from '../components/LabelTable'
import { ScanLine, Loader2, RefreshCw } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const FILTERS = [
  { value: '', label: 'All' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'needs_review', label: 'Needs Review' },
  { value: 'expired', label: 'Expired' },
  { value: 'expiring_soon', label: 'Expiring Soon' },
  { value: 'ok', label: 'Valid' },
]

export default function LabelsPage() {
  const navigate = useNavigate()
  const [records, setRecords] = useState<LabelRecord[]>([])
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      setRecords(await listLabels(filter || undefined))
    } catch {
      setError('Could not load labels. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [filter]) // eslint-disable-line

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this label record?')) return
    await deleteLabel(id)
    setRecords((prev) => prev.filter((r) => r.id !== id))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-white">All Labels</h1>
          <p className="text-slate-400 text-sm mt-1">
            {records.length} record{records.length !== 1 ? 's' : ''}
            {filter ? ` · filtered: ${filter.replace('_', ' ')}` : ''}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} className="btn-ghost text-xs px-3 py-2">
            <RefreshCw size={14} />
            Refresh
          </button>
          <button onClick={() => navigate('/scan')} className="btn-primary text-xs px-3 py-2">
            <ScanLine size={14} />
            Scan New
          </button>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 flex-wrap">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
              filter === f.value
                ? 'bg-electric-500/20 border-electric-500 text-electric-300'
                : 'border-navy-700 text-slate-400 hover:text-slate-100 hover:border-navy-500'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="card">
        {loading ? (
          <div className="flex items-center justify-center py-16 gap-2 text-slate-400">
            <Loader2 size={20} className="animate-spin" />
            Loading…
          </div>
        ) : error ? (
          <div className="text-red-400 text-sm py-8 text-center">{error}</div>
        ) : (
          <LabelTable records={records} onDelete={handleDelete} />
        )}
      </div>
    </div>
  )
}

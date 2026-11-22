import { LabelRecord } from '../types'
import StatusBadge from './StatusBadge'
import { format, parseISO } from 'date-fns'
import { Trash2, Eye } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

interface Props {
  records: LabelRecord[]
  onDelete: (id: number) => void
}

function fmtDate(d: string | null) {
  if (!d) return '—'
  try { return format(parseISO(d + (d.length === 7 ? '-01' : '')), 'dd MMM yyyy') }
  catch { return d }
}

export default function LabelTable({ records, onDelete }: Props) {
  const navigate = useNavigate()
  if (records.length === 0)
    return (
      <div className="text-center text-slate-500 py-16 text-sm">
        No labels found. Scan a product label to get started.
      </div>
    )

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-navy-700 text-xs text-slate-400 uppercase tracking-wider">
            <th className="pb-3 text-left pl-2">Product</th>
            <th className="pb-3 text-left">Batch</th>
            <th className="pb-3 text-left">MFG Date</th>
            <th className="pb-3 text-left">Expiry Date</th>
            <th className="pb-3 text-left">Type</th>
            <th className="pb-3 text-left">Expiry</th>
            <th className="pb-3 text-left">Status</th>
            <th className="pb-3 text-left">Scanned</th>
            <th className="pb-3"></th>
          </tr>
        </thead>
        <tbody>
          {records.map((r) => (
            <tr
              key={r.id}
              className="border-b border-navy-800 hover:bg-navy-800/40 transition-colors"
            >
              <td className="py-3 pl-2 font-medium text-white max-w-[160px] truncate">
                {r.product_name || <span className="text-slate-500 italic">Unknown</span>}
              </td>
              <td className="py-3 font-mono text-slate-300 text-xs">
                {r.batch_number || '—'}
              </td>
              <td className="py-3 text-slate-300">{fmtDate(r.manufacturing_date)}</td>
              <td className="py-3 text-slate-300">{fmtDate(r.expiry_date)}</td>
              <td className="py-3 text-slate-400 capitalize">{r.date_type || '—'}</td>
              <td className="py-3">
                <StatusBadge status={r.expiry_status} variant="expiry" />
              </td>
              <td className="py-3">
                <StatusBadge status={r.review_status} variant="review" />
              </td>
              <td className="py-3 text-slate-500 text-xs whitespace-nowrap">
                {r.created_at ? format(parseISO(r.created_at), 'dd MMM yyyy HH:mm') : '—'}
              </td>
              <td className="py-3 pr-2">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => navigate(`/labels/${r.id}`)}
                    className="text-slate-400 hover:text-electric-300 transition-colors"
                    title="View details"
                  >
                    <Eye size={15} />
                  </button>
                  <button
                    onClick={() => onDelete(r.id)}
                    className="text-slate-500 hover:text-red-400 transition-colors"
                    title="Delete"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

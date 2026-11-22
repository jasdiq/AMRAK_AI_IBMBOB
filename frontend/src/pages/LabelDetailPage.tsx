import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getLabel, updateLabel, deleteLabel } from '../api'
import { LabelRecord } from '../types'
import StatusBadge from '../components/StatusBadge'
import {
  ArrowLeft, Loader2, AlertTriangle, CheckCircle,
  Calendar, Hash, Package, Image as ImageIcon, Trash2
} from 'lucide-react'
import { format, parseISO } from 'date-fns'

function fmtDate(d: string | null) {
  if (!d) return '—'
  try { return format(parseISO(d + (d.length === 7 ? '-01' : '')), 'dd MMM yyyy') }
  catch { return d }
}

export default function LabelDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [record, setRecord] = useState<LabelRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState<Partial<LabelRecord>>({})
  const [ambiguityNotes, setAmbiguityNotes] = useState<string[]>([])

  useEffect(() => {
    if (!id) return
    getLabel(Number(id)).then((r) => {
      setRecord(r)
      setForm({
        product_name: r.product_name || '',
        batch_number: r.batch_number || '',
        manufacturing_date: r.manufacturing_date || '',
        expiry_date: r.expiry_date || '',
        date_type: r.date_type || 'expiry',
        review_status: r.review_status,
      })
      try {
        setAmbiguityNotes(JSON.parse(r.ambiguity_notes || '[]'))
      } catch {
        setAmbiguityNotes([])
      }
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [id])

  const handleConfirm = async () => {
    if (!record) return
    setSaving(true)
    try {
      const updated = await updateLabel(record.id, {
        ...form,
        review_status: 'confirmed',
      })
      setRecord(updated)
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!record || !confirm('Delete this record?')) return
    await deleteLabel(record.id)
    navigate('/labels')
  }

  if (loading)
    return (
      <div className="flex items-center justify-center h-64 gap-2 text-slate-400">
        <Loader2 size={20} className="animate-spin" />
      </div>
    )
  if (!record)
    return <div className="text-red-400 p-6">Record not found.</div>

  const needsReview = record.review_status === 'needs_review'

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-1 text-slate-400 hover:text-white text-sm mb-2 transition-colors"
          >
            <ArrowLeft size={14} />
            Back
          </button>
          <h1 className="text-2xl font-bold text-white">
            {record.product_name || 'Unnamed Product'}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <StatusBadge status={record.expiry_status} variant="expiry" />
            <StatusBadge status={record.review_status} variant="review" />
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setEditing(!editing)} className="btn-ghost text-sm">
            {editing ? 'Cancel' : 'Edit'}
          </button>
          <button onClick={handleDelete} className="btn-ghost text-sm text-red-400 border-red-900 hover:border-red-500">
            <Trash2 size={14} />
            Delete
          </button>
        </div>
      </div>

      {/* Ambiguity warning */}
      {needsReview && ambiguityNotes.length > 0 && (
        <div className="bg-amber-900/30 border border-amber-700 rounded-lg p-4 space-y-1">
          <div className="flex items-center gap-2 text-amber-300 font-semibold text-sm">
            <AlertTriangle size={15} />
            Dates need confirmation — ambiguity detected
          </div>
          {ambiguityNotes.map((n, i) => (
            <p key={i} className="text-amber-200 text-xs pl-5">• {n}</p>
          ))}
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-5">
        {/* Image */}
        <div className="card flex items-center justify-center min-h-[200px]">
          {record.label_image ? (
            <img
              src={`/uploads/${record.label_image.replace(/^uploads\//, '')}`}
              alt="Label"
              className="max-h-64 rounded object-contain"
            />
          ) : (
            <div className="text-slate-600 flex flex-col items-center gap-2">
              <ImageIcon size={36} />
              <span className="text-xs">No image</span>
            </div>
          )}
        </div>

        {/* Details */}
        <div className="card space-y-4">
          {editing ? (
            <div className="space-y-3">
              {[
                { key: 'product_name', label: 'Product Name', type: 'text' },
                { key: 'batch_number', label: 'Batch Number', type: 'text' },
                { key: 'manufacturing_date', label: 'MFG Date', type: 'date' },
                { key: 'expiry_date', label: 'Expiry Date', type: 'date' },
              ].map(({ key, label, type }) => (
                <div key={key}>
                  <label className="label-sm">{label}</label>
                  <input
                    className="input"
                    type={type}
                    value={
                      type === 'date' && (form as any)[key]?.length === 7
                        ? (form as any)[key] + '-01'
                        : (form as any)[key] || ''
                    }
                    onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                  />
                </div>
              ))}
              <div>
                <label className="label-sm">Date Type</label>
                <select
                  className="input"
                  value={(form.date_type as string) || 'expiry'}
                  onChange={(e) => setForm((f) => ({ ...f, date_type: e.target.value }))}
                >
                  <option value="expiry">Expiry</option>
                  <option value="use-by">Use By</option>
                  <option value="best-before">Best Before</option>
                  <option value="unknown">Unknown</option>
                </select>
              </div>
              <button disabled={saving} onClick={handleConfirm} className="btn-primary w-full mt-2">
                {saving ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
                Confirm &amp; Save
              </button>
            </div>
          ) : (
            <dl className="space-y-3 text-sm">
              {[
                { icon: Package, label: 'Product', value: record.product_name },
                { icon: Hash,    label: 'Batch',   value: record.batch_number },
                { icon: Calendar,label: 'MFG Date',value: fmtDate(record.manufacturing_date) },
                { icon: Calendar,label: 'Expiry',  value: fmtDate(record.expiry_date) },
                { icon: null,    label: 'Type',    value: record.date_type },
              ].map(({ icon: Icon, label, value }) => (
                <div key={label} className="flex items-start gap-2">
                  {Icon && <Icon size={14} className="text-electric-400 mt-0.5 shrink-0" />}
                  <div className={!Icon ? 'pl-4' : ''}>
                    <dt className="text-slate-500 text-xs">{label}</dt>
                    <dd className="text-white font-medium">{value || '—'}</dd>
                  </div>
                </div>
              ))}
            </dl>
          )}
        </div>
      </div>

      {/* AI reasoning */}
      {record.llm_used === 'true' && record.llm_reasoning && (
        <div className="card border-electric-500/30">
          <div className="flex items-center gap-2 text-electric-300 font-semibold text-sm mb-2">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
            AI Analysis (llama3.2)
          </div>
          <p className="text-sm text-slate-300">{record.llm_reasoning}</p>
        </div>
      )}

      {/* Raw OCR */}
      <div className="card">
        <span className="label-sm">Raw OCR Text</span>
        <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap max-h-48 overflow-auto mt-2">
          {record.raw_text || '(no text)'}
        </pre>
      </div>

      <p className="text-xs text-slate-600 text-center">
        Scanned {record.created_at ? format(parseISO(record.created_at), 'dd MMM yyyy HH:mm') : '—'} · ID #{record.id}
        {record.llm_used === 'true' && <span className="ml-2 text-electric-500/60">· AI-extracted</span>}
      </p>
    </div>
  )
}

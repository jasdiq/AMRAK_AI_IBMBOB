import { useState, useCallback, useRef } from 'react'
import { Upload, ScanLine, AlertTriangle, CheckCircle, Loader2, Image as ImageIcon } from 'lucide-react'
import { scanLabel, saveLabel } from '../api'
import { ExtractedLabel } from '../types'
import { useNavigate } from 'react-router-dom'

type Step = 'upload' | 'review' | 'saving' | 'done'

export default function ScanPage() {
  const navigate = useNavigate()
  const fileRef = useRef<HTMLInputElement>(null)
  const [step, setStep] = useState<Step>('upload')
  const [preview, setPreview] = useState<string | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [extracted, setExtracted] = useState<ExtractedLabel | null>(null)

  // Editable review fields
  const [form, setForm] = useState({
    product_name: '',
    batch_number: '',
    manufacturing_date: '',
    expiry_date: '',
    date_type: 'expiry',
  })

  const handleFile = useCallback((f: File) => {
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(f.type)) {
      setError('Only JPEG, PNG or WebP images are accepted.')
      return
    }
    if (f.size > 10 * 1024 * 1024) {
      setError('File must be under 10 MB.')
      return
    }
    setError(null)
    setFile(f)
    setPreview(URL.createObjectURL(f))
    setStep('upload')
    setExtracted(null)
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      const f = e.dataTransfer.files[0]
      if (f) handleFile(f)
    },
    [handleFile]
  )

  const handleScan = async () => {
    if (!file) return
    setScanning(true)
    setError(null)
    try {
      const result = await scanLabel(file)
      setExtracted(result)
      setForm({
        product_name: result.product_name || '',
        batch_number: result.batch_number || '',
        manufacturing_date: result.manufacturing_date || '',
        expiry_date: result.expiry_date || '',
        date_type: result.date_type || 'expiry',
      })
      setStep('review')
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Scanning failed. Please try again.')
    } finally {
      setScanning(false)
    }
  }

  const handleConfirm = async (reviewStatus: 'confirmed' | 'needs_review') => {
    if (!extracted) return
    setStep('saving')
    try {
      const record = await saveLabel({
        ...form,
        label_image: extracted.label_image || undefined,
        raw_text: extracted.raw_text,
        review_status: reviewStatus,
        ambiguity_notes:
          extracted.ambiguity_notes.length > 0
            ? JSON.stringify(extracted.ambiguity_notes)
            : undefined,
        llm_reasoning: extracted.llm_reasoning || undefined,
        llm_used: extracted.llm_used ? 'true' : 'false',
      })
      navigate(`/labels/${record.id}`)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Save failed.')
      setStep('review')
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Scan Product Label</h1>
        <p className="text-slate-400 text-sm mt-1">
          Upload or drag-and-drop a product label image. The system will extract dates and product details automatically.
        </p>
      </div>

      {/* Upload zone */}
      {(step === 'upload') && (
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => fileRef.current?.click()}
          className="border-2 border-dashed border-navy-600 hover:border-electric-400 rounded-xl p-10
                     flex flex-col items-center justify-center gap-3 cursor-pointer transition-colors
                     group"
        >
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
          {preview ? (
            <img
              src={preview}
              alt="Preview"
              className="max-h-64 rounded-lg object-contain"
            />
          ) : (
            <>
              <Upload size={36} className="text-slate-500 group-hover:text-electric-400 transition-colors" />
              <div className="text-center">
                <p className="text-slate-300 font-medium">Drop your image here</p>
                <p className="text-slate-500 text-xs mt-1">JPEG · PNG · WebP · up to 10 MB</p>
              </div>
            </>
          )}
        </div>
      )}

      {/* Preview + scan button */}
      {step === 'upload' && file && (
        <div className="flex gap-3">
          <button onClick={handleScan} disabled={scanning} className="btn-primary">
            {scanning ? <Loader2 size={16} className="animate-spin" /> : <ScanLine size={16} />}
            {scanning ? 'Scanning…' : 'Extract Label Details'}
          </button>
          <button
            onClick={() => { setFile(null); setPreview(null) }}
            className="btn-ghost"
          >
            Clear
          </button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-start gap-2 bg-red-900/30 border border-red-700 rounded-lg p-4 text-red-300 text-sm">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          {error}
        </div>
      )}

      {/* Review form */}
      {(step === 'review' || step === 'saving') && extracted && (
        <div className="space-y-5">

          {/* LLM reasoning banner */}
          {extracted.llm_used && extracted.llm_reasoning && (
            <div className="bg-electric-500/10 border border-electric-500/40 rounded-lg p-4 space-y-1">
              <div className="flex items-center gap-2 text-electric-300 font-semibold text-sm">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
                AI Analysis (llama3.2)
              </div>
              <p className="text-electric-200 text-xs pl-5">{extracted.llm_reasoning}</p>
            </div>
          )}

          {/* Ambiguity warnings */}
          {extracted.ambiguity_notes.length > 0 && (
            <div className="bg-amber-900/30 border border-amber-700 rounded-lg p-4 space-y-1">
              <div className="flex items-center gap-2 text-amber-300 font-semibold text-sm">
                <AlertTriangle size={15} />
                Ambiguous dates detected — please review before confirming
              </div>
              {extracted.ambiguity_notes.map((note, i) => (
                <p key={i} className="text-amber-200 text-xs pl-5">• {note}</p>
              ))}
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-4">
            {/* Image thumbnail */}
            <div className="card flex items-center justify-center min-h-[180px]">
              {preview ? (
                <img src={preview} alt="Label" className="max-h-56 rounded object-contain" />
              ) : (
                <ImageIcon size={40} className="text-slate-600" />
              )}
            </div>

            {/* Raw OCR text */}
            <div className="card">
              <span className="label-sm">OCR Raw Text</span>
              <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap max-h-52 overflow-auto">
                {extracted.raw_text || '(no text detected)'}
              </pre>
            </div>
          </div>

          {/* Editable fields */}
          <div className="card space-y-4">
            <h2 className="text-white font-semibold">Extracted Details — Review &amp; Edit</h2>
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="label-sm">Product Name</label>
                <input
                  className="input"
                  value={form.product_name}
                  onChange={(e) => setForm((f) => ({ ...f, product_name: e.target.value }))}
                  placeholder="e.g. Digestive Biscuits 400g"
                />
              </div>
              <div>
                <label className="label-sm">Batch / Lot Number</label>
                <input
                  className="input"
                  value={form.batch_number}
                  onChange={(e) => setForm((f) => ({ ...f, batch_number: e.target.value }))}
                  placeholder="e.g. BATCH-2024-001"
                />
              </div>
              <div>
                <label className="label-sm">Manufacturing Date</label>
                <input
                  className="input"
                  type="date"
                  value={form.manufacturing_date.length === 7 ? form.manufacturing_date + '-01' : form.manufacturing_date}
                  onChange={(e) => setForm((f) => ({ ...f, manufacturing_date: e.target.value }))}
                />
              </div>
              <div>
                <label className="label-sm">Expiry / Best-Before Date</label>
                <input
                  className="input"
                  type="date"
                  value={form.expiry_date.length === 7 ? form.expiry_date + '-01' : form.expiry_date}
                  onChange={(e) => setForm((f) => ({ ...f, expiry_date: e.target.value }))}
                />
              </div>
              <div>
                <label className="label-sm">Date Type</label>
                <select
                  className="input"
                  value={form.date_type}
                  onChange={(e) => setForm((f) => ({ ...f, date_type: e.target.value }))}
                >
                  <option value="expiry">Expiry</option>
                  <option value="use-by">Use By</option>
                  <option value="best-before">Best Before</option>
                  <option value="unknown">Unknown</option>
                </select>
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <button
                disabled={step === 'saving'}
                onClick={() => handleConfirm('confirmed')}
                className="btn-primary"
              >
                {step === 'saving' ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <CheckCircle size={16} />
                )}
                Confirm &amp; Save
              </button>
              <button
                disabled={step === 'saving'}
                onClick={() => handleConfirm('needs_review')}
                className="btn-ghost"
              >
                Save — Needs Review
              </button>
              <button
                disabled={step === 'saving'}
                onClick={() => { setStep('upload'); setExtracted(null) }}
                className="btn-ghost"
              >
                Start Over
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

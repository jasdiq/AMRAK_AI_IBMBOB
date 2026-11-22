export interface LabelRecord {
  id: number
  product_name: string | null
  batch_number: string | null
  manufacturing_date: string | null
  expiry_date: string | null
  date_type: string | null
  label_image: string | null
  raw_text: string | null
  review_status: 'confirmed' | 'needs_review'
  ambiguity_notes: string | null
  llm_reasoning: string | null
  llm_used: string | null
  created_at: string
  expiry_status: 'expired' | 'expiring_soon' | 'ok' | 'unknown' | null
}

export interface ExtractedLabel {
  product_name: string | null
  batch_number: string | null
  manufacturing_date: string | null
  expiry_date: string | null
  date_type: string | null
  raw_text: string
  ambiguity_notes: string[]
  label_image: string | null
  llm_used: boolean
  llm_reasoning: string | null
}

export interface DashboardStats {
  total: number
  confirmed: number
  needs_review: number
  expired: number
  expiring_soon: number
  ok: number
}

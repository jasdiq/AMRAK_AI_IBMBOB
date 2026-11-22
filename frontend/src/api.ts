import axios from 'axios'
import { DashboardStats, ExtractedLabel, LabelRecord } from './types'

const api = axios.create({ baseURL: '/api' })

export async function scanLabel(file: File): Promise<ExtractedLabel> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<ExtractedLabel>('/scan', form)
  return data
}

export async function saveLabel(fields: {
  product_name?: string
  batch_number?: string
  manufacturing_date?: string
  expiry_date?: string
  date_type?: string
  label_image?: string
  raw_text?: string
  review_status?: string
  ambiguity_notes?: string
  llm_reasoning?: string
  llm_used?: string
}): Promise<LabelRecord> {
  const form = new FormData()
  Object.entries(fields).forEach(([k, v]) => {
    if (v !== undefined && v !== null) form.append(k, v)
  })
  const { data } = await api.post<LabelRecord>('/labels', form)
  return data
}

export async function listLabels(statusFilter?: string): Promise<LabelRecord[]> {
  const params = statusFilter ? { status_filter: statusFilter } : {}
  const { data } = await api.get<LabelRecord[]>('/labels', { params })
  return data
}

export async function getLabel(id: number): Promise<LabelRecord> {
  const { data } = await api.get<LabelRecord>(`/labels/${id}`)
  return data
}

export async function updateLabel(
  id: number,
  payload: Partial<LabelRecord> & { review_status?: string }
): Promise<LabelRecord> {
  const { data } = await api.put<LabelRecord>(`/labels/${id}`, payload)
  return data
}

export async function deleteLabel(id: number): Promise<void> {
  await api.delete(`/labels/${id}`)
}

export async function getDashboard(): Promise<DashboardStats> {
  const { data } = await api.get<DashboardStats>('/dashboard')
  return data
}

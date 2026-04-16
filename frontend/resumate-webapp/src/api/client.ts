const BASE = '/api'

async function request<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, opts)
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status}: ${body}`)
  }
  return res.json() as Promise<T>
}

/* ── types mirroring backend Pydantic models ────────────────────── */

export interface DocumentElement {
  id: string
  type: string
  text: string
  offset: number
}

export interface UploadResponse {
  session_id: string
  rendered_html: string
  raw_text: string
  document_structure: DocumentElement[]
  file_format: string
  tex_pdf_url: string | null
}

export interface PlaceholderCreate {
  session_id: string
  selected_text: string
  start_offset: number
  end_offset: number
  key?: string
  type: 'tailor' | 'sensitive'
  value?: string
}

export interface PlaceholderResponse {
  key: string
  type: string
  selected_text: string
  start_offset: number
  end_offset: number
  value: string | null
}

export interface TailorRequest {
  session_id: string
  job_posting: string
  acc: string
  model?: string
  moddeg: string
  faux: boolean
  pages?: number | null
}

export interface PageInfo {
  page_count: number
  last_page_fill_pct: number
  target_pages: number | null
  within_target: boolean
}

export interface TailorResponse {
  output_id: string
  preview_html: string
  download_url: string
  page_info: PageInfo | null
  can_retry: boolean
  retry_number: number
}

export interface SessionSummary {
  session_id: string
  name: string | null
  file_format: string
  original_filename: string
  placeholder_count: number
  created_at: string
  updated_at: string
}

export interface SessionDetail {
  session_id: string
  name: string | null
  file_format: string
  original_filename: string
  created_at: string
  updated_at: string
  rendered_html: string
  raw_text: string
  document_structure: DocumentElement[]
  placeholders: Record<string, PlaceholderResponse>
  template_generated: boolean
  outputs: unknown[]
  tex_pdf_url: string | null
}

export interface ModelsResponse {
  models: string[]
  default_model: string
}

/* ── API calls ──────────────────────────────────────────────────── */

export async function uploadFile(file: File): Promise<UploadResponse> {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: fd })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json()
}

export function addPlaceholder(data: PlaceholderCreate): Promise<PlaceholderResponse> {
  return request('/placeholder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export function removePlaceholder(sessionId: string, key: string): Promise<{ ok: boolean }> {
  return request(`/placeholder/${sessionId}/${key}`, { method: 'DELETE' })
}

export function updatePlaceholderType(
  sessionId: string,
  key: string,
  newType: 'tailor' | 'sensitive',
): Promise<PlaceholderResponse> {
  return request(`/placeholder/${sessionId}/${key}/type?new_type=${newType}`, {
    method: 'PATCH',
  })
}

export function tailorResume(data: TailorRequest): Promise<TailorResponse> {
  return request('/tailor', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export function retryTailor(sessionId: string, outputId: string): Promise<TailorResponse> {
  return request('/retry', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, output_id: outputId }),
  })
}

export function listSessions(): Promise<SessionSummary[]> {
  return request('/sessions')
}

export function getSession(sessionId: string): Promise<SessionDetail> {
  return request(`/sessions/${sessionId}`)
}

export function saveSession(sessionId: string, name?: string): Promise<{ ok: boolean }> {
  return request(`/sessions/${sessionId}/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
}

export function deleteSession(sessionId: string): Promise<{ ok: boolean }> {
  return request(`/sessions/${sessionId}`, { method: 'DELETE' })
}

export function deleteAllSessions(): Promise<{ ok: boolean }> {
  return request('/sessions/all', { method: 'DELETE' })
}

export function fetchModels(): Promise<ModelsResponse> {
  return request('/models')
}

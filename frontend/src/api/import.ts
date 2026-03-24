import client from './client'

export interface ImportResult {
  match_id: string
  status: 'imported' | 'skipped' | 'error'
  format: string | null
  reason: string | null
}

export interface BatchImportResult {
  total: number
  imported: number
  skipped: number
  errors: number
  results: Array<{ filename: string; status: string; match_id?: string; format?: string; reason?: string }>
}

export interface SurveilPendingFile {
  filename: string
  match_id: string
  mtime: number
  size: number
}

export interface SurveilPendingResult {
  folder: string
  pending: SurveilPendingFile[]
  total: number
}

export async function importSingleFile(name: string, data: ArrayBuffer): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('file', new Blob([data], { type: 'application/octet-stream' }), name)
  const res = await client.post<ImportResult>('/api/import', formData, { timeout: 30000 })
  return res.data
}

// ── Surveil (MTGA) ────────────────────────────────────────────────────────────

export async function getSurveilFolder(): Promise<{ folder: string | null }> {
  const res = await client.get<{ folder: string | null }>('/api/import/surveil/folder')
  return res.data
}

export async function setSurveilFolder(folder: string): Promise<void> {
  await client.put('/api/import/surveil/folder', { folder })
}

export async function clearSurveilFolder(): Promise<void> {
  await client.delete('/api/import/surveil/folder')
}

export async function getSurveilImportedIds(): Promise<string[]> {
  const res = await client.get<{ ids: string[] }>('/api/import/surveil/imported-ids')
  return res.data.ids
}

export async function getSurveilPending(): Promise<SurveilPendingResult> {
  const res = await client.get<SurveilPendingResult>('/api/import/surveil/pending')
  return res.data
}

export async function scanSurveil(): Promise<BatchImportResult> {
  const res = await client.post<BatchImportResult>('/api/import/surveil/scan', {}, { timeout: 120000 })
  return res.data
}

export async function importSurveilFile(name: string, data: ArrayBuffer): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('file', new Blob([data], { type: 'application/json' }), name)
  const res = await client.post<ImportResult>('/api/import/surveil', formData, { timeout: 30000 })
  return res.data
}

export interface ImportStatus {
  active: boolean
  filename: string
  step: string
  scryfall_done: number
  scryfall_total: number
  log: string[]
}

export async function getImportStatus(): Promise<ImportStatus> {
  const res = await client.get<ImportStatus>('/api/import/status')
  return res.data
}

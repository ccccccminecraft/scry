import client from './client'

export interface ImportResult {
  match_id: string
  status: 'imported' | 'skipped' | 'error'
  format: string | null
  reason: string | null
}

export async function importSingleFile(name: string, data: ArrayBuffer): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('file', new Blob([data], { type: 'application/octet-stream' }), name)
  const res = await client.post<ImportResult>('/api/import', formData, { timeout: 30000 })
  return res.data
}

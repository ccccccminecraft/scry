import axios from 'axios'

const BASE = 'http://localhost:18432/api'

export async function downloadBackup(): Promise<void> {
  const response = await axios.get(`${BASE}/backup`, { responseType: 'blob' })
  const contentDisposition: string = response.headers['content-disposition'] ?? ''
  const match = contentDisposition.match(/filename=(.+)/)
  const filename = match ? match[1] : 'scry_backup.db'

  const url = URL.createObjectURL(response.data as Blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export async function restoreBackup(file: File): Promise<void> {
  const form = new FormData()
  form.append('file', file)
  await axios.post(`${BASE}/restore`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

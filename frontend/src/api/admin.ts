import axios from 'axios'

const BASE = 'http://localhost:18432/api'

export async function getMtgaFolder(): Promise<{ folder: string | null }> {
  const res = await axios.get(`${BASE}/admin/mtga-cards-folder`)
  return res.data
}

export async function setMtgaFolder(folder: string): Promise<void> {
  await axios.put(`${BASE}/admin/mtga-cards-folder`, { folder })
}

export async function getMtgaSyncStatus(): Promise<{ folder: string | null; last_synced_at: string | null }> {
  const res = await axios.get(`${BASE}/admin/sync-mtga-cards/status`)
  return res.data
}

export async function syncMtgaCards(installFolder: string): Promise<{ synced: number; source: string }> {
  const db_path = await window.electronAPI.prepareMtgaCardsDb(installFolder)
  const res = await axios.post<{ synced: number; source: string }>(`${BASE}/admin/sync-mtga-cards`, { db_path })
  return res.data
}

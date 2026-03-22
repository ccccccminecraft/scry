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
  // メインプロセスが直接 backend に HTTP POST し、結果を返す
  return window.electronAPI.syncMtgaCards(installFolder)
}
